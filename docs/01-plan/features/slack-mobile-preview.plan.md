---
name: slack-mobile-preview
type: plan
version: 0.1.0
status: draft
phase: plan
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
builds_on: morning-us-index-noai-v2 (Phase 2-NoAI, v10 운영 중)
prd: null
related_pain_point: 슬랙 모바일 화면 검증을 위해 매번 사용자 스크린샷 요구 (v5~v10 사이클에서 반복 발생)
---

# Plan — slack-mobile-preview (Ally 시각 검증 도구)

## Executive Summary

| 관점 | 한 줄 요약 |
|---|---|
| **Problem** | 슬랙 모바일 메시지 렌더링은 사용자 디바이스에서만 정확히 표시. Ally가 매 사이클(v5~v10) 사용자 스크린샷을 요구 → 검증 병목 + 사용자 부담. |
| **Solution** | Playwright + 모바일 viewport(**Galaxy S23+: 384×854, DPR=3**, Samsung One UI Sans / Noto Color Emoji 폰트)로 메시지를 HTML mock 렌더 → PNG 스크린샷 저장 → Ally가 멀티모달로 직접 이미지 분석. |
| **Function · UX · Effect** | `python scripts/preview_mobile.py` 실행 시 fixture 메시지를 모바일 viewport에서 렌더 → `scripts/output/preview-{timestamp}.png` 생성. CI에서도 메시지 dump 후 자동 스크린샷. |
| **Core Value** | "**스크린샷 부담 종결 + Ally가 직접 본다**" — 매 사이클 사용자 부담 0, 디자인 조정 사이클 시간 70% 단축. |

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | v5~v10 사이클 누적으로 검증 병목 발견. Ally가 텍스트만으로는 모바일 자동 줄바꿈/이모지 변환/한글 폰트 폭 추정 한계 → 90% 정확도 도구 필요 |
| **WHO** | 준 (1인 운영자). 슬랙 모바일 발송 메시지 시각 검증 부담 호소 |
| **RISK** | Playwright 의존성 추가 (~50MB chromium binary) / Slack 모바일 정확 렌더링 100% 재현 불가 (시뮬레이션) / HTML mock 폰트가 실 슬랙과 다를 수 있음 |
| **SUCCESS** | preview_mobile.py 실행 시 스크린샷 생성 / Ally가 이미지 분석으로 라인 잘림/이모지 변환 직접 감지 / 향후 사이클에서 사용자 스크린샷 요청 0회 |
| **SCOPE** | 슬랙 mrkdwn → HTML 변환 + Playwright 헤드리스 렌더 + 스크린샷 저장. 다른 메신저(카카오톡 등)는 Phase 2 확장 |

---

## 1. Overview

morning-us-index 메시지 발송 사이클(v5~v10)에서 반복적으로 발생한 **시각 검증 병목** 해결. Ally가 멀티모달 모델이라 이미지 직접 분석 가능 → "Ally가 화면을 보면서 개발"하는 워크플로우 구축.

**핵심 차별점**: 슬랙 API/Bot 토큰 없이도 작동. 자체 HTML mock + Playwright headless로 모바일 viewport 시뮬레이션. 슬랙뿐 아니라 향후 다른 메신저로 일반화 가능한 패턴.

## 2. Background & Problem

### 2.1 v5~v10 사이클 누적 페인포인트

| 사이클 | 페인포인트 |
|---|---|
| v5 | 사용자 스크린샷 1장 (한 종목 2줄 잘림) |
| v6 | 도구 추가 (Actions log dump) — 텍스트만 확보, 시각 X |
| v7 | 스크린샷 1장 (구분선 자동 줄바꿈) |
| v8 | 스크린샷 1장 (한 종목 2줄, 구분선 3줄) |
| v9 | 스크린샷 1장 (`범례는 어디?`) |
| v10 | 검증 못 함 (배포만) |

→ **누적 5회 사용자 스크린샷 요구**. 사용자 명시 호소: *"스크린샷 넘 힘드네...어케 방법이 없어?"*

### 2.2 Ally 텍스트만으로 추정 못 하는 항목

| 항목 | 텍스트 검증 가능? | 실제 렌더링 영향 |
|---|:-:|---|
| 라인 폭 (char 수) | ✅ | 부분 (모바일 폰트 폭 불일치) |
| 자동 줄바꿈 위치 | ❌ | 16-20자에서 자동 줄바꿈 |
| 한글-영문 폰트 폭 비율 | ❌ | 1.85배 (iOS) ~ 2배 (Android) |
| 이모지 변환 (🆙 → `UP!`) | ❌ | 슬랙 클라이언트 동작 |
| Code block monospace fallback | ❌ | 한글 시 가변폭으로 fallback |
| 줄 간격 / padding | ❌ | 시각적 어수선함 |

