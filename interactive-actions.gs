/**
 * Interactive Actions 핸들러
 */

// ==========================================
// 1. 자재사용대장 관련 액션
// ==========================================

function openMaterialLog(payload) {
  try {
    // payload 구조: { user: { id: "..." }, channel: { id: "..." }, ... }
    const userId = payload.user ? payload.user.id : (payload.user_id || "");
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!userId) {
      Logger.log("No user ID in payload");
      return;
    }
    
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
        text: { type: "mrkdwn", text: " " },
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
          text: { type: "plain_text", text: "✅ 사용량 기록시작" },
          action_id: "start_material_input",
          style: "primary"
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "자재사용대장", blocks);
  } catch(error) {
    Logger.log("Error in openMaterialLog: " + error);
  }
}

function startMaterialInput(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    // 선택된 방 가져오기
    let selectedRooms = [];
    if (payload.state && payload.state.values) {
      for (let blockId in payload.state.values) {
        const blockValues = payload.state.values[blockId];
        if (blockValues.select_rooms && blockValues.select_rooms.selected_options) {
          selectedRooms = blockValues.select_rooms.selected_options.map(opt => opt.value);
        }
      }
    }
    
    if (selectedRooms.length === 0) {
      sendSlackEphemeral(channelId, userId, "❌ 방을 최소 1개 이상 선택해주세요.");
      return;
    }
    
    // 첫 번째 방의 색상 선택 화면 표시
    openColorSelection(payload, selectedRooms, 0);
  } catch(error) {
    Logger.log("Error in startMaterialInput: " + error);
  }
}

function openColorSelection(payload, selectedRooms, roomIndex) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (roomIndex >= selectedRooms.length) {
      // 모든 방 완료 → 발주 필요 여부 확인
      showMaterialOrderPrompt(payload, selectedRooms);
      return;
    }
    
    const room = selectedRooms[roomIndex];
    const completedRooms = selectedRooms.slice(0, roomIndex);
    
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `📋 **자재사용대장**\n\n**${room}**을 선택하셨습니다.\n빅라이언 어떤 색상을 사용하셨나요?`
        }
      }
    ];
    
    // 색상 버튼들 (2열로 배치)
    const colorButtons = [];
    MATERIAL_COLORS.forEach(color => {
      if (color === "기타") {
        colorButtons.push({
          type: "button",
          text: { type: "plain_text", text: "기타" },
          action_id: "select_custom_color",
          value: `${room}|custom|${roomIndex}|${selectedRooms.join(",")}`
        });
      } else {
        colorButtons.push({
          type: "button",
          text: { type: "plain_text", text: color },
          action_id: `select_color_${color}`,
          value: `${room}|${color}|${roomIndex}|${selectedRooms.join(",")}`
        });
      }
    });
    
    // 2열로 나누기
    for (let i = 0; i < colorButtons.length; i += 2) {
      const rowButtons = colorButtons.slice(i, i + 2);
      blocks.push({
        type: "actions",
        elements: rowButtons
      });
    }
    
    // 완료된 방 표시
    if (completedRooms.length > 0) {
      blocks.push({
        type: "section",
        text: {
          type: "mrkdwn",
          text: `✅ 완료: ${completedRooms.join(", ")}`
        }
      });
    }
    
    sendSlackEphemeral(channelId, userId, "자재 색상을 선택해주세요.", blocks);
  } catch(error) {
    Logger.log("Error in openColorSelection: " + error);
  }
}

function handleSelectColor(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    const valueParts = payload.actions[0].value.split("|");
    const room = valueParts[0];
    const color = valueParts[1];
    const roomIndex = parseInt(valueParts[2]);
    const selectedRooms = valueParts[3].split(",");
    
    const roomEmoji = getRoomEmoji(room);
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `──────────────\n📋 **자재사용대장**\n──────────────\n\n${roomEmoji} ${room} [ ${color}번 색상 ]\n\n이 구역에 투입된 용량을 입력해주세요.`
        }
      },
      {
        type: "input",
        block_id: "qty_input",
        element: {
          type: "plain_text_input",
          action_id: "qty",
          placeholder: { type: "plain_text", text: "예: 200" }
        },
        label: { type: "plain_text", text: "사용량" }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          action_id: "save_material_usage",
          text: { type: "plain_text", text: "✅ 저장" },
          style: "primary",
          value: `${room}|${color}|${roomIndex}|${selectedRooms.join(",")}`
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "자재 사용량을 입력해주세요.", blocks);
  } catch(error) {
    Logger.log("Error in handleSelectColor: " + error);
  }
}

