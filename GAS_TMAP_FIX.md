# T-map 버튼 연결 문제 해결 가이드

## 문제 상황
- "귀환스킬발동" 버튼 클릭 시 연결 안 됨
- "오늘 현장 T-map 열기" 버튼 클릭 시 연결 안 됨

## 원인
`ScriptApp.getService().getUrl()`이 Web App 배포 전에는 `null`을 반환하거나, URL 생성 로직에 문제가 있을 수 있습니다.

## 해결 방법

### 1. `utils.gs` 수정 완료

주요 변경사항:
- `getWebAppUrl()` 헬퍼 함수 추가
- PropertiesService에 URL 캐싱
- 에러 처리 강화
- 모든 T-map 버튼 생성 함수에서 `getWebAppUrl()` 사용

### 2. GAS Web App 배포 확인

**중요**: T-map 버튼이 작동하려면 **반드시 Web App으로 배포**되어 있어야 합니다.

#### 배포 방법:
1. GAS 에디터에서 **배포 → 새 배포** 클릭
2. 유형: **웹 앱** 선택
3. 설정:
   - 실행 사용자: **나**
   - 액세스 권한: **모든 사용자** (또는 조직 내)
4. **배포** 클릭
5. **웹 앱 URL** 복사 (예: `https://script.google.com/macros/s/.../exec`)

#### URL 확인:
- URL이 `/exec`로 끝나야 합니다
- 예: `https://script.google.com/macros/s/AKfycbz.../exec`

### 3. PropertiesService에 URL 저장 (선택사항)

배포 후 URL을 PropertiesService에 저장하면 더 빠르게 접근할 수 있습니다:

```javascript
// GAS 에디터에서 실행할 함수
function setWebAppUrl() {
  const url = ScriptApp.getService().getUrl();
  if (url) {
    PropertiesService.getScriptProperties().setProperty("WEB_APP_URL", url);
    Logger.log("Web App URL saved: " + url);
  } else {
    Logger.log("Error: Web App not deployed yet");
  }
}
```

**실행 방법:**
1. GAS 에디터에서 위 함수 추가
2. 함수 선택 후 **실행** 클릭
3. 권한 승인 후 완료

### 4. `doGet` 함수 확인

`attendance-bot.gs`의 `doGet` 함수가 제대로 구현되어 있는지 확인:

```javascript
function doGet(e) {
  const addr = e.parameter.addr;
  if (!addr) return HtmlService.createHtmlOutput("주소가 없습니다.");
  
  // T-map 앱 열기 로직
  // ...
}
```

### 5. 테스트 방법

#### A. URL 직접 테스트
브라우저에서 다음 URL로 접근:
```
https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec?addr=서울시 강남구
```

**예상 결과:**
- T-map 앱이 열리거나
- 웹 지도가 표시됨

#### B. 버튼 클릭 테스트
1. `/출근` 또는 `/퇴근` 명령어 실행
2. T-map 버튼 클릭
3. T-map 앱 또는 웹 지도가 열리는지 확인

### 6. 문제 해결 체크리스트

- [ ] GAS Web App이 배포되었는가?
- [ ] Web App URL이 올바른가? (`/exec`로 끝나는지 확인)
- [ ] `doGet` 함수가 `attendance-bot.gs`에 있는가?
- [ ] PropertiesService에 `WEB_APP_URL`이 설정되어 있는가? (선택사항)
- [ ] 브라우저에서 URL 직접 접근 시 작동하는가?

### 7. 여전히 작동하지 않는 경우

#### A. GAS 실행 기록 확인
1. GAS 에디터 → **실행 → 실행 기록**
2. `getWebAppUrl` 함수 실행 기록 확인
3. 에러 메시지 확인

#### B. 수동 URL 설정
PropertiesService에 직접 URL 설정:

1. GAS 에디터 → **프로젝트 설정 → 스크립트 속성**
2. 속성 추가:
   - 이름: `WEB_APP_URL`
   - 값: Web App URL (예: `https://script.google.com/macros/s/.../exec`)

#### C. URL 형식 확인
- ✅ 올바른 형식: `https://script.google.com/macros/s/.../exec`
- ❌ 잘못된 형식: `https://script.google.com/macros/s/.../dev` (dev는 개발 모드)

#### D. `doGet` 함수 테스트
GAS 에디터에서 직접 테스트:

```javascript
function testDoGet() {
  const mockEvent = {
    parameter: {
      addr: "서울시 강남구"
    }
  };
  
  const result = doGet(mockEvent);
  Logger.log("Result: " + result.getContent());
}
```

### 8. 추가 개선 사항

#### A. 에러 메시지 개선
URL을 가져오지 못할 경우 사용자에게 안내:

```javascript
if (!scriptUrl) {
  sendSlackEphemeral(channelId, userId, 
    "❌ T-map 버튼을 사용하려면 Web App을 배포해야 합니다.\n" +
    "GAS 에디터에서 '배포 → 새 배포'를 실행해주세요."
  );
  return;
}
```

#### B. 로깅 추가
URL 생성 과정 로깅:

```javascript
function getWebAppUrl() {
  let url = PROPERTIES.getProperty("WEB_APP_URL");
  Logger.log("Cached URL: " + (url || "none"));
  
  if (!url) {
    try {
      url = ScriptApp.getService().getUrl();
      Logger.log("Service URL: " + (url || "none"));
      // ...
    } catch(e) {
      Logger.log("Error: " + e);
    }
  }
  
  return url;
}
```

---

**수정 완료일**: 2025-12-30
**버전**: 1.0

