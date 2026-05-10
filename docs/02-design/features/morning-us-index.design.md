---
name: morning-us-index
type: design
version: 0.1.0
status: draft
phase: design
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
plan: docs/01-plan/features/morning-us-index.plan.md
architecture: option-c-pragmatic-balance
---

# Design — morning-us-index

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 컴퓨터를 꺼도 항상 동작하는 미 증시 일일 종가 알림 (Phase 1=숫자만, Phase 2=AI/뉴스) |
| **WHO** | 단일 사용자(준), 본인 슬랙 채널 1개 |
| **RISK** | yfinance 장애 / Actions cron 5–15분 지연 / 휴장일 처리 / Webhook 노출 |
| **SUCCESS** | 평일 KST 06:00±30분 도착률 ≥ 95%, 정확도 100%, Secrets 노출 0건 |
| **SCOPE** | Phase 1만: ^IXIC + ^GSPC → Slack |

## 1. Overview

Plan에서 확정한 Phase 1을 **Option C — Pragmatic Balance** 아키텍처로 구현한다.

핵심: `main.py` 한 파일에 **3개의 순수 함수**(`fetch_indices`, `build_message`, `post_slack`) + `main()` 오케스트레이터, 환경변수/상수만 `config.py`로 분리. GitHub Actions cron이 `main.py`를 호출한다. Phase 2(AI/뉴스) 진입 시 `build_message()`의 시그니처에 `extra_blocks` 인자 1개만 추가하면 새 모듈이 슬롯인 형태로 들어간다.

## 2. Goals & Non-Goals (요약)

Plan §3을 그대로 따른다. 이 문서에서 새로 결정하는 것:

| Open Q (Plan §11) | 결정 |
|---|---|
| OQ-2 — 메시지 언어 | **영문 ticker + 한글 라벨 혼용** (예: `나스닥 ^IXIC`, `S&P 500 ^GSPC`). 숫자/% 표기는 영문 콤마/% |
| OQ-3 — 한국 공휴일 발송 | **그대로 발송**. KST 한국 공휴일이라도 미 증시 데이터는 의미 있음 |
| OQ-4 — KST 06:00 vs 07:00 | **KST 06:00 유지** (UTC 21:00). 데이터 안정성은 §6 데이터 흐름의 `period="5d"` + `dropna()` 패턴으로 해결. 단 EST 겨울철에는 메시지 도착 시점에 NY 16:00 정시라 yfinance 캔들이 미정착일 수 있어 `[-1]` 행 날짜를 그대로 라벨링하여 "직전 거래일" 의미를 보존 |
| OQ-5 — Repo visibility | **Public 권장** (Actions 무제한, 코드 자체에 비밀값 없음). private도 가능(2,000분/월 한도 충분) |
| OQ-1 — 채널 멘션 | **멘션 없음**. 매일 노이즈를 줄이기 위해 `@here`/`@channel` 미사용 |

## 3. Architecture Overview (Option C)

```
┌──────────────────────────────────────────────────────────────┐
│  GitHub Actions (cron: '0 21 * * *')                         │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Ubuntu runner                                        │    │
│  │  ┌────────────┐                                       │    │
│  │  │  python    │  ── reads env: SLACK_WEBHOOK_URL ──┐  │    │
│  │  │  main.py   │                                    │  │    │
│  │  └─────┬──────┘                                    │  │    │
│  │        │                                            │  │    │
│  │  ┌─────▼──────────┐                                │  │    │
│  │  │ fetch_indices()│ ── HTTPS ──► Yahoo Finance      │  │    │
│  │  │  (yfinance)    │ ◄── DataFrame──                 │  │    │
│  │  └─────┬──────────┘                                │  │    │
│  │        ▼                                            │  │    │
│  │  ┌─────────────────┐                               │  │    │
│  │  │ build_message() │  ── pure function ──          │  │    │
│  │  │  (str builder)  │                               │  │    │
│  │  └─────┬───────────┘                               │  │    │
│  │        ▼                                            │  │    │
│  │  ┌─────────────────┐         POST JSON              │  │    │
│  │  │ post_slack()    │ ──────────────────────► Slack  │  │    │
│  │  │  (requests +    │  webhook URL ◄──────────┘     │  │    │
│  │  │   retry)        │                                │  │    │
│  │  └─────────────────┘                                │  │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### 3.1 Phase 2 확장 지점

```python
# Phase 1 (지금)
build_message(idx_data: list[IndexQuote]) -> str

