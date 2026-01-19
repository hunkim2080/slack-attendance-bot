# GAS 전환 코드 빠진 기능 체크리스트

## 🔴 Critical (필수 구현)

### 1. Slack 요청 검증 (보안)
**현재 상태**: ❌ 없음  
**PRD 참조**: 7.4 Slack 요청 검증

```javascript
// 빠진 코드
function verifySlackRequest(timestamp, body, signature) {
  const signingSecret = PROPERTIES.getProperty("SLACK_SIGNING_SECRET");
  const baseString = `v0:${timestamp}:${body}`;
  const hmac = Utilities.computeHmacSha256Signature(baseString, signingSecret);
  const computedSignature = 'v0=' + hmac.map(b => ('0' + (b & 0xFF).toString(16)).slice(-2)).join('');
  return computedSignature === signature;
}

// doPost() 시작 부분에 추가 필요
function doPost(e) {
  const timestamp = e.parameter['X-Slack-Request-Timestamp'];
  const signature = e.parameter['X-Slack-Signature'];
  const body = e.postData ? e.postData.contents : JSON.stringify(e.parameter);
  
  if (!verifySlackRequest(timestamp, body, signature)) {
    return ContentService.createTextOutput("Invalid signature");
  }
  // ... 기존 코드
}
```

---

### 2. 관리자 권한 체크
**현재 상태**: ❌ 없음  
**PRD 참조**: 3.1.3, 3.1.4, 3.1.5, 3.1.6

```javascript
// 빠진 코드
function isAdmin(userId) {
  const adminIds = PROPERTIES.getProperty("ADMIN_SLACK_IDS").split(",");
  return adminIds.includes(userId);
}

// 각 관리자 전용 명령어에 추가 필요
function handlePayrollSettlement(payload) {
  if (!isAdmin(payload.user_id)) {
    return sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 관리자만 사용할 수 있습니다.");
  }
  // ... 기존 코드
}
```

---

### 3. 레벨업/각성 체크 및 DM 발송
**현재 상태**: ❌ 없음  
**PRD 참조**: 3.1.2, 5.1, 5.2

```javascript
// 빠진 코드
function checkLevelUpAndAwakening(userInfo, prevTotalDays, currentTotalDays) {
  // 레벨업 체크
  const prevLevel = Math.floor(prevTotalDays / 3);
  const currentLevel = Math.floor(currentTotalDays / 3);
  
  if (currentLevel > prevLevel) {
    const userTitle = getUserTitle(currentTotalDays);
    const levelUpMsg = `🎉 **레벨업!**\n\n` +
                       `Lv.${prevLevel} → Lv.${currentLevel}\n\n` +
                       `🎖 **새로운 칭호:** ${userTitle}\n\n` +
                       `현재 총 근무일수: ${currentTotalDays}일`;
    sendSlackMessage(userInfo.slackId, levelUpMsg);
  }
  
  // 각성 단계 달성 체크
  const cutscene = getAwakeningCutscene(currentTotalDays, prevTotalDays);
  if (cutscene.shouldSend) {
    sendSlackMessage(userInfo.slackId, cutscene.message);
  }
}

// handleCheckOut()에 추가 필요
function handleCheckOut(payload) {
  const userInfo = getUserInfo(payload.user_id);
  const prevTotalDays = getTotalWorkDays(userInfo.name);
  
  // 퇴근 기록
  // ...
  
  const currentTotalDays = getTotalWorkDays(userInfo.name);
  
  // 레벨업/각성 체크 (퇴근 시에만)
  checkLevelUpAndAwakening(userInfo, prevTotalDays, currentTotalDays);
  
  // ... 기존 코드
}
```

---

### 4. 일자별 단가 계산 (월 중간 단가 인상)
**현재 상태**: ❌ 단순 계산만 있음  
**PRD 참조**: 5.3.1, 3.1.3

```javascript
// 현재 코드 문제: 월 전체를 같은 단가로 계산
// PRD 요구사항: 월 중간에 단가가 오르는 경우 일자별로 계산

// 빠진 코드
function calculateMonthlyPayroll(userName, year, month) {
  const attendLog = SS.getSheetByName("AttendanceLog").getDataRange().getValues();
  const userInfo = getUserInfoByName(userName);
  const baseDays = userInfo.baseDays;
  
  // 이전 달까지의 총 근무일수 계산
  let previousDays = baseDays;
  attendLog.forEach(row => {
    if (row[1] === userName && row[3] === "퇴근") {
      const date = new Date(row[0]);
      if (date.getFullYear() < year || (date.getFullYear() === year && date.getMonth() + 1 < month)) {
        previousDays++;
      }
    }
  });
  
  // 해당 월의 출근일 추출
  const workDates = [];
  attendLog.forEach(row => {
    if (row[1] === userName && row[3] === "출근") {
      const date = new Date(row[0]);
      if (date.getFullYear() === year && date.getMonth() + 1 === month) {
        workDates.push(date);
      }
    }
  });
  
  // 일자별로 단가 계산
  let totalPay = 0;
  workDates.sort((a, b) => a - b);
  workDates.forEach((workDate, index) => {
    const currentTotalDays = previousDays + index + 1;
    const dailyPay = getDailyPay(currentTotalDays);
    totalPay += dailyPay;
  });
  
  return {
    totalPay: totalPay,
    workDays: workDates.length,
    dailyBreakdown: workDates.map((date, index) => ({
      date: date,
      cumulativeDays: previousDays + index + 1,
      dailyPay: getDailyPay(previousDays + index + 1)
    }))
  };
}
```

