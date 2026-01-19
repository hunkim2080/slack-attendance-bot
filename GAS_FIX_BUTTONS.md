# GAS 코드 수정: 자재기록 및 폴더생성 버튼 작동하도록 수정

## 문제점
1. `doPost()`에서 Interactive Actions 처리 로직이 불완전
2. `openMaterialModal()` 함수가 모달을 사용하지만 PRD는 Ephemeral 메시지 사용
3. `createPhotoFolder()` 함수가 제대로 구현되지 않음
4. 버튼 action_id 매칭 문제

## 수정된 코드

### 1. doPost() 수정 - Interactive Actions 처리 개선

```javascript
function doPost(e) {
  let payload;
  try {
    // Slack 요청 데이터 파싱
    if (e.postData && e.postData.type === "application/json") {
      payload = JSON.parse(e.postData.contents);
    } else if (e.parameter.payload) {
      payload = JSON.parse(e.parameter.payload);
    } else {
      payload = e.parameter;
    }
  } catch (error) {
    Logger.log("Error parsing payload: " + error);
    return ContentService.createTextOutput("Error: Invalid Payload");
  }

  // URL 검증 (Challenge)
  if (payload.type === "url_verification") {
    return ContentService.createTextOutput(payload.challenge);
  }

  // 2.1 Slash Command 처리
  if (payload.command) {
    const cmd = payload.command;
    if (cmd === "/출근") {
      handleCheckIn(payload);
      return ContentService.createTextOutput(""); // 즉시 응답
    } else if (cmd === "/퇴근") {
      handleCheckOut(payload);
      return ContentService.createTextOutput("");
    } else if (cmd === "/급여정산") {
      handlePayrollSettlement(payload);
      return ContentService.createTextOutput("");
    } else if (cmd === "/발주목록") {
      handleOrderList(payload);
      return ContentService.createTextOutput("");
    }
    return ContentService.createTextOutput("");
  }

  // 2.2 Interactive Action (버튼 클릭) - 수정 필요
  if (payload.type === "block_actions" || payload.actions) {
    const actions = payload.actions || (payload.type === "block_actions" ? payload.actions : []);
    
    if (actions.length > 0) {
      const actionId = actions[0].action_id;
      
      Logger.log("Action ID: " + actionId);
      
      // 자재사용대장 관련
      if (actionId === "open_material_log") {
        openMaterialLog(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "start_material_input") {
        startMaterialInput(payload);
        return ContentService.createTextOutput("");
      } else if (actionId.startsWith("select_color_")) {
        handleSelectColor(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "select_custom_color") {
        handleSelectCustomColor(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "confirm_custom_color") {
        handleConfirmCustomColor(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "save_material_usage") {
        saveMaterialUsage(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "material_order_required") {
        handleMaterialOrderRequired(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "material_order_not_required") {
        handleMaterialOrderNotRequired(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "save_material_order") {
        saveMaterialOrder(payload);
        return ContentService.createTextOutput("");
      }
      
      // 폴더 생성 관련
      if (actionId === "create_photo_folder") {
        createPhotoFolder(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "check_out_from_photo") {
        handleCheckOutFromPhoto(payload);
        return ContentService.createTextOutput("");
      }
      
      // 발주 관리 관련
      if (actionId === "order_request_btn") {
        openOrderInputModal(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "order_complete_btn") {
        completeOrder(payload);
        return ContentService.createTextOutput("");
      }
    }
  }

  // 2.3 View Submission (모달 제출)
  if (payload.type === "view_submission") {
    const callbackId = payload.view.callback_id;
    if (callbackId === "material_modal") {
      saveMaterialLog(payload);
      return ContentService.createTextOutput("");
    }
    if (callbackId === "order_modal") {
      saveMaterialOrder(payload);
      return ContentService.createTextOutput("");
    }
    return ContentService.createTextOutput("");
  }

  return ContentService.createTextOutput("OK");
}
```

---

### 2. openMaterialLog() 함수 수정 - Ephemeral 메시지 사용

