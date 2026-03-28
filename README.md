# AI Startup Fundraising Intelligence Platform

AI Startup Fundraising Intelligence Platform is a Flask-based product for founders who want to discover venture investors, understand investor fit, analyze pitch decks, generate outreach, and manage investor pipeline activity from one dashboard.

## Features

- Investor discovery with Playwright scraping for VC team and portfolio pages
- AI investor match scorecards with domain, stage, geography, and portfolio fit
- Portfolio analysis insights and warm intro suggestions
- AI outreach email generation
- Investor CRM with saved investors, notes, and status tracking
- Pitch deck analyzer with PDF text extraction
- Competitor intelligence and funding probability prediction
- Authentication with Flask-Login and SQLite

## Project Structure

```text
startup-investor-agent/
├── app.py
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── start.ps1
├── backend/
│   ├── __init__.py
│   ├── app.py
│   ├── ai_agents.py
│   ├── auth.py
│   ├── models.py
│   ├── scraper.py
│   └── outreach_generator.py
├── frontend/
│   └── README.md
├── templates/
│   ├── landing.html
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   ├── investor_results.html
│   ├── crm.html
│   └── deck_analyzer.html
├── static/
│   ├── script.js
│   └── style.css
└── database/
    └── .gitkeep
```

## Tech Stack

- Backend: Flask, Flask-Login
- Web scraping: Playwright
- AI services: OpenAI API
- Database: SQLite
- PDF analysis: pdfplumber
- Frontend: TailwindCSS, server-rendered Flask templates

## Local Setup

1. Clone the repository.
2. Create and activate a Python 3.8+ environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:

```bash
playwright install chromium
```

5. Create a local environment file:

```bash
copy .env.example .env
```

6. Add your `OPENAI_API_KEY` to `.env` if you want live AI responses.

7. Run the app:

```bash
python app.py
```

8. Open:

```text
http://127.0.0.1:5000
```

## Environment Variables

The application reads the following optional environment variables:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `DEMO_MODE`
- `SECRET_KEY`

If `OPENAI_API_KEY` is missing, the platform automatically falls back to demo mode for AI-heavy features.

## Notes

- The runtime SQLite file is intentionally ignored via `.gitignore`.
- The root `app.py` is a thin launcher so `python app.py` continues to work after the backend package refactor.
- Flask templates and static assets remain at the repository root for standard Flask conventions.