function handleSelectCustomColor(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    const valueParts = payload.actions[0].value.split("|");
    const room = valueParts[0];
    const roomIndex = parseInt(valueParts[2]);
    const selectedRooms = valueParts[3].split(",");
    
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `📋 **자재사용대장**\n\n**${room}**의 색상을 직접 입력해주세요:`
        }
      },
      {
        type: "input",
        block_id: "color_input",
        element: {
          type: "plain_text_input",
          action_id: "custom_color",
          placeholder: { type: "plain_text", text: "예: 187, 200, 기타색상" }
        },
        label: { type: "plain_text", text: "색상" }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          action_id: "confirm_custom_color",
          text: { type: "plain_text", text: "✅ 확인" },
          style: "primary",
          value: `${room}|${roomIndex}|${selectedRooms.join(",")}`
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "색상을 입력해주세요.", blocks);
  } catch(error) {
    Logger.log("Error in handleSelectCustomColor: " + error);
  }
}

function handleConfirmCustomColor(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    const valueParts = payload.actions[0].value.split("|");
    const room = valueParts[0];
    const roomIndex = parseInt(valueParts[1]);
    const selectedRooms = valueParts[2].split(",");
    
    // state에서 색상 읽기
    let customColor = "";
    if (payload.state && payload.state.values) {
      for (let blockId in payload.state.values) {
        const blockValues = payload.state.values[blockId];
        if (blockValues.color_input && blockValues.color_input.custom_color) {
          customColor = blockValues.color_input.custom_color.value.trim();
        }
      }
    }
    
    if (!customColor) {
      sendSlackEphemeral(channelId, userId, "❌ 자재사용대장: 색상을 입력해주세요.");
      return;
    }
    
    const roomEmoji = getRoomEmoji(room);
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `──────────────\n📋 **자재사용대장**\n──────────────\n\n${roomEmoji} ${room} [ ${customColor}번 색상 ]\n\n이 구역에 투입된 용량을 입력해주세요.`
        }
      },
      {
        type: "input",
        block_id: "qty_input",
        element: {
          type: "plain_text_input",
          action_id: "qty",
          placeholder: { type: "plain_text", text: "예: 5" }
        },
        label: { type: "plain_text", text: "사용량" }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          action_id: "save_material_usage",
          text: { type: "plain_text", text: "✅ 저장" },
          style: "primary",
          value: `${room}|${customColor}|${roomIndex}|${selectedRooms.join(",")}`
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "자재 사용량을 입력해주세요.", blocks);
  } catch(error) {
    Logger.log("Error in handleConfirmCustomColor: " + error);
  }
}

