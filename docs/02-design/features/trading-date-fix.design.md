---
name: trading-date-fix
type: design
version: 0.1.1
status: approved
phase: design
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
approved_at: 2026-05-11
approved_by: jooladen (Checkpoint 3 — Option C 선택)
plan: docs/01-plan/features/trading-date-fix.plan.md
architecture: option-c-pragmatic-helper-plus-config-constant
---

# Design — trading-date-fix (헤더 직전 거래일 모순 표시 해소)

> **Summary**: `_resolve_last_trading_date(quotes)` helper 함수 신규 + `TRADING_DAY_CATEGORIES = ('index', 'stock')` config 상수 추가. main.py:149, 635 두 호출처를 helper 호출로 교체. L1 테스트 3 케이스 추가.
>
> **Plan**: [trading-date-fix.plan.md](../../01-plan/features/trading-date-fix.plan.md)
> **Architecture**: Option C — Pragmatic Balance
> **Status**: Approved (Checkpoint 3 통과)

---

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 2026-05-11 발송에서 헤더 "직전 거래일: today (미 증시 휴장)" 모순 발견 |
| **WHO** | 준 — 헤더 신뢰성 필수 |
| **RISK** | 매우 낮음 (helper 1개 + 2곳 1줄씩) |
| **SUCCESS** | 휴장일 정확 표시 / 회귀 0 / 119+3=122 통과 |
| **SCOPE** | main.py 2곳 + config.py 상수 + tests 3 케이스. ≤30 lines |

---

## 1. Overview

### 1.1 Design Goals

- `last_trading_date` 계산 로직 1곳 (helper) 통합 → 시싱크 위험 0
- `TRADING_DAY_CATEGORIES` 상수로 본 시장 자산 그룹 의미 명확화
- 정상 거래일 회귀 0 (기존 119 테스트 통과 유지)
- 휴장일 모순 표시 0 (신규 L1 테스트 3개로 invariant 잠금)

### 1.2 Design Principles

- **YAGNI** — 클래스/모듈 분리 X. 함수 1개로 충분
- **DRY** — 동일 로직 2곳 중복 → 1곳으로
- **Fail-safe** — 본 시장 자산이 비어 있는 fixture에서 fallback
- **Code is truth** — Plan/Design은 코드를 따라옴

### 1.3 Plan OQ 해소

| Open Q (Plan §11) | Design 결정 | 근거 |
|---|---|---|
| OQ-1 helper 이름 | **`_resolve_last_trading_date`** | "resolve"가 fallback 포함 의미 잘 전달. 동사+명사 |
| OQ-2 상수 위치 | **config.py** (Plan 사용자 결정) | 사용처 1곳이지만 의미 명확화 + 다른 카테고리 상수와 같은 곳 |
| OQ-3 fallback 동작 | **`max(q.last_date for q in quotes)` 사용** | robust. RuntimeError는 운영 중 발생 시 잡기 어려움 |
| OQ-4 테스트 위치 | **tests/test_main.py** | 기존 헤더 테스트와 같은 파일 |
| OQ-5 다음 휴장일 재검증 강제 | Report 단계에서 안내만 | 자동화는 Phase 2 |

---

## 2. Architecture (Option C)

### 2.1 Component Diagram

