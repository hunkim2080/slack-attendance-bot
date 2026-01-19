# T-map 버튼 최종 해결 가이드

## 문제
버튼 클릭 시 여전히 `script.google.com/home?addr=...`로 이동

## 핵심 답변
**GAS를 거치지 않고 직접 T-map URL을 사용하는 것이 맞습니다!**

코드는 이미 올바르게 수정되어 있습니다. 문제는 다음 중 하나일 수 있습니다:

## 확인 사항

### 1. GAS 실행 기록에서 실제 URL 확인

GAS 에디터에서 `testTmapButtonUrls()` 함수를 실행하세요:

1. 함수 선택 드롭다운에서 `testTmapButtonUrls` 선택
2. **실행** 버튼 클릭
3. **실행 → 실행 기록**에서 결과 확인:
   - `"귀환스킬발동 버튼 URL: https://tmapapi.sktelecom.com/..."`
   - `"올바른 URL인가? true"`

### 2. 실제 메시지 생성 시 로그 확인

1. `/출근` 또는 `/퇴근` 명령어를 **새로 실행**
2. GAS 에디터 → **실행 → 실행 기록** 확인
3. 다음 로그 찾기:
   - `"오늘 현장 T-map 버튼 URL: ..."`
   - `"귀환스킬발동 버튼 URL: ..."`

**이 로그들이 `https://tmapapi.sktelecom.com/main/map.html?q=...`로 시작하는지 확인하세요!**

### 3. 코드가 실제로 배포되었는지 확인

1. **모든 파일 저장** (Ctrl+S)
2. **배포 → 배포 관리** 클릭
3. 최신 배포 버전 확인
4. **새 버전 배포** (필요한 경우)

### 4. 새로운 메시지 생성 (매우 중요!)

**기존 메시지의 버튼은 업데이트되지 않습니다!**

- `/출근` 명령어를 **새로 실행**하여 새로운 메시지 생성
- `/퇴근` 명령어를 **새로 실행**하여 새로운 메시지 생성
- **새로 생성된 메시지**의 버튼만 테스트

### 5. Slack 캐시 문제

- Slack 앱을 완전히 종료 후 재시작
- 브라우저에서 Slack을 사용하는 경우 캐시 삭제 (Ctrl+Shift+Delete)

## 코드 확인

`utils.gs` 파일의 다음 부분을 확인하세요:

```javascript
// 280번 줄 - 귀환스킬발동 버튼
const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;

// 338번 줄 - 오늘 현장 T-map 버튼  
const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
```

이 두 줄이 **반드시** `https://tmapapi.sktelecom.com/main/map.html?q=`로 시작해야 합니다.

## 여전히 작동하지 않는 경우

GAS 실행 기록에서 다음을 확인하세요:

1. `testTmapButtonUrls()` 함수 실행 결과
2. `/출근` 또는 `/퇴근` 실행 시 생성된 로그
3. 실제로 어떤 URL이 생성되고 있는지

**만약 로그에서도 GAS URL이 생성되고 있다면**, 다른 곳에서 버튼을 생성하는 코드가 있을 수 있습니다.

---

**작성일**: 2025-12-30

