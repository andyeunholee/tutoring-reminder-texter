# Tutoring Reminder Texter

날짜를 선택하면 Google Calendar(`andy.lee@eliteprep.com`)에서 `[TUT]` 수업을 찾아,
선생님(1:1)과 학생+부모님(그룹)에게 Google Voice로 영어 리마인드 문자를 보내는 앱.
**보내기 전에 항상 목록을 검토하고, 받을 사람을 체크하고, 내용을 수정할 수 있습니다.**

## 첫 설정 (한 번만)

1. **가상환경 + 패키지** (이미 되어 있으면 생략)
   ```
   py -3.14 -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   .venv\Scripts\playwright install chromium
   ```

2. **Google 인증** — 처음 실행 시 브라우저가 열리면 `andyeunholee@gmail.com`으로
   동의하세요. `token_tutoring.json`이 생성됩니다.
   ⚠️ `config.py`의 SCOPES를 바꾸면 `token_tutoring.json`을 삭제하고 다시 동의해야 합니다.

3. **명단 시트** — `create_roster_sheet.bat`을 실행하면 만들어집니다.
   출력된 `ROSTER_SPREADSHEET_ID=...` 줄을 `.env`에 넣으세요.
   (이미 쓰고 계신다면 `.env`에 시트 ID가 들어 있습니다.)

   시트를 열어 **전화번호를 채우세요** (Teachers 탭: Phone / Students 탭:
   Student Phone, Parent Phone). Display Name 칸에 문자에 쓰일 이름을 넣으면
   그 이름이 쓰입니다 (예: `Kyuheon (Andrew) Ahn` → `Andrew`). 비워두면
   괄호만 뗀 이름을 씁니다.

   나중에 새 학생/선생님이 생기면 **create_roster_sheet.bat**을 실행하세요.
   캘린더(지난 60일 ~ 앞으로 120일)를 훑어서 **빠진 이름만 추가**합니다.
   기존 행과 전화번호는 절대 건드리지 않습니다.

   캘린더에 적힌 이름이 시트 이름과 다르면 **Aliases 탭**에 매핑을 추가하세요:
   `캘린더에 적힌 이름 | student | 시트의 정확한 이름`

4. **Google Voice 로그인** — `login_google_voice.bat` 실행.
   브라우저가 열리면 Google Voice 번호를 가진 계정으로 로그인하고,
   **문자 목록이 보일 때까지 기다렸다가 창을 닫으세요.** 스크립트가 자동으로
   로그인 저장 여부를 확인해 SUCCESS/실패를 알려줍니다.

   세션은 몇 달에 한 번씩 만료되니, 발송이 "Not logged in"이라고 하면
   이 배치파일을 다시 실행하면 됩니다.

   ⚠️ **"로그인할 수 없음 / 브라우저 또는 앱이 안전하지 않을 수 있습니다"** 가
   뜬다면 자동화 브라우저가 감지된 것입니다. 이 프로그램은 이를 피하려고
   **실제 설치된 Chrome**을 씁니다 (`GV_BROWSER_CHANNEL=chrome`).
   그래도 막히면 `.env`에 `GV_BROWSER_CHANNEL=msedge`를 넣어 Edge로 바꿔보세요.

   브라우저 프로필은 `%LOCALAPPDATA%\TutoringReminder\gv_profile`에 저장됩니다
   (Google Drive 폴더에 두면 프로필이 깨져서 로컬 디스크를 씁니다).

## 다른 PC에서 설치하기

```
git clone https://github.com/andyeunholee/tutoring-reminder-texter.git
cd tutoring-reminder-texter
setup_new_pc.bat
```

`setup_new_pc.bat`이 Python 확인 → 가상환경 생성 → 패키지·브라우저 설치까지
자동으로 하고, **손으로 해야 할 남은 일을 화면에 알려줍니다.**

저장소에 없는 것 (보안상 일부러 제외):

| 파일 | 어떻게 |
|---|---|
| `credentials.json` | 기존 PC에서 USB로 복사 ⚠️ 이메일·채팅 금지 |
| `.env`의 `ROSTER_SPREADSHEET_ID` | 기존 PC의 `.env`에서 값만 복사, 또는 `create_roster_sheet.bat` 실행 |
| Google 계정 동의 | PC마다 한 번씩 (앱 첫 검색 시 자동으로 뜸) |
| Google Voice 로그인 | PC마다 한 번씩 `login_google_voice.bat` |