```
┌────────────────────────────────────────────────────────────────┐
│  config.py (수정)                                              │
│    TRADING_DAY_CATEGORIES = ('index', 'stock')   ← 신규 상수    │
└────────────────────┬───────────────────────────────────────────┘
                     │ import
                     ↓
┌────────────────────────────────────────────────────────────────┐
│  main.py (수정)                                                │
│                                                                │
│   def _resolve_last_trading_date(quotes: list[Quote]) -> date: │ ← 신규 helper
│       trading_assets = [q for q in quotes                      │
│                         if q.category in TRADING_DAY_CATEGORIES]│
│       if trading_assets:                                       │
│           return max(q.last_date for q in trading_assets)      │
│       return max(q.last_date for q in quotes)  # fallback      │
│                                                                │
│   line 149  → last_trading_date = _resolve_last_trading_date(  │ ← 교체
│   line 635  → last_trading_date = _resolve_last_trading_date(  │ ← 교체
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  tests/test_main.py (추가)                                     │
│                                                                │
│   L1-td-1: 정상거래일 (모두 fresh) → today/yesterday 표시       │
│   L1-td-2: 주말 혼합 (index/stock stale, future/macro fresh)   │
│             → 본 시장 last_date + "(미 증시 휴장)"              │
│   L1-td-3: 모두 stale → min=max=stale_date + 휴장 표시          │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
quotes: list[Quote]
        ↓
_resolve_last_trading_date(quotes)
        ↓
[trading_assets] = [q for q in quotes if q.category in TRADING_DAY_CATEGORIES]
        ↓
   ┌────┴────┐
   ↓         ↓
trading_assets  empty?
non-empty       ↓
   ↓        fallback: max(q.last_date for q in quotes)
max(q.last_date for q in trading_assets)
   ↓
return date
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|---|---|---|
| `_resolve_last_trading_date` | `TRADING_DAY_CATEGORIES` (config) | helper 로직 |
| `main.py:149` (Phase 1.5 build) | helper | 헤더 생성 |
| `main.py:635` (build_v15_message) | helper | 헤더 생성 |
| `test_main.py` (3 new cases) | helper, build functions | 검증 |

**다른 파일 영향**: 0 (data.py / news.py / signals.py / preview_mobile.py 변경 없음)

---

## 3. Data Model

변경 없음. 기존 Quote dataclass 그대로:

```python
@dataclass(frozen=True)
class Quote:
    ticker: str
    label: str
    category: Literal["index", "future", "stock", "macro"]
    sector: str | None
    last_close: float
    prev_close: float
    last_date: date           # ← helper 입력
    is_stale: bool
    ...
```

---

## 4. Module Design

### 4.1 `config.py` (수정 — 1줄 추가)

```python
# trading-date-fix: 본 시장(미국 정규장) 캘린더와 일치하는 자산 카테고리.
# Quote.category Literal["index", "future", "stock", "macro"] 중,
# index(나스닥/S&P/다우/VIX) + stock(NVDA/MU 등)은 본 시장 캘린더와 동일.
# future(야간선물) + macro(forex)는 24-5 거래 → today 마킹 가능 → 제외.
# 새 카테고리 추가 시 본 튜플 + Quote.category Literal 둘 다 갱신할 것.
TRADING_DAY_CATEGORIES: tuple[str, ...] = ("index", "stock")
```

위치: 기존 `STALE_THRESHOLD_DAYS = 2` 라인 근처 (line 28-29 사이).

### 4.2 `main.py` (수정 — helper 추가 + 2곳 교체)

#### 4.2.1 신규 helper (build_v15_message 앞에 배치)

```python
# Design Ref §4.2.1 — trading-date-fix helper.
def _resolve_last_trading_date(quotes: list[Quote]) -> date:
    """본 시장 캘린더 기준 last_trading_date 계산.

    Plan SC-TD-1: 헤더 "직전 거래일" 모순 표시 해소.

    24-7 가까이 거래되는 future/macro 자산은 today 마킹 가능 → 휴장일
    "직전 거래일: today (미 증시 휴장)" 인지 부조화 발생. 본 시장 캘린더와
    동기화된 자산(TRADING_DAY_CATEGORIES = ('index', 'stock'))만 max로
    집계해 정확한 마지막 본 시장 거래일 반환.

    Args:
        quotes: fetch_all()이 반환한 Quote 리스트.

    Returns:
        본 시장 자산 last_date의 max. trading_assets가 비어 있으면
        fallback으로 전체 quotes의 max 반환 (운영에선 발생 X, 안전망).
    """
    trading_assets = [q for q in quotes if q.category in TRADING_DAY_CATEGORIES]
    if trading_assets:
        return max(q.last_date for q in trading_assets)
    return max(q.last_date for q in quotes)
