# Campus Customs — Homework 4

A Yale-inspired merchandise storefront with a React/Vite/TypeScript front end, FastAPI API, and a PydanticAI shopping assistant. Product facts come from the supplied SQLite catalogue. Accounts use hashed passwords and server-managed sessions; signed-in customers can return to their saved conversations.

## Place the local data pack

Download the course Homework 4 data pack and extract it beside the project. The database and original product photographs stay local:

```text
working-folder/
├── data/
│   ├── campus_customs.db
│   └── products/
└── hw4/
    ├── backend/
    ├── frontend/
    └── output/
```

Use Python 3.11 or newer on macOS or Linux and Node.js 20.19+ or 22.12+. The audit writer uses Unix file locking. Open a terminal in hw4:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set your private PORTKEY_API_KEY in .env. The default course model is gpt-5.6-luna through https://api.portkey.ai/v1. The example configuration documents the available settings. Never commit the real .env or data pack.

## Start the backend

With the virtual environment active, run:

```bash
cd backend
uvicorn main:app --reload --port 8000
```

## Start the frontend

In a second terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. Vite proxies /api and /media to port 8000 so the browser can use same-origin session cookies. Keep both services running. Catalogue browsing and authentication work without a model key; chat requires a valid provider key and network access.

The supplied test account is test@campuscustoms.yale.edu with password password. Create an account to try a separate saved conversation. These are course data and a local coursework app; no payment or checkout flow is implemented.

## Review the evidence

- output/app_check.html: double-clickable screenshots and captions from the running app.
- output/harness.md: actual database fields, agent tools/models, auth, history, safety, and limits.
- output/usability.md and output/design.md: implemented usability and design choices.
- output/audit_trail.json: retained, redacted agent activity across runs.
- AI_prompts.md: the assignment request and four prepared working prompts for each of thirteen problems; the sequences are not a reconstructed transcript of separately typed messages.
- REQUIREMENTS_REVIEW.md: per-problem completion evidence and remaining publication/submission steps.

## Verify

```bash
python -m pytest backend/tests -q
python validate_submission.py --data-dir ../data
cd frontend
npm run build
```

The backend tests use temporary copies of the supplied data instead of overwriting the working database. The validator does not make model calls or submit anything to Canvas.

## Public repository and Canvas

Commit the hw4 code and required evidence. .gitignore excludes environment secrets, databases, original merchandise images, dependencies, and local builds. Required app screenshots are included as assignment evidence. Place the data pack separately after cloning.

Homework 4 requires a public GitHub repository URL submitted on Canvas, not a ZIP upload. The local app and evidence do not establish publication or Canvas submission. See REQUIREMENTS_REVIEW.md for the currently verified status.