---

## 🟡 Important (중요 기능)

### 5. Slash Commands 누락
**현재 상태**: 4개만 구현 (8개 필요)

#### 5.1 `/출근로그` (관리자 전용)
```javascript
// 빠진 코드
function handleAttendanceLogs(payload) {
  if (!isAdmin(payload.user_id)) {
    return sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 관리자만 사용할 수 있습니다.");
  }
  
  const users = getAllUsers();
  const options = users.map(user => ({
    text: { type: "plain_text", text: user.name },
    value: user.name
  }));
  
  const blocks = [
    {
      type: "section",
      text: { type: "mrkdwn", text: "📋 **출근 로그 조회**\n\n조회할 사용자를 선택하세요:" }
    },
    {
      type: "section",
      text: { type: "mrkdwn", text: "사용자 선택" },
      accessory: {
        type: "static_select",
        placeholder: { type: "plain_text", text: "사용자 선택" },
        options: options,
        action_id: "select_user_attendance"
      }
    }
  ];
  
  sendSlackEphemeral(payload.channel_id, payload.user_id, "", blocks);
}

// 액션 핸들러도 필요
function handleSelectUserAttendance(payload) {
  const selectedName = payload.actions[0].selected_option.value;
  const logs = getAttendanceLogs(selectedName);
  
  let msg = `📋 **${selectedName}님 출근 로그**\n\n총 ${logs.length}건의 출근 기록\n\n`;
  logs.forEach(log => {
    msg += `• ${log.date} ${log.time}`;
    if (log.remarks) msg += ` (${log.remarks})`;
    msg += "\n";
  });
  
  sendSlackEphemeral(payload.channel.id, payload.user.id, msg);
}
```

#### 5.2 `/정산내역` (관리자 전용)
```javascript
// 빠진 코드
function handlePayrollHistory(payload) {
  if (!isAdmin(payload.user_id)) {
    return sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 관리자만 사용할 수 있습니다.");
  }
  
  // 사용자 선택 메뉴 표시 (위와 유사)
  // ...
}

function handleSelectUserPayroll(payload) {
  const selectedName = payload.actions[0].selected_option.value;
  const payrolls = getUserPayrollHistory(selectedName);
  
  let msg = `💰 **${selectedName}님 정산 내역**\n\n총 ${payrolls.length}개월의 급여 기록\n\n`;
  payrolls.forEach(payroll => {
    msg += `━━━━━━━━━━━━━━━━━━━━\n`;
    msg += `📋 **${payroll.year}년 ${payroll.month}월**\n\n`;
    msg += `• 근무일수: ${payroll.work_days}일\n`;
    msg += `• 기본급: ${payroll.base_pay.toLocaleString()}원\n`;
    if (payroll.commission > 0) {
      msg += `• 인센티브: ${payroll.commission.toLocaleString()}원\n`;
    }
    msg += `• 교통비: ${payroll.transportation.toLocaleString()}원\n`;
    msg += `• **총 급여: ${payroll.total_pay.toLocaleString()}원**\n\n`;
  });
  
  sendSlackEphemeral(payload.channel.id, payload.user.id, msg);
}
```

#### 5.3 `/hello`, `/netcheck` (테스트용)
```javascript
// 빠진 코드
function handleHello(payload) {
  sendSlackMessage(payload.channel_id, `✅ GCF 서버에 도달했습니다!`);
}

function handleNetcheck(payload) {
  if (!isAdmin(payload.user_id)) {
    return sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 관리자만 사용할 수 있습니다.");
  }
  
  try {
    const response = UrlFetchApp.fetch("https://oauth2.googleapis.com/token", { timeout: 10 });
    sendSlackEphemeral(payload.channel_id, payload.user_id, `✅ 핸드셰이크 OK, 응답 코드 ${response.getResponseCode()}`);
  } catch(e) {
    sendSlackEphemeral(payload.channel_id, payload.user_id, `🚨 요청 실패: ${e}`);
  }
}
```

