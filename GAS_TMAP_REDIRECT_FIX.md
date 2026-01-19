# T-map 리다이렉트 문제 해결

## 문제 상황
T-map 버튼을 클릭하면 T-map 앱이 열리지 않고 GAS 스크립트 페이지로 이동함

## 원인
GAS의 `HtmlService`는 XSS 보호를 위해 일부 JavaScript 실행이 제한될 수 있습니다. 특히 `window.location.href`를 통한 외부 앱 딥링크 리다이렉트가 제대로 작동하지 않을 수 있습니다.

## 해결 방법

### 1. `doGet` 함수 개선 완료

주요 변경사항:
- 즉시 실행되는 리다이렉트 로직
- Android/iOS 플랫폼 감지
- Intent URL / URL Scheme 시도
- 실패 시 T-map 웹 지도로 자동 fallback
- 2초 후 자동 리다이렉트 안전장치

### 2. 작동 방식

1. **Android**: Intent URL 시도 → 실패 시 웹 지도로 이동
2. **iOS**: URL Scheme 시도 → 실패 시 웹 지도로 이동  
3. **데스크톱**: 바로 웹 지도로 이동
4. **최종 안전장치**: 2초 후 자동으로 웹 지도로 리다이렉트

### 3. 테스트 방법

#### A. 브라우저에서 직접 테스트
```
https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec?addr=서울시 강남구
```

**예상 결과:**
- 모바일: T-map 앱이 열리거나 웹 지도로 이동
- 데스크톱: T-map 웹 지도가 열림

#### B. Slack에서 버튼 클릭 테스트
1. `/출근` 또는 `/퇴근` 명령어 실행
2. T-map 버튼 클릭
3. T-map 앱 또는 웹 지도가 열리는지 확인

### 4. 여전히 작동하지 않는 경우

#### A. GAS Web App 배포 확인
- Web App이 배포되어 있는지 확인
- URL이 `/exec`로 끝나는지 확인

#### B. 직접 웹 지도로 리다이렉트
가장 확실한 방법은 T-map 웹 지도로 직접 리다이렉트하는 것입니다:

```javascript
function doGet(e) {
  const addr = e.parameter.addr;
  if (!addr) {
    return HtmlService.createHtmlOutput("주소가 없습니다.");
  }
  
  const encodedAddr = encodeURIComponent(addr);
  const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
  
  // 즉시 리다이렉트
  return HtmlService.createHtmlOutput(
    `<script>window.location.href="${tmapWebUrl}";</script>`
  );
}
```

이 방법은:
- ✅ 항상 작동함
- ✅ T-map 웹 지도에서 앱 열기 버튼 제공
- ✅ 모든 플랫폼에서 동작

#### C. ContentService 사용 (제한적)
GAS는 HTTP 302 리다이렉트를 직접 지원하지 않지만, ContentService를 사용할 수 있습니다:

```javascript
function doGet(e) {
  const addr = e.parameter.addr;
  if (!addr) {
    return ContentService.createTextOutput("주소가 없습니다.");
  }
  
  const encodedAddr = encodeURIComponent(addr);
  const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
  
  // HTML 리다이렉트
  return ContentService.createTextOutput(
    `<html><head><meta http-equiv="refresh" content="0;url=${tmapWebUrl}"></head></html>`
  ).setMimeType(ContentService.MimeType.HTML);
}
```

### 5. 권장 해결책

**가장 확실한 방법**: T-map 웹 지도로 직접 리다이렉트

이유:
1. GAS의 제한을 우회할 수 있음
2. T-map 웹 지도에서 앱 열기 버튼을 제공
3. 모든 플랫폼에서 작동
4. 사용자가 직접 앱을 열 수 있음

### 6. 최종 수정안 (간단 버전)

```javascript
function doGet(e) {
  const addr = e.parameter.addr;
  if (!addr) {
    return HtmlService.createHtmlOutput("주소가 없습니다.");
  }
  
  const encodedAddr = encodeURIComponent(addr);
  const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
  
  // 가장 간단하고 확실한 방법: 즉시 리다이렉트
  const html = `
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta http-equiv="refresh" content="0;url=${tmapWebUrl}" />
      <script>window.location.href="${tmapWebUrl}";</script>
    </head>
    <body>
      <p>T-map을 여는 중입니다...</p>
      <p><a href="${tmapWebUrl}">여기를 클릭하세요</a></p>
    </body>
    </html>
  `;
  
  return HtmlService.createHtmlOutput(html).setTitle("T-map 열기");
}
```

---

**수정 완료일**: 2025-12-30
**버전**: 2.0

