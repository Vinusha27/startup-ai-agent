import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class OutreachGenerator:
    """Generate personalized investor outreach content with OpenAI and a safe fallback."""

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

    def generate_outreach(
        self,
        startup_domain: str,
        startup_description: str,
        investor_name: str,
        firm_name: str,
    ) -> Dict[str, Any]:
        """Return structured outreach copy for a founder contacting an investor."""
        startup_domain = (startup_domain or "").strip()
        startup_description = (startup_description or "").strip()
        investor_name = (investor_name or "").strip()
        firm_name = (firm_name or "").strip()

        if not startup_domain or not startup_description or not investor_name or not firm_name:
            raise ValueError(
                "Fields 'startup_domain', 'startup_description', 'investor_name', and 'firm_name' are required."
            )

        errors: List[str] = []

        if self.force_demo_mode:
            errors.append("Demo mode was explicitly enabled with DEMO_MODE=true.")
            return self._demo_response(startup_domain, startup_description, investor_name, firm_name, errors)

        if not self.client:
            errors.append("OPENAI_API_KEY is missing. Falling back to demo outreach.")
            return self._demo_response(startup_domain, startup_description, investor_name, firm_name, errors)

        try:
            response = self.client.chat.completions.create(
                model=self.openai_model,
                temperature=0.6,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "investor_outreach",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "email_subject": {"type": "string"},
                                "email_body": {"type": "string"},
                                "reason_for_match": {"type": "string"},
                            },
                            "required": ["email_subject", "email_body", "reason_for_match"],
                            "additionalProperties": False,
                        },
                    },
                },
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You write crisp, high-conviction investor outreach for startup founders. "
                            "Be concise, specific, and professional."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Create a personalized outreach package for {investor_name} at {firm_name}.\n\n"
                            f"Startup domain: {startup_domain}\n"
                            f"Startup description: {startup_description}\n\n"
                            "Return JSON with:\n"
                            "email_subject\n"
                            "email_body\n"
                            "reason_for_match\n\n"
                            "The email body should be short, founder-like, and ask for a conversation."
                        ),
                    },
                ],
            )

            payload = response.choices[0].message.content or "{}"
            result = self._safe_json_loads(payload)
            if not result:
                errors.append("OpenAI returned an empty outreach payload.")
                return self._demo_response(startup_domain, startup_description, investor_name, firm_name, errors)

            result["email"] = result.get("email_body", "")
            result["mode"] = "live"
            result["errors"] = errors
            result["generated_at"] = datetime.now(timezone.utc).isoformat()
            return result
        except Exception as exc:
            errors.append(str(exc))
            return self._demo_response(startup_domain, startup_description, investor_name, firm_name, errors)

    def _demo_response(
        self,
        startup_domain: str,
        startup_description: str,
        investor_name: str,
        firm_name: str,
        errors: List[str],
    ) -> Dict[str, Any]:
        """Return deterministic fallback outreach content."""
        return {
            "mode": "demo",
            "email_subject": f"Intro from a founder building in {startup_domain}",
            "email_body": (
                f"Hi {investor_name},\n\n"
                f"I’m building a company in the {startup_domain} space: {startup_description}. "
                f"I’m reaching out because {firm_name} has a strong reputation for backing ambitious teams "
                "building foundational products in adjacent categories.\n\n"
                "If it sounds interesting, I’d love to share a short overview and see whether a quick intro call makes sense.\n\n"
                "Best,\nA Founder"
            ),
            "reason_for_match": (
                f"{firm_name} looks relevant because the firm is active in startup-backed growth categories "
                f"that are adjacent to {startup_domain}."
            ),
            "email": (
                f"Hi {investor_name},\n\n"
                f"I’m building a company in the {startup_domain} space: {startup_description}. "
                f"I’m reaching out because {firm_name} has a strong reputation for backing ambitious teams "
                "building foundational products in adjacent categories.\n\n"
                "If it sounds interesting, I’d love to share a short overview and see whether a quick intro call makes sense.\n\n"
                "Best,\nA Founder"
            ),
            "errors": errors,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _safe_json_loads(payload: str) -> Dict[str, Any]:
        """Best-effort JSON parsing for structured model output."""
        try:
            return __import__("json").loads(payload)
        except Exception:
            return {}