# Phase 2 (AI/뉴스 추가 시)
build_message(idx_data: list[IndexQuote],
              extra_blocks: list[str] | None = None) -> str
```

`extra_blocks`에 AI 브리핑/뉴스 요약 마크다운을 끼워 넣기만 하면 됨. 메시지 본문 골격은 변하지 않음.

## 4. Module Design

### 4.1 파일 구조

```
morning_us_index/
├── main.py                       ← 진입점 + 3 함수 + main()
├── config.py                     ← 환경변수 + 상수
├── requirements.txt              ← 의존성 (yfinance, requests)
├── .github/
│   └── workflows/
│       └── daily_report.yml      ← cron + secrets 주입
├── README.md                     ← 셋업 가이드 (gh repo create 포함)
├── .gitignore                    ← .env, __pycache__/, *.pyc 제외
└── docs/                         ← PDCA 문서 (이미 존재)
    ├── 01-plan/features/morning-us-index.plan.md
    └── 02-design/features/morning-us-index.design.md
```

### 4.2 함수 시그니처 (계약)

#### `config.py`

```python
# 상수
TICKERS: list[tuple[str, str]] = [
    ("^IXIC", "나스닥"),
    ("^GSPC", "S&P 500"),
]
TIMEZONE_KST = "Asia/Seoul"
YFINANCE_PERIOD = "5d"
# (connect, read) timeout 분리 — requests 공식 권장 패턴.
# connect는 짧게(서버 응답 시작까지), read는 본문 수신까지 별도 한도.
HTTP_CONNECT_TIMEOUT_SEC = 5
HTTP_READ_TIMEOUT_SEC = 15
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SEC = [30, 60, 120]
STALE_THRESHOLD_DAYS = 2

# 환경변수 로딩
def load_slack_webhook_url() -> str:
    """SLACK_WEBHOOK_URL 환경변수를 읽어 반환. 미설정/공백 시 RuntimeError."""
```

#### `main.py`

```python
@dataclass(frozen=True)
class IndexQuote:
    ticker: str            # "^IXIC"
    label: str             # "나스닥"
    last_close: float      # 17234.50
    prev_close: float      # 17089.18
    last_date: date        # 마지막 거래일 (datetime.date)
    is_stale: bool         # 발송 시점 기준 2일 이상 과거이면 True (휴장 표시용)

def fetch_indices() -> list[IndexQuote]:
    """
    yfinance로 TICKERS의 직전 거래일 종가/전일 종가를 조회.
    - period="5d"로 5거래일치 가져온 뒤 dropna() 후 마지막 2행 사용
    - is_stale: today_kst - last_date >= 2일이면 True
    Raises:
        RuntimeError: 데이터 부족(2거래일 미만)
    """

def build_message(
    quotes: list[IndexQuote],
    extra_blocks: list[str] | None = None,
) -> str:
    """
    Slack 마크다운 메시지 본문 빌드. 순수 함수 (외부 호출 없음).
    Phase 1에서 ``extra_blocks=None`` 으로 동작.
    Phase 2(AI/뉴스)에서는 마크다운 블록 리스트를 전달하여 헤더/지수 라인
    뒤에 부가 (Plan NFR-06).
    """

def post_slack(webhook_url: str, message: str) -> None:
    """
    Slack Incoming Webhook으로 POST. 3회 지수 백오프 재시도.
    Raises:
        RuntimeError: 최종 실패 시
    """

def main() -> int:
    """
    오케스트레이터: fetch → build → post.
    실패 시 stderr 로그 + 가능하면 슬랙 에러 메시지 + non-zero exit code.
    Returns: 0 성공, 1 실패
    """
