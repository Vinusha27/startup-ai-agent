import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
from openai import OpenAI
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Page, async_playwright


load_dotenv()


TEAM_TARGETS = [
    {"name": "Sequoia Capital", "url": "https://www.sequoiacap.com/our-team/"},
    {"name": "Accel", "url": "https://www.accel.com/team"},
]

PORTFOLIO_TARGETS = [
    {"name": "Sequoia Capital", "url": "https://www.sequoiacap.com/companies/"},
    {"name": "Accel", "url": "https://www.accel.com/portfolio"},
]

REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DOMAIN_KEYWORDS = {
    "ai": {"ai", "artificial intelligence", "machine learning", "llm", "automation", "agents"},
    "fintech": {"fintech", "payments", "banking", "finance", "lending", "embedded finance"},
    "healthtech": {"healthtech", "healthcare", "digital health", "biotech", "medical"},
    "saas": {"saas", "enterprise software", "cloud", "workflow", "productivity", "b2b software"},
    "cybersecurity": {"cybersecurity", "security", "identity", "fraud", "risk"},
    "climate": {"climate", "sustainability", "energy", "carbon", "clean tech"},
}

STAGE_KEYWORDS = {
    "pre-seed": {"pre-seed", "pre seed"},
    "seed": {"seed", "pre-seed", "pre seed", "early stage"},
    "series a": {"series a", "series-a"},
    "series b": {"series b", "series-b", "growth"},
}

SAMPLE_PORTFOLIOS = {
    "Sequoia Capital": ["UiPath", "MongoDB", "Confluent", "Fireflies", "Amplitude"],
    "Accel": ["Dropbox", "Slack", "Miro", "BrowserStack", "Freshworks"],
}

SAMPLE_INVESTORS = [
    {
        "investor_name": "Sarah Lin",
        "firm_name": "Sequoia Capital",
        "investment_focus": "AI infrastructure, enterprise software, and developer tooling",
        "profile_url": "https://www.sequoiacap.com/people/sarah-lin",
        "location": "San Francisco, USA",
        "bio_text": "Backs AI and enterprise software founders building category-defining infrastructure products.",
        "stage_preference": "Seed, Series A",
    },
    {
        "investor_name": "Marcus Reed",
        "firm_name": "Accel",
        "investment_focus": "SaaS platforms, workflow automation, and cloud applications",
        "profile_url": "https://www.accel.com/team/marcus-reed",
        "location": "New York, USA",
        "bio_text": "Focuses on early-stage SaaS and productivity startups serving global enterprises.",
        "stage_preference": "Seed",
    },
    {
        "investor_name": "Priya Sharma",
        "firm_name": "Accel",
        "investment_focus": "FinTech infrastructure, digital payments, and embedded finance",
        "profile_url": "https://www.accel.com/team/priya-sharma",
        "location": "Bangalore, India",
        "bio_text": "Partners with FinTech founders modernizing payment rails and financial operations.",
        "stage_preference": "Series A",
    },
]