---

### 6. 자재사용대장 복잡한 플로우
**현재 상태**: ❌ 단순 모달만 있음  
**PRD 참조**: 3.2.1

**현재 구현**: 모달로 한 번에 입력  
**PRD 요구사항**: 방 선택 → 색상 선택 → 사용량 입력 → 다음 방 반복

```javascript
// 빠진 코드: 복잡한 플로우 구현
// 1. open_material_log: 방 선택 체크박스 (Ephemeral)
// 2. start_material_input: 첫 번째 방 색상 선택
// 3. select_color_{색상}: 사용량 입력
// 4. save_material_usage: 저장 후 다음 방으로
// 5. 모든 방 완료 시 발주 필요 여부 확인

function openMaterialLog(payload) {
  // 현재는 모달, PRD는 Ephemeral 메시지 + 체크박스
  const blocks = [
    {
      type: "section",
      text: { type: "mrkdwn", text: "📋 **자재사용대장**\n\n작업한 구역을 선택하고 자재 사용량을 기록해주세요." }
    },
    {
      type: "section",
      text: { type: "mrkdwn", text: " " },
      accessory: {
        type: "checkboxes",
        options: [
          { text: { type: "plain_text", text: "🚽 거실 화장실" }, value: "거실 화장실" },
          { text: { type: "plain_text", text: "🚽 안방 화장실" }, value: "안방 화장실" },
          { text: { type: "plain_text", text: "🏠 거실" }, value: "거실" },
          { text: { type: "plain_text", text: "💧 세탁실" }, value: "세탁실" },
          { text: { type: "plain_text", text: "☀️ 베란다" }, value: "베란다" },
          { text: { type: "plain_text", text: "👟 현관" }, value: "현관" }
        ],
        action_id: "select_rooms"
      }
    },
    {
      type: "actions",
      elements: [{
        type: "button",
        text: { type: "plain_text", text: "✅ 사용량 기록시작" },
        action_id: "start_material_input",
        style: "primary"
      }]
    }
  ];
  
  sendSlackEphemeral(payload.channel.id, payload.user.id, "자재사용대장", blocks);
}

function startMaterialInput(payload) {
  // 선택된 방 가져오기
  const selectedRooms = payload.state.values[Object.keys(payload.state.values)[0]].select_rooms.selected_options.map(opt => opt.value);
  
  if (selectedRooms.length === 0) {
    return sendSlackEphemeral(payload.channel.id, payload.user.id, "❌ 방을 최소 1개 이상 선택해주세요.");
  }
  
  // 첫 번째 방의 색상 선택 화면 표시
  openColorSelection(payload, selectedRooms, 0);
}

function openColorSelection(payload, selectedRooms, roomIndex) {
  if (roomIndex >= selectedRooms.length) {
    // 모든 방 완료 → 발주 필요 여부 확인
    showMaterialOrderPrompt(payload);
    return;
  }
  
  const room = selectedRooms[roomIndex];
  const colorButtons = [
    { text: "110", value: `${room}|110|${roomIndex}|${selectedRooms.join(",")}` },
    { text: "111", value: `${room}|111|${roomIndex}|${selectedRooms.join(",")}` },
    { text: "112", value: `${room}|112|${roomIndex}|${selectedRooms.join(",")}` },
    { text: "113", value: `${room}|113|${roomIndex}|${selectedRooms.join(",")}` },
    { text: "130", value: `${room}|130|${roomIndex}|${selectedRooms.join(",")}` },
    { text: "기타", value: `${room}|custom|${roomIndex}|${selectedRooms.join(",")}`, action_id: "select_custom_color" }
  ];
  
  // 색상 버튼 표시 (Ephemeral)
  // ...
}

// 정규식 액션 핸들러
function handleSelectColor(payload) {
  const valueParts = payload.actions[0].value.split("|");
  const room = valueParts[0];
  const color = valueParts[1];
  const roomIndex = parseInt(valueParts[2]);
  const selectedRooms = valueParts[3].split(",");
  
  // 사용량 입력 화면 표시 (Ephemeral)
  // ...
}

function saveMaterialUsage(payload) {
  // 사용량 저장
  // 다음 방으로 이동 또는 완료 처리
  // ...
}
```

---

### 7. 발주 관리 완전한 기능
**현재 상태**: ❌ 기본 저장만 있음  
**PRD 참조**: 3.1.6, 3.2.3

