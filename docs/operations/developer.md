# 🔵 운영 Runbook (Developer)

> Phase 1 deployment 완료. 운영 일상·모니터링·변경관리·인시던트 대응.

생성: 2026-05-11

---

## TL;DR

```powershell
# 상태 확인
gh run list --workflow="Daily US Index Report" --limit 10
gh run view <run-id> --log

# 일정 변경 (예: KST 07)
# .github/workflows/daily_report.yml 의 cron 수정 후
git commit -am "chore(cron): KST 06 -> 07"
git push

# 일시 정지
gh workflow disable "Daily US Index Report"
gh workflow enable "Daily US Index Report"

# Webhook 회전
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/..."
```

---

## 1. 운영 상태 SLA

| 지표 | 목표 | 현재 측정값 |
|---|---|---|
| 도착 윈도우 | KST 06:00 ± 30 min | 첫 수동 검증 OK / D+1 자동 검증 대기 |
| 평일 30일 도착률 | ≥ 95% (28/30) | 운영 후 측정 (Plan SC-1) |
| 단일 실행 시간 | ≤ 60s | ~10–60s 범위 |
| 코드 정확도 | 100% | yfinance 데이터 일치 (Plan SC-2) |
| Secrets 노출 | 0건 | 정적 스캔 통과 (Plan SC-4) |

GitHub Actions free tier `schedule` cron은 **5–15분 jitter**가 정상. 06:00–06:30 KST 윈도우를 SLA로 합의.

## 2. Cron Schedule

`.github/workflows/daily_report.yml`:

```yaml
on:
  schedule:
    - cron: '0 21 * * *'   # UTC 21:00 = KST 06:00 (KST는 DST 미적용)
  workflow_dispatch: {}
```

### 2.1 시간 변경 매트릭스

| KST | UTC (전날) | cron |
|---|---|---|
| 06:00 (현재) | 21:00 | `'0 21 * * *'` |
| 06:30 | 21:30 | `'30 21 * * *'` |
| 07:00 | 22:00 | `'0 22 * * *'` |
| 08:00 | 23:00 | `'0 23 * * *'` |
| 평일만 (KST 평일=월–금 발송) | UTC 21:00 일–목 → KST 06:00 월–금 | `'0 21 * * 0-4'` |
| 평일만 (KST 화–토 발송) | UTC 21:00 월–금 → KST 06:00 화–토 | `'0 21 * * 1-5'` |

> ⚠️ cron의 요일 부분은 **UTC 기준**이라 KST와 1일 시프트가 일어남에 주의. 한국 월요일 발송하려면 일요일 UTC를 골라야.

### 2.2 변경 절차

```powershell
# 1. yml 편집
# 2. push
git add .github/workflows/daily_report.yml
git commit -m "chore(cron): change schedule to KST 07"
git push

# 3. 새 cron 적용 확인 (다음 firing이 새 시각에 잡혔는지)
gh workflow view "Daily US Index Report"
```

GitHub은 cron 수정 후 **다음 자연 시각부터** 새 일정 적용. 즉시 1회 실행은 별도 `workflow_dispatch` 필요.

### 2.3 Free tier idle 정지 주의

GitHub은 **60일 이상 push 활동이 없는 repo는 schedule cron을 자동 비활성화**한다. 활성 유지 방법:
- 정기적 commit (문서 한 줄 변경이라도)
- 또는 별도 workflow에서 `gh workflow run` 호출

## 3. 모니터링

### 3.1 빠른 헬스 체크

```powershell
# 최근 10회 실행 (status / conclusion / 시각)
gh run list --workflow="Daily US Index Report" --limit 10

# 가장 최근 실행 상세
gh run view --log

# 실패한 단계만 보기
gh run view --log-failed

# JSON으로 (스크립트화)
gh run list --workflow="Daily US Index Report" --limit 30 --json status,conclusion,createdAt,databaseId
```

### 3.2 외부 모니터링 옵션 (선택)

- **Healthchecks.io**: cron healthcheck. main.py 끝에 ping URL POST 추가 → 도착하지 않으면 이메일/슬랙 알림
- **UptimeRobot / Better Uptime**: Slack 채널 모니터링은 어려우니 Healthchecks 권장
- **GitHub Actions 자체 알림**: Settings → Notifications → "Send notifications for failed workflows only"

