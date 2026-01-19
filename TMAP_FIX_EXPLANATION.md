# T-map 버튼 수정 과정 설명

## 문제 해결 과정

### 1단계: `attendance-bot.gs`의 `doGet` 함수 수정 (처음 시도)

**목적**: GAS Web App URL로 요청이 왔을 때 T-map으로 리다이렉트

**작동 방식**:
```
버튼 클릭 → GAS URL (예: script.google.com/.../exec?addr=주소) 
  → `doGet` 함수 실행 
    → T-map 웹 지도로 리다이렉트
```

**문제점**:
- GAS의 XSS 보호 때문에 `window.location.href` 리다이렉트가 제대로 작동하지 않음
- 버튼을 클릭하면 GAS 스크립트 페이지에 머물러 있음

### 2단계: `utils.gs`의 버튼 URL 생성 함수 수정 (최종 해결)

**목적**: 버튼 URL 자체를 T-map 웹 지도로 직접 설정

**작동 방식**:
```
버튼 클릭 → T-map 웹 지도로 바로 이동 (GAS를 거치지 않음)
```

**장점**:
- GAS의 제한을 완전히 우회
- 더 빠르고 안정적
- 모든 플랫폼에서 작동

## 파일별 역할

### `attendance-bot.gs` - `doGet` 함수
- **역할**: GAS Web App URL로 GET 요청이 왔을 때 처리
- **현재 상태**: T-map 웹 지도로 리다이렉트하도록 구현되어 있음
- **사용 여부**: 현재는 사용되지 않음 (버튼 URL이 직접 T-map을 가리키므로)
- **유지 이유**: 혹시 다른 곳에서 사용될 수 있으므로 남겨둠

### `utils.gs` - 버튼 URL 생성 함수들
- **역할**: Slack 메시지에 표시될 버튼의 URL을 생성
- **수정된 함수들**:
  - `sendSlackWithButtons()` - 귀환스킬발동 버튼
  - `sendSlackWithTmap()` - 오늘 현장 T-map 버튼
  - `getRedirectUrl()` - 리다이렉트 URL 생성
- **변경 내용**: GAS URL 대신 T-map 웹 지도 URL 직접 사용

## 왜 두 파일을 모두 수정했나?

1. **첫 번째 시도** (`attendance-bot.gs`):
   - GAS를 중간 경유지로 사용하는 방식
   - GAS의 제한 때문에 실패

2. **최종 해결** (`utils.gs`):
   - GAS를 거치지 않고 직접 T-map으로 이동
   - 더 간단하고 확실한 방법

## 현재 구조

```
Slack 버튼 클릭
  ↓
T-map 웹 지도로 직접 이동
  ↓
웹 지도에서 앱 열기 버튼 클릭 (선택사항)
  ↓
T-map 앱 실행
```

**GAS는 이제 관여하지 않습니다!**

## 결론

- `attendance-bot.gs`의 `doGet`: 수정했지만 현재는 사용되지 않음
- `utils.gs`의 버튼 URL 생성: 실제로 작동하는 최종 해결책

**핵심**: 버튼 URL을 직접 T-map으로 설정하는 것이 가장 확실한 방법입니다.

---

**작성일**: 2025-12-30