```

### 4.3 메시지 포맷 (FR-04 결정판)

**평상시 (직전 거래일이 1일 이내)**:

```
[2026-05-11 KST 06:00 발송] 직전 거래일: 2026-05-10
• 나스닥 ^IXIC: 17,234.50  ▲ +145.32 (+0.85%) 🟢
• S&P 500 ^GSPC: 5,432.10  ▼ −12.45 (−0.23%) 🔴
```

**휴장 다음 날 (직전 거래일이 2일 이상 과거)**:

```
[2026-05-12 KST 06:00 발송] 직전 거래일: 2026-05-09 (미 증시 휴장 / 마지막 거래일)
• 나스닥 ^IXIC: 17,234.50  ▲ +145.32 (+0.85%) 🟢
• S&P 500 ^GSPC: 5,432.10  ▼ −12.45 (−0.23%) 🔴
```

**규칙**:
- 변동률 양수 → `▲` + `🟢`, 음수 → `▼` + `🔴`, 0 → `■` + `⚪`
- 종가는 천단위 콤마, 소수점 2자리
- 변동값(절대)은 부호(+/−), 소수점 2자리
- 변동률은 부호(+/−), 소수점 2자리, `%` 부호
- 음수 부호는 minus sign(`−`, U+2212) 대신 ASCII `-`도 무방 (가독성 우선이면 `−`)
- Slack `text` 필드 단일 문자열로 발송 (Block Kit 미사용 — 단순성)

## 5. Data Model

### 5.1 yfinance 응답 → IndexQuote 변환

```python
import yfinance as yf

ticker = yf.Ticker("^IXIC")
df = ticker.history(period="5d")  # DataFrame: Open, High, Low, Close, Volume, ...
df = df.dropna(subset=["Close"])
# df.index는 DatetimeIndex (US/Eastern timezone-aware)

last_row = df.iloc[-1]   # 직전 거래일
prev_row = df.iloc[-2]   # 그 이전 거래일

last_close = float(last_row["Close"])
prev_close = float(prev_row["Close"])
last_date  = df.index[-1].date()   # date 타입
```

### 5.2 변동값/변동률 계산

```python
delta = last_close - prev_close                  # 절대 포인트
pct   = (delta / prev_close) * 100               # 백분율
```

### 5.3 휴장 판단

```python
from datetime import datetime
from zoneinfo import ZoneInfo

now_kst = datetime.now(ZoneInfo(TIMEZONE_KST)).date()
is_stale = (now_kst - last_date).days >= 2
```

> **참고**: `last_date`는 NY/ET 기준 거래일 날짜이고 `now_kst`는 KST 기준. 두 timezone 차이가 14h이지만 `date()` 비교에서 1일 정도의 오프셋은 정상이며, "2일 이상" 임계로 휴장만 정확히 잡힌다. 토 → 월 KST 06시: NY 금요일 종가까지 약 1~2일 → is_stale=False/True 경계. 토요일·일요일 KST 06시 발송에서는 last_date가 금요일이라 일요일 KST 06시 발송에서는 `(일 - 금) = 2일` → is_stale=True ✓.

## 6. Data Flow / Sequence

```
[Cron 21:00 UTC]
      │
      ▼
[Runner: ubuntu-latest]
      │
      ▼
[git checkout + pip install -r requirements.txt]
      │
      ▼
[python main.py]
      │
      ▼
  ┌───────────────────────────────────┐
  │ main()                             │
  │  │                                 │
  │  ├─► fetch_indices()              │
  │  │     │                           │
  │  │     ├─► yf.Ticker("^IXIC")     │
  │  │     │     .history(period=5d)  │  ◄── 실패 시 RuntimeError
  │  │     │                           │
  │  │     ├─► yf.Ticker("^GSPC")     │
  │  │     │     .history(period=5d)  │
  │  │     │                           │
  │  │     └─► [IndexQuote, IndexQuote]│
  │  │                                 │
  │  ├─► build_message(quotes)        │  ◄── pure, no I/O
  │  │     └─► str (slack markdown)   │
  │  │                                 │
  │  ├─► post_slack(url, message)     │  ◄── 실패 시 retry x3
  │  │     │                           │
  │  │     └─► requests.post(...)     │
  │  │                                 │
  │  └─► return 0 (성공)              │
  │                                    │
  │  (예외 발생 시)                    │
  │  ├─► except → stderr 로그          │
  │  ├─► best-effort post_slack(에러)  │
  │  └─► return 1                      │
  └───────────────────────────────────┘
      │
      ▼