### 3.3 도착 시각 분포 분석 (운영 7일 후)

```powershell
gh run list --workflow="Daily US Index Report" --limit 30 --json createdAt,conclusion `
  | ConvertFrom-Json `
  | Where-Object { $_.conclusion -eq "success" } `
  | ForEach-Object {
      $utc = [datetime]::Parse($_.createdAt).ToUniversalTime()
      $kst = $utc.AddHours(9)
      [PSCustomObject]@{ KST = $kst.ToString("yyyy-MM-dd HH:mm"); Delay = ($kst.TimeOfDay - [TimeSpan]::Parse("06:00")).TotalMinutes }
  }
```

평균 지연 + 표준편차로 SLA 검증.

## 4. 변경 관리

### 4.1 Ticker 추가/변경

`config.py`:

```python
TICKERS: list[tuple[str, str]] = [
    ("^IXIC", "나스닥"),
    ("^GSPC", "S&P 500"),
    ("^DJI",  "다우"),         # 추가
    ("^RUT",  "러셀 2000"),    # 추가
    ("^VIX",  "변동성지수"),    # 추가
]
```

배포 전 로컬 검증:

```powershell
$env:SLACK_WEBHOOK_URL = "<test webhook>"
python main.py
# 메시지가 5줄로 늘어나는지 확인
```

### 4.2 메시지 포맷 변경

`main.py:_format_quote_line()` + `build_message()` 수정. 변경 전 단위 테스트 추가/갱신:

```powershell
pytest tests/test_main.py -v
```

회귀 테스트가 깨지면 그 자체로 변경 영향 가시화.

### 4.3 Webhook URL 회전

```powershell
gh secret set SLACK_WEBHOOK_URL --body "https://hooks.slack.com/services/..."
gh workflow run "Daily US Index Report"   # 즉시 검증
```

기존 Webhook은 슬랙 App 페이지에서 삭제 가능 (revoke).

## 5. 일시 정지 / 재개 / 종료

| 시나리오 | CLI | 웹 UI |
|---|---|---|
| 일시 정지 | `gh workflow disable "Daily US Index Report"` | Actions → 워크플로우 → ··· → Disable |
| 재개 | `gh workflow enable "Daily US Index Report"` | 같은 자리 → Enable |
| 워크플로우만 영구 삭제 | `Remove-Item .github\workflows\daily_report.yml; git commit -am "chore: end auto report"; git push` | yml 파일 삭제 + push |
| Repo 통째 삭제 | `gh repo delete jooladen/morning_us_index --yes` | Settings → Danger Zone → Delete |

## 6. Incident Response

### 6.1 메시지 미도착 진단 트리

```
도착 안 함
  ├─ Actions 탭에서 실행 기록 있음?
  │  ├─ Yes → conclusion 확인
  │  │   ├─ success → Slack 측 문제
  │  │   │   ├─ Webhook revoke됨? → 재발급 + secret 갱신
  │  │   │   ├─ 채널 archive됨? → 새 webhook 발급
  │  │   │   └─ 슬랙 알림 무음 모드?
  │  │   └─ failure → log 분석
  │  │       ├─ yfinance 에러 → Yahoo 일시 장애. 24h 대기 또는 즉시 rerun
  │  │       ├─ Slack HTTP 4xx → secret 점검
  │  │       └─ Python 에러 → 코드 변경 후 회귀
  │  └─ No → cron 멈춤
  │      ├─ 60일 idle → 더미 commit으로 활성화
  │      ├─ Workflow disabled → enable
  │      └─ Actions 비활성화 (repo) → Settings → Actions → Allow all
