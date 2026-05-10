# morning-us-index

매일 한국 시간 오전 6시, **나스닥 종합지수(^IXIC)** 와 **S&P 500(^GSPC)** 의 직전 거래일 종가/변동률을 슬랙으로 자동 발송합니다. GitHub Actions cron 기반이라 **본인 컴퓨터를 꺼도 항상 동작**합니다.

## 메시지 미리보기

```
[2026-05-12 KST 06:00 발송] 직전 거래일: 2026-05-09 (미 증시 휴장 / 마지막 거래일)
• 나스닥 ^IXIC: 17,234.50  ▲ +145.32 (+0.85%) 🟢
• S&P 500 ^GSPC: 5,432.10  ▼ -12.45 (-0.23%) 🔴
```

## 더 자세한 가이드

처음 셋업하시는 분은 본인 수준에 맞게 골라 보세요:

- **🟢 [초보자용 가이드](docs/getting-started/beginner.md)** — 비유로 풀어 설명, 단계별 체크리스트, 자주 막히는 곳 그림 비유
- **🔵 [개발자용 Runbook](docs/getting-started/developer.md)** — `gh` CLI 중심 copy-paste 명령어, 트러블슈팅 매트릭스, Phase 2 마이그레이션 포인트

아래는 핵심만 추린 5단계 셋업입니다.

## 빠른 셋업 (≤ 30분)

### 1. Slack Incoming Webhook URL 발급

1. https://api.slack.com/apps → **Create New App** → From scratch
2. App Name: 자유 (예: `morning-us-index`), 워크스페이스 선택
3. 좌측 **Incoming Webhooks** → 활성화 ON → **Add New Webhook to Workspace**
4. 발송할 채널 선택 → 발급된 URL 복사 (`https://hooks.slack.com/services/...`)

### 2. GitHub 저장소 생성

GitHub CLI(`gh`)가 설치돼 있으면:

```bash
gh auth login   # 처음 1회
gh repo create morning-us-index --public --source . --push
```

웹에서 만들 경우: GitHub → New repository → 이름 `morning-us-index` → Public → Create. 이후:

```bash
git init
git add .
git commit -m "init: morning-us-index Phase 1"
git branch -M main
git remote add origin https://github.com/<your-id>/morning-us-index.git
git push -u origin main
```

> **Public 권장**: GitHub Free 플랜에서 public repo는 Actions가 무제한이고, 본 워크플로우는 비밀값을 코드에 두지 않으므로 안전합니다. Private도 동작(월 2,000분 무료, 본 워크플로우는 월 ~30분 사용).

### 3. Secrets 등록

GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Name | Value |
| --- | --- |
| `SLACK_WEBHOOK_URL` | 1단계에서 발급받은 Webhook URL 전체 |

### 4. 즉시 1회 발송 테스트

GitHub repo → **Actions** 탭 → 좌측 `Daily US Index Report` → **Run workflow** (수동 실행)

10–30초 내 슬랙 채널에 메시지가 도착해야 합니다.

### 5. 자동 발송 확인 (D+1)

다음 날 KST 06:00–06:30 사이 자동 메시지 도착 여부 확인.

> GitHub Actions의 schedule cron은 5–15분 정도 지연될 수 있어 **06:00 정시가 아닌 06:00–06:30 윈도우**로 이해하면 됩니다.

## 로컬 실행 (선택)

발송 전 코드 수정 후 로컬 검증용.

### Windows (PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."
python main.py
```

### macOS / Linux (bash)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python main.py
```

성공 시 콘솔에 `[OK] morning-us-index 발송 완료` 출력 + 슬랙 메시지 도착.

## 테스트 실행

```bash
# 1) pytest 설치 (1회)
pip install pytest

# 2) 단위 테스트 (외부 API 의존 없음, 빠름)
pytest

# 3) 통합 테스트 (실제 yfinance 호출, 네트워크 필요)
pytest -m integration

# 4) 모든 테스트
pytest -m "integration or not integration"
```

