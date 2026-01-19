# 스크립트 속성 확인 및 수정 가이드

## 현재 스크립트 속성 상태

### ✅ 설정된 속성
1. `DRIVE_PARENT_ID` → **이름 변경 필요**: `GOOGLE_DRIVE_PARENT_FOLDER_ID`
2. `GOOGLE_CALENDAR_ID` ✅ (값이 잘린 것 같음 - 전체 값 확인 필요)
3. `SLACK_BOT_TOKEN` ✅ (값이 잘린 것 같음 - 전체 값 확인 필요)
4. `WEATHER_API_KEY` ✅ (값이 잘린 것 같음 - 전체 값 확인 필요)
5. `WEB_APP_URL` ✅ (값이 잘린 것 같음 - `/exec`로 끝나는지 확인 필요)

### ❌ 누락된 속성
1. `SLACK_SIGNING_SECRET` - **필수**
2. `ADMIN_SLACK_IDS` - **필수**
3. `SITE_ADDRESS` - **필수**

### ⚠️ 선택적 속성
- `SPREADSHEET_KEY` - 현재 코드는 `SpreadsheetApp.getActiveSpreadsheet()`를 사용하므로 필요 없을 수 있음

## 수정 방법

### 1. 이름 변경: `DRIVE_PARENT_ID` → `GOOGLE_DRIVE_PARENT_FOLDER_ID`

**방법 A: GAS 에디터에서 수동 변경**
1. GAS 에디터 → 프로젝트 설정 → 스크립트 속성
2. `DRIVE_PARENT_ID` 행 삭제
3. 새 행 추가:
   - 속성 이름: `GOOGLE_DRIVE_PARENT_FOLDER_ID`
   - 속성 값: `1SPc_60nfGeiDKQISef80jtV3TNnzAGCW`

**방법 B: 코드로 변경**
```javascript
function fixDriveParentId() {
  const props = PropertiesService.getScriptProperties();
  const oldValue = props.getProperty("DRIVE_PARENT_ID");
  if (oldValue) {
    props.setProperty("GOOGLE_DRIVE_PARENT_FOLDER_ID", oldValue);
    props.deleteProperty("DRIVE_PARENT_ID");
    Logger.log("✅ DRIVE_PARENT_ID → GOOGLE_DRIVE_PARENT_FOLDER_ID 변경 완료");
  }
}
```

### 2. 누락된 속성 추가

#### `SLACK_SIGNING_SECRET`
- 속성 이름: `SLACK_SIGNING_SECRET`
- 속성 값: `07af65842396972fb0f617f87d682761`

#### `ADMIN_SLACK_IDS`
- 속성 이름: `ADMIN_SLACK_IDS`
- 속성 값: `U059H02UNF9` (여러 개면 쉼표로 구분: `U059H02UNF9,U12345678`)

#### `SITE_ADDRESS`
- 속성 이름: `SITE_ADDRESS`
- 속성 값: `서울시 강남구 테헤란로 123` (또는 기본 현장 주소)

### 3. 값이 잘린 속성 확인

다음 속성들의 값이 잘려 보일 수 있습니다. 전체 값을 확인하세요:

1. **`GOOGLE_CALENDAR_ID`**
   - 전체 값: `4cbc5b4bec77ee0dd17f929de422fe61ab57413a383963266d811d614d84b074@group.calendar.google.com`
   - 끝에 `@group.calendar.google.com`이 있는지 확인

2. **`SLACK_BOT_TOKEN`**
   - 전체 값: `xoxb-...` (실제 값은 환경 변수에서 설정)
   - `xoxb-`로 시작하고 전체 토큰이 있는지 확인

3. **`WEATHER_API_KEY`**
   - 전체 값: `...` (실제 값은 환경 변수에서 설정)
   - 전체 키가 있는지 확인

4. **`WEB_APP_URL`**
   - 형식: `https://script.google.com/macros/s/AKfycb.../exec`
   - **반드시 `/exec`로 끝나야 함**
   - `/dev`로 끝나면 안 됨 (개발 모드 URL)

## 한 번에 설정하는 코드

