# Google Calendar 설정 가이드

## 문제: GOOGLE_CALENDAR_ID가 설정되지 않음

테스트 결과 `GOOGLE_CALENDAR_ID`가 PropertiesService에 설정되지 않았습니다.

## 해결 방법

### 1. Google Calendar ID 찾기

#### 방법 A: Google Calendar 웹에서 찾기
1. [Google Calendar](https://calendar.google.com) 접속
2. 설정 (⚙️) → 설정 클릭
3. 왼쪽 메뉴에서 "내 캘린더" 또는 "다른 캘린더" 선택
4. 사용할 캘린더 옆의 "⋮" (더보기) 클릭
5. "설정 및 공유" 클릭
6. "캘린더 통합" 섹션에서 **캘린더 ID** 확인
   - 형식: `xxxxxxxxxxxxx@group.calendar.google.com` 또는 이메일 주소

#### 방법 B: 캘린더 URL에서 찾기
1. Google Calendar에서 캘린더 선택
2. URL을 확인:
   ```
   https://calendar.google.com/calendar/u/0/r?cid=캘린더ID@group.calendar.google.com
   ```
   - `cid=` 뒤의 값이 캘린더 ID입니다
   - URL 인코딩되어 있을 수 있으므로 `%40`은 `@`로 변환

### 2. GAS PropertiesService에 설정

#### 방법 A: GAS 에디터에서 설정
1. GAS 에디터 열기
2. **프로젝트 설정** (⚙️ 아이콘) 클릭
3. **스크립트 속성** 탭 클릭
4. **행 추가** 클릭
5. 속성 이름: `GOOGLE_CALENDAR_ID`
6. 속성 값: 위에서 찾은 캘린더 ID 입력
   - 예: `4cbc5b4bec77ee0dd17f929de422fe61ab57413a383963266d811d614d84b074@group.calendar.google.com`
7. **저장** 클릭

#### 방법 B: 코드로 설정 (임시)
GAS 에디터에서 다음 함수를 실행:

```javascript
function setupCalendarId() {
  const props = PropertiesService.getScriptProperties();
  // 여기에 캘린더 ID를 입력하세요
  props.setProperty("GOOGLE_CALENDAR_ID", "여기에_캘린더_ID_입력");
  Logger.log("GOOGLE_CALENDAR_ID 설정 완료");
}
```

1. `setupCalendarId` 함수 선택
2. 실행 버튼 클릭
3. 캘린더 ID를 코드에 입력 후 다시 실행

### 3. 캘린더 접근 권한 확인

GAS 프로젝트가 캘린더에 접근할 수 있는지 확인:

1. GAS 에디터에서 **실행 → 함수 실행** → `testGoogleCalendar` 선택
2. 실행 버튼 클릭
3. 권한 요청 팝업이 나타나면:
   - **권한 검토** 클릭
   - **고급** 클릭
   - **프로젝트로 이동** 클릭
   - **허용** 클릭

### 4. 캘린더 공유 설정 (필요한 경우)

GAS 프로젝트가 다른 계정의 캘린더를 사용하는 경우:

1. Google Calendar에서 해당 캘린더 선택
2. "설정 및 공유" 클릭
3. "특정 사용자와 공유" 섹션에서:
   - GAS 프로젝트를 실행하는 Google 계정 추가
   - 권한: "변경 및 공유 관리" 또는 "모든 일정 보기"

### 5. 테스트 다시 실행

설정 완료 후:

1. GAS 에디터에서 `testGoogleCalendar` 함수 실행
2. 실행 기록 확인:
   - `✅ GOOGLE_CALENDAR_ID: [캘린더 ID]` 메시지 확인
   - `✅ Calendar 객체 생성 성공` 메시지 확인
   - 일정 정보가 제대로 조회되는지 확인

## 문제 해결

### 문제 1: "캘린더를 찾을 수 없습니다"
- **원인**: 캘린더 ID가 잘못되었거나 접근 권한이 없음
- **해결**: 
  - 캘린더 ID 다시 확인
  - 캘린더 공유 설정 확인
  - GAS 프로젝트 권한 확인

### 문제 2: "위치 정보가 있는 일정이 없습니다"
- **원인**: 일정의 Location 필드가 비어있음
- **해결**: 
  - Google Calendar에서 일정 편집
  - "위치" 필드에 주소 입력
  - 저장

### 문제 3: "캘린더 접근 권한이 없습니다"
- **원인**: GAS 프로젝트에 Calendar 접근 권한이 없음
- **해결**: 
  - GAS 에디터에서 함수 실행 시 권한 요청 팝업에서 허용
  - 또는 프로젝트 설정 → 권한에서 Calendar 권한 확인

---

**작성일**: 2025-12-30

