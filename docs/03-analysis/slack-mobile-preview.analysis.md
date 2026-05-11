---
name: slack-mobile-preview
type: analysis
version: 0.1.0
status: complete
phase: check
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
plan: docs/01-plan/features/slack-mobile-preview.plan.md
design: docs/02-design/features/slack-mobile-preview.design.md
match_rate: 100
match_rate_breakdown:
  structural: 100
  functional: 100
  contract: 100
gap_counts:
  critical: 0
  important: 0
  minor: 4
formula: "static-only: structural × 0.2 + functional × 0.4 + contract × 0.4"
agent: bkit:gap-detector
---

# Analysis — slack-mobile-preview (Match Rate 100%)

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | v5~v10 누적 페인포인트(스크린샷 5회 요구) 해소 + Ally 텍스트 추정 한계 극복 |
| **WHO** | 준 (1인 운영자, Galaxy S23+) |
| **RISK** | Playwright 50MB 의존성 / 슬랙 100% 재현 불가(90-95%) / Jinja2 추가 |
| **SUCCESS** | 향후 사이클 사용자 스크린샷 요청 0회 / 줄바꿈 정확도 ≥90% (Galaxy 기준) |
| **SCOPE** | 슬랙 + Galaxy S23+. 카카오톡/iPhone은 Phase 2 |

---

## 1. Overall Match Rate

```
Static-only = Structural × 0.2 + Functional × 0.4 + Contract × 0.4
            = 100 × 0.2     + 100 × 0.4     + 100 × 0.4
            = 20 + 40 + 40
            = 100%
```

| Category | Score | Status |
|---|:-:|:-:|
| Structural Match | **100%** | ✅ |
| Functional Depth | **100%** | ✅ |
| Contract Compliance | **100%** | ✅ |
| **Overall Match Rate** | **100%** | ✅ |

런타임 verification: 도구 사이클(CLI Python, 웹 UI/API 없음) → L1 API / L2 Playwright UI / L3 E2E는 **N/A**. 대신 단위 9 케이스 + smoke run + Ally 멀티모달 1회로 대체.

---

## 2. Structural Match — 100% (16/16)

| 항목 | Design 명세 | 실제 | 결과 |
|---|---|---|---|
| `scripts/preview_mobile.py` | §4.1 단일 entry | 278 lines | ✅ |
| `scripts/templates/slack_mobile.html.j2` | §4.2 Jinja2 외부 | 76 lines | ✅ |
| `tests/test_preview_mobile.py` | §4.3 / §8.2 — 7+ | 9 cases | ✅ |
| `requirements-dev.txt` | §11.1 신규 | playwright + jinja2 정확 2개 | ✅ |
| `.gitignore` `scripts/output/` | §11.1 / §14 | lines 37-39 | ✅ |
| `scripts/output/` 자동 mkdir | FR-07 | `OUTPUT_DIR.mkdir(parents=True, exist_ok=True)` | ✅ |
| `slack_mrkdwn_to_html(text)->str` | §4.1 | line 53, 일치 | ✅ |
| `fetch_message_from_actions_log(run_id)->str` | §4.1 | line 158, 일치 | ✅ |
| `resolve_message(source, run_id)->tuple` | §4.1 | line 195, 일치 | ✅ |
| `render_html(message_text)->str` | §4.1 | line 212, 일치 | ✅ |
| `screenshot_mobile(html, path)->None` | §4.1 | line 223, 일치 | ✅ |
| `GALAXY_S23_PLUS_VIEWPORT` 384×854 | FR-04 | lines 29-32 | ✅ |
| `GALAXY_S23_PLUS_DPR = 3` | FR-04 | line 33 | ✅ |
| `GALAXY_S23_PLUS_UA` (SM-S916N Android 14) | FR-04 | lines 34-38 | ✅ |
| Import 순서 PEP 8 | §10.2 | lines 12-21 | ✅ |
| 양방향 격리 (main↛preview, preview↛main) | §9.1 / NFR-06 | grep 결과 import 0 | ✅ |

---

## 3. Functional Depth — 100%

### 3.1 Plan FR-01 ~ FR-08

| FR | 요구 | 구현 위치 | 충족 |
|---|---|---|---|
| FR-01 | preview_mobile.py 신규 + fixture/stdin | `main()` lines 245-274 | ✅ |
| FR-02 | mrkdwn→HTML 변환 4종 | `slack_mrkdwn_to_html` 53-113 | ✅ |
| FR-03 | Noto Sans KR + Roboto + Noto Color Emoji | template lines 14, 22 | ✅ |
| FR-04 | Playwright Galaxy S23+ 384×854 DPR=3 | `screenshot_mobile` 223-238 | ✅ |
| FR-05 | `preview-{label}-{ts}.png` | lines 267-269 | ✅ |
| FR-06 | CLI fixture/stdin/actions-log | argparse 249-258 | ✅ |
| FR-07 | `scripts/output/` 자동 mkdir | line 264 | ✅ |
| FR-08 | requirements-dev.txt 격리 | 파일 존재, main reqs diff 0 | ✅ |

### 3.2 Design §4 함수 동작 깊이