토큰 파일(`token_*.json`)은 PC 간에 옮기지 마세요. 각 PC에서 새로 받는 것이
안전합니다. Google Chrome도 설치돼 있어야 합니다.

## 매일 사용법

```
run_app.bat
```
1. 날짜 선택 → **Search calendar**
2. 문자 목록 검토: 체크박스로 받을 사람 선택, 내용 수정
3. 사이드바 **Send mode**:
   - `Preview only` — 화면으로만 확인 (기본값)
   - `Browser rehearsal` — 브라우저가 문자를 작성해보고 스크린샷만 남기고 **보내지 않음**
   - `LIVE SEND` — 실제 발송
4. **Send N selected messages** 클릭

## 매일 오후 4시에 자동으로 띄우기

```
setup_daily_task.bat
```
한 번만 실행하면 Windows 작업 스케줄러에 등록됩니다. 매일 오후 4시에
**다음날 [TUT] 일정을 이미 검색한 상태로** 앱이 열립니다.

- **문자가 자동으로 나가지는 않습니다.** 검토하고 직접 보내기 버튼을 누르셔야 합니다.
- 시간 바꾸기: `setup_daily_task.bat 15:30`
- 지금 바로 실행: `schtasks /run /tn "Tutoring Reminder Texter - Daily"`
- 없애기: `schtasks /delete /tn "Tutoring Reminder Texter - Daily" /f`

컴퓨터가 켜져 있고 로그인된 상태여야 실행됩니다. 4시에 자고 있었다면
깨운 직후에 실행됩니다.

특정 날짜로 열고 싶으면 주소창에 직접 넣으셔도 됩니다:
`http://localhost:8501/?date=2026-08-01&auto=1`

### 안전하게 테스트하기
사이드바 "Redirect ALL messages to this number"에 본인 번호를 넣으면
모든 문자가 그 번호로만 갑니다. 실전 전에 꼭 한 번 해보세요.

### 잘못된 사람에게 가지 않도록 하는 장치
문자를 작성한 뒤 **화면에 올라간 수신자 번호를 프로그램이 직접 읽어서**
의도한 번호와 대조합니다 (로그의 `Recipients verified:` 줄). 하나라도
다르면 발송하지 않고 실패로 처리합니다. 1:1 발송은 대화창 주소가 요청한
번호와 일치하는지도 확인합니다.

### 처음 문자하는 번호
대화 이력이 없는 번호는 대화창 주소로 바로 못 들어갑니다. 이 경우
자동으로 "새 메시지" 방식으로 전환하니 따로 하실 일은 없습니다.

## 문제 해결
- **"Not logged in to Google Voice"** → `login_google_voice.bat` 실행 후 재시도.
  (문자는 한 통도 시도되지 않으니 안전합니다.)
- **"profile is already in use"** → 자동화 브라우저 창을 닫고 재시도
- **이름을 못 찾음 (빨간 표시)** → 시트의 Students/Teachers 탭에 행 추가, 또는
  Aliases 탭에 `캘린더에 적힌 이름 | student | 시트의 정확한 이름` 추가
- **문자 발송 실패** → `debug_screenshots\` 폴더의 스크린샷 확인.
  Google Voice 화면이 바뀌었을 수 있음 (rehearsal 모드로 먼저 점검)
- 발송 도중 브라우저를 닫으면 남은 문자는 `skipped`로 표시되고,
  **Retry failed/skipped only** 버튼으로 안 나간 것만 다시 보낼 수 있습니다.
- **SSL / 인증서 오류가 난다면** — 이 프로젝트는 Google Drive 폴더(H:)에 있는데,
  Google Drive 가상 파일시스템에서는 Python이 SSL 인증서 파일을 못 읽습니다
  (내용이 같아도 핸드셰이크가 끊깁니다). `config.py`가 시작할 때 인증서를
  `%LOCALAPPDATA%\TutoringReminder\cacert.pem`으로 복사해 우회합니다.
  이 폴더를 지웠다면 앱을 다시 실행하면 자동으로 다시 만듭니다.

## 구조
- `src/tut_parser.py` — 이벤트 제목 파싱 (취소 감지, v/? 마커 제거, 다중 학생)
- `src/roster.py` — 시트 명단 로드 + 이름 매칭 (별명/부분이름/Aliases)
- `src/message_builder.py` — 받는 사람별 문자 생성 (같은 날 여러 수업 합침)
- `sms/gv_sender.py` — Google Voice 발송 (브라우저 1번 열어 여러 통 처리)
- `app.py` — Streamlit 화면

테스트: `.venv\Scripts\python -m pytest tests -q`