```javascript
// 빠진 코드
function handleOrderList(payload) {
  if (!isAdmin(payload.user_id)) {
    return sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 관리자만 사용할 수 있습니다.");
  }
  
  const now = new Date();
  const orders = getPendingMaterialOrders(now.getFullYear(), now.getMonth() + 1);
  
  if (orders.length === 0) {
    return sendSlackMessage(payload.channel_id, `📦 ${now.getMonth() + 1}월 발주 목록이 비어있습니다.`);
  }
  
  let orderListText = orders.map((order, idx) => `${idx + 1}. ${order.content}`).join("\n");
  
  const blocks = [
    {
      type: "section",
      text: { type: "mrkdwn", text: `──────────────\n📦 **${now.getMonth() + 1}월 자재 발주 요청서 [Total: ${orders.length}건]**\n──────────────\n\n${orderListText}\n\n❗ 발주 완료된 항목의 번호를 입력하면 목록에서 지워집니다.` }
    },
    {
      type: "actions",
      elements: [
        {
          type: "button",
          text: { type: "plain_text", text: "📤 문자 발송 후 목록 최신화" },
          action_id: "send_order_message",
          style: "primary",
          value: JSON.stringify(orders)
        },
        {
          type: "button",
          text: { type: "plain_text", text: "🔄 목록 최신화" },
          action_id: "refresh_order_list",
          value: JSON.stringify(orders)
        }
      ]
    }
  ];
  
  sendSlackMessage(payload.channel_id, "", blocks);
}

function handleSendOrderMessage(payload) {
  const orders = JSON.parse(payload.actions[0].value);
  const orderListText = orders.map((order, idx) => `${idx + 1}. ${order.content}`).join("\n");
  
  const messageText = `---\n안녕하세요.\n디테일라인입니다.\n\n${orderListText}\n\n택배 발송 부탁드립니다.\n감사합니다.\n---`;
  
  // 관리자에게 DM 발송
  const adminIds = PROPERTIES.getProperty("ADMIN_SLACK_IDS").split(",");
  adminIds.forEach(adminId => {
    if (adminId) sendSlackMessage(adminId, messageText);
  });
  
  // 발주 완료 번호 입력 화면 표시
  // ...
}

function handleRefreshOrderList(payload) {
  // 발주 완료 번호 입력 화면 표시
  // ...
}

function handleUpdateOrderList(payload) {
  const completedNumbersStr = payload.view.state.values.completed_numbers_input.completed_numbers.value;
  const completedIndices = completedNumbersStr.split(",").map(x => parseInt(x.trim()) - 1);
  
  const orders = JSON.parse(payload.view.private_metadata);
  const rowIndicesToComplete = completedIndices
    .filter(idx => idx >= 0 && idx < orders.length)
    .map(idx => orders[idx].row_index);
  
  markOrdersCompleted(rowIndicesToComplete);
  
  // 잔여 발주 목록 표시
  // ...
}

function getPendingMaterialOrders(year, month) {
  const sheet = SS.getSheetByName("MaterialOrder");
  const data = sheet.getDataRange().getValues();
  
  const orders = [];
  const targetMonthStr = `${year}-${String(month).padStart(2, '0')}`;
  
  for (let i = 1; i < data.length; i++) {
    const dateStr = data[i][0];
    const completedTime = data[i][3] || "";
    
    if (!completedTime && dateStr && dateStr.toString().startsWith(targetMonthStr)) {
      orders.push({
        row_index: i + 1,
        date: dateStr,
        name: data[i][1],
        content: data[i][2]
      });
    }
  }
  
  return orders;
}

function markOrdersCompleted(rowIndices) {
  const sheet = SS.getSheetByName("MaterialOrder");
  const now = Utilities.formatDate(new Date(), "GMT+9", "yyyy-MM-dd HH:mm:ss");
  
  rowIndices.forEach(rowIdx => {
    sheet.getRange(rowIdx, 4).setValue(now); // D열에 완료 시간
  });
}
```

---

### 8. 급여 정산 미리보기 및 버튼
**현재 상태**: ❌ 바로 발송만 있음  
**PRD 참조**: 3.1.3, payroll-settlement-scenario.md

