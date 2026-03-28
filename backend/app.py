import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

import pdfplumber
from dotenv import load_dotenv
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required

from .ai_agents import FundraisingAIAgents
from .auth import auth_bp
from .models import SavedInvestor, User, init_db
from .scraper import InvestorDiscoveryScraper


load_dotenv()


def create_app() -> Flask:
    """Create and configure the AI Startup Fundraising Intelligence Platform."""
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "development-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    init_db()

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    login_manager.init_app(app)

    ai_agents = FundraisingAIAgents(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        force_demo_mode=os.getenv("DEMO_MODE", "false").lower() == "true",
    )
    scraper = InvestorDiscoveryScraper(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        force_demo_mode=os.getenv("DEMO_MODE", "false").lower() == "true",
        intelligence_agent=ai_agents,
    )

    @login_manager.user_loader
    def load_user(user_id: str):
        """Reload the signed-in user from the current session."""
        return User.get_by_id(user_id)

    app.register_blueprint(auth_bp)

    def platform_context(active_page: str) -> Dict[str, Any]:
        """Build shared UI context for protected product pages."""
        saved_investors = SavedInvestor.list_by_user(current_user.id)
        scan_targets = [target["name"] for target in scraper.targets]
        portfolio_targets = [target["name"] for target in scraper.portfolio_targets]
        return {
            "active_page": active_page,
            "saved_count": len(saved_investors),
            "scan_targets": scan_targets,
            "portfolio_targets": portfolio_targets,
            "platform_mode": "demo" if ai_agents.is_demo_mode else "live",
            "feature_cards": [
                "Investor Discovery",
                "AI Match Scoring",
                "Portfolio Analysis",
                "AI Outreach",
                "Investor CRM",
                "Deck Analyzer",
                "Competitor Intelligence",
                "Warm Intro Finder",
                "Funding Probability",
            ],
        }

    def json_error(message: str, status_code: int = 400, **extra: Any):
        """Return a consistent JSON error payload."""
        payload = {"error": message, "mode": "demo" if ai_agents.is_demo_mode else "live"}
        payload.update(extra)
        return jsonify(payload), status_code

    @app.get("/")
    def landing():
        """Render the public landing page or redirect authenticated users."""
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.get("/dashboard")
    @login_required
    def dashboard():
        """Render the main fundraising intelligence workspace."""
        return render_template("dashboard.html", **platform_context("dashboard"))

    @app.get("/deck_analyzer")
    @login_required
    def deck_analyzer():
        """Render the pitch deck analyzer page."""
        return render_template("deck_analyzer.html", **platform_context("deck"))

    @app.get("/saved_investors")
    @login_required
    def saved_investors():
        """Render the investor CRM page."""
        saved = SavedInvestor.list_by_user(current_user.id)
        return render_template(
            "crm.html",
            saved_investors=saved,
            status_options=SavedInvestor.STATUS_OPTIONS,
            **platform_context("crm"),
        )

    @app.get("/api/saved-investors")
    @login_required
    def saved_investors_api():
        """Return saved investors in JSON form for product integrations."""
        saved = SavedInvestor.list_by_user(current_user.id)
        return jsonify(
            {
                "saved_investors": [item.to_dict() for item in saved],
                "count": len(saved),
            }
        )

    @app.post("/save_investor")
    @login_required
    def save_investor():
        """Save an investor into the authenticated user's CRM workspace."""
        payload = request.get_json(silent=True) or request.form.to_dict()
        investor_name = (payload.get("investor_name") or "").strip()
        firm_name = (payload.get("firm_name") or "").strip()
        profile_url = (payload.get("profile_url") or "Unknown").strip()
        notes = (payload.get("notes") or "").strip()
        status = (payload.get("status") or "To Contact").strip()

        if not investor_name or not firm_name:
            return json_error("Fields 'investor_name' and 'firm_name' are required.")

        saved = SavedInvestor.create(
            user_id=current_user.id,
            investor_name=investor_name,
            firm_name=firm_name,
            profile_url=profile_url,
            notes=notes,
            status=status,
        )
        return jsonify(
            {
                "message": "Investor saved to CRM.",
                "saved_investor": saved.to_dict(),
            }
        )

    @app.post("/update_saved_investor/<int:saved_investor_id>")
    @login_required
    def update_saved_investor(saved_investor_id: int):
        """Update notes and status for a saved investor CRM entry."""
        payload = request.get_json(silent=True) or request.form.to_dict()
        notes = (payload.get("notes") or "").strip()
        status = (payload.get("status") or "To Contact").strip()
        SavedInvestor.update(str(saved_investor_id), current_user.id, notes, status)

        if request.is_json:
            item = SavedInvestor.get_by_id_and_user(str(saved_investor_id), current_user.id)
            return jsonify({"message": "Saved investor updated.", "saved_investor": item.to_dict() if item else None})

        flash("Saved investor updated.", "success")
        return redirect(url_for("saved_investors"))

    @app.post("/discover")
    @app.post("/api/find-investors")
    @login_required
    def discover():
        """Discover and score investors for the provided startup profile."""
        payload = request.get_json(silent=True) or request.form.to_dict()
        domain = (payload.get("domain") or "").strip()
        stage = (payload.get("stage") or payload.get("funding_stage") or "").strip()
        location = (payload.get("location") or "").strip()

        if not domain or not stage:
            return json_error("Both 'domain' and 'stage' are required.", investors=[])

        try:
            return jsonify(scraper.find_investors(domain=domain, stage=stage, location=location))
        except ValueError as exc:
            return json_error(str(exc), investors=[])
        except Exception as exc:  # pragma: no cover - defensive safeguard
            return json_error(
                "Unexpected server error while discovering investors.",
                500,
                investors=[],
                details=str(exc),
            )

    @app.post("/generate_outreach")
    @app.post("/api/generate-email")
    @login_required
    def generate_outreach():
        """Generate personalized investor outreach with AI or a demo fallback."""
        payload = request.get_json(silent=True) or request.form.to_dict()
        startup_domain = (payload.get("startup_domain") or payload.get("domain") or "").strip()
        startup_description = (
            payload.get("startup_description")
            or "An ambitious early-stage startup with early product momentum and a focused market wedge."
        ).strip()
        investor_name = (payload.get("investor_name") or "").strip()
        firm_name = (payload.get("firm_name") or "").strip()

        try:
            result = ai_agents.generate_outreach(
                startup_domain=startup_domain,
                startup_description=startup_description,
                investor_name=investor_name,
                firm_name=firm_name,
            )
            return jsonify(result)
        except ValueError as exc:
            return json_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive safeguard
            return json_error(
                "Unexpected server error while generating outreach.",
                500,
                details=str(exc),
            )

    @app.post("/analyze_deck")
    @login_required
    def analyze_deck():
        """Extract text from an uploaded PDF pitch deck and analyze it."""
        payload = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
        startup_domain = (payload.get("domain") or "").strip()
        funding_stage = (payload.get("stage") or "").strip()
        deck_text = (payload.get("deck_text") or "").strip()

        pitch_deck = request.files.get("pitch_deck")
        filename = ""
        if pitch_deck and pitch_deck.filename:
            filename = pitch_deck.filename
            try:
                deck_text = extract_pdf_text(pitch_deck.read())
            except Exception as exc:
                return json_error("The uploaded PDF could not be processed.", details=str(exc))

        if not deck_text:
            return json_error("Upload a PDF pitch deck or provide deck text.")

        try:
            analysis = ai_agents.analyze_pitch_deck(
                deck_text=deck_text,
                startup_domain=startup_domain,
                funding_stage=funding_stage,
            )
            analysis["filename"] = filename or "Inline text"
            return jsonify(analysis)
        except ValueError as exc:
            return json_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive safeguard
            return json_error(
                "Unexpected server error while analyzing the pitch deck.",
                500,
                details=str(exc),
            )

    @app.post("/competitors")
    @login_required
    def competitors():
        """Generate competitor intelligence for a startup idea."""
        payload = request.get_json(silent=True) or request.form.to_dict()
        startup_idea = (payload.get("startup_idea") or payload.get("startup_description") or "").strip()
        startup_domain = (payload.get("domain") or "").strip()

        try:
            result = ai_agents.analyze_competitors(startup_idea=startup_idea, startup_domain=startup_domain)
            return jsonify(result)
        except ValueError as exc:
            return json_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive safeguard
            return json_error(
                "Unexpected server error while generating competitor intelligence.",
                500,
                details=str(exc),
            )

    @app.post("/funding_probability")
    @login_required
    def funding_probability():
        """Predict fundraising probability from startup inputs."""
        payload = request.get_json(silent=True) or request.form.to_dict()

        try:
            result = ai_agents.predict_funding_probability(
                domain=(payload.get("domain") or "").strip(),
                stage=(payload.get("stage") or "").strip(),
                team_size=(payload.get("team_size") or "").strip(),
                market=(payload.get("market") or "").strip(),
                traction=(payload.get("traction") or "").strip(),
            )
            return jsonify(result)
        except ValueError as exc:
            return json_error(str(exc))
        except Exception as exc:  # pragma: no cover - defensive safeguard
            return json_error(
                "Unexpected server error while estimating fundraising probability.",
                500,
                details=str(exc),
            )

    @app.get("/api/health")
    def health_check():
        """Return lightweight app health for local verification."""
        return jsonify(
            {
                "status": "ok",
                "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
                "demo_mode": ai_agents.is_demo_mode,
                "authenticated": current_user.is_authenticated,
            }
        )

    return app


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from a PDF using pdfplumber."""
    pages = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text.strip())
    return "\n\n".join(pages)


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