function saveMaterialUsage(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    // state에서 수량 읽기
    let qtyStr = "";
    if (payload.state && payload.state.values) {
      for (let blockId in payload.state.values) {
        const blockValues = payload.state.values[blockId];
        if (blockValues.qty_input && blockValues.qty_input.qty) {
          qtyStr = blockValues.qty_input.qty.value.trim();
        }
      }
    }
    
    if (!qtyStr) {
      sendSlackEphemeral(channelId, userId, "❌ 자재사용대장: 사용량을 입력해주세요.");
      return;
    }
    
    const quantity = parseFloat(qtyStr);
    if (isNaN(quantity) || quantity <= 0) {
      sendSlackEphemeral(channelId, userId, "❌ 자재사용대장: 올바른 숫자를 입력해주세요.");
      return;
    }
    
    // value에서 room / color / room_index / selected_rooms 파싱
    const valueParts = payload.actions[0].value.split("|");
    const room = valueParts[0];
    const color = valueParts[1];
    const roomIndex = parseInt(valueParts[2]);
    const selectedRooms = valueParts[3].split(",");
    
    // 사용자 정보 조회
    const userInfo = getUserInfo(userId);
    if (!userInfo) {
      sendSlackEphemeral(channelId, userId, "❌ 사용자 정보가 없습니다.");
      return;
    }
    
    // 시트 기록
    const result = recordMaterialUsage(userInfo.name, room, color, quantity);
    if (!result.success) {
      sendSlackEphemeral(channelId, userId, `❌ 자재사용대장 기록 실패: ${result.message}`);
      return;
    }
    
    // 현재 방 완료 안내
    const roomEmoji = getRoomEmoji(room);
    const completionText = `──────────────\n👌 **입력 확인!**\n──────────────\n\n깔끔하게 장부에 적어두었습니다.\n\n──────────────\n＊ **기록 내용**\n\n1. ${roomEmoji} ${room} [ ${color}번 색상 ] -  ${quantity}g 사용`;
    
    sendSlackEphemeral(channelId, userId, "입력 확인", [{
      type: "section",
      text: { type: "mrkdwn", text: completionText }
    }]);
    
    // 다음 방이 있으면 계속, 없으면 발주 필요 여부 확인
    const nextRoomIndex = roomIndex + 1;
    if (nextRoomIndex < selectedRooms.length) {
      openColorSelection(payload, selectedRooms, nextRoomIndex);
    } else {
      showMaterialOrderPrompt(payload, selectedRooms);
    }
  } catch(error) {
    Logger.log("Error in saveMaterialUsage: " + error);
  }
}

function showMaterialOrderPrompt(payload, selectedRooms) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    const doneRooms = selectedRooms.join(", ");
    
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `──────────────\n✋ **잠깐! 자재가 비어가진 않나요?**\n──────────────`
        }
      },
      {
        type: "actions",
        elements: [
          {
            type: "button",
            text: { type: "plain_text", text: "발주 요청하기" },
            action_id: "material_order_required",
            style: "primary",
            value: doneRooms
          },
          {
            type: "button",
            text: { type: "plain_text", text: "기록 종료하기(없음)" },
            action_id: "material_order_not_required",
            value: doneRooms
          }
        ]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "자재 사용 기록 완료", blocks);
  } catch(error) {
    Logger.log("Error in showMaterialOrderPrompt: " + error);
  }
}

function handleMaterialOrderRequired(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `──────────────\n🛒 **자재 발주 요청**\n──────────────\n\n필요하신 물품과 수량을 적어주세요.\n바로 발주 넣을 수 있게 준비하겠습니다.`
        }
      },
      {
        type: "input",
        block_id: "order_input",
        element: {
          type: "plain_text_input",
          action_id: "order_text",
          multiline: true,
          placeholder: { type: "plain_text", text: "예: 빅라이언 100, 짤주머니 한 박스 등" }
        },
        label: { type: "plain_text", text: "발주 내용" }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          text: { type: "plain_text", text: "✅ 저장" },
          action_id: "save_material_order",
          style: "primary"
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "발주 필요 자재 입력", blocks);
  } catch(error) {
    Logger.log("Error in handleMaterialOrderRequired: " + error);
  }
}

function handleMaterialOrderNotRequired(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    const doneRooms = payload.actions[0].value;
    
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `✅ 모든 방의 자재 사용 기록이 완료되었습니다!\n완료된 방: ${doneRooms}\n\n📦 발주 필요 자재 없음`
        }
      },
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "**아래 버튼을 클릭하면 현장 사진 폴더가 생성됩니다.**"
        }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          text: { type: "plain_text", text: "📁 현장사진 폴더생성" },
          action_id: "create_photo_folder",
          style: "primary",
          value: "create"
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "자재 사용 기록 완료", blocks);
  } catch(error) {
    Logger.log("Error in handleMaterialOrderNotRequired: " + error);
  }
}