[exit code 0/1 → Action 성공/실패]
      │
      ▼
[실패 시 GitHub이 사용자에게 이메일 자동 통지]
```

## 7. Configuration & Secrets

### 7.1 환경변수 (런타임)

| 이름 | 출처 | 용도 | 필수 |
|---|---|---|---|
| `SLACK_WEBHOOK_URL` | GitHub Secrets | 슬랙 발송 대상 | ✅ |

### 7.2 GitHub Secrets 등록

```
Repo Settings → Secrets and variables → Actions → New repository secret
  Name: SLACK_WEBHOOK_URL
  Value: https://hooks.slack.com/services/T.../B.../...
```

### 7.3 로컬 개발(선택)

`.env` 파일은 git에 커밋 금지. README에 PowerShell/bash 예시 둘 다 제공:

```powershell
# Windows PowerShell
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."
python main.py
```

```bash
# bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
python main.py
```

### 7.4 `.gitignore`

```
__pycache__/
*.pyc
.env
.venv/
.python-version
```

## 8. Test Plan (L1–L5)

본 프로젝트는 백엔드 스크립트(서버 없음, UI 없음). L2/L3는 N/A. L1은 함수 단위 자체 검증, L4는 cron 안정성, L5는 Secrets 검토.

| 레벨 | 항목 | 방법 | 통과 기준 |
|---|---|---|---|
| **L1-1** | `build_message()` 평상시 포맷 | 더미 IndexQuote 2개 입력 → 문자열 비교 | 정규식 매치, 이모지 포함 |
| **L1-2** | `build_message()` 휴장 포맷 | is_stale=True 입력 → "(미 증시 휴장 ..." 부가 텍스트 | 부가 텍스트 포함 |
| **L1-3** | 변동률 계산 정확도 | 알려진 수치(17234.50/17089.18) → 수기 검증 | 0.85% (소수 2자리) |
| **L1-4** | `fetch_indices()` 통합 | 실제 yfinance 호출 (`pytest -m integration`) | 2개 IndexQuote 반환, last_close > 0 |
| **L1-5** | `post_slack()` 재시도 로직 | 잘못된 URL로 호출 → 3회 재시도 후 RuntimeError | 시도 카운트 = 3 |
| **L1-6** | `post_slack()` 정상 발송 | 실제 webhook URL로 1회 호출 | HTTP 200, Slack 메시지 도착 |
| **L4-1** | Cron 안정성 | `workflow_dispatch` 5회 + 평일 7일 자동 실행 | 12회 중 ≥ 11회 성공, 도착 시각 06:00–06:30 KST |
| **L5-1** | Secrets 노출 검사 | `git log -p \| grep -iE "webhook\|hooks.slack"` | 0건 |
| **L5-2** | `.env` 미커밋 | `git ls-files \| grep -E "^\.env$"` | 0건 |

> L1-4, L1-6은 외부 API 호출이므로 `pytest -m integration`로만 실행. CI에서는 secret 노출 위험으로 제외, 로컬에서만 수동 실행.

## 9. Error Handling & Retry

### 9.1 에러 유형별 대응

| 단계 | 에러 | 대응 |
|---|---|---|
| `fetch_indices` | yfinance ConnectionError/Timeout | 즉시 RuntimeError → main()에서 catch |
| `fetch_indices` | DataFrame 행 < 2 | RuntimeError("데이터 부족") |
| `post_slack` | HTTP 4xx (Webhook 오류) | 재시도하지 않고 즉시 실패 (URL이 잘못된 경우) |
| `post_slack` | HTTP 5xx / 네트워크 오류 | 30s → 60s → 120s 백오프 후 재시도, 3회 모두 실패 시 RuntimeError |
| `post_slack` | HTTP 429 (rate limit) | `Retry-After` 헤더 우선, 없으면 위 백오프 |
| `main` | 어떤 예외든 | stderr 로그 + best-effort 슬랙 에러 메시지 + return 1 |

### 9.2 best-effort 에러 알림

```python
def main() -> int:
    try:
        quotes = fetch_indices()
        msg = build_message(quotes)
        post_slack(load_slack_webhook_url(), msg)
        return 0
    except Exception as e:
        sys.stderr.write(f"[ERROR] {type(e).__name__}: {e}\n")
        try:
            url = os.environ.get("SLACK_WEBHOOK_URL")
            if url:
                post_slack(url, f"⚠️ morning-us-index 실패: {type(e).__name__}: {e}")
        except Exception:
            pass  # 에러 알림조차 실패하면 GitHub Actions가 fail로 통지
        return 1
