# 🟢 운영 가이드 (초딩용)

> "배포 끝났어요! 이제부터 알람시계예요. 매일 아침 자동으로 옵니다."

생성: 2026-05-11

---

## 🎉 지금 상황

✅ 슬랙에 첫 메시지 도착함
✅ GitHub Actions가 매일 알아서 발송
✅ **컴퓨터를 꺼도, 노트북을 닫아도, 비행기를 타도** 매일 같은 시간에 슬랙에 메시지가 와요

비유: **알람시계를 맞춰놓은 거예요.** 이제 거실에 두고 외출해도 새벽에 알아서 울려요.

---

## ⏰ 일정

| 항목 | 값 |
|---|---|
| 도착 시각 | **매일 KST 06:00 ~ 06:30** |
| 왜 정각이 아닌 윈도우? | GitHub의 무료 알람시계는 5–15분 정도 늦을 수 있어요 (정상) |
| 다음 자동 발송 | **내일 아침 6시쯤** |
| 멈추는 조건 | 본인이 명시적으로 끄기 전까지 계속 발송 |
| 비용 | **0원** (무료 한도 안에서 평생) |

---

## 🔍 내일 메시지 도착 확인하는 3가지 방법

### 방법 A — 슬랙에서 (가장 쉬움)

내일 아침 슬랙 채널 열어서 메시지 1개 떠 있으면 끝. 끝.

### 방법 B — GitHub 화면에서

링크 열기 → 가장 위에 ✅ 녹색 체크가 있으면 성공:

**https://github.com/jooladen/morning_us_index/actions**

### 방법 C — PowerShell 한 줄 (개발자 스타일)

```powershell
gh run list --workflow="Daily US Index Report" --limit 5
```

최근 5번 실행 결과를 줄줄이 보여줘요. `success`라고 적혀 있으면 OK.

---

## 🛠️ 바꾸고 싶을 때

### 시간 바꾸기 (예: 7시로)

`.github/workflows/daily_report.yml` 파일 열어서:

```
- cron: '0 21 * * *'      ← 이 줄 찾아서
- cron: '0 22 * * *'      ← 이렇게 (UTC 22 = KST 07)
```

저장하고 깃허브에 push:

```powershell
cd C:\Users\jooladen\Desktop\stock\morning_us_index
git add .github/workflows/daily_report.yml
git commit -m "chore: 발송 시간 KST 06 → 07로 변경"
git push
```

| 원하는 KST | UTC | cron 값 |
|---|---|---|
| 06:00 (현재) | 21:00 전날 | `'0 21 * * *'` |
| 07:00 | 22:00 전날 | `'0 22 * * *'` |
| 08:00 | 23:00 전날 | `'0 23 * * *'` |
| 평일만 (한국 평일 기준) | UTC 21:00 화–토 | `'0 21 * * 2-6'` |

> 비유: 알람시계의 시간 다이얼을 돌리는 거예요. 다이얼 = `cron` 줄.

### 잠깐 멈추기 (휴가 등)

화면에서 멈추는 게 가장 쉬워요:

1. https://github.com/jooladen/morning_us_index/actions
2. 왼쪽 사이드바 **`Daily US Index Report`** 클릭
3. 오른쪽 위 **`···`**(점 3개) → **Disable workflow**

다시 켜고 싶을 때: 같은 자리에 **Enable workflow** 버튼이 생겨 있어요.

> 비유: 알람시계 ON/OFF 스위치. 끄는 거 잊지 말고, 켜는 것도 잊지 말기.

### 영원히 끄기 (이 프로젝트 더 이상 안 쓸 때)

방법 1: 워크플로우 파일만 삭제

```powershell
cd C:\Users\jooladen\Desktop\stock\morning_us_index
Remove-Item .github\workflows\daily_report.yml
git add -A
git commit -m "chore: 자동 발송 종료"
git push
```

방법 2: repo 자체 삭제 (가장 확실)

