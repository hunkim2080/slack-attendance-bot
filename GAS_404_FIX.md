# 404 에러 해결 가이드

## 문제 상황
- "자재사용대장" 버튼 클릭 시 404 에러 발생
- "현장사진 업로드" 버튼 클릭 시 404 에러 발생

## 원인
Slack Interactive Actions의 payload 파싱이 제대로 되지 않아 `action_id`를 찾지 못하고, 핸들러가 실행되지 않음

## 해결 방법

### 1. `attendance-bot.gs`의 `doPost` 함수 수정 완료

주요 변경사항:
- Interactive Actions payload 파싱 로직 개선
- `application/x-www-form-urlencoded` 형식 처리 추가
- 모든 경우에 빈 응답 반환 (404 방지)
- 디버깅을 위한 로깅 추가

### 2. 확인 사항

#### A. Slack App 설정 확인
1. [Slack API](https://api.slack.com/apps) 접속
2. 해당 앱 선택
3. **Interactive Components** 메뉴 확인:
   - **Interactivity**가 **ON**인지 확인
   - **Request URL**이 GAS Web App URL과 일치하는지 확인
   - 예: `https://script.google.com/macros/s/.../exec`

#### B. GAS Web App 배포 확인
1. GAS 에디터에서 **배포 → 배포 관리** 클릭
2. 최신 배포 버전 확인
3. **웹 앱 URL** 복사하여 Slack App 설정과 비교

#### C. 버튼의 `action_id` 확인
퇴근 메시지에 표시되는 버튼의 `action_id`가 다음 중 하나인지 확인:
- `open_material_log` (자재사용대장)
- `create_photo_folder` (현장사진 업로드)

### 3. 디버깅 방법

#### A. GAS 실행 기록 확인
1. GAS 에디터에서 **실행 → 실행 기록** 클릭
2. 최근 실행 기록에서 에러 메시지 확인
3. `Logger.log` 출력 확인:
   - "Payload type: ..."
   - "Action ID: ..."
   - "Error in ..."

#### B. 수동 테스트
GAS 에디터에서 다음 함수를 실행하여 테스트:

```javascript
function testPayloadParsing() {
  // 테스트용 payload (실제 Slack에서 보내는 형식)
  const testPayload = {
    type: "block_actions",
    user: { id: "U12345678" },
    channel: { id: "C12345678" },
    actions: [{
      action_id: "open_material_log",
      value: "test"
    }]
  };
  
  // openMaterialLog 함수 직접 호출
  openMaterialLog(testPayload);
}
```

### 4. 추가 수정 사항

#### A. `interactive-actions.gs` 수정 완료
- `openMaterialLog` 함수: payload 파싱 개선
- `createPhotoFolder` 함수: payload 파싱 개선, 에러 처리 강화

#### B. 에러 처리
모든 핸들러 함수에서:
- `try-catch` 블록으로 에러 처리
- 에러 발생 시에도 빈 응답 반환 (404 방지)
- `Logger.log`로 에러 기록

### 5. 확인 체크리스트

- [ ] GAS Web App이 최신 버전으로 배포되었는가?
- [ ] Slack App의 Interactive Components 설정이 올바른가?
- [ ] `SLACK_BOT_TOKEN`이 PropertiesService에 설정되어 있는가?
- [ ] 버튼의 `action_id`가 코드와 일치하는가?
- [ ] GAS 실행 기록에 에러가 없는가?

### 6. 여전히 404가 발생하는 경우

1. **GAS 실행 기록 확인**
   - 에러 메시지 확인
   - `Logger.log` 출력 확인

2. **Slack App 설정 재확인**
   - Interactive Components URL이 정확한지 확인
   - Web App URL과 일치하는지 확인

3. **버튼 코드 확인**
   - 퇴근 메시지 생성 부분에서 버튼의 `action_id` 확인
   - `handleCheckOut` 함수에서 버튼 생성 코드 확인

4. **수동 테스트**
   - `testPayloadParsing` 함수 실행
   - 각 핸들러 함수 직접 호출 테스트

---

**수정 완료일**: 2025-12-30
**버전**: 1.0