```

## 10. Deployment (GitHub Actions)

### 10.1 `.github/workflows/daily_report.yml`

```yaml
name: Daily US Index Report

on:
  schedule:
    - cron: '0 21 * * *'   # UTC 21:00 = KST 06:00
  workflow_dispatch:        # 수동 실행 (디버깅/즉시 검증)

jobs:
  report:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run report
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: python main.py
```

### 10.2 의존성 (`requirements.txt`)

```
yfinance>=0.2.40
requests>=2.31
```

> `pandas`, `numpy`는 yfinance가 자동으로 설치한다. Phase 2에서 google-genai, anthropic 추가 예정.

### 10.3 README.md 골격

```
# morning-us-index

매일 KST 06:00 미국 증시(나스닥/S&P500) 종가를 슬랙으로 발송하는 서버리스 자동화.

## 설치

1. Slack Incoming Webhook URL 발급
2. GitHub repo fork or 새로 생성 (`gh repo create morning-us-index --public`)
3. Settings → Secrets → Actions → `SLACK_WEBHOOK_URL` 등록
4. Actions 탭에서 `Daily US Index Report` 워크플로우 활성화 (필요 시)
5. Actions → Run workflow로 즉시 1회 발송 테스트

## 로컬 실행

(7.3 참고)

## 일정 변경

`.github/workflows/daily_report.yml`의 cron 라인 수정.

## Phase 2 (예정)

뉴스 헤드라인 + AI 분석 브리핑 추가 — 별도 PDCA 사이클로 진행.
```

## 11. Implementation Guide

### 11.1 구현 순서 체크리스트

| # | 항목 | 산출물 | DoD (Definition of Done) |
|---|---|---|---|
| 1 | `.gitignore` 작성 | `.gitignore` | `.env`, `__pycache__/` 제외 |
| 2 | `config.py` — 상수, 환경변수 로더 | `config.py` | `load_slack_webhook_url()` 호출 가능 |
| 3 | `requirements.txt` | `requirements.txt` | `pip install -r` 무에러 |
| 4 | `main.py` — IndexQuote dataclass | `main.py` (1차) | `from main import IndexQuote` 임포트 가능 |
| 5 | `main.py` — `fetch_indices()` | `main.py` (2차) | 로컬 1회 실행 시 2개 IndexQuote 반환 |
| 6 | `main.py` — `build_message()` | `main.py` (3차) | 더미 입력으로 예상 포맷 문자열 출력 |
| 7 | `main.py` — `post_slack()` + 재시도 | `main.py` (4차) | 로컬 환경변수 설정 후 1회 슬랙 도착 |
| 8 | `main.py` — `main()` + 에러 핸들링 | `main.py` (5차) | 잘못된 ticker로 실패 시 슬랙 에러 메시지 도착 |
| 9 | `.github/workflows/daily_report.yml` | yml | YAML lint 통과, syntax 정상 |
| 10 | GitHub repo 생성 + Secrets 등록 | (외부) | `gh repo create`, secret 등록 완료 |
| 11 | `workflow_dispatch` 수동 실행 검증 | Action 로그 | exit 0, 슬랙 도착 |
| 12 | README.md 작성 | `README.md` | 처음 보는 사람이 30분 이내 셋업 가능 |
| 13 | 첫 cron 자동 실행 확인 (D+1) | Action 로그 | 06:00–06:30 KST 사이 도착 |

### 11.2 의존성 설치

```bash
python -m venv .venv
# Windows
.venv\Scripts\Activate.ps1
# bash
source .venv/bin/activate