class InvestorDiscoveryScraper:
    """Scrape VC data, analyze portfolios, and return product-ready investor records."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4.1-mini",
        force_demo_mode: bool = False,
        timeout_ms: int = 45000,
        headless: bool = True,
        intelligence_agent: Optional[Any] = None,
    ) -> None:
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.openai_model = openai_model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.force_demo_mode = force_demo_mode
        self.timeout_ms = timeout_ms
        self.headless = headless
        self.client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None
        self.targets = TEAM_TARGETS
        self.portfolio_targets = PORTFOLIO_TARGETS
        self.intelligence_agent = intelligence_agent

    def find_investors(self, domain: str, stage: str, location: str = "") -> Dict[str, Any]:
        """Discover investors and return scorecards, portfolio analysis, and fit scores."""
        domain = (domain or "").strip()
        stage = (stage or "").strip()
        location = (location or "").strip()

        if not domain or not stage:
            raise ValueError("Startup domain and funding stage are required.")

        errors: List[str] = []

        if self.force_demo_mode:
            errors.append("Demo mode was explicitly enabled with DEMO_MODE=true.")
            return self._demo_response(domain, stage, location, errors)

        if not self.client:
            errors.append("OPENAI_API_KEY is missing. Falling back to demo investors.")
            return self._demo_response(domain, stage, location, errors)

        try:
            scraped_sources, scrape_errors = self.scrape_targets()
            errors.extend(scrape_errors)

            team_pages = scraped_sources.get("team_pages", [])
            portfolio_pages = scraped_sources.get("portfolio_pages", {})

            if not team_pages:
                errors.append("No VC team pages returned readable data.")
                return self._demo_response(domain, stage, location, errors)

            raw_investors = self.parse_investors_with_openai(
                self._combine_scraped_text(team_pages), domain, stage
            )
            if not raw_investors:
                errors.append("OpenAI returned no investor records.")
                return self._demo_response(domain, stage, location, errors)

            portfolio_companies_by_firm = self._build_portfolio_map(portfolio_pages, errors)
            portfolio_analysis_by_firm = self._build_portfolio_analysis(
                domain, portfolio_companies_by_firm, errors
            )

            investors = self._normalise_investors(
                raw_investors=raw_investors,
                startup_domain=domain,
                startup_stage=stage,
                startup_location=location,
                portfolio_companies_by_firm=portfolio_companies_by_firm,
                portfolio_analysis_by_firm=portfolio_analysis_by_firm,
            )
            if not investors:
                errors.append("The parsed investor list could not be normalized.")
                return self._demo_response(domain, stage, location, errors)

            return {
                "mode": "live",
                "investors": investors,
                "errors": errors,
                "sources": [page["url"] for page in team_pages] + [target["url"] for target in PORTFOLIO_TARGETS],
                "scan_steps": [
                    "Searching VC websites...",
                    "Extracting investor data...",
                    "Analyzing portfolios...",
                    "Calculating AI scores...",
                ],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            errors.append(str(exc))
            return self._demo_response(domain, stage, location, errors)

    def scrape_targets(self) -> Tuple[Dict[str, Any], List[str]]:
        """Run the async scraper from the sync Flask request flow."""
        return asyncio.run(self._scrape_targets_async())

    async def _scrape_targets_async(self) -> Tuple[Dict[str, Any], List[str]]:
        """Visit team and portfolio pages, extract body text, and collect relevant links."""
        team_pages: List[Dict[str, str]] = []
        portfolio_pages: Dict[str, str] = {}
        errors: List[str] = []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=REALISTIC_USER_AGENT,
                viewport={"width": 1440, "height": 960},
                locale="en-US",
                timezone_id="America/Los_Angeles",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Upgrade-Insecure-Requests": "1",
                },
            )

            try:
                for target in TEAM_TARGETS:
                    page = await context.new_page()
                    try:
                        await page.goto(target["url"], wait_until="domcontentloaded", timeout=self.timeout_ms)
                        await page.wait_for_timeout(1200)
                        await self._scroll_page(page)
                        body_text = self._clean_body_text(await page.locator("body").inner_text())
                        profile_links = await self._extract_relevant_links(page, target["url"])

                        if not body_text:
                            errors.append(f"{target['name']}: extracted body text was empty.")
                            continue

                        link_block = "\n".join(profile_links[:40])
                        team_pages.append(
                            {
                                "name": target["name"],
                                "url": target["url"],
                                "text": (
                                    f"{body_text}\n\nCandidate profile links:\n{link_block}"
                                    if link_block
                                    else body_text
                                ),
                            }
                        )
                    except (PlaywrightTimeoutError, PlaywrightError) as exc:
                        errors.append(f"{target['name']}: {exc}")
                    finally:
                        await page.close()

                for target in PORTFOLIO_TARGETS:
                    page = await context.new_page()
                    try:
                        await page.goto(target["url"], wait_until="domcontentloaded", timeout=self.timeout_ms)
                        await page.wait_for_timeout(1200)
                        await self._scroll_page(page)
                        body_text = self._clean_body_text(await page.locator("body").inner_text())

                        if body_text:
                            portfolio_pages[target["name"]] = body_text
                        else:
                            errors.append(f"{target['name']} portfolio: extracted body text was empty.")
                    except (PlaywrightTimeoutError, PlaywrightError) as exc:
                        errors.append(f"{target['name']} portfolio: {exc}")
                    finally:
                        await page.close()
            finally:
                await context.close()
                await browser.close()

        return {"team_pages": team_pages, "portfolio_pages": portfolio_pages}, errors

    def parse_investors_with_openai(
        self, scraped_text: str, domain: str, stage: str
    ) -> List[Dict[str, Any]]:
        """Use OpenAI to extract investor records from VC team page text."""
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        response = self.client.chat.completions.create(
            model=self.openai_model,
            temperature=0.2,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ai_investor_discovery",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "investors": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "investor_name": {"type": "string"},
                                        "firm_name": {"type": "string"},
                                        "bio_text": {"type": "string"},
                                        "investment_focus": {"type": "string"},
                                        "profile_url": {"type": "string"},
                                        "location": {"type": "string"},
                                        "stage_preference": {"type": "string"},
                                    },
                                    "required": [
                                        "investor_name",
                                        "firm_name",
                                        "bio_text",
                                        "investment_focus",
                                        "profile_url",
                                        "location",
                                        "stage_preference",
                                    ],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["investors"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract venture investor data from public VC team pages. "
                        "Use only the supplied text. Prefer investors, partners, and named decision-makers. "
                        "If something is unclear, return 'Unknown'."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Extract investor records from this VC website text.\n\n"
                        "Return JSON only with these fields:\n"
                        "investor_name\nfirm_name\nbio_text\ninvestment_focus\nprofile_url\nlocation\nstage_preference\n\n"
                        f"Find the investors most relevant to a {stage} startup in the {domain} space.\n\n"
                        f"Website text:\n{scraped_text}"
                    ),
                },
            ],
        )

        payload = json.loads(response.choices[0].message.content or "{}")
        return payload.get("investors", [])

    def parse_portfolio_companies_with_openai(self, firm_name: str, portfolio_text: str) -> List[str]:
        """Use OpenAI to extract company names from a VC portfolio page."""
        if not self.client:
            return []

        response = self.client.chat.completions.create(
            model=self.openai_model,
            temperature=0.1,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "portfolio_companies",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {"companies": {"type": "array", "items": {"type": "string"}}},
                        "required": ["companies"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[
                {"role": "system", "content": "Extract portfolio company names from public VC portfolio page text."},
                {
                    "role": "user",
                    "content": (
                        f"Extract a clean list of company names from {firm_name}'s portfolio page text. "
                        "Return JSON only.\n\n"
                        f"Portfolio page text:\n{portfolio_text[:25000]}"
                    ),
                },
            ],
        )

        payload = json.loads(response.choices[0].message.content or "{}")
        return [company.strip() for company in payload.get("companies", []) if company.strip()]

    def analyze_portfolio_fit(self, startup_domain: str, firm_name: str, companies: List[str]) -> Dict[str, Any]:
        """Use OpenAI to compare startup domain with a VC firm's portfolio."""
        if not self.client:
            return self._fallback_portfolio_analysis(startup_domain, firm_name, companies)

        response = self.client.chat.completions.create(
            model=self.openai_model,
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "portfolio_analysis",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "portfolio_examples": {"type": "array", "items": {"type": "string"}},
                            "insight": {"type": "string"},
                            "portfolio_similarity": {"type": "integer"},
                        },
                        "required": ["portfolio_examples", "insight", "portfolio_similarity"],
                        "additionalProperties": False,
                    },
                },
            },
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze how a startup domain aligns with a VC firm's portfolio. "
                        "Respond only from the supplied company list."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"A founder is building in the {startup_domain} sector. "
                        f"Analyze how well {firm_name}'s portfolio aligns with that domain.\n\n"
                        f"Portfolio companies:\n{', '.join(companies[:40])}\n\n"
                        "Return JSON with:\n"
                        "portfolio_examples: 3 to 5 relevant examples from the list\n"
                        "insight: one concise sentence\n"
                        "portfolio_similarity: integer from 0 to 100"
                    ),
                },
            ],
        )

        payload = json.loads(response.choices[0].message.content or "{}")
        return {
            "portfolio_examples": payload.get("portfolio_examples", [])[:5],
            "insight": payload.get(
                "insight",
                "This firm has a relevant portfolio footprint for the startup domain.",
            ),
            "portfolio_similarity": int(payload.get("portfolio_similarity", 60)),
        }

    def _build_portfolio_map(
        self, portfolio_pages: Dict[str, str], errors: List[str]
    ) -> Dict[str, List[str]]:
        """Extract portfolio company names for each firm."""
        portfolio_map: Dict[str, List[str]] = {}

        for firm_name, portfolio_text in portfolio_pages.items():
            try:
                companies = self.parse_portfolio_companies_with_openai(firm_name, portfolio_text)
                if companies:
                    portfolio_map[firm_name] = companies
            except Exception as exc:
                errors.append(f"{firm_name} portfolio parsing: {exc}")

        for firm_name, sample_companies in SAMPLE_PORTFOLIOS.items():
            portfolio_map.setdefault(firm_name, sample_companies)

        return portfolio_map

    def _build_portfolio_analysis(
        self,
        startup_domain: str,
        portfolio_companies_by_firm: Dict[str, List[str]],
        errors: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Generate portfolio analysis insights for each VC firm."""
        analysis: Dict[str, Dict[str, Any]] = {}

        for firm_name, companies in portfolio_companies_by_firm.items():
            try:
                analysis[firm_name] = self.analyze_portfolio_fit(startup_domain, firm_name, companies)
            except Exception as exc:
                errors.append(f"{firm_name} portfolio analysis: {exc}")
                analysis[firm_name] = self._fallback_portfolio_analysis(startup_domain, firm_name, companies)

        return analysis

    def _combine_scraped_text(self, pages: List[Dict[str, str]]) -> str:
        """Combine scraped team text into a single prompt payload."""
        sections: List[str] = []
        total_characters = 0

        for page in pages:
            section = f"Source: {page['name']} ({page['url']})\n{page['text'][:20000]}"
            if total_characters + len(section) > 45000:
                break
            sections.append(section)
            total_characters += len(section)

        return "\n\n".join(sections)

    def _normalise_investors(
        self,
        raw_investors: List[Dict[str, Any]],
        startup_domain: str,
        startup_stage: str,
        startup_location: str,
        portfolio_companies_by_firm: Dict[str, List[str]],
        portfolio_analysis_by_firm: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Normalize parsed investors and attach scorecards plus portfolio analysis."""
        investors: List[Dict[str, Any]] = []
        seen = set()

        for item in raw_investors:
            if not isinstance(item, dict):
                continue

            investor_name = self._as_text(item.get("investor_name")) or "Unknown"
            firm_name = self._as_text(item.get("firm_name")) or "Unknown"
            bio_text = self._as_text(item.get("bio_text")) or "Unknown"
            investment_focus = self._as_text(item.get("investment_focus")) or bio_text or "Unknown"
            profile_url = self._clean_profile_url(item.get("profile_url"))
            location = self._as_text(item.get("location")) or "Unknown"
            stage_preference = self._as_text(item.get("stage_preference")) or "Unknown"

            dedupe_key = (investor_name.lower(), firm_name.lower(), profile_url.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            portfolio_analysis = portfolio_analysis_by_firm.get(
                firm_name,
                self._fallback_portfolio_analysis(
                    startup_domain, firm_name, portfolio_companies_by_firm.get(firm_name, [])
                ),
            )
            scorecard = self._build_scorecard(
                startup_domain=startup_domain,
                startup_stage=startup_stage,
                startup_location=startup_location,
                investor_focus=investment_focus,
                bio_text=bio_text,
                investor_location=location,
                stage_preference=stage_preference,
                portfolio_similarity=int(portfolio_analysis.get("portfolio_similarity", 60)),
            )
            total_score = round(
                (
                    scorecard["domain_fit"]
                    + scorecard["stage_fit"]
                    + scorecard["geography_fit"]
                    + scorecard["portfolio_similarity"]
                )
                / 4
            )

            investors.append(
                {
                    "investor_name": investor_name,
                    "firm_name": firm_name,
                    "investment_focus": investment_focus,
                    "location": location,
                    "profile_url": profile_url,
                    "bio_text": bio_text,
                    "portfolio_examples": portfolio_analysis.get("portfolio_examples", [])[:5],
                    "portfolio_insight": portfolio_analysis.get(
                        "insight",
                        "This firm has adjacent portfolio experience relevant to the startup domain.",
                    ),
                    "warm_intro_suggestions": self._warm_intro_suggestions(
                        startup_domain=startup_domain,
                        investor_name=investor_name,
                        firm_name=firm_name,
                        portfolio_examples=portfolio_analysis.get("portfolio_examples", [])[:5],
                    ),
                    "scorecard": scorecard,
                    "total_match_score": total_score,
                    "match_score": total_score,
                }
            )

        investors.sort(key=lambda investor: investor["total_match_score"], reverse=True)
        return investors[:20]

    def _demo_response(
        self, domain: str, stage: str, location: str, errors: List[str]
    ) -> Dict[str, Any]:
        """Return demo investor data with scorecards and portfolio analysis."""
        investors: List[Dict[str, Any]] = []

        for sample in SAMPLE_INVESTORS:
            portfolio_analysis = self._fallback_portfolio_analysis(
                startup_domain=domain,
                firm_name=sample["firm_name"],
                companies=SAMPLE_PORTFOLIOS.get(sample["firm_name"], []),
            )
            scorecard = self._build_scorecard(
                startup_domain=domain,
                startup_stage=stage,
                startup_location=location,
                investor_focus=sample["investment_focus"],
                bio_text=sample["bio_text"],
                investor_location=sample["location"],
                stage_preference=sample["stage_preference"],
                portfolio_similarity=int(portfolio_analysis["portfolio_similarity"]),
            )
            total_score = round(
                (
                    scorecard["domain_fit"]
                    + scorecard["stage_fit"]
                    + scorecard["geography_fit"]
                    + scorecard["portfolio_similarity"]
                )
                / 4
            )
            investors.append(
                {
                    "investor_name": sample["investor_name"],
                    "firm_name": sample["firm_name"],
                    "investment_focus": sample["investment_focus"],
                    "location": sample["location"],
                    "profile_url": sample["profile_url"],
                    "bio_text": sample["bio_text"],
                    "portfolio_examples": portfolio_analysis["portfolio_examples"],
                    "portfolio_insight": portfolio_analysis["insight"],
                    "warm_intro_suggestions": self._warm_intro_suggestions(
                        startup_domain=domain,
                        investor_name=sample["investor_name"],
                        firm_name=sample["firm_name"],
                        portfolio_examples=portfolio_analysis["portfolio_examples"],
                    ),
                    "scorecard": scorecard,
                    "total_match_score": total_score,
                    "match_score": total_score,
                }
            )

        investors.sort(key=lambda investor: investor["total_match_score"], reverse=True)
        return {
            "mode": "demo",
            "investors": investors,
            "errors": errors,
            "sources": [target["url"] for target in TEAM_TARGETS] + [target["url"] for target in PORTFOLIO_TARGETS],
            "scan_steps": [
                "Searching VC websites...",
                "Extracting investor data...",
                "Analyzing portfolios...",
                "Calculating AI scores...",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _build_scorecard(
        self,
        startup_domain: str,
        startup_stage: str,
        startup_location: str,
        investor_focus: str,
        bio_text: str,
        investor_location: str,
        stage_preference: str,
        portfolio_similarity: int,
    ) -> Dict[str, int]:
        """Generate a fit score breakdown for a single investor."""
        focus_text = self._normalise(f"{investor_focus} {bio_text}")
        domain_keywords = self._expand_domain_keywords(startup_domain)

        if self._contains_any_keyword(focus_text, domain_keywords):
            domain_fit = 90
        elif self._has_keyword_similarity(domain_keywords, focus_text):
            domain_fit = 72
        else:
            domain_fit = 48

        if self._stage_matches(startup_stage, stage_preference) or self._stage_matches(startup_stage, focus_text):
            stage_fit = 85
        elif stage_preference and stage_preference != "Unknown":
            stage_fit = 60
        else:
            stage_fit = 50

        geography_fit = self._geography_fit(startup_location, investor_location)

        return {
            "domain_fit": int(max(0, min(domain_fit, 100))),
            "stage_fit": int(max(0, min(stage_fit, 100))),
            "geography_fit": int(max(0, min(geography_fit, 100))),
            "portfolio_similarity": int(max(0, min(portfolio_similarity, 100))),
        }

    def _fallback_portfolio_analysis(
        self, startup_domain: str, firm_name: str, companies: List[str]
    ) -> Dict[str, Any]:
        """Fallback portfolio analysis when the LLM is unavailable."""
        examples = companies[:3] if companies else ["Unknown"]
        similarity = 80 if self._has_keyword_similarity(
            self._expand_domain_keywords(startup_domain), " ".join(companies).lower()
        ) else 62
        return {
            "portfolio_examples": examples,
            "insight": f"{firm_name} has portfolio exposure that appears adjacent to the {startup_domain} category.",
            "portfolio_similarity": similarity,
        }

    def _warm_intro_suggestions(
        self,
        startup_domain: str,
        investor_name: str,
        firm_name: str,
        portfolio_examples: List[str],
    ) -> List[Dict[str, str]]:
        """Attach warm intro paths to each investor result without breaking discovery latency."""
        if self.intelligence_agent:
            suggestions = self.intelligence_agent.suggest_warm_intros(
                investor_name=investor_name,
                firm_name=firm_name,
                startup_domain=startup_domain,
                portfolio_examples=portfolio_examples,
            )
            if suggestions:
                return suggestions

        return [
            {
                "introducer_name": f"{firm_name} scout or founder network",
                "role": "Firm-adjacent ecosystem",
                "connection_path": "Portfolio operators, angel scouts, or founder communities",
                "rationale": f"A warm path through {firm_name}'s extended founder network can raise reply probability for {investor_name}.",
            },
            {
                "introducer_name": f"{startup_domain} angel network",
                "role": "Sector connector",
                "connection_path": "Domain operators and startup advisors",
                "rationale": "Domain-native angels can add context on market timing and founder credibility.",
            },
        ]

    @staticmethod
    async def _scroll_page(page: Page) -> None:
        """Scroll repeatedly to trigger lazy loading."""
        previous_height = 0
        for _ in range(6):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(900)
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                break
            previous_height = current_height

    @staticmethod
    async def _extract_relevant_links(page: Page, base_url: str) -> List[str]:
        """Extract profile-like links from the DOM."""
        hrefs = await page.locator("a[href]").evaluate_all("(nodes) => nodes.map((node) => node.href)")
        base_domain = urlparse(base_url).netloc
        links: List[str] = []

        for href in hrefs:
            if not href:
                continue
            absolute_url = urljoin(base_url, href).strip()
            if any(token in absolute_url for token in ("javascript:", "mailto:", "#")):
                continue
            parsed = urlparse(absolute_url)
            if parsed.netloc == base_domain or "linkedin.com" in absolute_url:
                links.append(absolute_url)

        deduped: List[str] = []
        seen = set()
        for link in links:
            if link not in seen:
                seen.add(link)
                deduped.append(link)
        return deduped

    @staticmethod
    def _clean_body_text(text: str) -> str:
        """Normalize whitespace and trim repeated empty lines."""
        return re.sub(r"\n{3,}", "\n\n", (text or "").strip())[:30000]

    @staticmethod
    def _clean_profile_url(value: Any) -> str:
        """Return a valid profile URL or Unknown."""
        text = str(value or "").strip()
        if text.startswith("http://") or text.startswith("https://"):
            return text
        return "Unknown"

    @staticmethod
    def _as_text(value: Any) -> str:
        """Convert scalar values into clean strings."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @staticmethod
    def _normalise(value: str) -> str:
        """Normalize text for keyword matching."""
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    @staticmethod
    def _expand_domain_keywords(domain: str) -> List[str]:
        """Expand a startup domain into a list of related keywords."""
        clean_domain = InvestorDiscoveryScraper._normalise(domain)
        if not clean_domain:
            return []

        keywords = {clean_domain}
        for canonical_domain, related_keywords in DOMAIN_KEYWORDS.items():
            if clean_domain == canonical_domain or clean_domain in related_keywords:
                keywords.add(canonical_domain)
                keywords.update(related_keywords)
        return list(keywords)

    @staticmethod
    def _stage_matches(startup_stage: str, stage_text: str) -> bool:
        """Check if a startup stage aligns with the investor description."""
        clean_stage = InvestorDiscoveryScraper._normalise(startup_stage)
        clean_text = InvestorDiscoveryScraper._normalise(stage_text)
        if not clean_stage or not clean_text:
            return False

        valid_terms = STAGE_KEYWORDS.get(clean_stage, {clean_stage})
        return any(term in clean_text for term in valid_terms)

    @staticmethod
    def _contains_any_keyword(text: str, keywords: List[str]) -> bool:
        """Return True if any keyword appears in the text."""
        for keyword in keywords:
            if not keyword:
                continue
            if len(keyword) <= 2:
                tokens = re.findall(r"[a-z0-9]+", text)
                if any(token == keyword or token.startswith(keyword) or token.endswith(keyword) for token in tokens):
                    return True
            elif re.search(r"\b" + re.escape(keyword) + r"\b", text):
                return True
        return False

    @staticmethod
    def _has_keyword_similarity(domain_keywords: List[str], focus_text: str) -> bool:
        """Grant a boost when multiple domain keywords overlap with the text."""
        overlap = sum(1 for keyword in domain_keywords if keyword and keyword in focus_text)
        return overlap >= 2

    @staticmethod
    def _geography_fit(startup_location: str, investor_location: str) -> int:
        """Estimate location fit between the startup and investor."""
        startup_tokens = set(re.findall(r"[a-z]{3,}", InvestorDiscoveryScraper._normalise(startup_location)))
        investor_tokens = set(re.findall(r"[a-z]{3,}", InvestorDiscoveryScraper._normalise(investor_location)))

        if not startup_tokens or not investor_tokens:
            return 55
        if startup_tokens.intersection(investor_tokens):
            return 85
        return 50
