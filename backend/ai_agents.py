import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


COMPETITOR_SAMPLES = {
    "ai": [
        {
            "company_name": "Writer",
            "funding_raised": "$326M",
            "investors": "ICONIQ Growth, Premji Invest, Radical Ventures",
            "differentiation_note": "Focuses on enterprise generative AI workflows and model governance.",
        },
        {
            "company_name": "Glean",
            "funding_raised": "$360M",
            "investors": "Sequoia Capital, Lightspeed, Kleiner Perkins",
            "differentiation_note": "Built strong traction around AI enterprise search and workflow orchestration.",
        },
        {
            "company_name": "Harvey",
            "funding_raised": "$506M",
            "investors": "Sequoia Capital, OpenAI Startup Fund, Kleiner Perkins",
            "differentiation_note": "Vertical AI example showing appetite for domain-specific copilots.",
        },
    ],
    "logistics": [
        {
            "company_name": "Flexport",
            "funding_raised": "$2.3B",
            "investors": "SoftBank, Founders Fund, Shopify",
            "differentiation_note": "Strong benchmark for logistics software plus supply-chain visibility.",
        },
        {
            "company_name": "project44",
            "funding_raised": "$942M",
            "investors": "Insight Partners, Generation Investment Management, Eight Roads",
            "differentiation_note": "Deep enterprise traction in shipment visibility and operations.",
        },
        {
            "company_name": "Motive",
            "funding_raised": "$567M",
            "investors": "Insight Partners, Index Ventures, Kleiner Perkins",
            "differentiation_note": "Useful proxy for AI-enabled fleet and operations infrastructure.",
        },
    ],
    "fintech": [
        {
            "company_name": "Stripe",
            "funding_raised": "$9.4B",
            "investors": "Sequoia Capital, Andreessen Horowitz, Thrive Capital",
            "differentiation_note": "Payments infrastructure leader and benchmark for developer-first finance tools.",
        },
        {
            "company_name": "Mercury",
            "funding_raised": "$272M",
            "investors": "Sequoia Capital, Coatue, CRV",
            "differentiation_note": "Strong example of fintech infrastructure plus founder-friendly positioning.",
        },
        {
            "company_name": "Razorpay",
            "funding_raised": "$741M",
            "investors": "Sequoia Capital, Lone Pine, GIC",
            "differentiation_note": "Illustrates investor appetite for payment platforms in high-growth markets.",
        },
    ],
}