```javascript
// 현재 코드: 바로 모든 직원에게 발송
// PRD 요구사항: 미리보기 → 버튼 클릭 → 발송

// 빠진 코드
function handlePayrollSettlement(payload) {
  if (!isAdmin(payload.user_id)) {
    return sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 관리자만 사용할 수 있습니다.");
  }
  
  // 년월 파싱
  const text = payload.text ? payload.text.trim() : "";
  let year, month;
  if (text) {
    [year, month] = text.split("-").map(x => parseInt(x));
  } else {
    const now = new Date();
    year = now.getFullYear();
    month = now.getMonth() + 1;
  }
  
  const payrolls = calculateAllPayrolls(year, month);
  
  if (payrolls.length === 0) {
    return sendSlackEphemeral(payload.channel_id, payload.user_id, `❌ ${year}년 ${month}월 근무 기록이 없습니다.`);
  }
  
  const totalAmount = payrolls.reduce((sum, p) => sum + p.total_pay, 0);
  const totalWorkDays = payrolls.reduce((sum, p) => sum + p.work_days, 0);
  
  let previewText = `📊 **${year}년 ${month}월 급여 정산 미리보기**\n\n`;
  previewText += `• 총 인원: ${payrolls.length}명\n`;
  previewText += `• 총 근무일수: ${totalWorkDays}일\n`;
  previewText += `• 총 급여액: ${totalAmount.toLocaleString()}원\n\n`;
  previewText += "**상세 내역:**\n";
  payrolls.forEach(p => {
    previewText += `• ${p.name}: ${p.work_days}일, ${p.total_pay.toLocaleString()}원\n`;
  });
  
  const blocks = [
    {
      type: "section",
      text: { type: "mrkdwn", text: previewText }
    },
    {
      type: "actions",
      elements: [{
        type: "button",
        text: { type: "plain_text", text: "✅ 전 직원 발송" },
        style: "primary",
        action_id: "send_payrolls",
        value: `${year}-${month}`
      }]
    }
  ];
  
  sendSlackEphemeral(payload.channel_id, payload.user_id, previewText, blocks);
}

function handleSendPayrolls(payload) {
  const [year, month] = payload.actions[0].value.split("-").map(x => parseInt(x));
  const payrolls = calculateAllPayrolls(year, month);
  
  let successCount = 0;
  let failCount = 0;
  
  payrolls.forEach(payroll => {
    if (!payroll.slack_id) {
      failCount++;
      return;
    }
    
    try {
      // 개인별 급여 명세서 생성
      const totalDays = getTotalWorkDays(payroll.name);
      const avgDailyPay = payroll.base_pay / payroll.work_days;
      const avgDailyPayManwon = Math.floor(avgDailyPay / 10000);
      
      // 다음 일당 인상일 계산
      let nextRaiseDays = null;
      for (let rate of PAY_RATES) {
        if (totalDays < rate.max) {
          nextRaiseDays = rate.max + 1;
          break;
        }
      }
      
      // 인센티브 상세 내역
      const commissionDetails = getCommissionDetails(payroll.name, year, month);
      
      let msg = `📋 **[${payroll.name}님 ${year}년 ${month}월 급여 명세서]**\n\n`;
      msg += `💰 **총 지급액: ${Math.floor(payroll.total_pay / 10000)}만원**\n\n`;
      msg += `📅 **근무 내역**\n`;
      if (nextRaiseDays) {
        msg += `일당: ${avgDailyPayManwon}만원(${nextRaiseDays}일 근무시 인상)\n`;
      } else {
        msg += `일당: ${avgDailyPayManwon}만원\n`;
      }
      msg += `총 출근일수: ${payroll.work_days}일\n`;
      msg += `계산: ${avgDailyPayManwon}만원 × ${payroll.work_days}일 = ${Math.floor(payroll.base_pay / 10000)}만원\n`;
      msg += `교통비: ${Math.floor(payroll.transportation / 10000)}만원\n\n`;
      
      if (payroll.commission > 0) {
        msg += `💎 **인센티브**\n`;
        const commissionHalf = Math.floor(payroll.commission / 2);
        msg += `총 인센티브: ${Math.floor(payroll.commission / 10000)}만원 (${Math.floor(commissionHalf / 10000)}만원)\n\n`;
        
        if (commissionDetails.length > 0) {
          msg += `📆 **상세 내역**\n`;
          commissionDetails.forEach(detail => {
            const dateDisplay = detail.date.replace(/-/g, ".");
            const totalAmount = detail.total;
            const halfAmount = Math.floor(totalAmount / 2);
            msg += `⭐ ${dateDisplay} [${Math.floor(totalAmount / 10000)}만원 (${Math.floor(halfAmount / 10000)}만원)]\n`;
            detail.items.forEach(item => {
              if (item.description) {
                msg += ` ㆍ${item.description} ${Math.floor(item.amount / 10000)}만원\n`;
              }
            });
          });
          msg += "\n";
        }
      }
      
      msg += `🙌 한 달 동안 고생 많으셨습니다!`;
      
      sendSlackMessage(payroll.slack_id, msg);
      successCount++;
    } catch(e) {
      failCount++;
    }
  });
  
  // 관리자에게 결과 알림
  let resultMsg = `✅ **급여 명세서 발송 완료**\n\n`;
  resultMsg += `• 성공: ${successCount}명\n`;
  if (failCount > 0) {
    resultMsg += `• 실패: ${failCount}명\n`;
  }
  
  sendSlackEphemeral(payload.channel.id, payload.user.id, resultMsg);
}
```