→ **시각 검증이 본질**. 텍스트 도구로는 70-80% 정확도가 한계.

## 3. Goals & Non-Goals

### 3.1 Goals

- **G1.** `scripts/preview_mobile.py` 실행 시 fixture 메시지를 모바일 viewport (**Galaxy S23+: 384×854, DPR=3**)에서 렌더 → PNG 스크린샷 저장
- **G2.** 슬랙 mrkdwn 핵심 문법 (`*bold*`, `` `code` ``, ```` ```code block``` ````, 이모지) HTML 변환
- **G3.** 한글-영문 혼합 폰트 시뮬레이션 (**Samsung One UI Sans / Noto Sans KR + Noto Color Emoji** — Galaxy 환경)
- **G4.** Ally가 멀티모달로 스크린샷 분석 → 자동 줄바꿈 위치 / 이모지 변환 / 컬럼 정렬 직접 확인
- **G5.** 향후 사이클에서 사용자 스크린샷 요청 0회 (대신 Actions log dump + 자동 스크린샷)
- **G6.** 메인 프로그램(`main.py`)에 의존성 0 — 도구는 별도 모듈

### 3.2 Non-Goals (이번 사이클에서 안 함)

- ❌ 슬랙 모바일 100% 정확 재현 — 90-95% 시뮬레이션 목표
- ❌ Slack Bot 토큰 / OAuth 설정 (Phase 2 검토)
- ❌ iOS 폰트 시뮬레이션 (Android Galaxy S23+ 우선 — 사용자 디바이스)
- ❌ 카카오톡 / 텔레그램 / 이메일 렌더링 (Phase 2)
- ❌ Actions 워크플로에 스크린샷 자동 업로드 (Phase 2)
- ❌ 모바일 에뮬레이터 (Android Emulator + ADB) — Phase 3

## 4. Requirements

### 4.1 Functional Requirements

| ID | 요구사항 | 비고 |
|---|---|---|
| **FR-01** | `scripts/preview_mobile.py` 신규 스크립트 | fixture 또는 stdin 메시지 입력 → 스크린샷 출력 |
| **FR-02** | mrkdwn → HTML 변환 함수 | `_slack_mrkdwn_to_html(text: str) -> str`. `*bold*`/` `code` `/```` ```code block``` ````/줄바꿈 처리 |
| **FR-03** | HTML 템플릿 — 슬랙 Galaxy S23+ 시뮬레이션 | `scripts/templates/slack_mobile.html.j2`. **'Noto Sans KR', 'Roboto', sans-serif 폰트 + 'Noto Color Emoji' 이모지 fallback** + 슬랙 스타일 (배경/padding/code block 회색) |
| **FR-04** | Playwright headless + **Galaxy S23+ viewport** | **384×854, deviceScaleFactor=3, isMobile=True, userAgent=Android Chrome**. Playwright 기본 deviceDescriptors에 Galaxy S23+ 없음 → custom viewport 직접 지정 |
| **FR-05** | 스크린샷 저장 — 타임스탬프 파일명 | `scripts/output/preview-YYYYMMDD-HHMMSS.png` |
| **FR-06** | CLI 옵션 — fixture 모드 / stdin 모드 / Actions log 모드 | `--source fixture` / `--source stdin` / `--source actions-log <run-id>` |
| **FR-07** | 출력 디렉토리 자동 생성 | `scripts/output/` 없으면 mkdir |
| **FR-08** | requirements-dev.txt (선택) | playwright 운영용 main.py와 분리 |

### 4.2 Non-Functional Requirements

| ID | 요구사항 | 측정 |
|---|---|---|
| NFR-01 | 실행 시간 | ≤ 10초 (chromium 시작 + 렌더 + 스크린샷) |
| NFR-02 | 메모리 | ≤ 200MB (chromium headless) |
| NFR-03 | 추가 의존성 | 2개 (`playwright>=1.49.0`, `jinja2>=3.1.0`) — requirements-dev.txt 격리, main requirements.txt 변경 0, main.py 의존성 0 (운영 영향 X) |
| NFR-04 | 스크린샷 정확도 | 90-95% (슬랙 모바일 실 렌더 대비 자동 줄바꿈 위치 90%+ 일치) |
| NFR-05 | OS 호환 | Windows + macOS + Linux (Actions runner ubuntu-latest 포함) |
| NFR-06 | main.py 영향 | 0 — 도구는 scripts/ 디렉토리에 격리 |
| NFR-07 | 신규 테스트 | ≥ 6 케이스 (mrkdwn 변환 + HTML 생성 + 스크린샷 파일 존재) |