pip install -r requirements.txt
```

### 11.3 Session Guide (Module Map + Recommended Sessions)

#### Module Map

| Module Key | 설명 | 파일 | 항목(11.1 #) |
|---|---|---|---|
| **module-1-config** | 환경변수/상수 + .gitignore | `config.py`, `.gitignore`, `requirements.txt` | 1, 2, 3 |
| **module-2-data** | yfinance 데이터 수집 + 모델 | `main.py` (IndexQuote, fetch_indices) | 4, 5 |
| **module-3-format** | 메시지 포맷팅 (순수 함수) | `main.py` (build_message) | 6 |
| **module-4-notify** | Slack 발송 + 재시도 | `main.py` (post_slack) | 7 |
| **module-5-orchestration** | main() + 에러 핸들링 | `main.py` (main) | 8 |
| **module-6-deploy** | GitHub Actions cron | `.github/workflows/daily_report.yml` | 9, 10, 11 |
| **module-7-docs** | README | `README.md` | 12, 13 |

#### Recommended Session Plan

세션은 **로컬 동작 → 클라우드 배포 → 문서화** 3단계로 나누는 것을 권장.

| 세션 | 범위 | 목표 (DoD) | 예상 시간 |
|---|---|---|---|
| **Session 1 — Local** | module-1, 2, 3, 4, 5 | 로컬에서 `python main.py` 1회 실행 → 슬랙 메시지 도착 | 60–90분 |
| **Session 2 — Cloud** | module-6 | `workflow_dispatch` 수동 실행 → Actions에서 슬랙 메시지 도착 | 30분 |
| **Session 3 — Docs & Verify** | module-7 + 익일 자동 cron 확인 | README 완성 + D+1일 자동 실행 검증 | 30분 + 익일 5분 |

호출 예시:

```bash
/pdca do morning-us-index --scope module-1-config,module-2-data,module-3-format,module-4-notify,module-5-orchestration
/pdca do morning-us-index --scope module-6-deploy
/pdca do morning-us-index --scope module-7-docs
```

또는 단일 세션으로:

```bash
/pdca do morning-us-index
```

> 1인 + ~120줄 규모라서 단일 세션도 합리적. 다만 module-1~5 끝난 시점에 로컬 동작이 검증되면 module-6의 GitHub 사이드 작업이 깔끔하게 분리되어 디버깅이 편함.

## 12. Risks Update (Plan §8 보완)

| Plan ID | Design 단계 추가 대응 |
|---|---|
| R-1 (yfinance 장애) | `period="5d"` + `dropna()` 패턴으로 일시 데이터 결측 흡수 |
| R-2 (cron 지연) | `timeout-minutes: 5` 명시 — runner가 막히지 않도록 안전장치 |
| R-4 (서머타임) | `last_date` 라벨링으로 사용자에게 "직전 거래일이 언제인지" 명시 → 시각적 혼란 방지 |
| R-5 (Phase 2 확장) | `build_message(quotes, extra_blocks=None)` 시그니처 확장 지점 §3.1에 명시 |

## 13. Out of Scope (재확인)

- AI 분석 / 뉴스 수집 / Block Kit / 차트 이미지 / 다채널 라우팅 / 다른 지수 — 모두 Phase 2 이후

## 14. References

- yfinance: https://github.com/ranaroussi/yfinance
- Slack Incoming Webhooks: https://api.slack.com/messaging/webhooks
- GitHub Actions schedule cron: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- Python `zoneinfo`: https://docs.python.org/3/library/zoneinfo.html

---

**다음 단계**: `/pdca do morning-us-index` (단일 세션) 또는 `/pdca do morning-us-index --scope module-1-config,module-2-data,module-3-format,module-4-notify,module-5-orchestration` (Session 1만)