---

## 🟢 Nice to Have (개선 사항)

### 9. 여러 현장 주소 처리
**현재 상태**: ⚠️ 첫 번째만 처리  
**PRD 참조**: 3.1.1

```javascript
// 현재: getCalendarSite()는 첫 번째만 반환
// PRD: 여러 현장 주소 모두 표시, T-map 버튼도 여러 개

function getTodaySiteAddresses() {
  const calId = PROPERTIES.getProperty("CALENDAR_ID");
  if (!calId) return [PROPERTIES.getProperty("SITE_ADDRESS")];
  
  try {
    const calendar = CalendarApp.getCalendarById(calId);
    const now = new Date();
    const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const endOfDay = new Date(startOfDay);
    endOfDay.setDate(endOfDay.getDate() + 1);
    
    const events = calendar.getEvents(startOfDay, endOfDay);
    const addresses = events
      .map(event => event.getLocation())
      .filter(location => location && location.trim() !== '');
    
    return addresses.length > 0 ? addresses : [PROPERTIES.getProperty("SITE_ADDRESS")];
  } catch(e) {
    return [PROPERTIES.getProperty("SITE_ADDRESS")];
  }
}

// handleCheckIn()에서 여러 주소 처리
function handleCheckIn(payload) {
  // ...
  const sites = getTodaySiteAddresses();
  
  // 메시지에 여러 현장 표시
  if (sites.length === 1) {
    // 단일 현장
  } else {
    // 여러 현장 (첫번째, 두번째 등으로 표시)
  }
  
  // T-map 버튼도 여러 개 생성
  // ...
}
```

---

### 10. 날씨 API 실제 구현
**현재 상태**: ⚠️ 구조만 있음  
**PRD 참조**: 6.5

```javascript
// 빠진 코드: 실제 기상청 API 연동
function getWeatherForecast(siteAddress) {
  const apiKey = PROPERTIES.getProperty("WEATHER_API_KEY");
  if (!apiKey) return { pop: null, pty: "없음", error: "API키 미설정" };
  
  // 주소를 격자 좌표로 변환
  const grid = addressToGrid(siteAddress);
  
  // 현재 시간 기준 base_time 계산
  const now = new Date();
  const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
  const today = Utilities.formatDate(kst, "GMT+9", "yyyyMMdd");
  const currentHour = kst.getHours();
  
  const baseTimes = [23, 20, 17, 14, 11, 8, 5, 2];
  let baseTimeHour = null;
  for (let bt of baseTimes) {
    if (currentHour >= bt || (bt === 23 && currentHour < 2)) {
      baseTimeHour = bt;
      break;
    }
  }
  
  if (baseTimeHour === null) baseTimeHour = 23;
  
  const baseDate = baseTimeHour === 23 ? 
    Utilities.formatDate(new Date(kst.getTime() - 24 * 60 * 60 * 1000), "GMT+9", "yyyyMMdd") : 
    today;
  const baseTime = String(baseTimeHour).padStart(2, '0') + "00";
  
  // API 호출
  const url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst";
  const params = {
    serviceKey: apiKey,
    numOfRows: 100,
    pageNo: 1,
    dataType: "JSON",
    base_date: baseDate,
    base_time: baseTime,
    nx: grid.nx,
    ny: grid.ny
  };
  
  const queryString = Object.keys(params)
    .map(key => `${key}=${encodeURIComponent(params[key])}`)
    .join('&');
  
  try {
    const response = UrlFetchApp.fetch(`${url}?${queryString}`, {
      method: "get",
      muteHttpExceptions: true
    });
    
    const data = JSON.parse(response.getContentText());
    
    if (data.response.header.resultCode !== "00") {
      return { pop: null, pty: "없음", error: data.response.header.resultMsg };
    }
    
    const items = data.response.body.items.item;
    const forecastDate = Utilities.formatDate(kst, "GMT+9", "yyyyMMdd");
    
    const popValues = [];
    const ptyValues = [];
    
    items.forEach(item => {
      if (item.fcstDate === forecastDate && 
          ["12", "13", "14", "15", "16", "17", "18"].includes(item.fcstTime.substring(0, 2))) {
        if (item.category === "POP") {
          popValues.push(parseInt(item.fcstValue));
        } else if (item.category === "PTY") {
          const ptyCode = parseInt(item.fcstValue);
          const ptyMap = { 0: "없음", 1: "비", 2: "비/눈", 3: "눈", 4: "소나기" };
          ptyValues.push(ptyMap[ptyCode] || "없음");
        }
      }
    });
    
    const avgPop = popValues.length > 0 ? 
      Math.max(Math.floor(popValues.reduce((a, b) => a + b, 0) / popValues.length), Math.max(...popValues)) : 
      null;
    
    let pty = "없음";
    if (ptyValues.length > 0) {
      if (ptyValues.some(p => p !== "없음")) {
        if (ptyValues.some(p => p.includes("비"))) pty = "비";
        else if (ptyValues.some(p => p.includes("눈"))) pty = "눈";
      }
    }
    
    return { pop: avgPop, pty: pty, error: null };
  } catch(e) {
    return { pop: null, pty: "없음", error: e.toString() };
  }
}

function addressToGrid(address) {
  // 주소를 기상청 격자 좌표로 변환
  // 간단한 매핑 테이블 사용 (실제로는 더 정교한 변환이 필요)
  const regionCoords = {
    "서울": { nx: 60, ny: 127 },
    "강남": { nx: 61, ny: 126 },
    // ... 더 많은 지역 매핑
  };
  
  for (let region in regionCoords) {
    if (address.includes(region)) {
      return regionCoords[region];
    }
  }
  
  return { nx: 60, ny: 127 }; // 기본값 (서울)
}
```