```

위치: `build_v15_message` 함수 정의 바로 앞 (line 605 근처).

#### 4.2.2 호출처 — main.py 단일 위치 (v0.1.1 정정)

**v0.1.0 작성 시 main.py:149 + main.py:635 두 곳을 helper로 통합한다고 명시했으나,
Do 단계 회귀 테스트에서 IndexQuote/Quote dataclass 차이가 발견되어 정정.**

| 위치 | 함수 | 입력 dataclass | helper 적용 |
|---|---|---|---|
| main.py:149 (Phase 1 build_message) | `build_message(quotes)` | **IndexQuote** — category 필드 **없음** | ❌ helper 미적용 (AttributeError) |
| main.py:635 (Phase 1.5 build_v15_message) | `build_v15_message(quotes, signals, news_map)` | **Quote** — category 필드 있음 | ✅ helper 적용 |

Phase 1 build_message는 5개 지수(모두 index 카테고리)만 받아 모순 표시 발생 불가 →
helper 통합 가치 없음. Phase 1.5 build_v15_message만 helper 호출:

```python
# main.py:635 (build_v15_message) — 유일한 호출처
# Before:
last_trading_date = max(q.last_date for q in quotes)
# After (Design Ref §4.2.2):
last_trading_date = _resolve_last_trading_date(quotes)

# main.py:149 (Phase 1 build_message) — 변경 없이 원래대로
last_trading_date = max(q.last_date for q in quotes)
# (위에 IndexQuote/Quote 차이 설명 주석 추가)
```

#### 4.2.4 Import 추가

`from config import` 라인에 `TRADING_DAY_CATEGORIES` 추가.

### 4.3 `tests/test_main.py` (추가 — 3 케이스)

```python
def test_resolve_last_trading_date_all_fresh():
    """L1-td-1: 정상 거래일 — 모든 자산 fresh.

    모두 같은 거래일(예: 2026-05-08 금) → max = 그 날짜.
    """
    quotes = [
        _q(category="index",  last_date_=date(2026, 5, 8), is_stale=False),
        _q(category="stock",  last_date_=date(2026, 5, 8), is_stale=False),
        _q(category="future", last_date_=date(2026, 5, 8), is_stale=False),
        _q(category="macro",  last_date_=date(2026, 5, 8), is_stale=False),
    ]
    from main import _resolve_last_trading_date
    assert _resolve_last_trading_date(quotes) == date(2026, 5, 8)


def test_resolve_last_trading_date_weekend_mixed():
    """L1-td-2: 주말 혼합 — index/stock stale, future/macro fresh.

    버그 시나리오의 직접 재현: max(전체)는 today(5/11)지만,
    helper는 본 시장 자산만으로 5/8 반환해야 함.
    """
    quotes = [
        _q(category="index",  last_date_=date(2026, 5, 8),  is_stale=True),
        _q(category="stock",  last_date_=date(2026, 5, 8),  is_stale=True),
        _q(category="future", last_date_=date(2026, 5, 11), is_stale=False),
        _q(category="macro",  last_date_=date(2026, 5, 11), is_stale=False),
    ]
    from main import _resolve_last_trading_date
    assert _resolve_last_trading_date(quotes) == date(2026, 5, 8)


def test_resolve_last_trading_date_all_stale():
    """L1-td-3: 미국 정부 공휴일 같은 드문 케이스 — 모두 stale."""
    quotes = [
        _q(category="index",  last_date_=date(2026, 5, 7), is_stale=True),
        _q(category="stock",  last_date_=date(2026, 5, 7), is_stale=True),
        _q(category="future", last_date_=date(2026, 5, 7), is_stale=True),
        _q(category="macro",  last_date_=date(2026, 5, 7), is_stale=True),
    ]
    from main import _resolve_last_trading_date
    assert _resolve_last_trading_date(quotes) == date(2026, 5, 7)