function saveMaterialOrder(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    // state에서 발주 내용 읽기
    let orderText = "";
    if (payload.state && payload.state.values) {
      for (let blockId in payload.state.values) {
        const blockValues = payload.state.values[blockId];
        if (blockValues.order_input && blockValues.order_input.order_text) {
          orderText = blockValues.order_input.order_text.value.trim();
        }
      }
    }
    
    if (!orderText) {
      sendSlackEphemeral(channelId, userId, "❌ 발주 내용을 입력해주세요.");
      return;
    }
    
    // 사용자 정보 조회
    const userInfo = getUserInfo(userId);
    if (!userInfo) {
      sendSlackEphemeral(channelId, userId, "❌ 사용자 정보가 없습니다.");
      return;
    }
    
    // 시트에 발주 기록
    const result = recordMaterialOrder(userInfo.name, orderText);
    if (!result.success) {
      sendSlackEphemeral(channelId, userId, `❌ 발주 기록 실패: ${result.message}`);
      return;
    }
    
    // 폴더 생성 버튼 포함 메시지
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: `✅ 발주 내용이 기록되었습니다!\n\n📦 **발주 내용:**\n${orderText}`
        }
      },
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "**아래 버튼을 클릭하면 현장 사진 폴더가 생성됩니다.**"
        }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          text: { type: "plain_text", text: "📁 현장사진 폴더생성" },
          action_id: "create_photo_folder",
          style: "primary",
          value: "create"
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "발주 기록 완료", blocks);
  } catch(error) {
    Logger.log("Error in saveMaterialOrder: " + error);
  }
}

// ==========================================
// 2. 현장사진 관련 액션
// ==========================================

function createPhotoFolder(payload) {
  try {
    // payload 구조 확인
    const userId = payload.user ? payload.user.id : (payload.user_id || "");
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!userId) {
      Logger.log("No user ID in payload for createPhotoFolder");
      return;
    }
    
    // 생성 중 메시지 전송
    sendSlackEphemeral(channelId, userId, "📁 드라이브를 생성중입니다...");
    
    // 현장 주소 가져오기
    const siteAddresses = getTodaySiteAddresses();
    const siteAddress = siteAddresses.length > 0 ? siteAddresses[0] : "";
    
    // Google Drive 폴더 생성
    const result = createSitePhotoFolder(siteAddress);
    
    if (!result.success) {
      sendSlackEphemeral(channelId, userId, `❌ ${result.message}`);
      return;
    }
    
    // 사진 업로드 버튼 포함 완료 메시지
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
            text: { type: "plain_text", text: "📷 현장사진 업로드" },
            url: result.folderUrl,
            style: "primary"
          },
          {
            type: "button",
            text: { type: "plain_text", text: "⭐ 경험치 획득(퇴근)" },
            action_id: "check_out_from_photo",
            style: "primary",
            value: "check_out"
          }
        ]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "폴더 생성 완료", blocks);
  } catch(error) {
    Logger.log("Error in createPhotoFolder: " + error);
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    sendSlackEphemeral(channelId, userId, "❌ 폴더 생성 중 오류가 발생했습니다. 다시 시도해 주세요.");
  }
}

function handleCheckOutFromPhoto(payload) {
  // 폴더 생성 후 "경험치 획득(퇴근)" 버튼 클릭 시 퇴근 처리
  const checkOutPayload = {
    user_id: payload.user ? payload.user.id : payload.user_id,
    channel_id: payload.channel ? payload.channel.id : (payload.channel_id || payload.user.id),
    user: payload.user || { id: payload.user_id, name: "" }
  };
  
  handleCheckOut(checkOutPayload);
}

// ==========================================
// 3. 발주 관리 관련 액션
// ==========================================

function handleSendOrderMessage(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!isAdmin(userId)) {
      sendSlackEphemeral(channelId, userId, "❌ 이 작업은 관리자만 수행할 수 있습니다.");
      return;
    }
    
    // value에서 주문 목록 파싱
    const orders = JSON.parse(payload.actions[0].value);
    const orderListText = orders.map((order, idx) => `${idx + 1}. ${order.content}`).join("\n");
    
    const messageText = `---\n안녕하세요.\n디테일라인입니다.\n\n${orderListText}\n\n택배 발송 부탁드립니다.\n감사합니다.\n---`;
    
    // 관리자에게 DM 발송
    const adminIds = PROPERTIES.getProperty("ADMIN_SLACK_IDS").split(",");
    adminIds.forEach(adminId => {
      if (adminId) sendSlackMessage(adminId, messageText);
    });
    
    // 발주 완료 번호 입력 화면 표시
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "✅ 관리자에게 발주 메시지가 전송되었습니다.\n\n발주 완료된 항목의 번호를 입력해주세요. (예: 1,3)"
        }
      },
      {
        type: "input",
        block_id: "completed_numbers_input",
        element: {
          type: "plain_text_input",
          action_id: "completed_numbers",
          placeholder: { type: "plain_text", text: "예: 1,3" }
        },
        label: { type: "plain_text", text: "발주 완료 번호" }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          text: { type: "plain_text", text: "✅ 최신화" },
          action_id: "update_order_list",
          style: "primary",
          value: payload.actions[0].value
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "발주 완료 번호를 입력해주세요.", blocks);
  } catch(error) {
    Logger.log("Error in handleSendOrderMessage: " + error);
  }
}