## 5. User Stories & Acceptance Criteria

### US-1. Ally가 직접 모바일 화면 보기

> *Ally로서, 슬랙 메시지를 발송하기 전 모바일에서 어떻게 보이는지 직접 확인하고 싶다. 사용자에게 매번 스크린샷 요청하지 않아도 됨.*

**AC:**
- ✅ `python scripts/preview_mobile.py` 실행 시 `scripts/output/preview-*.png` 생성
- ✅ Ally가 이미지 파일 경로로 Read 도구 사용 → 모바일 viewport 결과 직접 분석
- ✅ 라인 잘림 / 이모지 변환 / 컬럼 정렬 정확도 90%+ 시뮬레이션

### US-2. 사용자 부담 0

> *준으로서, 매번 폰 스크린샷 찍는 부담 없이 메시지 디자인 변경 결과를 신뢰하고 싶다.*

**AC:**
- ✅ 메시지 형식 변경 사이클에서 사용자 스크린샷 요청 0회 발생
- ✅ Actions log dump (v6) + 자동 스크린샷 (이번 사이클)으로 검증 자동화
- ✅ 사용자가 스크린샷 보내고 싶을 때만 (즉, 추가 검증 시에만) 보냄

### US-3. 다른 메신저로 확장 가능

> *향후 카카오톡/이메일 알림 추가 시 동일 도구로 시각 검증.*

**AC:**
- ✅ HTML 템플릿 분리 (slack_mobile.html.j2)로 다른 메신저 템플릿 추가 가능
- ✅ `--profile slack-mobile` / `--profile kakao-mobile` 옵션 확장 가능 구조

## 6. Success Criteria (Measurable)

| ID | 지표 | 목표 | 측정 방식 |
|---|---|---|---|
| SC-MP-1 | 스크린샷 생성 성공률 | 100% (정상 메시지 입력 시) | preview_mobile.py 10회 실행 후 PNG 파일 존재 |
| SC-MP-2 | 자동 줄바꿈 위치 정확도 | ≥ 90% (실 모바일 대비) | 동일 메시지 실 모바일 vs 시뮬레이션 비교 (10 라인) |
| SC-MP-3 | 실행 시간 | ≤ 10초 | `time python scripts/preview_mobile.py` |
| SC-MP-4 | 추가 의존성 | 2개 (playwright + jinja2, requirements-dev.txt) | requirements-dev.txt diff. main requirements.txt는 변경 0. |
| SC-MP-5 | main.py 회귀 | 0건 (110 단위 테스트 그대로 통과) | pytest |
| SC-MP-6 | 신규 테스트 | ≥ 6 | pytest --collect-only \| grep test_mrkdwn\|test_html\|test_screenshot |
| SC-MP-7 | 사용자 스크린샷 요청 횟수 (운영 후) | 0회 (3 사이클 무사고) | 사이클 회고 |

## 7. Constraints & Assumptions

### 7.1 Constraints

- **C-1.** Playwright chromium binary 50MB (1회 다운로드, 캐시됨)
- **C-2.** Ally의 멀티모달 이미지 분석은 PNG 또는 JPG만 (SVG/HTML 직접 분석 X)
- **C-3.** 슬랙 자체 폰트/이모지 시스템 100% 재현 불가
- **C-4.** main.py + tests/ 변경 0 (격리 원칙)

### 7.2 Assumptions

- **A-1.** Ally가 멀티모달이라 이미지 파일 Read 도구로 분석 가능 (검증됨)
- **A-2.** 모바일 viewport 시뮬레이션이 90%+ 정확도면 사용자 스크린샷 보다 우월 (사용자 폰별 차이 흡수)
- **A-3.** Playwright + chromium은 Windows/macOS/Linux 일관 동작
- **A-4.** HTML mock의 자동 줄바꿈은 실 슬랙 모바일과 거의 일치 (단, 슬랙 자체 mrkdwn 파싱 동작 차이는 있을 수 있음)

## 8. Risks & Mitigations