```

기존 `_q()` factory(test_main.py 안)를 그대로 활용. 새 fixture 필요 없음.

---

## 5. UI/UX Design

**N/A** — 백엔드/CLI. 출력 변화는 슬랙 메시지 헤더 한 줄(텍스트)만.

| Before (버그) | After (수정) |
|---|---|
| `직전 거래일: 2026-05-11 (미 증시 휴장)` | `직전 거래일: 2026-05-08 (미 증시 휴장)` |

---

## 6. Error Handling

| 시나리오 | helper 동작 |
|---|---|
| quotes가 빈 리스트 | `RuntimeError` (main.py:627 이미 보장 — build_v15_message가 빈 quotes 거부) |
| trading_assets 0개 (운영 시 발생 X) | fallback `max(q.last_date for q in quotes)` 동작. 기존 동작 보존 |
| Quote.category Literal 외 값 | mypy strict가 컴파일 시 차단 |

---

## 7. Configuration & Secrets

| 항목 | 변경 |
|---|---|
| Secrets | 0 |
| 환경변수 | 0 |
| config.py | **1 줄 추가** (`TRADING_DAY_CATEGORIES`) |

---

## 8. Test Plan (L1 단위 3 케이스)

### 8.1 Test Scope

| Type | Target | Tool | Phase |
|---|---|---|---|
| L1 단위 | `_resolve_last_trading_date` | pytest | Do |
| L1 통합 (기존) | `build_v15_message` 헤더 출력 | pytest 기존 케이스 | Do (회귀) |

### 8.2 신규 L1 케이스 (3개)

| # | 테스트 함수 | 시나리오 | 통과 기준 |
|---|---|---|---|
| L1-td-1 | `test_resolve_last_trading_date_all_fresh` | 정상 거래일 모두 fresh (동일 last_date) | helper 반환 = 그 날짜 |
| L1-td-2 | `test_resolve_last_trading_date_weekend_mixed` | 주말 — index/stock stale + future/macro fresh | helper 반환 = 본 시장 last_date (today 아님) |
| L1-td-3 | `test_resolve_last_trading_date_all_stale` | 모두 stale (미 공휴일 등) | helper 반환 = stale_date |

### 8.3 회귀 검증

| 검증 | 기대 |
|---|---|
| 기존 110 테스트 + 신규 9 slack-mobile-preview + 신규 3 trading-date-fix | **122 passed** |
| Phase 1.5 회귀 0 | `test_main.py::test_header_*` 기존 케이스 통과 |
| slack-mobile-preview 영향 0 | 9 cases 통과 |
| integration 6 deselected | 그대로 |

---

## 9. Clean Architecture

이 사이클은 main.py 안의 helper 함수 1개 + config 상수 1개라 다층 아키텍처 N/A.

| 항목 | 위반 검사 |
|---|---|
| 의존성 방향 | main.py → config.py (정방향) ✅ |
| 도메인 로직 프레임워크 무관 | helper는 stdlib만 사용 ✅ |
| 데이터 접근 X 비즈니스 로직 분리 | helper는 순수 함수 — fetch 없음 ✅ |

---

## 10. Coding Convention

| 대상 | 규칙 | 예시 |
|---|---|---|
| 내부 헬퍼 | `_` prefix | `_resolve_last_trading_date` |
| 상수 | UPPER_SNAKE | `TRADING_DAY_CATEGORIES` |
| 함수 docstring | Args/Returns + Plan SC ref | §4.2.1 참조 |
| Design Ref 주석 | 변경 코드 위에 한 줄 | `# Design Ref §4.2.1 ...` |

---

## 11. Implementation Guide

### 11.1 File Structure

```
morning_us_index/
├── config.py                 (수정 — TRADING_DAY_CATEGORIES 1줄 추가)
├── main.py                   (수정 — helper 1개 + 2곳 호출 교체 + import 1개)
├── tests/
│   └── test_main.py          (추가 — 3 L1 케이스)
└── (다른 파일 변경 0)
```

### 11.2 Implementation Order (5 단계)

| # | 항목 | 산출물 | DoD |
|---|---|---|---|
| 1 | `config.py` — `TRADING_DAY_CATEGORIES` 상수 추가 | 1 줄 | python -c "from config import TRADING_DAY_CATEGORIES" 성공 |
| 2 | `main.py` import 추가 — `TRADING_DAY_CATEGORIES` | 기존 from config import 라인에 추가 | import 에러 0 |
| 3 | `main.py` — `_resolve_last_trading_date` helper 추가 | 11 줄 함수 (docstring 포함) | python -c "from main import _resolve_last_trading_date" 성공 |
| 4 | `main.py:149, 635` — helper 호출로 교체 | 2 줄 변경 | grep "max(q.last_date for q in quotes)" main.py → 0 hit |
| 5 | `tests/test_main.py` — 3 L1 케이스 추가 | 신규 함수 3개 (~40줄) | pytest tests/test_main.py -v → 신규 3 passed |

