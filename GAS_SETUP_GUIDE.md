# GAS 전환 코드 설정 가이드

## 📁 파일 구조

```
attendance-bot.gs          # 메인 진입점 (doPost, doGet)
sheets-handler.gs          # Google Sheets 연동 함수
game-system.gs             # 게임화 시스템 함수
interactive-actions.gs     # Interactive Actions 핸들러
utils.gs                   # 유틸리티 함수
```

## 🔧 설정 방법

### 1. Google Apps Script 프로젝트 생성

1. [Google Apps Script](https://script.google.com) 접속
2. "새 프로젝트" 클릭
3. 프로젝트 이름: "디테일라인 출결 봇"

### 2. 파일 생성 및 코드 복사

1. 각 `.gs` 파일의 내용을 GAS 에디터에 복사
2. 파일 이름은 자동으로 함수명 기반으로 생성됨 (수동으로 변경 가능)

### 3. Google Sheets 연결

1. 사용할 Google Sheets를 열기
2. GAS 에디터에서 `SS = SpreadsheetApp.getActiveSpreadsheet();` 부분 확인
   - 현재 열려있는 시트를 사용하려면 그대로 사용
   - 특정 시트 ID를 사용하려면:
   ```javascript
   const SS = SpreadsheetApp.openById("시트_ID");
   ```

### 4. PropertiesService 설정 (환경 변수)

**GAS 에디터 → 프로젝트 설정 → 스크립트 속성**에서 다음 값들을 설정:

| 속성 이름 | 설명 | 예시 |
|---------|------|------|
| `SLACK_BOT_TOKEN` | Slack Bot Token (xoxb-로 시작) | `xoxb-5337415751251-...` |
| `SLACK_SIGNING_SECRET` | Slack Signing Secret | `07af65842396972fb0f617f87d682761` |
| `SPREADSHEET_KEY` | Google Sheets ID (시트 URL에서 /d/ 뒤) | `1VUTFpY_kaZQno9G3cfq-5guDCQvyJQGCL0AKJQ_MgZ0` |
| `ADMIN_SLACK_IDS` | 관리자 Slack ID (쉼표로 구분) | `U059H02UNF9,U12345678` |
| `GOOGLE_CALENDAR_ID` | Google Calendar ID | `4cbc5b4bec77ee0dd17f929de422fe61ab57413a383963266d811d614d84b074@group.calendar.google.com` |
| `GOOGLE_DRIVE_PARENT_FOLDER_ID` | Google Drive 부모 폴더 ID | `1SPc_60nfGeiDKQISef80jtV3TNnzAGCW` |
| `WEATHER_API_KEY` | 기상청 API 키 | `e8a0d87748fac1598848802a9ff22afc2b55bcc7c5e10c9a060da7e722da2472` |
| `SITE_ADDRESS` | 기본 현장 주소 | `서울시 강남구 테헤란로 123` |

**또는 코드에서 직접 설정:**

```javascript
// utils.gs 파일 상단에 추가
function setupProperties() {
  const props = PropertiesService.getScriptProperties();
  props.setProperty("SLACK_BOT_TOKEN", "xoxb-...");
  props.setProperty("SLACK_SIGNING_SECRET", "...");
  // ... 나머지 설정
}
```

### 5. Google Sheets 시트 구조 확인

다음 시트들이 있어야 합니다:

1. **AttendanceLog** (출퇴근 기록)
   - 컬럼: 날짜 | 이름 | 시간 | 구분 | 비고

2. **UserMaster** (사용자 마스터)
   - 컬럼: 이름 | Slack_ID | 기본근무일수 | ... | 주소

3. **MaterialLog** (자재 사용 기록)
   - 컬럼: 날짜시간 | 이름 | 방 이름 | 색상 코드 | 사용량

4. **MaterialOrder** (발주 관리)
   - 컬럼: 날짜시간 | 이름 | 발주내용 | 발주완료 처리시간

5. **Incentive** (인센티브)
   - 컬럼: 날짜 | 이름 | 금액 | 내용

### 6. Web App 배포

**⚠️ 중요**: T-map 버튼이 작동하려면 반드시 Web App으로 배포해야 합니다.

**⚠️ 매우 중요: "배포 관리 → 수정"은 사용하지 마세요!**
- "배포 관리 → 수정"을 사용하면 코드 변경사항이 제대로 반영되지 않을 수 있습니다
- **반드시 "배포 → 새 배포"를 사용하세요**

**올바른 배포 방법:**
1. GAS 에디터에서 **배포 → 새 배포** 클릭
2. 유형: **웹 앱** 선택
3. 설정:
   - 실행 사용자: **나**
   - 액세스 권한: **모든 사용자** (또는 조직 내)
4. **배포** 클릭
5. **웹 앱 URL** 복사 (예: `https://script.google.com/macros/s/.../exec`)
   - URL은 반드시 `/exec`로 끝나야 합니다
6. (선택사항) PropertiesService에 URL 저장:
   - GAS 에디터 → 프로젝트 설정 → 스크립트 속성
   - 속성 이름: `WEB_APP_URL`
   - 속성 값: 복사한 Web App URL

**코드 수정 후 재배포:**
- 코드를 수정한 후에는 **반드시 "배포 → 새 배포"**를 사용하여 새 버전으로 배포해야 합니다
- "배포 관리 → 수정"을 사용하면 변경사항이 반영되지 않을 수 있습니다

### 7. Slack App 설정

1. [Slack API](https://api.slack.com/apps) 접속
2. 해당 앱 선택
3. **Slash Commands** 메뉴에서 각 명령어 등록:
   - `/출근`
   - `/퇴근`
   - `/급여정산`
   - `/출근로그`
   - `/정산내역`
   - `/발주목록`
   - `/hello`
   - `/netcheck`
4. 각 명령어의 **요청 URL**에 GAS Web App URL 입력
5. **Interactive Components** 메뉴:
   - **요청 URL**에 GAS Web App URL 입력
   - **Interactivity** 활성화
6. **OAuth & Permissions**에서 필요한 권한 확인:
   - `chat:write`
   - `chat:write.public`
   - `commands`
   - `users:read`

### 8. 권한 설정

1. GAS 에디터에서 **실행 → 함수 실행** 클릭
2. 처음 실행 시 권한 요청 팝업이 나타남
3. **권한 검토** → **고급** → **프로젝트로 이동** → **허용** 클릭
4. 필요한 권한:
   - Google Sheets 읽기/쓰기
   - Google Calendar 읽기
   - Google Drive 읽기/쓰기
   - 외부 URL 접근 (Slack API, 날씨 API)

## 🧪 테스트

### 1. 기본 연결 테스트
```
/hello
```

### 2. 출퇴근 테스트
```
/출근
/퇴근
```

### 3. 버튼 테스트
- 퇴근 후 "자재기록" 버튼 클릭
- 퇴근 후 "폴더생성" 버튼 클릭

## ⚠️ 주의사항

1. **시트 이름 확인**: 코드의 `SHEET_NAMES` 상수와 실제 시트 이름이 일치해야 함
2. **PropertiesService 설정**: 모든 환경 변수가 올바르게 설정되어야 함
3. **권한 설정**: Google Sheets, Calendar, Drive 접근 권한이 필요
4. **Slack Webhook URL**: GAS Web App URL이 올바르게 설정되어야 함
5. **에러 로그**: GAS 에디터의 **실행** → **실행 기록**에서 에러 확인 가능

## 🔍 문제 해결

### 버튼이 작동하지 않을 때
1. Slack App의 Interactive Components 설정 확인
2. GAS Web App URL이 올바른지 확인
3. `doPost()` 함수의 Interactive Actions 처리 로직 확인

### 시트 접근 오류
1. 시트가 GAS와 같은 Google 계정에 있는지 확인
2. 시트 이름이 정확한지 확인
3. 시트 공유 설정 확인

### 날씨 API 오류
1. `WEATHER_API_KEY`가 올바른지 확인
2. API 할당량 확인
3. 주소 → 격자 좌표 변환 로직 확인

## 📝 추가 설정

### 시트 ID 직접 지정 (선택사항)

`attendance-bot.gs` 파일 상단 수정:

```javascript
// 현재: 활성 시트 사용
const SS = SpreadsheetApp.getActiveSpreadsheet();

// 변경: 특정 시트 ID 사용
const SPREADSHEET_ID = "1VUTFpY_kaZQno9G3cfq-5guDCQvyJQGCL0AKJQ_MgZ0";
const SS = SpreadsheetApp.openById(SPREADSHEET_ID);
```

---

**작성 완료일**: 2025-12-30
**버전**: 2.0