| 함수 | Design 단계 | 구현 단계 | 깊이 |
|---|---|---|---|
| `slack_mrkdwn_to_html` | 6단계 | 동일 6단계 (NUL sentinel) | 100 |
| `fetch_message_from_actions_log` | 마커+prefix 제거 | line-based + prefix strip | 100 (Design 0.1.1 버그 수정) |
| `resolve_message` | 3 소스 분기 | 동일 | 100 |
| `render_html` | autoescape=False | 동일 + 주석 명시 | 100 |
| `screenshot_mobile` | sync_playwright + full_page=True | 동일, try/finally | 100 |

### 3.3 Placeholder 검사

| 검사 항목 | 결과 |
|---|---|
| `# TODO` / `# placeholder` | 0건 |
| 빈 함수 | 0건 |
| 디버그 print/console.log | 정당한 사용자 출력 2건 외 0건 |
| 빈 이벤트 핸들러 | N/A |

### 3.4 Design 0.1.1 → Implementation 의도된 변경 (strictly better)

| # | 변경 | 정당성 | 회귀 가드 |
|---|---|---|---|
| (a) | NUL-byte sentinel vs `___CODE_BLOCK_N___` | 사용자 텍스트 충돌 위험 0 | `test_mrkdwn_sentinel_collision_safety` |
| (b) | line-based slicing vs regex `^.*Z `... | Design regex가 gh log multiline 매칭 실패 | `test_fetch_actions_log_missing_markers_raises` |

→ Design v0.1.2로 후행 동기화 (이번 Check 완료 시 같이 진행).

---

## 4. Contract Compliance — 100%

### 4.1 Plan Success Criteria

| ID | 목표 | 결과 |
|---|---|---|
| SC-MP-1 | 스크린샷 100% 성공 | ✅ smoke 1/1 |
| SC-MP-2 | 줄바꿈 ≥90% | ⏳ 운영 측정 (구조 충족, Ally 1회 시각 검증 OK) |
| SC-MP-3 | 실행 ≤10s | ✅ 4.8s (52% 마진) |
| SC-MP-4 | 의존성 2개 (갱신) | ✅ playwright + jinja2 |
| SC-MP-5 | main.py 회귀 0 | ✅ 119 passed (110 기존 + 9 신규) |
| SC-MP-6 | 신규 테스트 ≥6 | ✅ 9 (50% 초과) |
| SC-MP-7 | 사용자 스크린샷 요청 0 (3 사이클) | ⏳ 운영 측정 |

### 4.2 Plan NFR-01 ~ NFR-07

| ID | 목표 | 결과 |
|---|---|---|
| NFR-01 ≤10s | 4.8s | ✅ |
| NFR-02 ≤200MB | 구조상 충족, 측정 대기 | ⏳ |
| NFR-03 dev 의존성 격리 2개 | requirements-dev.txt | ✅ |
| NFR-04 정확도 90-95% | Ally 1회 OK, 운영 정량화 대기 | ⏳ |
| NFR-05 OS 호환 | Playwright + pathlib | ✅ |
| NFR-06 main.py 영향 0 | grep import 0 | ✅ |
| NFR-07 신규 테스트 ≥6 | 9 | ✅ |

### 4.3 Design §6 Error Handling

| Design 행 | 실제 처리 | 결과 |
|---|---|---|
| playwright 미설치 | ImportError 자연 전파 | ✅ |
| chromium 미설치 | Playwright 안내 | ✅ |
| gh CLI 미설치 | CalledProcessError | ✅ |
| MSG-DUMP 마커 없음 | RuntimeError + 테스트 가드 | ✅ |
| 템플릿 누락 | TemplateNotFound | ✅ |
| OUTPUT_DIR 쓰기 권한 X | OSError | ✅ |
| 빈 입력 | 정상 (Design 명세대로) | ✅ |

### 4.4 Design §8 Test Plan ↔ 실제 테스트 매핑

| Design # | 실제 함수 | 결과 |
|---|---|---|
| L1-prev-1 | `test_mrkdwn_code_block_to_pre` | ✅ |
| L1-prev-2 | `test_mrkdwn_inline_code` | ✅ |
| L1-prev-3 | `test_mrkdwn_bold` | ✅ |
| L1-prev-4 | `test_mrkdwn_html_escape` | ✅ |
| L1-prev-5 | `test_mrkdwn_newline_to_br` | ✅ |
| L1-prev-6 | `test_mrkdwn_preserves_code_block_specials` | ✅ |
| L1-prev-7 | `test_fetch_actions_log_extracts_dump` | ✅ |
| L1-prev-7b (추가) | `test_fetch_actions_log_missing_markers_raises` | ✅ §6 에러 강화 |
| L1-prev-8 (추가) | `test_mrkdwn_sentinel_collision_safety` | ✅ Architecture coaching 가드 |

---

## 5. Gap Classification

### 5.1 Critical Gaps — **0건**

### 5.2 Important Gaps — **0건**

### 5.3 Minor Gaps — 4건 (모두 Design 문서 후행 동기화)

