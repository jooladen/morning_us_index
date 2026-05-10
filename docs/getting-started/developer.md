# 🔵 morning-us-index Deploy Runbook (Developer)

> Phase 1 운영 배포. ~30분.

---

## TL;DR

```powershell
# 0. Local sanity (1 min)
cd C:\Users\jooladen\Desktop\stock\morning_us_index
pip install -r requirements.txt pytest
pytest                                            # 16 passed expected
pytest -m integration                             # 1 passed (yfinance live)

# 1. Slack Webhook (manual, 5 min)
# https://api.slack.com/apps → Create App (from scratch) →
# Incoming Webhooks ON → Add New Webhook to Workspace → copy URL

# 2. GitHub repo + push (5 min)
gh auth login
gh repo create morning-us-index --public --source . --push

# 3. Secrets (1 min)
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/..."
# or via web: Settings → Secrets and variables → Actions → New repository secret

# 4. Manual trigger validation (1 min)
gh workflow run "Daily US Index Report"
gh run list --workflow="Daily US Index Report" --limit 1
gh run view --log

# 5. Wait for D+1 cron (~06:00–06:30 KST) → check Slack channel
```

---

## Prerequisites

| Item | Version | Check |
|---|---|---|
| Python | 3.10+ | `python --version` |
| Git | 2.x | `git --version` |
| GitHub CLI (optional, recommended) | 2.x | `gh --version` |
| Slack workspace | with admin or app-create permission | — |
| GitHub account | — | — |

> Python 3.10 local OK; CI uses 3.11 per `daily_report.yml`. `zoneinfo` is stdlib in 3.9+; no `tzdata` package required on `ubuntu-latest`.

---

## Step 1 — Local Verification

### 1.1 Unit + integration tests

```powershell
cd C:\Users\jooladen\Desktop\stock\morning_us_index
pip install -r requirements.txt
pip install pytest

# Default: deselect integration markers (no network)
pytest                                            # → 16 passed
pytest -v                                         # verbose

# Integration only (live yfinance call)
pytest -m integration                             # → 1 passed

# All
pytest -m "integration or not integration"        # → 17 passed
```

### 1.2 Manual end-to-end (optional)

Requires Webhook URL from Step 2. After obtaining it:

```powershell
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/T.../B.../..."
python main.py
# stdout: [OK] morning-us-index 발송 완료
# Slack: message in target channel
```

To test the failure path (best-effort error notification):

```powershell
# Force a failure by breaking a ticker symbol
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."
python -c "from config import TICKERS; print(TICKERS)"
# Then temporarily edit TICKERS to include "^INVALID_TICKER" and run main.py
# Expect: stderr error log + Slack error message + exit 1
```

---

## Step 2 — Slack Incoming Webhook

1. https://api.slack.com/apps → **Create New App** → **From scratch**
2. Name: `morning-us-index`, Workspace: target
3. **Features → Incoming Webhooks** → toggle **On**
4. **Add New Webhook to Workspace** → select channel → **Allow**
5. Copy the URL: `https://hooks.slack.com/services/T<team>/B<bot>/<token>`

Webhook URL acts as a bearer token. Treat as secret. Rotation: regenerate by removing and adding the webhook in the same Slack App page.

---

## Step 3 — GitHub Repository

### 3.1 With `gh` (recommended)

```powershell
cd C:\Users\jooladen\Desktop\stock\morning_us_index
gh auth login                                     # one-time
gh repo create morning-us-index --public --source . --push
```

### 3.2 Without `gh`

```powershell
# https://github.com/new → name: morning-us-index → Public → no README/gitignore/license
cd C:\Users\jooladen\Desktop\stock\morning_us_index
git init
git add .
git commit -m "init: morning-us-index Phase 1"
git branch -M main
git remote add origin https://github.com/<user>/morning-us-index.git
git push -u origin main
```

### 3.3 Verify push

```powershell
git log --oneline                                 # 1 commit
git ls-remote                                     # remote refs visible
```

GitHub web should show 9 files: `main.py`, `config.py`, `requirements.txt`, `.gitignore`, `pytest.ini`, `tests/`, `.github/`, `README.md`, `docs/`.

---

## Step 4 — Secrets Registration

### 4.1 With `gh`

```powershell
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/T.../B.../..."

# verify
gh secret list                                    # SLACK_WEBHOOK_URL  Updated YYYY-MM-DD
```

### 4.2 Via web

```
Repo → Settings → Secrets and variables → Actions → New repository secret
  Name: SLACK_WEBHOOK_URL
  Secret: <full URL>
→ Add secret
```

### 4.3 Sanity — confirm secret is referenced

`grep` the workflow:

```powershell
Select-String -Path .github/workflows/daily_report.yml -Pattern "SLACK_WEBHOOK_URL"
# Expected: env line + secrets.SLACK_WEBHOOK_URL reference
```

---

## Step 5 — Manual Trigger (workflow_dispatch)

### 5.1 With `gh`

```powershell
gh workflow run "Daily US Index Report"

# poll until completion
gh run list --workflow="Daily US Index Report" --limit 1
gh run watch                                      # interactive

# inspect logs
gh run view --log
gh run view --log-failed                          # only failed steps
```

### 5.2 Via web

`Actions` tab → **Daily US Index Report** → **Run workflow** dropdown → **Run workflow** button.

