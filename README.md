# 슬랙 출퇴근 레벨업 시스템

슬랙을 통한 직원 출퇴근 관리 및 게임화 레벨업 시스템입니다.

## 🎮 주요 기능

### 출퇴근 관리
- 슬랙 명령어(`/출근`, `/퇴근`)로 출퇴근 기록
- Google Sheets에 자동 저장
- 위치 기반 출근 확인 (TMAP 연동)

### 레벨업 시스템
- **레벨 계산**: 3일 근무마다 레벨 1 상승
- **칭호 시스템**: 레벨 1~100까지 총 100개의 칭호
- **각성 단계**: 45일, 90일, 135일, 180일, 225일, 270일 달성 시 각성 단계 진행
- **일당 인상**: 각성 단계마다 일당 자동 인상

### 게임화 요소
- 레벨업 시 슬랙 DM으로 알림
- 각성 단계 달성 시 컷신 메시지
- 경험치 진행률 바 표시
- 다음 각성까지 남은 일수 표시

## 📁 프로젝트 구조

```
slack-attendance-bot/
├── main.py              # Google Cloud Functions 진입점
├── worker_main.py       # 출퇴근 처리 워커
├── sheets_handler.py    # Google Sheets 연동 및 레벨 계산
├── config.py            # 설정 파일
├── game-system.gs       # Google Apps Script 게임화 시스템
├── attendance-bot.gs    # Google Apps Script 출퇴근 핸들러
├── requirements.txt     # Python 의존성
└── docs/                # 문서 파일들
```

## 🚀 설치 및 설정

### 1. Python 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일 또는 환경 변수에 다음을 설정:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
GOOGLE_SHEETS_ID=your-spreadsheet-id
GCP_PROJECT=your-gcp-project
TASKS_LOCATION=asia-northeast3
```

### 3. Google Cloud 설정

1. **Google Cloud 프로젝트 생성**
2. **Cloud Functions 배포**:
   ```bash
   gcloud functions deploy slack_attendance_bot \
     --runtime python310 \
     --trigger-http \
     --allow-unauthenticated
   ```

### 4. Google Sheets 설정

1. **스프레드시트 생성**:
   - `AttendanceLog` 시트: 출퇴근 기록
   - `UserMaster` 시트: 사용자 정보
   - `Payroll` 시트: 급여 정산

2. **서비스 계정 설정**:
   - Google Cloud Console에서 서비스 계정 생성
   - JSON 키 파일 다운로드
   - 스프레드시트에 서비스 계정 이메일 공유

### 5. Slack 앱 설정

1. [Slack API](https://api.slack.com/apps)에서 앱 생성
2. **Bot Token Scopes** 추가:
   - `chat:write`
   - `users:read`
   - `commands`
3. **Slash Commands** 등록:
   - `/출근`: 출근 기록
   - `/퇴근`: 퇴근 기록

## 🎯 사용법

### 슬랙에서 사용

1. **출근**:
   ```
   /출근
   ```

2. **퇴근**:
   ```
   /퇴근
   ```

### 레벨 시스템

- **레벨 계산**: `레벨 = int(총 근무일수 / 3)`
- **레벨업**: 3일 근무할 때마다 자동 레벨업
- **칭호**: 레벨에 따라 자동 부여 (예: "현장 참관자", "줄눈 기술자", "줄눈 마스터")

### 각성 단계

| 단계 | 달성일수 | 일당 인상 |
|------|---------|----------|
| 1단계 | 45일 | 15만원 |
| 2단계 | 90일 | 17만원 |
| 3단계 | 135일 | 19만원 |
| 4단계 | 180일 | 21만원 |
| 5단계 | 225일 | 23만원 |
| 6단계 | 270일 | 25만원 |

## 🔧 개발

### 로컬 실행

```bash
# Cloud Functions 로컬 에뮬레이터 실행
functions-framework --target=slack_attendance_bot --port=8080
```

### 테스트

```bash
python test_sheets.py
```

## 📚 주요 파일 설명

### `worker_main.py`
- 출퇴근 처리 로직
- 레벨업 및 각성 단계 체크
- 슬랙 메시지 전송

### `sheets_handler.py`
- Google Sheets 연동
- 레벨 및 칭호 계산
- 근무일수 집계

### `game-system.gs`
- Google Apps Script 게임화 시스템
- 레벨 계산 함수
- 칭호 시스템
- 각성 단계 컷신

## ⚠️ 주의사항

- 민감한 정보(`client_secret.json`, `service-account-key.json`)는 절대 커밋하지 마세요
- `.gitignore`에 추가되어 있습니다
- 환경 변수는 안전하게 관리하세요

## 📝 라이선스

MIT License
"# slack-attendance-bot" 