```

### 6.2 흔한 에러와 해결

| 에러 메시지 | 원인 | 해결 |
|---|---|---|
| `SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다` | Secret 미등록 또는 이름 오타 | `gh secret list` → `gh secret set SLACK_WEBHOOK_URL --body "..."` |
| `Slack 발송 실패 (재시도 무의미, HTTP 400)` | Webhook URL 손상 또는 payload 오류 | URL 재발급 + secret 갱신 |
| `Slack 발송 실패 (재시도 무의미, HTTP 403)` | Webhook revoke됨 (workspace에서 삭제) | 슬랙 App 페이지에서 webhook 재발급 |
| `Slack 발송 실패 (재시도 무의미, HTTP 404)` | Webhook URL 자체가 무효 | 재발급 |
| `yfinance 데이터 부족` (df < 2) | Yahoo 일시 장애 또는 ticker 오타 | `gh run rerun <id>` 후에도 지속이면 yfinance issue tracker 확인 |
| `Slack 발송 실패 (3회 재시도 후): HTTP 5xx` | Slack 측 일시 장애 | 1회 manual trigger로 재시도 |
| `Action timeout (5 min)` | network hang 등 극드문 케이스 | yml의 `timeout-minutes` 늘림 (현재 5) |

### 6.3 Manual rerun

```powershell
# 가장 최근 run 재실행
gh run rerun

# 특정 run-id
gh run rerun 12345678901

# 실패한 jobs만
gh run rerun 12345678901 --failed
```

## 7. 비용

| 항목 | 한도 | 우리 사용량 | 비고 |
|---|---|---|---|
| GitHub Actions (public) | 무제한 | ~30 min/월 | Public repo는 과금 0 |
| GitHub Actions (private) | 2,000 min/월 free | (해당 시 ~30 min) | 1.5% 사용 |
| GitHub Storage | 500 MB free | ~1 MB | 무시 가능 |
| Slack Workspace | 무료 플랜 | — | 메시지 90일 보존 (Free) |
| Yahoo Finance | 비공식 무료 | — | 합리적 빈도 (1일 2회 호출) |

추가 비용 발생 트리거: private repo로 전환 후 사용량 ≥ 2,000 min/월 (현실적으로 매우 낮음).

## 8. 보안 운영

```powershell
# 1) Webhook URL이 git history에 새지 않았는지
git log -p --all | Select-String -Pattern "hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+" -CaseSensitive
# 0 hits expected

# 2) .env 트래킹 여부
git ls-files | Select-String "^\.env$"
# empty expected

# 3) Secret 목록
gh secret list
# Should only contain: SLACK_WEBHOOK_URL

# 4) Actions 권한
gh api repos/jooladen/morning_us_index/actions/permissions
```

Webhook URL 노출 의심 시 **즉시**:
1. 슬랙 App 페이지에서 webhook 삭제 (revoke)
2. 새 webhook 발급
3. `gh secret set SLACK_WEBHOOK_URL` 갱신
4. `git filter-repo` 또는 BFG로 history rewrite (필요 시)

## 9. Phase 2 마이그레이션 준비

`build_message(quotes, extra_blocks=None)` 시그니처가 이미 Phase 2 ready. 추가 변경 사항:

| 파일 | 변경 |
|---|---|
| `requirements.txt` | `+google-genai` 또는 `+anthropic`, `+feedparser` 또는 `+newsapi-python` |
| `config.py` | `+ load_gemini_api_key()` 또는 `+ load_anthropic_api_key()` |
| 신규 모듈 | `news.py`(헤드라인 수집), `briefing.py`(AI 호출) |
| `main.py:main()` | `news = fetch_news(); briefing = build_briefing(news, quotes); message = build_message(quotes, extra_blocks=[briefing])` |
| `daily_report.yml:env` | `+ GEMINI_API_KEY` 또는 `+ ANTHROPIC_API_KEY` |
| 새 PDCA | `/pdca pm morning-us-index-ai` |

## 10. References

- yfinance: https://github.com/ranaroussi/yfinance
- Slack Incoming Webhooks: https://api.slack.com/messaging/webhooks
- GitHub Actions schedule cron: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- gh CLI: https://cli.github.com/manual/
- Cron syntax check: https://crontab.guru/
- 본 프로젝트:
  - Plan: `docs/01-plan/features/morning-us-index.plan.md`
  - Design: `docs/02-design/features/morning-us-index.design.md`
  - Analysis: `docs/03-analysis/morning-us-index.analysis.md`
  - 배포 Runbook: `docs/getting-started/developer.md`