### 5.3 Success criteria

- `gh run list` shows status `completed` and conclusion `success` (green check)
- Slack channel receives message in 10–60s
- Message format: `[YYYY-MM-DD KST 06:00 발송] 직전 거래일: ... • 나스닥 ^IXIC: ...`

---

## Step 6 — D+1 Cron Validation

Wait until next 21:00 UTC (KST 06:00). Then:

```powershell
gh run list --workflow="Daily US Index Report" --limit 5
# Expect: scheduled trigger entry, conclusion: success
```

Cron jitter on free runners: ~5–15 min typical, up to 30 min in peak hours. Treat 06:00–06:30 KST as the SLA window.

---

## Operational Notes

### Cost

GitHub Actions free tier:
- Public repo: unlimited minutes
- Private repo: 2,000 min/month free (this workflow uses ~30 min/month — 1.5%)

Slack Incoming Webhook: free, no per-message cost.

### Schedule modification

Edit `.github/workflows/daily_report.yml` cron line. UTC only, no DST.

| KST target | UTC | cron |
|---|---|---|
| 06:00 (default) | 21:00 prev day | `'0 21 * * *'` |
| 07:00 | 22:00 prev day | `'0 22 * * *'` |
| Weekdays only (KST 평일) | 21:00 Tue–Sat UTC | `'0 21 * * 2-6'` |

### Logs / observability

```powershell
# Last 5 runs
gh run list --workflow="Daily US Index Report" --limit 5

# Specific run logs
gh run view <run-id> --log

# Filter to failed steps
gh run view <run-id> --log-failed
```

GitHub auto-emails the repo owner on workflow failure (if email notifications enabled in profile).

### Manual rerun on failure

```powershell
gh run rerun <run-id>
gh run rerun <run-id> --failed                    # only failed jobs
```

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---|---|---|
| `pytest` collection error | dependency missing | `pip install -r requirements.txt pytest` |
| `git push` 403 / 401 | HTTPS auth expired | `gh auth login` or generate PAT with `repo` scope |
| `gh: command not found` | CLI not installed | `winget install GitHub.cli` or use web flow |
| Workflow not appearing in Actions | Actions disabled for new public repo | Settings → Actions → General → Allow all actions |
| Workflow runs but no Slack message | secret name typo / wrong URL | `gh secret list` to confirm name; re-set with correct URL |
| Slack 400 invalid_payload | message too long or malformed JSON | Check `gh run view --log` for stderr; build_message produced unusual chars? |
| Slack 403 invalid_token | webhook deleted/regenerated | Re-issue Webhook (Step 2), re-set secret (Step 4) |
| Slack 429 rate_limited | too many manual triggers | Wait ~1 min; code's retry backoff handles transient 429 |
| yfinance returns empty DataFrame | Yahoo upstream issue | Wait, retry. Persistent → check yfinance GitHub issues |
| Cron runs at 06:25 KST not 06:00 | GH Actions free-tier cron jitter | Expected. Document as 06:00–06:30 SLA. Self-hosted runner if tighter SLA needed |
| Encoding issues in CI logs | runner default | Workflow sets `PYTHONUTF8: '1'`; main.py reconfigures stdout |
| Timezone wrong | EST/EDT confusion | KST has no DST. Cron in UTC always. `period="5d"` + `dropna()` ensures last 2 confirmed trading days |

### Reproducing CI failures locally

```powershell
# Match CI environment closely
$env:PYTHONUTF8 = "1"
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."
python main.py
```

### Debugging build_message output without sending

```powershell
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/dummy"
python -c @'
import main
quotes = main.fetch_indices()
print(main.build_message(quotes))
'@
```

---

## Security Checklist

```powershell
# .env not tracked
git ls-files | Select-String "^\.env$"            # → empty

# No webhook URL leak in history
git log -p --all | Select-String -Pattern "hooks\.slack|SLACK_WEBHOOK_URL\s*="
# → empty (no matches)

# Secrets only via GH Secrets
Select-String -Path . -Recurse -Pattern "hooks\.slack\.com" -Exclude *.md,docs\*
# → 0 hits in code (only in docs as examples)
```

---

## Phase 2 Migration Path (for later)

When AI/뉴스 features are added (separate PDCA cycle), the migration touches:

1. `requirements.txt` — add `google-genai` or `anthropic`, `feedparser`/`newsapi-python`
2. `config.py` — add `GEMINI_API_KEY` loader
3. `main.py` — add `fetch_news()` + `build_briefing()` (new module or inline)
4. `main.py:build_message(quotes, extra_blocks=...)` — pass briefing as `extra_blocks` (signature already supports this)
5. `.github/workflows/daily_report.yml` — add `GEMINI_API_KEY` env from secrets
6. New PDCA: `/pdca pm morning-us-index-ai`

The `extra_blocks` extension point in `build_message` was added in Iter 1 specifically to make this future migration touch-free for the message rendering layer.

---

## References

- yfinance: https://github.com/ranaroussi/yfinance
- Slack Incoming Webhooks: https://api.slack.com/messaging/webhooks
- GitHub Actions schedule: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- GitHub CLI: https://cli.github.com/
- Plan: `docs/01-plan/features/morning-us-index.plan.md`
- Design: `docs/02-design/features/morning-us-index.design.md`
- Analysis: `docs/03-analysis/morning-us-index.analysis.md`
