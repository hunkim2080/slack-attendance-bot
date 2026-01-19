# Perplexity 질문: Slack 봇 GAS 마이그레이션 문제 해결

## 현재 상황

Python 기반 Slack 출결 봇을 Google Apps Script (GAS)로 마이그레이션 중입니다. 원래 Python 코드는 Google Cloud Functions에서 정상 작동했지만, GAS로 변환 후 여러 문제가 발생했습니다.

## 원본 시스템 (Python)

- **프레임워크**: Slack Bolt (Python)
- **배포 환경**: Google Cloud Functions
- **주요 기능**:
  - Slash Commands: `/출근`, `/퇴근`, `/급여정산`, `/출근로그`, `/정산내역`, `/발주목록`
  - Interactive Actions: 버튼 클릭 처리 (자재기록, 현장사진 업로드, T-map 링크 등)
  - Google Sheets 연동 (출결 기록, 자재 사용, 급여 정산)
  - Google Calendar 연동 (현장 주소 조회)
  - Google Drive 연동 (폴더 생성)
  - 게임화 시스템 (레벨, 경험치, 각성 단계, 스킬)

## 현재 문제점

### 1. Slash Command가 작동하지 않음
- **증상**: `/출근`, `/퇴근` 명령어 실행 시 아무 반응이 없음
- **에러 로그**: 
  - `"ERROR: No valid data source found"`
  - `"Error parsing payload"`
  - `"e is undefined - this should not happen in production"` (에디터에서 직접 실행 시)

### 2. T-map 버튼 리다이렉트 문제
- **증상**: T-map 버튼 클릭 시 T-map 앱/웹사이트로 이동하지 않고 GAS 스크립트 페이지(`script.google.com/home?addr=...`)로 리다이렉트됨
- **시도한 해결책**:
  - `doGet` 함수로 리다이렉트 처리 시도 → GAS XSS 보호로 실패
  - 버튼 URL에 직접 T-map 웹 URL (`https://tmapapi.sktelecom.com/main/map.html?q=...`) 설정 → 여전히 GAS 스크립트로 이동
  - `PropertiesService`에 캐시된 Web App URL 삭제 시도 → 효과 없음

### 3. Interactive Actions (버튼) 404 에러
- **증상**: "자재사용대장", "현장사진업로드" 버튼 클릭 시 404 에러
- **해결 시도**: `doPost` 함수의 payload 파싱 로직 수정 → 일부 해결되었지만 여전히 불안정

### 4. Payload 파싱 불안정
- **증상**: Slack 요청 데이터를 파싱하는 과정에서 에러 발생
- **현재 코드**:
```javascript
function doPost(e) {
  try {
    if (!e) {
      Logger.log("ERROR: e is undefined");
      return ContentService.createTextOutput("");
    }
    
    let payload;
    if (e.postData && e.postData.type === "application/json") {
      payload = JSON.parse(e.postData.contents);
    } else if (e.parameter && e.parameter.payload) {
      payload = JSON.parse(e.parameter.payload);
    } else if (e.parameter) {
      payload = e.parameter; // Slash Command
    } else {
      Logger.log("ERROR: No valid data source found");
      return ContentService.createTextOutput("");
    }
    // ... 처리 로직
  } catch(error) {
    Logger.log("Error parsing payload: " + error);
    return ContentService.createTextOutput("");
  }
}
```

## 하고 싶은 것

1. **Slash Command 정상 작동**: `/출근`, `/퇴근` 등 모든 명령어가 정상적으로 작동하도록
2. **T-map 버튼 정상 작동**: 버튼 클릭 시 T-map 앱(모바일) 또는 웹사이트(PC)로 정상 리다이렉트
3. **Interactive Actions 정상 작동**: 모든 버튼이 404 에러 없이 정상 작동
4. **안정적인 Payload 파싱**: Slack의 다양한 요청 형식을 안정적으로 처리

## 기술 스택 및 제약사항

- **언어**: Google Apps Script (JavaScript ES5/ES6)
- **배포**: GAS Web App (배포 → 새 배포 → 웹 앱)
- **Slack 통신 방식**:
  - Slash Commands: `application/x-www-form-urlencoded` 형식으로 `e.parameter`에 직접 전달
  - Interactive Actions: `application/x-www-form-urlencoded` 형식으로 `e.parameter.payload`에 JSON 문자열로 전달
  - Event Subscriptions: `application/json` 형식으로 `e.postData.contents`에 전달
- **GAS 제약사항**:
  - `doPost`, `doGet` 함수는 웹 앱으로 배포되어야 외부 요청을 받을 수 있음
  - 에디터에서 직접 실행하면 `e` 파라미터가 `undefined`로 전달됨 (정상 동작)
  - XSS 보호로 인해 JavaScript 리다이렉트가 제한됨

## Slack App 설정

- **Slash Commands**: 각 명령어의 Request URL이 GAS Web App URL로 설정됨
- **Interactive Components**: Request URL이 GAS Web App URL로 설정됨
- **OAuth & Permissions**: 필요한 권한 모두 부여됨

## 질문

1. **Slack Slash Command가 GAS `doPost` 함수로 전달될 때 `e.parameter`에 어떤 형식으로 데이터가 들어오는가?**
   - 실제 예시 데이터 구조를 알려주세요
   - `e.postData`와 `e.parameter` 중 어느 것을 사용해야 하는가?

2. **GAS에서 Slack Interactive Actions의 버튼 URL을 T-map 앱/웹사이트로 직접 리다이렉트하는 방법은?**
   - GAS `doGet`을 통한 리다이렉트가 작동하지 않는 이유는?
   - 버튼의 `url` 속성에 직접 T-map URL을 넣었는데도 GAS 스크립트로 이동하는 이유는?

3. **GAS `doPost` 함수에서 Slack의 다양한 요청 형식을 안정적으로 파싱하는 베스트 프랙티스는?**
   - Slash Commands, Interactive Actions, Event Subscriptions를 모두 처리하는 방법
   - 에러 핸들링 및 로깅 방법

4. **현재 코드의 문제점과 수정 방법을 구체적으로 알려주세요.**

## 참고 파일

- `attendance-bot.gs`: 메인 진입점 (`doPost`, `doGet`)
- `utils.gs`: Slack 메시지 전송, T-map URL 생성
- `interactive-actions.gs`: Interactive Actions 핸들러
- `sheets-handler.gs`: Google Sheets 연동
- `game-system.gs`: 게임화 시스템

## 원본 Python 코드 참고

원본 Python 코드는 `main.py`에 있으며, Slack Bolt 프레임워크를 사용합니다:
- `@slack_app.command("/출근")`: Slash Command 핸들러
- `@slack_app.action("action_id")`: Interactive Action 핸들러
- `handler.handle(request)`: Flask 어댑터를 통한 요청 처리

---

**핵심 질문**: GAS에서 Slack 봇을 구현할 때 Slash Command와 Interactive Actions를 안정적으로 처리하고, 버튼 URL을 외부 앱/웹사이트로 리다이렉트하는 완전한 작동 코드를 제공해주세요.

