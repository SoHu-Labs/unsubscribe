# email-digest

Two email tools sharing one Gmail API backend:

- **unsubscribe** — automate unsubscribing from newsletters
- **digest** — topic-oriented email summaries with LLM synthesis and trending detection (in progress)

## Setup

```bash
mamba env create -f environment.yml
mamba activate email-digest
pip install -e ".[dev]"
```

## Credentials

| What | Env var | Notes |
|---|---|---|
| Google OAuth token (Gmail readonly) | `GOOGLE_OAUTH_TOKEN` | Path to token file |
| DeepSeek API key | `DEEPSEEK_API_KEY` | For digest LLM extraction/synthesis |
| LM Studio base URL | `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` (optional local fallback) |

## CLI

```
# Unsubscribe
python -m email_digest unsubscribe              # same as `unsubscribe check`
python -m email_digest unsubscribe check [-d DAYS]

# Digest (in progress)
python -m email_digest digest run ai
python -m email_digest digest run --all
python -m email_digest digest run ai --dry-run
python -m email_digest digest cost
```

## Docs

- `docs/PROJECT_BRIEF_EMAIL_SUMMARIES.md` — digest engine project brief
- `docs/PLAN.md` — implementation plan
- `docs/INVENTORY.md` — code inventory