class FundraisingAIAgents:
    """LLM-backed product intelligence helpers with robust demo fallbacks."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4.1-mini",
        force_demo_mode: bool = False,
    ) -> None:
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_model = openai_model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.force_demo_mode = force_demo_mode
        self.client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None

    @property
    def is_demo_mode(self) -> bool:
        """Return True when LLM-backed features should fall back to local heuristics."""
        return self.force_demo_mode or not self.client

    def generate_outreach(
        self,
        startup_domain: str,
        startup_description: str,
        investor_name: str,
        firm_name: str,
    ) -> Dict[str, Any]:
        """Generate a personalized investor outreach draft."""
        startup_domain = (startup_domain or "").strip()
        startup_description = (startup_description or "").strip()
        investor_name = (investor_name or "").strip()
        firm_name = (firm_name or "").strip()

        if not startup_domain or not investor_name or not firm_name:
            raise ValueError("startup_domain, investor_name, and firm_name are required.")

        if self.is_demo_mode:
            return self._demo_outreach(startup_domain, startup_description, investor_name, firm_name)

        schema = {
            "type": "object",
            "properties": {
                "email_subject": {"type": "string"},
                "email_body": {"type": "string"},
                "reason_for_match": {"type": "string"},
            },
            "required": ["email_subject", "email_body", "reason_for_match"],
            "additionalProperties": False,
        }
        payload = self._chat_json(
            schema_name="fundraising_outreach",
            schema=schema,
            system_prompt=(
                "You write concise, credible fundraising outreach for startup founders. "
                "Sound polished, specific, and warm without overhyping. Avoid fake traction claims."
            ),
            user_prompt=(
                f"Generate a short personalized investor outreach email.\n\n"
                f"Startup domain: {startup_domain}\n"
                f"Startup description: {startup_description or 'An early-stage startup with a focused market opportunity.'}\n"
                f"Investor name: {investor_name}\n"
                f"Firm name: {firm_name}\n\n"
                "Return JSON only with:\n"
                "email_subject\nemail_body\nreason_for_match"
            ),
        )
        payload["mode"] = "live"
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        payload["email"] = payload["email_body"]
        return payload

    def analyze_pitch_deck(
        self,
        deck_text: str,
        startup_domain: str = "",
        funding_stage: str = "",
    ) -> Dict[str, Any]:
        """Analyze an uploaded pitch deck and return structured scoring."""
        clean_text = (deck_text or "").strip()
        if not clean_text:
            raise ValueError("Pitch deck text could not be extracted.")

        if self.is_demo_mode:
            return self._demo_pitch_analysis(clean_text, startup_domain, funding_stage)

        schema = {
            "type": "object",
            "properties": {
                "pitch_score": {"type": "integer"},
                "summary": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "improvements": {"type": "array", "items": {"type": "string"}},
                "evaluations": {
                    "type": "object",
                    "properties": {
                        "problem_clarity": {"type": "integer"},
                        "market_size": {"type": "integer"},
                        "traction": {"type": "integer"},
                        "team_strength": {"type": "integer"},
                        "investment_readiness": {"type": "integer"},
                    },
                    "required": [
                        "problem_clarity",
                        "market_size",
                        "traction",
                        "team_strength",
                        "investment_readiness",
                    ],
                    "additionalProperties": False,
                },
            },
            "required": ["pitch_score", "summary", "strengths", "improvements", "evaluations"],
            "additionalProperties": False,
        }
        payload = self._chat_json(
            schema_name="pitch_deck_analysis",
            schema=schema,
            system_prompt=(
                "You are an investment associate reviewing startup pitch decks. "
                "Provide actionable but concise fundraising feedback based only on the supplied deck text."
            ),
            user_prompt=(
                f"Analyze this pitch deck for a {funding_stage or 'startup'} in {startup_domain or 'technology'}.\n"
                "Return JSON only.\n\n"
                f"Pitch deck text:\n{clean_text[:28000]}"
            ),
        )
        payload["mode"] = "live"
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    def analyze_competitors(self, startup_idea: str, startup_domain: str = "") -> Dict[str, Any]:
        """Generate structured competitor intelligence for a startup idea."""
        clean_idea = (startup_idea or "").strip()
        clean_domain = (startup_domain or "").strip()
        if not clean_idea:
            raise ValueError("startup_idea is required.")

        if self.is_demo_mode:
            return self._demo_competitors(clean_idea, clean_domain)

        schema = {
            "type": "object",
            "properties": {
                "market_summary": {"type": "string"},
                "competitors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "company_name": {"type": "string"},
                            "funding_raised": {"type": "string"},
                            "investors": {"type": "string"},
                            "differentiation_note": {"type": "string"},
                        },
                        "required": [
                            "company_name",
                            "funding_raised",
                            "investors",
                            "differentiation_note",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["market_summary", "competitors"],
            "additionalProperties": False,
        }
        payload = self._chat_json(
            schema_name="competitor_intelligence",
            schema=schema,
            system_prompt=(
                "You are a startup market intelligence analyst. "
                "Give concise competitor mapping with plausible fundraising benchmarks."
            ),
            user_prompt=(
                f"Startup idea: {clean_idea}\n"
                f"Startup domain: {clean_domain or 'Unknown'}\n\n"
                "Return JSON only with:\n"
                "market_summary\ncompetitors[] containing company_name, funding_raised, investors, differentiation_note"
            ),
        )
        payload["mode"] = "live"
        payload["generated_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    def predict_funding_probability(
        self,
        domain: str,
        stage: str,
        team_size: str,
        market: str,
        traction: str = "",
    ) -> Dict[str, Any]:
        """Estimate a fundraising probability score and explain the key factors."""
        clean_domain = (domain or "").strip()
        clean_stage = (stage or "").strip()
        clean_market = (market or "").strip()
        clean_team_size = str(team_size or "").strip()
        clean_traction = (traction or "").strip()

        if not clean_domain or not clean_stage:
            raise ValueError("domain and stage are required.")

        factor_scores = self._heuristic_probability_factors(
            clean_domain, clean_stage, clean_team_size, clean_market, clean_traction
        )
        funding_probability = round(
            sum(item["score"] for item in factor_scores) / max(len(factor_scores), 1)
        )

        if self.is_demo_mode:
            summary = self._build_probability_summary(clean_domain, clean_stage, factor_scores)
            return {
                "mode": "demo",
                "funding_probability": funding_probability,
                "summary": summary,
                "factors": factor_scores,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        schema = {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
            "additionalProperties": False,
        }
        payload = self._chat_json(
            schema_name="funding_probability_summary",
            schema=schema,
            system_prompt=(
                "You are an experienced early-stage VC analyst. "
                "Summarize fundraising probability clearly from the supplied factors."
            ),
            user_prompt=(
                f"Startup domain: {clean_domain}\n"
                f"Stage: {clean_stage}\n"
                f"Team size: {clean_team_size or 'Unknown'}\n"
                f"Market: {clean_market or 'Unknown'}\n"
                f"Traction: {clean_traction or 'Unknown'}\n"
                f"Probability score: {funding_probability}\n"
                f"Factors: {json.dumps(factor_scores)}\n\n"
                "Return JSON only with a one-paragraph summary."
            ),
        )
        return {
            "mode": "live",
            "funding_probability": funding_probability,
            "summary": payload["summary"],
            "factors": factor_scores,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def suggest_warm_intros(
        self,
        investor_name: str,
        firm_name: str,
        startup_domain: str,
        portfolio_examples: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Return plausible warm intro pathways using public-like relationship heuristics."""
        examples = portfolio_examples or []
        intros: List[Dict[str, str]] = []

        if examples:
            intros.append(
                {
                    "introducer_name": f"{examples[0]} founder network",
                    "role": "Portfolio founder pathway",
                    "connection_path": f"{firm_name} portfolio relationship",
                    "rationale": (
                        f"Founders inside {firm_name}'s portfolio can create higher-context warm introductions for {investor_name}."
                    ),
                }
            )

        intros.append(
            {
                "introducer_name": f"{startup_domain} operator community",
                "role": "Domain expert network",
                "connection_path": "Angel operators and startup advisors",
                "rationale": "Operators with domain credibility often create faster trust in first investor conversations.",
            }
        )
        intros.append(
            {
                "introducer_name": "Accelerator and alumni ecosystem",
                "role": "Founder community",
                "connection_path": "YC, Techstars, angel syndicates, and startup communities",
                "rationale": "Founder communities often surface warm paths through shared operators, scouts, and founders.",
            }
        )
        return intros[:3]

    def _chat_json(
        self,
        schema_name: str,
        schema: Dict[str, Any],
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Call OpenAI with a strict JSON schema and return parsed content."""
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        response = self.client.chat.completions.create(
            model=self.openai_model,
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return json.loads(response.choices[0].message.content or "{}")

    def _demo_outreach(
        self,
        startup_domain: str,
        startup_description: str,
        investor_name: str,
        firm_name: str,
    ) -> Dict[str, Any]:
        """Return a strong default outreach draft when live LLM access is unavailable."""
        description = startup_description or "an early-stage product with clear founder-market fit"
        return {
            "mode": "demo",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "email_subject": f"{startup_domain} startup exploring fit with {firm_name}",
            "email_body": (
                f"Hi {investor_name},\n\n"
                f"I'm building {description} in the {startup_domain} category. "
                f"I reached out because {firm_name} has a strong reputation for backing ambitious founders early, "
                "especially where product velocity and long-term market conviction matter.\n\n"
                "We're focused on solving a painful workflow problem with a product-led approach, "
                "and I'd value the chance to share what we're seeing in the market and learn whether it fits your investment lens.\n\n"
                "Would you be open to a short introductory conversation next week?\n\n"
                "Best,\nFounder"
            ),
            "reason_for_match": (
                f"{firm_name} appears relevant for {startup_domain} founders because the firm is active in early-stage software and platform investments."
            ),
            "email": (
                f"Hi {investor_name},\n\n"
                f"I'm building {description} in the {startup_domain} category and would love to explore whether there could be fit with {firm_name}.\n\n"
                "Best,\nFounder"
            ),
        }

    def _demo_pitch_analysis(
        self,
        deck_text: str,
        startup_domain: str,
        funding_stage: str,
    ) -> Dict[str, Any]:
        """Heuristic deck analysis when OpenAI is unavailable."""
        normalized = deck_text.lower()
        evaluations = {
            "problem_clarity": 86 if "problem" in normalized or "pain" in normalized else 68,
            "market_size": 82 if "tam" in normalized or "market" in normalized else 64,
            "traction": 84 if any(token in normalized for token in ("revenue", "growth", "users", "arr")) else 58,
            "team_strength": 80 if any(token in normalized for token in ("founder", "team", "experience")) else 62,
            "investment_readiness": 78 if any(token in normalized for token in ("ask", "use of funds", "raise")) else 60,
        }
        pitch_score = round(sum(evaluations.values()) / len(evaluations))
        return {
            "mode": "demo",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pitch_score": pitch_score,
            "summary": (
                f"The {startup_domain or 'startup'} deck shows a credible early narrative for a {funding_stage or 'fundraising'} round, "
                "but the strongest gains will come from sharper traction proof and clearer market sizing."
            ),
            "strengths": [
                "The story presents a recognizable problem and solution arc.",
                "There are enough market cues to support investor curiosity.",
                "The deck structure appears suitable for an initial fundraising conversation.",
            ],
            "improvements": [
                "Quantify traction with one or two headline metrics.",
                "Tighten the market slide with a clearer wedge and ICP definition.",
                "Make the funding ask and use-of-funds section more explicit.",
            ],
            "evaluations": evaluations,
        }

    def _demo_competitors(self, startup_idea: str, startup_domain: str) -> Dict[str, Any]:
        """Fallback competitor mapping based on domain heuristics."""
        normalized = (startup_domain or startup_idea).lower()
        sample_key = "ai"
        for key in COMPETITOR_SAMPLES:
            if key in normalized:
                sample_key = key
                break

        competitors = COMPETITOR_SAMPLES[sample_key]
        return {
            "mode": "demo",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "market_summary": (
                f"The {startup_domain or 'startup'} market is active, and investors are backing companies with clear GTM focus, differentiated workflows, and repeatable revenue signals."
            ),
            "competitors": competitors,
        }

    def _heuristic_probability_factors(
        self,
        domain: str,
        stage: str,
        team_size: str,
        market: str,
        traction: str,
    ) -> List[Dict[str, Any]]:
        """Score the major fundraising variables using lightweight heuristics."""
        clean_domain = domain.lower()
        clean_stage = stage.lower()
        clean_market = market.lower()
        clean_traction = traction.lower()
        parsed_team_size = int(team_size) if str(team_size).isdigit() else 0

        market_growth = 82 if any(token in clean_domain for token in ("ai", "fintech", "climate")) else 70
        if any(token in clean_market for token in ("enterprise", "global", "large")):
            market_growth += 5

        competition = 62 if any(token in clean_domain for token in ("ai", "fintech")) else 72
        if any(token in clean_market for token in ("niche", "underserved", "mid-market")):
            competition += 8

        traction_score = 88 if any(token in clean_traction for token in ("revenue", "growth", "paid", "pipeline")) else 61
        team_strength = 78 if parsed_team_size >= 5 else 64
        if "series a" in clean_stage:
            execution_readiness = 76
        elif "seed" in clean_stage:
            execution_readiness = 69
        else:
            execution_readiness = 63

        return [
            {
                "label": "Market Growth",
                "score": min(market_growth, 100),
                "detail": "Measures whether the market narrative is currently attractive to venture investors.",
            },
            {
                "label": "Competition",
                "score": min(competition, 100),
                "detail": "Estimates how crowded the space feels and whether differentiation will be hard to defend.",
            },
            {
                "label": "Traction",
                "score": min(traction_score, 100),
                "detail": "Rewards evidence of adoption, revenue, pilots, or strong customer pull.",
            },
            {
                "label": "Team Strength",
                "score": min(team_strength, 100),
                "detail": "Looks at team depth and whether execution capability feels credible for the stage.",
            },
            {
                "label": "Execution Readiness",
                "score": min(execution_readiness, 100),
                "detail": "Reflects how ready the startup sounds for the stated round and investor expectations.",
            },
        ]

    @staticmethod
    def _build_probability_summary(domain: str, stage: str, factor_scores: List[Dict[str, Any]]) -> str:
        """Create a compact summary for the probability predictor fallback."""
        strongest = max(factor_scores, key=lambda item: item["score"])
        weakest = min(factor_scores, key=lambda item: item["score"])
        return (
            f"For a {stage} company in {domain}, the strongest fundraising signal is {strongest['label'].lower()}, "
            f"while the biggest risk area is {weakest['label'].lower()}. Tightening that weaker dimension would materially improve investor readiness."
        )
