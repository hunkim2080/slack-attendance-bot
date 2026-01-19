# T-map 버튼 디버깅 가이드

## 문제: 버튼이 여전히 GAS 스크립트 페이지로 이동

### 확인 사항

#### 1. GAS 코드 저장 및 배포 확인
- [ ] GAS 에디터에서 **모든 파일 저장** (Ctrl+S 또는 저장 버튼)
- [ ] **배포 → 새 배포** 또는 **배포 → 배포 관리 → 새 버전 배포**
- [ ] 배포 후 **새로운 버전 번호** 확인

#### 2. 새로운 메시지 생성 필요
**중요**: 기존에 전송된 메시지의 버튼은 업데이트되지 않습니다!

- [ ] `/출근` 명령어를 **새로 실행**하여 새로운 메시지 생성
- [ ] `/퇴근` 명령어를 **새로 실행**하여 새로운 메시지 생성
- [ ] 새로 생성된 메시지의 버튼을 클릭하여 테스트

#### 3. 버튼 URL 확인 방법

##### A. GAS 실행 기록에서 확인
1. GAS 에디터 → **실행 → 실행 기록** 클릭
2. 최근 실행 기록에서 다음 로그 확인:
   - `"귀환스킬발동 버튼 URL: ..."`
   - `"오늘 현장 T-map 버튼 URL: ..."`
3. URL이 `https://tmapapi.sktelecom.com/main/map.html?q=...`로 시작하는지 확인

##### B. Slack 메시지에서 직접 확인
1. Slack에서 메시지 우클릭 → **메시지 링크 복사**
2. 브라우저에서 열기
3. 버튼에 마우스 오버 → 하단에 표시되는 URL 확인
4. 또는 개발자 도구(F12) → Network 탭 → 버튼 클릭 → 요청 URL 확인

#### 4. 코드 확인

**`utils.gs` 파일 확인:**
```javascript
// 귀환스킬발동 버튼 (276-287번 줄)
const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
// ✅ 올바른 URL: https://tmapapi.sktelecom.com/main/map.html?q=...
// ❌ 잘못된 URL: https://script.google.com/.../exec?addr=...

// 오늘 현장 T-map 버튼 (336-343번 줄)
const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
// ✅ 올바른 URL: https://tmapapi.sktelecom.com/main/map.html?q=...
// ❌ 잘못된 URL: https://script.google.com/.../exec?addr=...
```

### 테스트 방법

#### 1. 로그 확인 테스트
```javascript
// GAS 에디터에서 실행할 테스트 함수
function testTmapButtonUrl() {
  const testAddress = "서울시 강남구";
  const encodedAddr = encodeURIComponent(testAddress);
  const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
  Logger.log("생성된 T-map URL: " + tmapWebUrl);
  Logger.log("URL이 올바른가? " + (tmapWebUrl.startsWith("https://tmapapi.sktelecom.com")));
}
```

**실행 방법:**
1. GAS 에디터에서 위 함수 추가
2. 함수 선택 후 **실행** 클릭
3. **실행 → 실행 기록**에서 결과 확인

#### 2. 실제 버튼 테스트
1. `/출근` 명령어 실행
2. 생성된 메시지의 "🚩 오늘 현장 T-map 열기" 버튼 클릭
3. T-map 웹 지도가 열리는지 확인

4. `/퇴근` 명령어 실행
5. 생성된 메시지의 "🏠 귀환스킬발동" 버튼 클릭
6. T-map 웹 지도가 열리는지 확인

### 여전히 작동하지 않는 경우

#### A. 캐시 문제
- Slack 앱을 완전히 종료 후 재시작
- 브라우저 캐시 삭제 (Ctrl+Shift+Delete)

#### B. 코드가 실제로 업데이트되지 않음
1. `utils.gs` 파일을 다시 열어서 확인
2. 280번 줄과 337번 줄의 URL이 올바른지 확인
3. `https://tmapapi.sktelecom.com/main/map.html?q=`로 시작해야 함

#### C. 다른 곳에서 버튼 생성
혹시 다른 파일에서 버튼을 생성하는 코드가 있는지 확인:
```bash
# 모든 .gs 파일에서 "tmap" 또는 "T-map" 검색
grep -r "tmap\|T-map" *.gs
```

### 예상되는 올바른 URL 형식

```
✅ 올바른 URL:
https://tmapapi.sktelecom.com/main/map.html?q=%EC%84%9C%EC%9A%B8%EC%8B%9C%20%EA%B0%95%EB%82%A8%EA%B5%AC

❌ 잘못된 URL:
https://script.google.com/macros/s/.../exec?addr=서울시 강남구
```

---

**작성일**: 2025-12-30