GAS 에디터에서 다음 함수를 실행하면 모든 속성을 한 번에 설정할 수 있습니다:

```javascript
function setupAllProperties() {
  const props = PropertiesService.getScriptProperties();
  
  // 기존 DRIVE_PARENT_ID를 GOOGLE_DRIVE_PARENT_FOLDER_ID로 변경
  const oldDriveId = props.getProperty("DRIVE_PARENT_ID");
  if (oldDriveId && !props.getProperty("GOOGLE_DRIVE_PARENT_FOLDER_ID")) {
    props.setProperty("GOOGLE_DRIVE_PARENT_FOLDER_ID", oldDriveId);
    props.deleteProperty("DRIVE_PARENT_ID");
    Logger.log("✅ DRIVE_PARENT_ID → GOOGLE_DRIVE_PARENT_FOLDER_ID 변경 완료");
  }
  
  // 누락된 속성 추가
  if (!props.getProperty("SLACK_SIGNING_SECRET")) {
    props.setProperty("SLACK_SIGNING_SECRET", "your-signing-secret-here");
    Logger.log("✅ SLACK_SIGNING_SECRET 설정 완료");
  }
  
  if (!props.getProperty("ADMIN_SLACK_IDS")) {
    props.setProperty("ADMIN_SLACK_IDS", "your-admin-slack-id-here");
    Logger.log("✅ ADMIN_SLACK_IDS 설정 완료");
  }
  
  if (!props.getProperty("SITE_ADDRESS")) {
    props.setProperty("SITE_ADDRESS", "your-site-address");
    Logger.log("✅ SITE_ADDRESS 설정 완료");
  }
  
  // 값 확인 및 로그 출력
  Logger.log("=== 현재 설정된 속성 ===");
  Logger.log("GOOGLE_DRIVE_PARENT_FOLDER_ID: " + props.getProperty("GOOGLE_DRIVE_PARENT_FOLDER_ID"));
  Logger.log("GOOGLE_CALENDAR_ID: " + props.getProperty("GOOGLE_CALENDAR_ID"));
  Logger.log("SLACK_BOT_TOKEN: " + (props.getProperty("SLACK_BOT_TOKEN") ? "설정됨 (길이: " + props.getProperty("SLACK_BOT_TOKEN").length + ")" : "❌ 없음"));
  Logger.log("SLACK_SIGNING_SECRET: " + (props.getProperty("SLACK_SIGNING_SECRET") ? "설정됨" : "❌ 없음"));
  Logger.log("WEATHER_API_KEY: " + (props.getProperty("WEATHER_API_KEY") ? "설정됨 (길이: " + props.getProperty("WEATHER_API_KEY").length + ")" : "❌ 없음"));
  Logger.log("ADMIN_SLACK_IDS: " + props.getProperty("ADMIN_SLACK_IDS"));
  Logger.log("SITE_ADDRESS: " + props.getProperty("SITE_ADDRESS"));
  Logger.log("WEB_APP_URL: " + props.getProperty("WEB_APP_URL"));
}
```

## 확인 체크리스트

- [ ] `DRIVE_PARENT_ID` → `GOOGLE_DRIVE_PARENT_FOLDER_ID`로 이름 변경
- [ ] `SLACK_SIGNING_SECRET` 추가
- [ ] `ADMIN_SLACK_IDS` 추가
- [ ] `SITE_ADDRESS` 추가
- [ ] `GOOGLE_CALENDAR_ID` 전체 값 확인 (끝에 `@group.calendar.google.com` 포함)
- [ ] `SLACK_BOT_TOKEN` 전체 값 확인 (`xoxb-`로 시작)
- [ ] `WEATHER_API_KEY` 전체 값 확인
- [ ] `WEB_APP_URL` 확인 (`/exec`로 끝나는지 확인)

## 참고

- `env.yaml` 파일에 모든 원본 값이 있습니다
- `SPREADSHEET_KEY`는 현재 코드에서 사용하지 않으므로 설정하지 않아도 됩니다
- `WEB_APP_URL`은 Web App 배포 후 자동으로 생성되거나 수동으로 설정할 수 있습니다