```javascript
// 기존: openMaterialModal() - 모달 사용
// 수정: openMaterialLog() - Ephemeral 메시지 사용 (PRD 요구사항)

function openMaterialLog(payload) {
  const userId = payload.user ? payload.user.id : payload.user_id;
  const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
  
  // 방 목록 (이모지 포함)
  const roomOptions = [
    { text: { type: "plain_text", text: "🚽 거실 화장실" }, value: "거실 화장실" },
    { text: { type: "plain_text", text: "🚽 안방 화장실" }, value: "안방 화장실" },
    { text: { type: "plain_text", text: "🏠 거실" }, value: "거실" },
    { text: { type: "plain_text", text: "💧 세탁실" }, value: "세탁실" },
    { text: { type: "plain_text", text: "☀️ 베란다" }, value: "베란다" },
    { text: { type: "plain_text", text: "👟 현관" }, value: "현관" }
  ];
  
  const blocks = [
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: "📋 **자재사용대장**\n\n작업한 구역을 선택하고 자재 사용량을 기록해주세요."
      }
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: " "
      },
      accessory: {
        type: "checkboxes",
        options: roomOptions,
        action_id: "select_rooms"
      }
    },
    {
      type: "actions",
      elements: [{
        type: "button",
        text: {
          type: "plain_text",
          text: "✅ 사용량 기록시작"
        },
        action_id: "start_material_input",
        style: "primary"
      }]
    }
  ];
  
  sendSlackEphemeral(channelId, userId, "자재사용대장", blocks);
}

// select_rooms 액션 핸들러 (단순 ack)
function handleSelectRooms(payload) {
  // 체크박스 선택은 단순히 ack만 하면 됨
  return ContentService.createTextOutput("");
}
```

---

### 3. createPhotoFolder() 함수 완전 구현

```javascript
function createPhotoFolder(payload) {
  const userId = payload.user ? payload.user.id : payload.user_id;
  const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
  
  try {
    // 생성 중 메시지 전송
    sendSlackEphemeral(channelId, userId, "📁 드라이브를 생성중입니다...");
    
    // 현장 주소 가져오기
    const siteAddress = getTodaySiteAddress();
    
    // Google Drive 폴더 생성
    const parentFolderId = PROPERTIES.getProperty("GOOGLE_DRIVE_PARENT_FOLDER_ID");
    if (!parentFolderId) {
      sendSlackEphemeral(channelId, userId, "❌ GOOGLE_DRIVE_PARENT_FOLDER_ID 환경 변수가 설정되지 않았습니다.");
      return;
    }
    
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    const dateStr = Utilities.formatDate(kst, "GMT+9", "yyyy.MM.dd");
    
    // 주소에서 건물명 추출
    const addressParts = siteAddress.split(" ");
    const buildingName = addressParts.length >= 2 ? 
      addressParts.slice(-2).join(" ") : siteAddress;
    const folderName = `${dateStr} ${buildingName}`;
    
    // 폴더 생성
    const parentFolder = DriveApp.getFolderById(parentFolderId);
    const newFolder = parentFolder.createFolder(folderName);
    const folderUrl = newFolder.getUrl();
    
    // 완료 메시지 및 버튼
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "✅ 드라이브가 생성되었습니다!\n현장사진 업로드가 끝난 후, 경험치 획득 버튼을 클릭해주세요."
        }
      },
      {
        type: "actions",
        elements: [
          {
            type: "button",
            text: {
              type: "plain_text",
              text: "📷 현장사진 업로드"
            },
            url: folderUrl,
            style: "primary"
          },
          {
            type: "button",
            text: {
              type: "plain_text",
              text: "⭐ 경험치 획득(퇴근)"
            },
            action_id: "check_out_from_photo",
            style: "primary",
            value: "check_out"
          }
        ]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "폴더 생성 완료", blocks);
    
  } catch(e) {
    Logger.log("Error creating photo folder: " + e);
    sendSlackEphemeral(channelId, userId, "❌ 폴더 생성 중 오류가 발생했습니다: " + e.toString());
  }
}

// 오늘 현장 주소 가져오기 (간소화 버전)
function getTodaySiteAddress() {
  const calId = PROPERTIES.getProperty("GOOGLE_CALENDAR_ID");
  const defaultAddress = PROPERTIES.getProperty("SITE_ADDRESS") || "현장정보 없음";
  
  if (!calId) return defaultAddress;
  
  try {
    const calendar = CalendarApp.getCalendarById(calId);
    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const endOfDay = new Date(startOfDay);
    endOfDay.setDate(endOfDay.getDate() + 1);
    
    const events = calendar.getEvents(startOfDay, endOfDay);
    if (events.length > 0) {
      const location = events[0].getLocation();
      return location || defaultAddress;
    }
    return defaultAddress;
  } catch(e) {
    Logger.log("Error getting calendar site: " + e);
    return defaultAddress;
  }
}
```

---

### 4. sendSlackEphemeral() 함수 추가

```javascript
function sendSlackEphemeral(channel, user, text, blocks = null) {
  const token = PROPERTIES.getProperty("SLACK_BOT_TOKEN");
  if (!token) {
    Logger.log("SLACK_BOT_TOKEN not set");
    return;
  }
  
  const payload = {
    channel: channel,
    user: user,
    text: text
  };
  
  if (blocks) {
    payload.blocks = blocks;
  }
  
  const options = {
    method: "post",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    const response = UrlFetchApp.fetch("https://slack.com/api/chat.postEphemeral", options);
    const result = JSON.parse(response.getContentText());
    
    if (!result.ok) {
      Logger.log("Slack API error: " + result.error);
    }
  } catch(e) {
    Logger.log("Error sending ephemeral message: " + e);
  }
}
```