GitHub 화면 → repo → **Settings** → 맨 아래 **Danger Zone** → **Delete this repository** → 이름 적고 confirm.

---

## 🚨 메시지가 안 오면 (트러블슈팅)

당황하지 말고 순서대로:

### 1단계 — 어디서 막혔는지 보기

링크 열기: https://github.com/jooladen/morning_us_index/actions

가장 위 행에:
- ✅ 녹색 = 성공인데 슬랙에 안 옴 → **2단계로**
- ❌ 빨간 = 실패 → **3단계로**
- 🟡 노란 점 = 아직 실행 중 → 잠깐 기다리기 (보통 1분 안)
- 아예 실행 행이 없음 → cron이 안 돌아간 것 → **4단계로**

### 2단계 — 슬랙 쪽 문제 의심

- 슬랙 채널이 맞는지? Webhook 발급할 때 잘못된 채널 골랐을 수도
- 슬랙 알림 설정이 무음으로 돼 있나?
- ⚠️ 에러 메시지가 따로 와 있는지? 그럼 본 메시지가 막힌 거예요

### 3단계 — 빨간 X 클릭해서 로그 보기

빨간 X 행 클릭 → 가장 빨간 단계 클릭 → **에러 메시지 화면을 통째로 캡처해서** Claude에게 보여주세요.

가장 흔한 원인:
- `SLACK_WEBHOOK_URL` 비밀번호 이름 오타 (대소문자!)
- Webhook URL이 만료/삭제됨 → 새로 발급받아야

### 4단계 — Actions 자체가 멈췄나

GitHub 화면 → repo → **Settings** → **Actions** → **General**
→ "Allow all actions and reusable workflows" 가 선택돼 있는지 확인

> 처음 한 번은 잘 동작했는데 그 후로 한 번도 안 돌면, GitHub가 60일 이상 push가 없는 repo는 schedule cron을 자동으로 멈춰요. 아무 변경이나 1번 push하면 다시 살아나요.

---

## 📅 자주 묻는 질문

**Q. 한국 공휴일에도 메시지가 와요?**
A. 네. 미국 시장이 열려 있으면 무조건 와요.

**Q. 미국 공휴일(추수감사절 같은)에는?**
A. 마지막 거래일의 종가를 보내고, **(미 증시 휴장 / 마지막 거래일)** 표시가 같이 와요.

**Q. 매번 똑같은 데이터인데 토요일에도 와요?**
A. 토요일 KST 06:00에는 **금요일(미국 마감일) 종가**를 보내요. 일요일에도 같은 데이터(휴장 표시 같이). 월요일은 또 같은 금요일 데이터.

**Q. 한 달에 돈 나가요?**
A. 안 나가요. 우리 사용량은 월 ~30분이고 무료 한도가 2,000분이에요(public repo는 무제한).

**Q. 다른 지수도 추가하고 싶어요. (예: 다우, KOSPI)**
A. `config.py` 파일 열어서 `TICKERS` 목록에 한 줄 추가하면 돼요:

```python
TICKERS = [
    ("^IXIC", "나스닥"),
    ("^GSPC", "S&P 500"),
    ("^DJI", "다우"),         # ← 추가
]
```

저장하고 push하면 다음날부터 3개 지수가 같이 와요.

**Q. AI 분석도 같이 받고 싶어요.**
A. **Phase 2**에서 만들 거예요. `Claude`에게 `/pdca pm morning-us-index-ai` 라고 하면 새 사이클 시작해줘요.

---

## ▶ 이제 뭐?

기본 운영은 끝났어요. 이번 사이클을 **공식 종료**하려면:

```
/pdca report morning-us-index
```

라고 Claude에게 말하면 PDCA 종료 보고서가 자동으로 만들어져요. 이건 내일 도착 1번 더 확인하고 해도 돼요.

> 💡 며칠 운영해보고 → 별 문제 없으면 → Phase 2(AI 분석) 추가 PDCA 사이클로 넘어가는 흐름이 자연스러워요.