---

### 11. T-map 리다이렉트 개선
**현재 상태**: ⚠️ iOS만 처리  
**PRD 참조**: 6.6

```javascript
// 현재: iOS URL만
// PRD: Android/iOS 감지 및 Fallback

function doGet(e) {
  const addr = e.parameter.addr;
  if (!addr) return HtmlService.createHtmlOutput("주소가 없습니다.");
  
  const encodedAddr = encodeURIComponent(addr);
  const androidIntent = `intent://search?name=${encodedAddr}#Intent;scheme=tmap;package=com.skt.tmap.ku;end;`;
  const iosScheme = `tmap://search?name=${encodedAddr}`;
  const fallbackWeb = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
  
  const html = `
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>T-map 열기</title>
      <script>
        function isAndroid() {
          return /Android/i.test(navigator.userAgent);
        }
        function isIOS() {
          return /iPhone|iPad|iPod/i.test(navigator.userAgent);
        }
        function openApp() {
          var tried = false;
          if (isAndroid()) {
            tried = true;
            window.location.href = "${androidIntent}";
          } else if (isIOS()) {
            tried = true;
            window.location.href = "${iosScheme}";
          }
          setTimeout(function() {
            if (tried) {
              window.location.href = "${fallbackWeb}";
            }
          }, 1500);
        }
        window.onload = openApp;
      </script>
    </head>
    <body style="font-family: sans-serif; text-align: center; padding: 20px;">
      <p>T-map 앱을 여는 중입니다...</p>
      <p>자동으로 열리지 않으면 <a href="${fallbackWeb}">여기</a>를 눌러주세요.</p>
    </body>
    </html>
  `;
  
  return HtmlService.createHtmlOutput(html).setTitle("T-map 열기");
}
```

---

### 12. 칭호 시스템
**현재 상태**: ❌ 없음  
**PRD 참조**: 5.1

```javascript
// 빠진 코드
function getUserTitle(totalDays) {
  const level = Math.floor(totalDays / 3);
  const titles = {
    1: "현장 참관자", 2: "작업 보조", 3: "도구 전달자",
    // ... 100단계까지
    100: "줄눈 마스터"
  };
  return titles[level] || `Lv.${level}`;
}
```

---

### 13. 경험치 진행률 상세
**현재 상태**: ⚠️ 간단한 진행바만  
**PRD 참조**: 5.4

```javascript
// 현재: getProgressBar()는 레벨 기준만
// PRD: 레벨 진행률 + 각성 진행률 모두 필요

function getExpProgress(totalDays) {
  const currentLevel = Math.floor(totalDays / 3);
  const nextLevel = currentLevel + 1;
  const currentLevelDays = currentLevel * 3;
  const nextLevelDays = nextLevel * 3;
  const levelRequiredDays = nextLevelDays - currentLevelDays;
  const progressDays = totalDays - currentLevelDays;
  
  const percentage = levelRequiredDays > 0 ? 
    Math.floor((progressDays / levelRequiredDays) * 100) : 100;
  
  const filled = Math.floor(percentage / 10);
  const progressBar = "■".repeat(filled) + "□".repeat(10 - filled);
  const daysToNext = nextLevelDays - totalDays;
  
  return { progressBar, percentage, daysToNext };
}

