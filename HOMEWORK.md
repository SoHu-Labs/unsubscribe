# Homework — post-implementation manual steps

## 1. Verify the `cheap` alias works with your Go subscription

```bash
# Quick test — override a topic to use the cheap alias, then dry-run
# Edit topics/<your-topic>.yaml and set:
#   extract_model: cheap
#   synthesize_model: cheap

# Then:
mamba run -n email-digest python -m email_digest digest run <topic> --dry-run
```

Expected: the pipeline uses `openai/minimax-m2.5` via `https://opencode.ai/zen/go/v1` using your Go API key from `~/.local/share/opencode/auth.json`.

If it fails with auth errors, check:
- `CHEAP_API_KEY` env var or run `opencode /connect` for Go
- `CHEAP_API_BASE` default is `https://opencode.ai/zen/go/v1`
- `CHEAP_MODEL` default is `openai/minimax-m2.5`

## 2. Verify `digest walkthrough --all`

```bash
mamba run -n email-digest python -m email_digest digest walkthrough --all --dry-run
```

Wait — `--dry-run` doesn't exist for walkthrough. Use `--max-results 3` to limit scope:

```bash
mamba run -n email-digest python -m email_digest digest walkthrough --all --max-results 3
```

## 3. Verify `digest walkthrough --body`

```bash
mamba run -n email-digest python -m email_digest digest walkthrough <topic> --body --max-results 3
```

## 4. Update topics with real sender addresses

Replace `example.com` senders in `topics/*.yaml` with actual newsletter From addresses you receive.

## 5. Set up cron

Follow `scripts/digest-cron.example.sh`.