function handleRefreshOrderList(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!isAdmin(userId)) {
      sendSlackEphemeral(channelId, userId, "❌ 이 작업은 관리자만 수행할 수 있습니다.");
      return;
    }
    
    // 발주 완료 번호 입력 화면
    const blocks = [
      {
        type: "section",
        text: {
          type: "mrkdwn",
          text: "발주 완료된 항목의 번호를 입력해주세요. (예: 1,3)"
        }
      },
      {
        type: "input",
        block_id: "completed_numbers_input",
        element: {
          type: "plain_text_input",
          action_id: "completed_numbers",
          placeholder: { type: "plain_text", text: "예: 1,3" }
        },
        label: { type: "plain_text", text: "발주 완료 번호" }
      },
      {
        type: "actions",
        elements: [{
          type: "button",
          text: { type: "plain_text", text: "✅ 최신화" },
          action_id: "update_order_list",
          style: "primary",
          value: payload.actions[0].value
        }]
      }
    ];
    
    sendSlackEphemeral(channelId, userId, "발주 완료 번호를 입력해주세요.", blocks);
  } catch(error) {
    Logger.log("Error in handleRefreshOrderList: " + error);
  }
}

function handleUpdateOrderList(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!isAdmin(userId)) {
      sendSlackEphemeral(channelId, userId, "❌ 이 작업은 관리자만 수행할 수 있습니다.");
      return;
    }
    
    // state에서 완료 번호 읽기
    let completedNumbersStr = "";
    if (payload.view && payload.view.state && payload.view.state.values) {
      for (let blockId in payload.view.state.values) {
        const blockValues = payload.view.state.values[blockId];
        if (blockValues.completed_numbers_input && blockValues.completed_numbers_input.completed_numbers) {
          completedNumbersStr = blockValues.completed_numbers_input.completed_numbers.value.trim();
        }
      }
    }
    
    if (!completedNumbersStr) {
      sendSlackEphemeral(channelId, userId, "❌ 발주 완료 번호를 입력해주세요.");
      return;
    }
    
    // 번호 파싱 (예: "1,3" -> [1, 3])
    const completedIndices = completedNumbersStr.split(",").map(x => parseInt(x.trim()) - 1);
    
    // value에서 주문 목록 파싱
    const orders = JSON.parse(payload.actions[0].value);
    
    // 완료 처리할 행 번호 추출
    const rowIndicesToComplete = [];
    completedIndices.forEach(idx => {
      if (idx >= 0 && idx < orders.length) {
        rowIndicesToComplete.push(orders[idx].row_index);
      }
    });
    
    if (rowIndicesToComplete.length === 0) {
      sendSlackEphemeral(channelId, userId, "❌ 유효한 발주 번호를 입력해주세요.");
      return;
    }
    
    // 시트에 완료 처리
    const result = markOrdersCompleted(rowIndicesToComplete);
    if (!result.success) {
      sendSlackEphemeral(channelId, userId, `❌ 발주 완료 처리 실패: ${result.message}`);
      return;
    }
    
    // 잔여 발주 목록 구성
    const remainingOrders = orders.filter((order, idx) => !completedIndices.includes(idx));
    
    let msg = `──────────────\n👌 **발주 목록을 최신화 합니다.**\n──────────────\n\n`;
    if (remainingOrders.length > 0) {
      const remainingListText = remainingOrders.map((order, idx) => `${idx + 1}. ${order.content}`).join("\n");
      msg += `아래 항목은 잔여 발주 목록 입니다.\n\n${remainingListText}\n\n(잔여 발주: ${remainingOrders.length}건 남음)`;
    } else {
      msg += `✅ 모든 발주가 완료 처리되었습니다!`;
    }
    
    sendSlackEphemeral(channelId, userId, msg);
  } catch(error) {
    Logger.log("Error in handleUpdateOrderList: " + error);
  }
}