### 11.3 Session Guide

#### Module Map

| Module | Scope Key | Description | 11.2 # |
|---|---|---|---|
| **module-1-config** | `module-1-config` | TRADING_DAY_CATEGORIES 상수 추가 | 1 |
| **module-2-helper** | `module-2-helper` | _resolve_last_trading_date 함수 + import | 2, 3 |
| **module-3-callsites** | `module-3-callsites` | main.py:149, 635 호출 교체 | 4 |
| **module-4-tests** | `module-4-tests` | L1-td-1/2/3 단위 테스트 3개 | 5 |

#### Recommended Session Plan

| 세션 | 범위 | DoD | 시간 |
|---|---|---|---|
| **단일 세션** | module-1, 2, 3, 4 일괄 | 122 passed, 회귀 0 | ~20분 |

작은 사이클이라 분할 불필요. 단일 세션 권장.

---

## 12. Risks Update (Plan §8 보완)

| Plan ID | Design 단계 추가 대응 |
|---|---|
| R-1 빈 trading_assets | helper fallback이 `max(q.last_date for q in quotes)` 사용 → 안전망 |
| R-2 새 카테고리 추가 | config.py 상수에 주석 명시: "새 카테고리 추가 시 본 튜플 + Quote.category Literal 둘 다 갱신" |
| R-3 yfinance stock today 마킹 | yfinance 1d daily 기준이라 발생 가능성 낮음. 발견 시 helper의 `is_stale=True` 필터 추가 검토 (Phase 2) |
| R-4 시뮬 ↔ 실 슬랙 차이 | slack-mobile-preview v0.1.3 캘리브레이션 완료 — 헤더 영역 1:1 검증됨 |
| R-5 (신규) helper 위치 — main.py vs config.py | main.py 안에 두기로 결정. config.py는 데이터(상수)만, 로직은 main.py |

---

## 13. Out of Scope (Phase 2+)

(Plan §9 그대로)

- Phase 2: 헤더 표시 분리 ("본시장: 5/8 / 시간외: 5/11")
- Phase 2: NYSE 캘린더 API 연동
- Phase 2: 시장 오픈/클로즈 직전·후 fresh/stale 경계 처리
- Phase 3: STALE_THRESHOLD_DAYS 동적 계산

---

## 14. Deployment

| 항목 | 변경 |
|---|---|
| `requirements.txt` | 0 |
| `.github/workflows/daily_report.yml` | 0 |
| Secrets | 0 |
| 신규 `config.py` 1 줄 | + |
| 신규 `main.py` helper + import + 2곳 교체 | + |
| 신규 `tests/test_main.py` 3 케이스 | + |

**다음 배포**: 평소처럼 `git push origin main` + workflow auto-trigger 또는 manual `gh workflow run`. 다음 휴장일(주말 또는 미국 공휴일) 발송 시 actions-log 모드로 시뮬 재검증 권장.

---

## 15. References

- Plan: `docs/01-plan/features/trading-date-fix.plan.md`
- 발견 메시지: GitHub Actions run-id 25649430993 (2026-05-11)
- 메모리: `~/.claude/projects/.../memory/project_trading_date_display_bug.md`
- 도구: `scripts/preview_mobile.py` (slack-mobile-preview v0.1.3, Match Rate 100%)
- main.py:149 (Phase 1.5) / main.py:635 (build_v15_message)

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 0.1.0 | 2026-05-11 | Initial. Option C(Pragmatic Balance) 선택. helper + config 상수. 4 모듈, 단일 세션. 3 L1 테스트. | jooladen (with Ally) |
| 0.1.1 | 2026-05-11 | **Do 단계 회귀 발견 후 정정**: §4.2.2 호출처 main.py:149 + main.py:635 두 곳 → main.py:635 단일로 정정. 원인: Phase 1 build_message는 IndexQuote(category 필드 없음)를 받아 helper 호출 시 AttributeError. Phase 1은 5개 지수만(모두 index)이라 모순 표시 발생 불가 → 단순 max 유지. 122 passed 회귀 0. | jooladen (with Ally — 정직한 보고) |

---

**다음 단계**: `/pdca do trading-date-fix` (단일 세션 ~20분 권장)
