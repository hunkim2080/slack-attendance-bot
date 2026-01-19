# 실제 전송되는 URL 확인 가이드

## 문제
버튼 클릭 시 404 에러 발생 → 버튼 URL이 여전히 GAS URL을 가리키고 있음

## 확인 방법

### 1. `/출근` 명령어 실행 후 로그 확인

1. Slack에서 `/출근` 명령어를 **새로 실행**
2. GAS 에디터 → **실행 → 실행 기록** 클릭
3. 최근 실행 기록에서 다음 로그들을 찾아주세요:

**필수 확인 로그:**
- `"오늘 현장 T-map 버튼 URL: ..."`
- `"[sendSlackMessage] Block X, Button Y URL: ..."`

### 2. 예상되는 로그

**✅ 올바른 경우:**
```
오늘 현장 T-map 버튼 URL: https://tmapapi.sktelecom.com/main/map.html?q=...
[sendSlackMessage] Block 1, Button 0 URL: https://tmapapi.sktelecom.com/main/map.html?q=...
```

**❌ 문제가 있는 경우:**
```
오늘 현장 T-map 버튼 URL: https://script.google.com/.../exec?addr=...
또는
[sendSlackMessage] Block 1, Button 0 URL: https://script.google.com/.../exec?addr=...
```

### 3. 로그가 없는 경우

만약 위 로그들이 전혀 보이지 않는다면:
- 코드가 실제로 실행되지 않고 있거나
- 다른 코드 경로를 사용하고 있을 수 있습니다

### 4. 로그 확인 후 조치

**케이스 A: 버튼 생성 로그는 올바른데 전송 로그가 잘못된 경우**
- `sendSlackMessage` 함수에서 URL이 변경되고 있을 수 있음
- blocks가 전송 전에 수정되고 있을 수 있음

**케이스 B: 버튼 생성 로그 자체가 잘못된 경우**
- `sendSlackWithTmap` 함수가 제대로 수정되지 않았거나
- 다른 버전의 코드가 실행되고 있을 수 있음

**케이스 C: 로그가 전혀 없는 경우**
- 코드가 배포되지 않았거나
- 다른 파일의 함수를 사용하고 있을 수 있음

---

**작성일**: 2025-12-30