function handleConfirmOrderUpdate(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    sendSlackEphemeral(channelId, userId, "감사합니다. 추가 요청이 있으면 말씀해주세요.");
  } catch(error) {
    Logger.log("Error in handleConfirmOrderUpdate: " + error);
  }
}

// ==========================================
// 4. 급여 정산 관련 액션
// ==========================================

function handleSendPayrolls(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!isAdmin(userId)) {
      sendSlackEphemeral(channelId, userId, "❌ 이 작업은 관리자만 수행할 수 있습니다.");
      return;
    }
    
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
        const avgDailyPay = payroll.work_days > 0 ? payroll.base_pay / payroll.work_days : 0;
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
            msg += `\n`;
          }
        }
        
        msg += `🙌 한 달 동안 고생 많으셨습니다!`;
        
        sendSlackMessage(payroll.slack_id, msg);
        successCount++;
      } catch(e) {
        Logger.log("Error sending payroll to " + payroll.name + ": " + e);
        failCount++;
      }
    });
    
    // 관리자에게 결과 알림
    let resultMsg = `✅ **급여 명세서 발송 완료**\n\n`;
    resultMsg += `• 성공: ${successCount}명\n`;
    if (failCount > 0) {
      resultMsg += `• 실패: ${failCount}명\n`;
    }
    
    sendSlackEphemeral(channelId, userId, resultMsg);
  } catch(error) {
    Logger.log("Error in handleSendPayrolls: " + error);
  }
}

function handleSelectUserAttendance(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!isAdmin(userId)) {
      return;
    }
    
    const selectedName = payload.actions[0].selected_option.value;
    const logs = getAttendanceLogs(selectedName);
    
    if (logs.length === 0) {
      sendSlackEphemeral(channelId, userId, `❌ ${selectedName}님의 출근 기록이 없습니다.`);
      return;
    }
    
    let msg = `📋 **${selectedName}님 출근 로그**\n\n총 ${logs.length}건의 출근 기록\n\n`;
    logs.forEach(log => {
      msg += `• ${log.date} ${log.time}`;
      if (log.remarks) msg += ` (${log.remarks})`;
      msg += `\n`;
    });
    
    sendSlackEphemeral(channelId, userId, msg);
  } catch(error) {
    Logger.log("Error in handleSelectUserAttendance: " + error);
  }
}

function handleSelectUserPayroll(payload) {
  try {
    const userId = payload.user ? payload.user.id : payload.user_id;
    const channelId = payload.channel ? payload.channel.id : (payload.channel_id || userId);
    
    if (!isAdmin(userId)) {
      return;
    }
    
    const selectedName = payload.actions[0].selected_option.value;
    const payrolls = getUserPayrollHistory(selectedName);
    
    if (payrolls.length === 0) {
      sendSlackEphemeral(channelId, userId, `❌ ${selectedName}님의 급여 기록이 없습니다.`);
      return;
    }
    
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
    
    sendSlackEphemeral(channelId, userId, msg);
  } catch(error) {
    Logger.log("Error in handleSelectUserPayroll: " + error);
  }
}

// ==========================================
// 5. View Submission 핸들러
// ==========================================

function handleMaterialQuantitySubmit(payload) {
  // 모달 제출 처리 (현재는 사용하지 않지만 에러 방지용)
  return ContentService.createTextOutput("");
}

// ==========================================
// 6. 유틸리티 함수
// ==========================================

function getRoomEmoji(room) {
  const roomEmojis = {
    "거실 화장실": "🚽",
    "안방 화장실": "🚽",
    "거실": "🏠",
    "세탁실": "💧",
    "베란다": "☀️",
    "현관": "👟"
  };
  return roomEmojis[room] || "📍";
}