function getAwakeningProgress(totalDays) {
  const milestones = [45, 90, 135, 180, 225, 270];
  let currentMilestone = 0;
  let nextMilestone = 45;
  
  for (let milestone of milestones) {
    if (totalDays >= milestone) {
      currentMilestone = milestone;
    } else {
      nextMilestone = milestone;
      break;
    }
  }
  
  if (totalDays >= 270) {
    return { progressBar: "■■■■■■■■■■", percentage: 100, daysToNext: 0, nextMilestone: null };
  }
  
  const progressDays = totalDays - currentMilestone;
  const requiredDays = nextMilestone - currentMilestone;
  const percentage = requiredDays > 0 ? Math.floor((progressDays / requiredDays) * 100) : 100;
  
  const filled = Math.floor(percentage / 10);
  const progressBar = "■".repeat(filled) + "□".repeat(10 - filled);
  const daysToNext = nextMilestone - totalDays;
  
  return { progressBar, percentage, daysToNext, nextMilestone };
}
```

---

### 14. 인센티브 상세 내역
**현재 상태**: ❌ 총액만 계산  
**PRD 참조**: 3.1.3

```javascript
// 빠진 코드
function getCommissionDetails(userName, year, month) {
  const sheet = SS.getSheetByName("Incentive");
  const data = sheet.getDataRange().getValues();
  
  const detailsByDate = {};
  const targetMonthStr = `${year}-${String(month).padStart(2, '0')}`;
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][1] === userName) {
      const dateStr = data[i][0].toString();
      if (dateStr.startsWith(targetMonthStr)) {
        const date = dateStr.split(' ')[0]; // 날짜 부분만
        const amount = Number(data[i][2]) || 0;
        const description = data[i][3] || "";
        
        if (!detailsByDate[date]) {
          detailsByDate[date] = {
            date: date,
            total: 0,
            items: []
          };
        }
        
        detailsByDate[date].total += amount;
        detailsByDate[date].items.push({
          description: description,
          amount: amount
        });
      }
    }
  }
  
  return Object.values(detailsByDate);
}
```

---

### 15. check_out_from_photo 액션
**현재 상태**: ❌ 없음  
**PRD 참조**: 3.2.2

```javascript
// 빠진 코드
function handleCheckOutFromPhoto(payload) {
  // 폴더 생성 후 "경험치 획득(퇴근)" 버튼 클릭 시
  // 퇴근 처리
  handleCheckOut({
    user_id: payload.user.id,
    channel_id: payload.channel.id,
    user: payload.user
  });
}
```

---

### 16. Ephemeral 메시지 전송 함수
**현재 상태**: ❌ 없음  
**PRD 참조**: 여러 곳에서 사용

```javascript
// 빠진 코드
function sendSlackEphemeral(channel, user, text, blocks = null) {
  const token = PROPERTIES.getProperty("SLACK_BOT_TOKEN");
  const payload = {
    channel: channel,
    user: user,
    text: text
  };
  if (blocks) payload.blocks = blocks;
  
  UrlFetchApp.fetch("https://slack.com/api/chat.postEphemeral", {
    method: "post",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    payload: JSON.stringify(payload)
  });
}
```

---

### 17. 에러 처리 강화
**현재 상태**: ⚠️ 기본적인 try-catch만  
**PRD 참조**: 12.2

```javascript
// 모든 함수에 에러 처리 추가 필요
// Logger 서비스 활용
// 사용자에게 친화적인 에러 메시지 전송
```

---

### 18. 시트 이름 상수화
**현재 상태**: ⚠️ 하드코딩  
**PRD 참조**: 4.1

```javascript
// 빠진 코드
const SHEET_NAMES = {
  ATTENDANCE_LOG: "AttendanceLog",
  USER_MASTER: "UserMaster",
  MATERIAL_LOG: "MaterialLog",
  MATERIAL_ORDER: "MaterialOrder",
  INCENTIVE: "Incentive"  // 현재 코드는 "CommissionLog"로 되어있음
};
```

---

## 📋 요약

### Critical (즉시 구현 필요)
1. ✅ Slack 요청 검증
2. ✅ 관리자 권한 체크
3. ✅ 레벨업/각성 체크 및 DM 발송
4. ✅ 일자별 단가 계산

### Important (중요 기능)
5. ✅ `/출근로그`, `/정산내역`, `/hello`, `/netcheck` 명령어
6. ✅ 자재사용대장 복잡한 플로우
7. ✅ 발주 관리 완전한 기능
8. ✅ 급여 정산 미리보기 및 버튼

### Nice to Have (개선)
9. ✅ 여러 현장 주소 처리
10. ✅ 날씨 API 실제 구현
11. ✅ T-map 리다이렉트 개선
12. ✅ 칭호 시스템
13. ✅ 경험치 진행률 상세
14. ✅ 인센티브 상세 내역
15. ✅ check_out_from_photo 액션
16. ✅ Ephemeral 메시지 전송 함수
17. ✅ 에러 처리 강화
18. ✅ 시트 이름 상수화

---

**총 빠진 기능**: 약 18개 주요 기능 + 여러 세부 기능