| ID | 위험 | 영향 | 확률 | 대응 |
|---|---|---|---|---|
| **R-1** | Playwright chromium 다운로드 실패 (네트워크) | 도구 동작 불가 | 저 | `playwright install chromium` 1회 + 캐시 |
| **R-2** | HTML mock과 실 슬랙 렌더링 차이 | 검증 정확도 저하 | 중 | 90% 목표 명시. 차이 발견 시 템플릿 수정 (CSS line-height, font-family 조정) |
| **R-3** | 이모지 변환 (🆙 → `UP!`) 시뮬레이션 한계 | 잘못된 검증 | 중 | 슬랙 알려진 이모지 변환 목록을 매핑 사전으로 (예: `:up_arrow:` → "UP!" 박스 텍스트로 치환) |
| **R-4** | scripts/ 디렉토리 의존성 main.py에 누출 | 운영 영향 | 저 | requirements-dev.txt 분리 또는 import 격리 |
| **R-5** | 스크린샷 파일 누적으로 디스크 ↑ | 디스크 압박 | 저 | `.gitignore`에 `scripts/output/*.png` 추가 |
| **R-6** | Actions log 모드에서 gh CLI 의존 | Actions 외 환경 동작 X | 저 | fixture 모드 fallback (gh 없이도 동작) |

## 9. Out of Scope (Phase 2-MobilePreview+)

- **Phase 2** — 카카오톡 / 텔레그램 / 이메일 HTML 템플릿 확장
- **Phase 2** — Slack Bot 토큰 + 실 채널 메시지 fetch 자동화
- **Phase 2** — Actions 워크플로 자동 스크린샷 업로드 (GitHub Actions artifact)
- **Phase 3** — Android Emulator + ADB screenshot (99% 정확도)
- **Phase 3** — A/B 시안 비교 (두 버전 동시 렌더 + diff)

## 10. Roadmap & Milestones

| 마일스톤 | 산출물 | DoD |
|---|---|---|
| M1 — Plan ✅ | 본 문서 | 4 Checkpoint 통과, 사용자 승인 |
| M2 — Design | `docs/02-design/features/slack-mobile-preview.design.md` | 3 옵션 비교 + 모듈 맵 + HTML 템플릿 wireframe + 테스트 플랜 |
| M3 — Do | scripts/preview_mobile.py + templates/slack_mobile.html.j2 + tests/test_preview_mobile.py | 로컬 실행 시 PNG 생성, 6+ 테스트 통과 |
| M4 — Check | analysis.md | Match Rate ≥ 90%, 실 슬랙 모바일 대비 시뮬레이션 정확도 검증 |
| M5 — Iter | (필요 시) | 100% 도달 |
| M6 — Deploy | (선택) Actions artifact 업로드 | 도구 일상 사용 시작 |
| M7 — Report | report.md | 사이클 종료 + Phase 2 안내 |

## 11. Open Questions

| ID | 질문 | 결정 시점 |
|---|---|---|
| OQ-1 | Playwright vs Puppeteer vs Selenium — 선택 | Design (Playwright 권장 — 모바일 viewport 내장 지원) |
| OQ-2 | HTML 템플릿 엔진 — Jinja2 vs f-string | Design (Jinja2 권장 — 향후 확장 시 깔끔) |
| OQ-3 | 출력 파일명 규칙 — 타임스탬프 vs 해시 vs 사용자 지정 | Design |
| OQ-4 | viewport 표준 — ~~iPhone 13 vs Galaxy S22~~ | **결정됨 (사용자 디바이스 Galaxy S23+): 384×854, DPR=3**. iPhone 시뮬레이션은 Phase 2에서 옵션으로 추가 검토 |
| OQ-5 | 이모지 변환 사전 — 어디까지 매핑? | Do (운영 중 발견된 케이스 추가) |

## 12. References

- 사용자 페인포인트 호소: 2026-05-11 세션 ("스크린샷 넘 힘드네…")
- v6 도구 (Actions log dump): main.py:_print_message_dump, _print_width_diagnostics
- Playwright Python: https://playwright.dev/python/docs/intro
- Playwright deviceDescriptors: https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/deviceDescriptorsSource.json
- Galaxy S23+ 사양: 6.6" 2340×1080 FHD+, CSS viewport ~384×854, DPR=3, Android 13/14 One UI 5/6
- Slack mrkdwn 문법: https://api.slack.com/reference/surfaces/formatting
- Noto Color Emoji (Google CDN): https://fonts.googleapis.com/css2?family=Noto+Color+Emoji
- Noto Sans KR (Google CDN): https://fonts.googleapis.com/css2?family=Noto+Sans+KR

---

**다음 단계**: `/pdca design slack-mobile-preview`