기본 17개 테스트 (단위 16 + 통합 1)는 약 1초 안에 끝납니다.

## 보안 점검 (셋업 후 1회 권장)

`.env` 또는 Webhook URL이 실수로 커밋되지 않았는지 확인:

```bash
# git log 전체에서 webhook 흔적 검색 (0건이어야 정상)
git log -p --all | grep -iE "hooks\.slack|SLACK_WEBHOOK_URL[[:space:]]*=" || echo "OK: no leak"

# 트래킹 중인 .env 파일 검색 (0건이어야 정상)
git ls-files | grep -E "^\.env$" || echo "OK: .env not tracked"
```

## 일정 변경

`.github/workflows/daily_report.yml` 의 `cron` 라인 수정. 시간은 **UTC** 기준입니다.

| 원하는 시각 (KST) | UTC | cron |
| --- | --- | --- |
| 06:00 (기본) | 21:00 (전날) | `'0 21 * * *'` |
| 07:00 | 22:00 (전날) | `'0 22 * * *'` |
| 08:00 | 23:00 (전날) | `'0 23 * * *'` |
| 평일만 발송 | 21:00 화–토 | `'0 21 * * 2-6'` (UTC 기준 요일이라 한국 평일에 맞춤) |

> KST 06:00 운영 시 EST 겨울철에는 NY 증시 마감 직후라 Yahoo 데이터가 미정착일 수 있지만, 본 코드는 `period="5d"` + `dropna()` 로 항상 *확정된* 직전 거래일을 사용합니다. "직전 거래일" 라벨링으로 사용자 혼란을 방지합니다.

## 구조

```
morning_us_index/
├── main.py                              # 진입점 + 3 함수 (~150줄)
├── config.py                            # 환경변수 + 상수
├── requirements.txt                     # yfinance, requests
├── .gitignore                           # .env, __pycache__/ 제외
├── .github/workflows/daily_report.yml   # cron + secrets 주입
├── README.md                            # 본 문서
└── docs/                                # PDCA 문서 (Plan / Design)
```

## 트러블슈팅

| 증상 | 원인 후보 | 대응 |
| --- | --- | --- |
| 메시지가 도착하지 않음 | Webhook URL 오타, Secrets 미등록 | Actions 로그 확인, Secrets 재등록 |
| `SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다` | GitHub Secrets 또는 로컬 env var 미설정 | 위 3단계 확인 |
| `yfinance 데이터 부족` | Yahoo Finance 일시 장애 | `Run workflow` 수동 재실행. 며칠 지속되면 Issue |
| 06:00 정각이 아닌 06:20에 도착 | GitHub Actions cron 지연 | 정상. 06:00–06:30 윈도우로 합의 |
| 토/일 메시지에 `(미 증시 휴장 / 마지막 거래일)` 표기 | 의도된 동작 | 마지막 거래일(금요일) 종가를 발송 |
| 한글이 깨짐 (로컬 Windows) | 콘솔 코드페이지 cp949 | 코드는 UTF-8 명시. 슬랙 메시지는 항상 정상 |

## Phase 2 (예정)

뉴스 헤드라인 + AI(Gemini/Claude) 시장 해설 추가는 별도 PDCA 사이클로 진행:

```bash
# 다음 작업 시 (현재 저장소에서)
/pdca pm morning-us-index-ai
```

`build_message(quotes, extra_blocks=...)` 시그니처에 AI 블록을 끼워 넣는 방식으로 본 코드를 거의 변경하지 않고 확장 가능합니다.

## 라이선스 / 면책

- yfinance는 Yahoo Finance의 비공식 스크래핑이며 Yahoo의 정책 변경 시 동작이 중단될 수 있습니다.
- 본 도구는 **참고용 정보 제공**이 목적이며, 투자 조언이 아닙니다.
