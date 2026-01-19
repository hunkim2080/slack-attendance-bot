# WEB_APP_URL 문제 해결

## 문제
버튼 클릭 시 `script.google.com/home?addr=...`로 이동함

## 원인
PropertiesService에 잘못된 URL(`/home`)이 저장되어 있거나, `getWebAppUrl()`이 잘못된 URL을 반환하고 있음

## 해결 방법

### 1. PropertiesService의 잘못된 URL 삭제

GAS 에디터에서 다음 함수를 실행:

```javascript
function clearWebAppUrl() {
  PropertiesService.getScriptProperties().deleteProperty("WEB_APP_URL");
  Logger.log("WEB_APP_URL property cleared");
}
```

**실행 방법:**
1. GAS 에디터에서 위 함수 추가
2. 함수 선택 후 **실행** 클릭
3. **실행 → 실행 기록**에서 "cleared" 메시지 확인

### 2. 코드 확인

**중요**: T-map 버튼은 이제 `getWebAppUrl()`을 사용하지 않습니다!

`utils.gs` 파일 확인:
- 280번 줄: `const tmapWebUrl = 'https://tmapapi.sktelecom.com/main/map.html?q=...'`
- 338번 줄: `const tmapWebUrl = 'https://tmapapi.sktelecom.com/main/map.html?q=...'`

이 URL들이 직접 T-map 웹 지도 URL을 사용하고 있는지 확인하세요.

### 3. GAS 코드 저장 및 배포

1. **모든 파일 저장** (Ctrl+S)
2. **배포 → 새 배포** (또는 기존 배포 업데이트)
3. **새로운 메시지 생성** (`/출근` 또는 `/퇴근` 명령어 새로 실행)

### 4. 테스트

1. `/출근` 명령어 새로 실행
2. 생성된 메시지의 T-map 버튼 클릭
3. URL 확인:
   - ✅ 올바른 URL: `https://tmapapi.sktelecom.com/main/map.html?q=...`
   - ❌ 잘못된 URL: `script.google.com/home?addr=...` 또는 `script.google.com/.../exec?addr=...`

### 5. GAS 실행 기록 확인

1. GAS 에디터 → **실행 → 실행 기록**
2. 다음 로그 확인:
   - `"오늘 현장 T-map 버튼 URL: https://tmapapi.sktelecom.com/..."`
   - `"귀환스킬발동 버튼 URL: https://tmapapi.sktelecom.com/..."`

이 로그들이 올바른 T-map URL을 보여주는지 확인하세요.

---

**작성일**: 2025-12-30

