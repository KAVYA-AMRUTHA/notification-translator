# Notification Translator

Turn notification noise into clear actions.

## Problem

People receive too many notifications from too many apps. The problem isn't
that notifications are hard to *read* — it's that it's hard to tell **which
ones actually deserve your attention**.

## Solution

Notification Translator is an AI agent that takes a batch of pasted
notifications and translates them into an attention-focused feed. For each
notification it decides:

- What is it about?
- Does the user need to do anything?
- How urgent is it?
- What action should be taken?
- Is there a deadline?
- Why does it deserve (or not deserve) attention?

It's not a summarizer — it's a triage/decision agent that reasons about the
*meaning and consequence* of each notification, then sorts them into:

`ACTION_REQUIRED` → `IMPORTANT` → `INFORMATIONAL` → `LOW_PRIORITY` → `IGNORE`

## How the AI agent works

Each notification is run through a small [LangGraph](https://github.com/langchain-ai/langgraph)
state graph, using Google Gemini as the reasoning model and Pydantic to
validate the model's structured output.

## Agent workflow

```
START
  ↓
normalize            – split "Source: message" and clean the text
  ↓
understand_intent    – single LLM call; asks Gemini to reason about the
                        notification and return a structured JSON object
  ↓
determine_attention  – parse/repair the model's JSON output
  ↓
determine_urgency    – guard-rail: coerce category/urgency into a known enum
  ↓
extract_action_deadline – normalize action/deadline fields
  ↓
generate_explanation – fill in summary/reason defaults if missing
  ↓
validate_output      – validate against the NotificationAnalysis Pydantic
                        model; falls back to a safe, deterministic
                        "informational/low" result if anything is invalid
  ↓
END
```

If Gemini is unavailable, returns malformed output, or `GEMINI_API_KEY` is
not configured, the agent degrades gracefully to a safe fallback
classification instead of crashing — the app never exposes a raw error or
stack trace to the user.

## Technology stack

**Backend:** Python, FastAPI, LangChain, LangGraph, Google Gemini API, Pydantic
**Frontend:** plain HTML, CSS, JavaScript (no frameworks) — one responsive
page that works on desktop and mobile browsers, no installation required.

## Project structure

```
notification-translator/
│
├── app/
│   ├── main.py                        # FastAPI app, routes
│   ├── agents/notification_agent.py   # LangGraph workflow
│   ├── models/notification.py         # Pydantic request/response models
│   ├── prompts/notification_prompt.py # LLM prompt templates
│   └── services/analyzer.py           # Wires up Gemini + runs the graph
│
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── tests/
│   └── test_api.py
│
├── requirements.txt
├── .env.example
├── .gitignore
├── render.yaml
└── README.md
```

## Local setup

```bash
git clone <this-repo-url>
cd notification-translator
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY
```

## Environment variables

| Variable         | Required | Description                                   |
|------------------|----------|------------------------------------------------|
| `GEMINI_API_KEY` | Yes*     | Your Google Gemini API key.                    |

\* Without it, the app still runs and serves the UI/API, but falls back to a
safe deterministic "informational" classification instead of using AI —
this keeps local development and CI usable without a key, but it is **not**
a substitute for configuring a real key for actual use.

## Running locally

```bash
uvicorn app.main:app --reload
```

Then open `http://localhost:8000` in a browser (desktop or mobile viewport).

## Running tests

```bash
pip install pytest httpx
pytest tests/ -v
```

## API endpoints

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /api/analyze`

Request:

```json
{
  "notifications": [
    "GitHub: You were assigned issue #42 in repository Espial.",
    "Amazon: Your package will arrive tomorrow.",
    "Instagram: Someone liked your post."
  ]
}
```

Response:

```json
{
  "total": 3,
  "results": [
    {
      "source": "GitHub",
      "original_text": "GitHub: You were assigned issue #42 in repository Espial.",
      "category": "ACTION_REQUIRED",
      "urgency": "HIGH",
      "requires_action": true,
      "action": "Review and respond to issue #42.",
      "deadline": null,
      "summary": "You've been assigned a GitHub issue to work on.",
      "reason": "A task has been directly assigned to you."
    }
  ]
}
```

## Render deployment

This repo includes a `render.yaml` (Render "Blueprint") that:

- installs dependencies with `pip install -r requirements.txt`
- starts the app with `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- expects a `GEMINI_API_KEY` environment variable to be set in the Render
  dashboard (never committed to the repo)

The frontend is served directly from the FastAPI app at `/`, so the deployed
Render URL is the whole application — no separate hosting needed.

## Privacy considerations

- The app is **stateless**: notification text is only held in memory for the
  duration of a single request and is never written to a database or disk.
- No authentication, accounts, or persistent storage of any kind.
- The Gemini API key is read from environment variables on the backend only
  and is never sent to, or exposed in, the frontend JavaScript.