---

### 5. handleCheckOutFromPhoto() 함수 추가

```javascript
function handleCheckOutFromPhoto(payload) {
  // 폴더 생성 후 "경험치 획득(퇴근)" 버튼 클릭 시 퇴근 처리
  const checkOutPayload = {
    user_id: payload.user ? payload.user.id : payload.user_id,
    channel_id: payload.channel ? payload.channel.id : (payload.channel_id || payload.user.id),
    user: payload.user || { id: payload.user_id, name: "" }
  };
  
  handleCheckOut(checkOutPayload);
}
```

---

### 6. handleCheckOut() 수정 - 버튼 action_id 확인

```javascript
function handleCheckOut(payload) {
  const userInfo = getUserInfo(payload.user_id);
  if (!userInfo) return;

  const now = new Date();
  
  // 시트 기록
  SS.getSheetByName("AttendanceLog").appendRow([
    Utilities.formatDate(now, "GMT+9", "yyyy-MM-dd"),
    userInfo.name,
    Utilities.formatDate(now, "GMT+9", "HH:mm:ss"),
    "퇴근",
    ""
  ]);

  // 정산 및 게임화 데이터 계산
  const workStats = calculateWorkStats(userInfo);
  const progressBar = getProgressBar(workStats.totalDays);
  
  const blocks = [
    { 
      type: "section", 
      text: { 
        type: "mrkdwn", 
        text: `✅ *[${userInfo.name}님 퇴근]*\n오늘 하루 흘린 땀방울이 멋진 결과로 쌓였습니다. 👏` 
      } 
    },
    { type: "divider" },
    { 
      type: "section", 
      fields: [
        { 
          type: "mrkdwn", 
          text: `💰 *예상 일당*\n${workStats.dailyPay.toLocaleString()}원` 
        },
        { 
          type: "mrkdwn", 
          text: `⚔️ *각성 단계*\n${workStats.stageTitle}` 
        }
      ]
    },
    { 
      type: "section", 
      text: { 
        type: "mrkdwn", 
        text: `*경험치 진행률* (총 ${workStats.totalDays}일)\n${progressBar}` 
      } 
    },
    { type: "divider" },
    { 
      type: "actions", 
      elements: [
        { 
          type: "button", 
          text: { type: "plain_text", text: "🏠 귀환(집)" }, 
          url: getRedirectUrl(userInfo.address), 
          style: "primary" 
        },
        { 
          type: "button", 
          text: { type: "plain_text", text: "📋 자재기록" },  // 스크린샷과 동일한 텍스트
          action_id: "open_material_log"  // action_id 확인 필요
        },
        { 
          type: "button", 
          text: { type: "plain_text", text: "📷 폴더생성" },  // 스크린샷과 동일한 텍스트
          action_id: "create_photo_folder"  // action_id 확인 필요
        }
      ]
    }
  ];

  sendSlackMessage(payload.channel_id, "", blocks);
}
```

---

## 주요 수정 사항 요약

1. ✅ **doPost() Interactive Actions 처리 개선**
   - `payload.actions` 배열에서 action_id 추출
   - 모든 액션 핸들러 연결

2. ✅ **openMaterialLog() 수정**
   - 모달 대신 Ephemeral 메시지 사용
   - 방 선택 체크박스 표시

3. ✅ **createPhotoFolder() 완전 구현**
   - Google Drive 폴더 생성
   - 오늘 날짜의 Calendar에서 현장 주소 가져오기
   - 완료 메시지 및 버튼 표시

4. ✅ **sendSlackEphemeral() 함수 추가**
   - Ephemeral 메시지 전송 함수

5. ✅ **handleCheckOutFromPhoto() 함수 추가**
   - 폴더 생성 후 퇴근 처리

6. ✅ **버튼 텍스트 확인**
   - "자재기록" → `action_id: "open_material_log"`
   - "폴더생성" → `action_id: "create_photo_folder"`

---

## 테스트 체크리스트

- [ ] `/퇴근` 명령어 실행 후 버튼 표시 확인
- [ ] "자재기록" 버튼 클릭 → 방 선택 화면 표시 확인
- [ ] "폴더생성" 버튼 클릭 → 폴더 생성 및 메시지 표시 확인
- [ ] 폴더 생성 후 "경험치 획득(퇴근)" 버튼 → 퇴근 처리 확인