| # | 항목 | Evidence | 권고 |
|---|---|---|---|
| MIN-1 | Design §4.1 코드 예시에 `___CODE_BLOCK_N___` placeholder 잔존 (실제는 NUL-byte) | design.md 301-302, 308-309 / preview_mobile.py 43-46 | Design v0.1.2: §4.1 NUL-byte로 교체 + Architecture coaching 사유 명시 |
| MIN-2 | Design §4.1 `fetch_message_from_actions_log` regex 예시 (실제는 line-based) | design.md 386-392 / preview_mobile.py 155, 175-192 | Design v0.1.2: §4.1 line-based slicing 예시로 교체 + 사유 명시 |
| MIN-3 | Design §8.3 "117 단위 케이스" → 실제 119 | design.md 691 / pytest 119 passed | Design v0.1.2: 119로 갱신 |
| MIN-4 | Design §8.2 7행 → 실제 9 테스트 (L1-prev-7b, L1-prev-8) | design.md §8.2 / 테스트 9개 | Design v0.1.2: §8.2 표에 2행 추가 |

→ **이번 Check 단계에서 같이 처리** (gap-detector 정적 분석 별개로 문서 정합성 마무리).

---

## 6. Decision Record Verification

| Layer | 결정 | 구현 반영 | 결과 |
|---|---|---|---|
| [Plan] | Galaxy S23+ 384×854 DPR=3 | `GALAXY_S23_PLUS_*` 상수 정확 | ✅ |
| [Plan] | Noto Sans KR + Roboto + Noto Color Emoji | template font-family | ✅ |
| [Plan] | main.py 의존성 0 (양방향 격리) | grep 결과 import 0 | ✅ |
| [Design] | Option C (Pragmatic Balance) | 단일 entry + 외부 .j2 | ✅ |
| [Design] | OQ-1 Playwright | sync_playwright 사용 | ✅ |
| [Design] | OQ-2 Jinja2 | Environment + FileSystemLoader | ✅ |
| [Design] | OQ-3 `preview-{label}-{ts}.png` | line 269 정확 포맷 | ✅ |
| [Design] | OQ-5 이모지 사전 운영 중 발견 케이스만 (YAGNI) | 미구현 (의도) | ✅ |

→ Decision Record Chain 100% 일치.

---

## 7. Strategic Alignment (Phase 3)

| 질문 | 답 |
|---|---|
| 구현이 PRD/Plan의 핵심 문제(WHY)를 다루나? | ✅ v5~v10 페인포인트 해소 — Ally 멀티모달 검증 1회 실증 |
| Plan Success Criteria 달성? | 정적 5/7 ✅ + 운영 측정 2/7 ⏳ |
| Design 핵심 결정(아키텍처/데이터모델/API) 따랐나? | 8/8 ✅ |
| 전략적 misalignment? | 없음 |

---

## 8. Runtime Verification (도구 사이클 변형)

도구 사이클이라 통상 L1 API / L2 Playwright UI / L3 E2E는 **N/A**. 다음으로 대체:

| Layer | 항목 | 결과 |
|---|---|---|
| L1 단위 | pytest 9 cases | ✅ 9 passed |
| L1 전체 회귀 | pytest 전체 | ✅ 119 passed in 2.15s |
| Smoke run | `python scripts/preview_mobile.py --source fixture` | ✅ 4.8s, 128KB PNG |
| 멀티모달 검증 | Ally가 PNG Read | ✅ 1회 성공 (페인포인트 해소 실증) |

---

## 9. Checkpoint 5 Decision

| 옵션 | 적용 |
|---|---|
| 지금 모두 수정 | **선택됨** — Minor 4건 (Design 후행 동기화) 즉시 처리. Match Rate는 이미 100%지만 코드/문서 정합 마무리. |
| Critical만 수정 | N/A (Critical 0건) |
| 그대로 진행 | 보류 — 문서 정합성 위해 4건 처리 후 Report 단계 |

---

## 10. 100% 도달 평가 — 솔직 진단

| 질문 | 답 |
|---|---|
| 현재 Match Rate가 정확히 100%인가? | **그렇다 (정적 분석 기준).** |
| 본질적으로 100%를 막는 갭이 있나? | **없다.** Design 0.1.1 → 구현의 2건 변경은 strictly better. |
| 운영 시 100% 유지 가능한가? | SC-MP-2 / SC-MP-7 / NFR-02 / NFR-04는 운영 시점 측정 — 구조는 충족. |
| 이번 사이클을 100%로 닫을 자격이 있나? | **있다.** 정적 갭 0 + smoke run 성공 + 멀티모달 1회 검증. |

---

## 11. Next Steps

1. **Design v0.1.2 후행 동기화** (Minor 4건 해소, ~5분)
2. **Report 단계 진입**: `/pdca report slack-mobile-preview`
3. **운영 측정 마커 등록** (다음 v11 메시지 사이클에서 SC-MP-2 / SC-MP-7 회고 항목 묶기)

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 0.1.0 | 2026-05-11 | Initial. Match Rate 100% (정적). gap-detector + 직접 3축 분석. Minor 4건 문서 후행 동기화 권고. | jooladen (with Ally + bkit:gap-detector) |
