/**
 * 유틸리티 함수들
 */

// ==========================================
// 1. 관리자 권한 체크
// ==========================================
function isAdmin(userId) {
  const adminIds = PROPERTIES.getProperty("ADMIN_SLACK_IDS");
  if (!adminIds) return false;
  return adminIds.split(",").includes(userId);
}

// ==========================================
// 2. Google Calendar 연동
// ==========================================
function getTodaySiteAddresses() {
  const calId = PROPERTIES.getProperty("GOOGLE_CALENDAR_ID");
  const defaultAddress = PROPERTIES.getProperty("SITE_ADDRESS") || "현장정보 없음";
  
  if (!calId) {
    Logger.log("GOOGLE_CALENDAR_ID not set, using default address: " + defaultAddress);
    return [defaultAddress];
  }
  
  try {
    const calendar = CalendarApp.getCalendarById(calId);
    const now = new Date();
    // KST 시간대로 변환 (UTC+9)
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    const startOfDay = new Date(kst.getFullYear(), kst.getMonth(), kst.getDate());
    const endOfDay = new Date(startOfDay);
    endOfDay.setDate(endOfDay.getDate() + 1);
    
    Logger.log("=== Calendar 조회 시작 ===");
    Logger.log("조회 기간: " + Utilities.formatDate(startOfDay, "GMT+9", "yyyy-MM-dd HH:mm") + " ~ " + Utilities.formatDate(endOfDay, "GMT+9", "yyyy-MM-dd HH:mm"));
    
    const events = calendar.getEvents(startOfDay, endOfDay);
    Logger.log("조회된 일정 개수: " + events.length);
    
    // Location이 있는 일정만 필터링 (로깅 최소화)
    const addresses = [];
    for (let i = 0; i < events.length; i++) {
      try {
        const location = events[i].getLocation();
        if (location && location.trim() !== '') {
          addresses.push(location.trim());
          // 처음 3개만 상세 로깅
          if (i < 3) {
            Logger.log(`일정 ${i + 1}: "${events[i].getTitle()}" - Location: "${location}"`);
          }
        }
      } catch(e) {
        Logger.log("Error getting location from event " + i + ": " + e);
      }
    }
    
    Logger.log("유효한 주소 개수: " + addresses.length);
    if (addresses.length > 0) {
      Logger.log("주소 목록: " + addresses.join(", "));
    }
    
    return addresses.length > 0 ? addresses : [defaultAddress];
  } catch(e) {
    Logger.log("Error getting calendar site: " + e);
    Logger.log("Error stack: " + (e.stack || "no stack"));
    return [defaultAddress];
  }
}

function getTodaySiteAddress() {
  const addresses = getTodaySiteAddresses();
  return addresses.length > 0 ? addresses[0] : "";
}

// Google Calendar 테스트 함수
function testGoogleCalendar() {
  Logger.log("=== Google Calendar 테스트 시작 ===");
  
  const calId = PROPERTIES.getProperty("GOOGLE_CALENDAR_ID");
  if (!calId) {
    Logger.log("❌ GOOGLE_CALENDAR_ID가 설정되지 않았습니다.");
    Logger.log("PropertiesService에서 GOOGLE_CALENDAR_ID를 확인하세요.");
    return;
  }
  
  Logger.log("✅ GOOGLE_CALENDAR_ID: " + calId);
  
  try {
    const calendar = CalendarApp.getCalendarById(calId);
    Logger.log("✅ Calendar 객체 생성 성공");
    
    // 캘린더 이름 확인
    const calendarName = calendar.getName();
    Logger.log("✅ 캘린더 이름: " + calendarName);
    
    // 현재 시간 기준으로 오늘 일정 조회
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    const startOfDay = new Date(kst.getFullYear(), kst.getMonth(), kst.getDate());
    const endOfDay = new Date(startOfDay);
    endOfDay.setDate(endOfDay.getDate() + 1);
    
    Logger.log("=== 조회 기간 ===");
    Logger.log("시작: " + Utilities.formatDate(startOfDay, "GMT+9", "yyyy-MM-dd HH:mm:ss"));
    Logger.log("종료: " + Utilities.formatDate(endOfDay, "GMT+9", "yyyy-MM-dd HH:mm:ss"));
    
    // 일정 조회
    const events = calendar.getEvents(startOfDay, endOfDay);
    Logger.log("✅ 일정 조회 성공");
    Logger.log("조회된 일정 개수: " + events.length);
    
    if (events.length === 0) {
      Logger.log("⚠️ 오늘 일정이 없습니다.");
      Logger.log("Google Calendar에 오늘 날짜의 일정이 있는지 확인하세요.");
    } else {
      Logger.log("=== 일정 상세 정보 ===");
      events.forEach((event, idx) => {
        try {
          const title = event.getTitle();
          const location = event.getLocation();
          const startTime = event.getStartTime();
          const endTime = event.getEndTime();
          
          Logger.log(`\n[일정 ${idx + 1}]`);
          Logger.log("  제목: " + title);
          Logger.log("  위치: " + (location || "(없음)"));
          Logger.log("  시작: " + Utilities.formatDate(startTime, "GMT+9", "yyyy-MM-dd HH:mm"));
          Logger.log("  종료: " + Utilities.formatDate(endTime, "GMT+9", "yyyy-MM-dd HH:mm"));
          
          if (location && location.trim() !== '') {
            Logger.log("  ✅ 위치 정보 있음");
          } else {
            Logger.log("  ⚠️ 위치 정보 없음 (Location 필드가 비어있음)");
          }
        } catch(e) {
          Logger.log("  ❌ 일정 정보 조회 실패: " + e);
        }
      });
      
      // Location이 있는 일정 필터링
      const addresses = [];
      for (let i = 0; i < events.length; i++) {
        try {
          const location = events[i].getLocation();
          if (location && location.trim() !== '') {
            addresses.push(location.trim());
          }
        } catch(e) {
          Logger.log("Error getting location from event " + i + ": " + e);
        }
      }
      
      Logger.log("\n=== 결과 요약 ===");
      Logger.log("전체 일정: " + events.length + "개");
      Logger.log("위치 정보가 있는 일정: " + addresses.length + "개");
      
      if (addresses.length > 0) {
        Logger.log("✅ 유효한 주소 목록:");
        addresses.forEach((addr, idx) => {
          Logger.log("  " + (idx + 1) + ". " + addr);
        });
      } else {
        Logger.log("⚠️ 위치 정보가 있는 일정이 없습니다.");
        Logger.log("일정의 '위치' 필드에 주소를 입력해야 합니다.");
      }
    }
    
    Logger.log("\n=== 테스트 완료 ===");
    
  } catch(e) {
    Logger.log("❌ 에러 발생: " + e);
    Logger.log("에러 스택: " + (e.stack || "no stack"));
    
    if (e.toString().includes("not found")) {
      Logger.log("⚠️ 캘린더를 찾을 수 없습니다.");
      Logger.log("GOOGLE_CALENDAR_ID가 올바른지 확인하세요.");
      Logger.log("또는 GAS 프로젝트에 해당 캘린더 접근 권한이 있는지 확인하세요.");
    } else if (e.toString().includes("permission")) {
      Logger.log("⚠️ 캘린더 접근 권한이 없습니다.");
      Logger.log("GAS 프로젝트에 Calendar 접근 권한을 부여해야 합니다.");
    }
  }
}

// ==========================================
// 3. 날씨 API 연동
// ==========================================
function getWeatherForecast(siteAddress) {
  const apiKey = PROPERTIES.getProperty("WEATHER_API_KEY");
  if (!apiKey) {
    return { pop: null, pty: "없음", error: "API키 미설정" };
  }
  
  try {
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
    Logger.log("Error in getWeatherForecast: " + e);
    return { pop: null, pty: "없음", error: e.toString() };
  }
}

function addressToGrid(address) {
  // 주소를 기상청 격자 좌표로 변환
  const regionCoords = {
    // 서울
    "서울": { nx: 60, ny: 127 }, "강남": { nx: 61, ny: 126 }, "강북": { nx: 60, ny: 128 },
    "강동": { nx: 62, ny: 126 }, "강서": { nx: 58, ny: 126 }, "관악": { nx: 59, ny: 125 },
    "광진": { nx: 62, ny: 126 }, "구로": { nx: 58, ny: 125 }, "금천": { nx: 58, ny: 125 },
    "노원": { nx: 61, ny: 129 }, "도봉": { nx: 61, ny: 129 }, "동대문": { nx: 61, ny: 127 },
    "동작": { nx: 59, ny: 125 }, "마포": { nx: 59, ny: 126 }, "서대문": { nx: 59, ny: 127 },
    "서초": { nx: 61, ny: 125 }, "성동": { nx: 61, ny: 127 }, "성북": { nx: 61, ny: 128 },
    "송파": { nx: 62, ny: 126 }, "양천": { nx: 58, ny: 126 }, "영등포": { nx: 58, ny: 125 },
    "용산": { nx: 60, ny: 126 }, "은평": { nx: 59, ny: 128 }, "종로": { nx: 60, ny: 127 },
    "중구": { nx: 60, ny: 127 }, "중랑": { nx: 62, ny: 128 },
    // 경기
    "수원": { nx: 60, ny: 121 }, "성남": { nx: 62, ny: 123 }, "고양": { nx: 57, ny: 129 },
    "용인": { nx: 64, ny: 119 }, "부천": { nx: 56, ny: 125 }, "안산": { nx: 58, ny: 121 },
    "안양": { nx: 59, ny: 123 }, "평택": { nx: 58, ny: 114 }, "시흥": { nx: 57, ny: 123 },
    "김포": { nx: 55, ny: 128 }, "의정부": { nx: 61, ny: 130 }, "광명": { nx: 58, ny: 125 },
    "광주": { nx: 65, ny: 123 }, "군포": { nx: 59, ny: 122 }, "하남": { nx: 64, ny: 126 },
    "오산": { nx: 62, ny: 118 }, "이천": { nx: 68, ny: 121 }, "안성": { nx: 65, ny: 115 },
    "화성": { nx: 57, ny: 119 }, "양평": { nx: 69, ny: 125 }, "구리": { nx: 62, ny: 127 },
    "남양주": { nx: 64, ny: 128 }, "파주": { nx: 56, ny: 131 }, "의왕": { nx: 60, ny: 122 },
    "과천": { nx: 60, ny: 124 }, "광교": { nx: 61, ny: 121 }, "테헤란로": { nx: 61, ny: 126 }
  };
  
  for (let region in regionCoords) {
    if (address.includes(region)) {
      return regionCoords[region];
    }
  }
  
  return { nx: 60, ny: 127 }; // 기본값 (서울)
}

// ==========================================
// 4. Slack 메시지 전송
// ==========================================
function sendSlackMessage(channel, text, blocks = null) {
  const token = PROPERTIES.getProperty("SLACK_BOT_TOKEN");
  if (!token) {
    Logger.log("SLACK_BOT_TOKEN not set");
    return;
  }
  
  const payload = {
    channel: channel,
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
    // 디버깅: blocks에 버튼이 있는 경우 URL 로그 출력
    if (blocks) {
      blocks.forEach((block, idx) => {
        if (block.type === "actions" && block.elements) {
          block.elements.forEach((element, elemIdx) => {
            if (element.type === "button" && element.url) {
              Logger.log(`[sendSlackMessage] Block ${idx}, Button ${elemIdx} URL: ${element.url}`);
            }
          });
        }
      });
    }
    
    const response = UrlFetchApp.fetch("https://slack.com/api/chat.postMessage", options);
    const result = JSON.parse(response.getContentText());
    
    if (!result.ok) {
      Logger.log("Slack API error: " + result.error);
    } else {
      Logger.log("Slack message sent successfully");
    }
  } catch(e) {
    Logger.log("Error sending Slack message: " + e);
  }
}

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

function sendSlackWithButtons(channel, text, homeAddress = null) {
  const blocks = [
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: text
      }
    }
  ];
  
  const buttons = [];
  
  // 1. 귀환스킬발동 버튼 (집주소로 t-map)
  // GAS doGet을 통해 리다이렉트 (Python 방식과 동일)
  if (homeAddress) {
    const webAppUrl = getWebAppUrl();
    if (webAppUrl) {
      const encodedAddr = encodeURIComponent(homeAddress);
      const redirectUrl = `${webAppUrl}?addr=${encodedAddr}`;
      Logger.log("귀환스킬발동 버튼 URL: " + redirectUrl);
      buttons.push({
        type: "button",
        text: { type: "plain_text", text: "🏠 귀환스킬발동" },
        url: redirectUrl,
        style: "primary"
      });
    } else {
      Logger.log("⚠️ Web App URL을 가져올 수 없어 귀환스킬발동 버튼을 생성하지 않습니다.");
    }
  }
  
  // 2. 자재사용대장 버튼
  buttons.push({
    type: "button",
    text: { type: "plain_text", text: "📋 자재사용대장" },
    action_id: "open_material_log",
    value: "start"
  });
  
  // 3. 현장사진 업로드 버튼 (폴더 생성부터 시작)
  buttons.push({
    type: "button",
    text: { type: "plain_text", text: "📷 현장사진 업로드" },
    action_id: "create_photo_folder",
    value: "create"
  });
  
  if (buttons.length > 0) {
    blocks.push({
      type: "actions",
      elements: buttons
    });
  }
  
  sendSlackMessage(channel, text, blocks);
}

function sendSlackWithTmap(channel, text, siteAddresses = null) {
  const blocks = [
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: text
      }
    }
  ];
  
  // T-map 버튼 추가
  const buttons = [];
  
  if (!siteAddresses || siteAddresses.length === 0) {
    siteAddresses = [PROPERTIES.getProperty("SITE_ADDRESS") || ""];
  }
  
  // 유효한 주소만 필터링 (빈 문자열, "현장정보 없음" 제외)
  const validAddresses = siteAddresses.filter(addr => 
    addr && 
    addr.trim() !== "" && 
    addr.trim() !== "현장정보 없음" &&
    !addr.includes("현장정보 없음")
  );
  
  if (validAddresses.length === 0) {
    // 유효한 주소가 없으면 버튼을 표시하지 않음
    Logger.log("유효한 현장 주소가 없어 T-map 버튼을 표시하지 않습니다.");
    sendSlackMessage(channel, text, blocks);
    return;
  }
  
  // GAS Web App URL 가져오기 (doGet을 통해 리다이렉트)
  Logger.log("=== T-map 버튼 URL 생성 시작 ===");
  const webAppUrl = getWebAppUrl();
  if (!webAppUrl) {
    Logger.log("⚠️ Web App URL을 가져올 수 없습니다.");
    Logger.log("대신 직접 T-map 웹 URL을 사용합니다.");
    // Fallback: 직접 T-map 웹 URL 사용
    if (validAddresses.length === 1) {
      const address = validAddresses[0];
      const encodedAddr = encodeURIComponent(address);
      const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
      Logger.log("Fallback: 오늘 현장 T-map 버튼 URL: " + tmapWebUrl);
      buttons.push({
        type: "button",
        text: { type: "plain_text", text: "🚩 오늘 현장 T-map 열기" },
        url: tmapWebUrl,
        style: "primary"
      });
    } else if (validAddresses.length >= 2) {
      validAddresses.slice(0, 2).forEach((address, idx) => {
        const encodedAddr = encodeURIComponent(address);
        const tmapWebUrl = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
        const buttonText = idx === 0 ? "🚩 첫번째 현장 T-map 열기" : "🚩 두번째 현장 T-map 열기";
        Logger.log(`Fallback: ${buttonText} 버튼 URL: ${tmapWebUrl}`);
        buttons.push({
          type: "button",
          text: { type: "plain_text", text: buttonText },
          url: tmapWebUrl,
          style: "primary"
        });
      });
    }
  } else {
    Logger.log("✅ Web App URL: " + webAppUrl);
    
    if (validAddresses.length === 1) {
      // 현장이 1개인 경우
      const address = validAddresses[0];
      const encodedAddr = encodeURIComponent(address);
      // GAS doGet을 통해 리다이렉트 (Python 방식과 동일)
      const redirectUrl = `${webAppUrl}?addr=${encodedAddr}`;
      Logger.log("오늘 현장 T-map 버튼 URL: " + redirectUrl);
      Logger.log("주소: " + address);
      buttons.push({
        type: "button",
        text: { type: "plain_text", text: "🚩 오늘 현장 T-map 열기" },
        url: redirectUrl,
        style: "primary"
      });
    } else if (validAddresses.length >= 2) {
      // 현장이 2개 이상인 경우
      validAddresses.slice(0, 2).forEach((address, idx) => {
        const encodedAddr = encodeURIComponent(address);
        const redirectUrl = `${webAppUrl}?addr=${encodedAddr}`;
        const buttonText = idx === 0 ? "🚩 첫번째 현장 T-map 열기" : "🚩 두번째 현장 T-map 열기";
        Logger.log(`${buttonText} 버튼 URL: ${redirectUrl}`);
        Logger.log(`주소: ${address}`);
        buttons.push({
          type: "button",
          text: { type: "plain_text", text: buttonText },
          url: redirectUrl,
          style: "primary"
        });
      });
    }
  }
  
  // 버튼이 있으면 blocks에 추가하고 메시지 전송
  if (buttons.length > 0) {
    blocks.push({
      type: "actions",
      elements: buttons
    });
  }
  
  sendSlackMessage(channel, text, blocks);
}

// ==========================================
// 5. 게임화 통계 계산
// ==========================================
function calculateWorkStats(userInfo) {
  const totalDays = userInfo.base_work_days + getTotalWorkDays(userInfo.name);
  const awakening = getAwakeningStage(totalDays);
  const dailyPay = calculateDailyPay(totalDays);
  
  return {
    totalDays: totalDays,
    dailyPay: dailyPay,
    stageTitle: `${awakening.emoji} [각성 ${awakening.num}단계]`
  };
}

// ==========================================
// 6. T-map 리다이렉트 URL 생성
// ==========================================
function getWebAppUrl() {
  // T-map 버튼에서 사용: GAS doGet을 통해 리다이렉트
  let url = PROPERTIES.getProperty("WEB_APP_URL");
  if (url && url.includes("/exec")) {
    Logger.log("Web App URL from cache: " + url);
    return url;
  }
  
  // 잘못된 URL이 저장되어 있으면 삭제
  if (url && !url.includes("/exec")) {
    Logger.log("Warning: Invalid WEB_APP_URL found: " + url);
    PROPERTIES.deleteProperty("WEB_APP_URL");
  }
  
  // ScriptApp.getService().getUrl() 시도
  try {
    url = ScriptApp.getService().getUrl();
    if (url && url.includes("/exec")) {
      PROPERTIES.setProperty("WEB_APP_URL", url);
      Logger.log("Web App URL from getService(): " + url);
      return url;
    } else if (url) {
      Logger.log("Warning: getUrl() returned non-exec URL: " + url);
      Logger.log("URL should end with /exec");
    } else {
      Logger.log("Error: getService().getUrl() returned null");
      Logger.log("Web App이 배포되지 않았을 수 있습니다.");
    }
  } catch(e) {
    Logger.log("Error getting Web App URL: " + e);
    Logger.log("Error stack: " + (e.stack || "no stack"));
  }
  
  Logger.log("❌ Web App URL을 가져올 수 없습니다.");
  return null;
}

// PropertiesService의 잘못된 URL 삭제 함수
function clearWebAppUrl() {
  PROPERTIES.deleteProperty("WEB_APP_URL");
  Logger.log("WEB_APP_URL property cleared");
}

// T-map 버튼 URL 생성 테스트 함수
// 실제로 어떤 URL이 생성되는지 확인
function testTmapButtonUrls() {
  const testAddress = "서울시 강남구";
  const testSiteAddresses = ["서울시 강남구", "서울시 서초구"];
  
  Logger.log("=== T-map 버튼 URL 테스트 ===");
  
  // 귀환스킬발동 버튼 URL 테스트
  const encodedAddr1 = encodeURIComponent(testAddress);
  const tmapWebUrl1 = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr1}`;
  Logger.log("귀환스킬발동 버튼 URL: " + tmapWebUrl1);
  Logger.log("올바른 URL인가? " + (tmapWebUrl1.startsWith("https://tmapapi.sktelecom.com")));
  
  // 오늘 현장 T-map 버튼 URL 테스트
  const encodedAddr2 = encodeURIComponent(testSiteAddresses[0]);
  const tmapWebUrl2 = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr2}`;
  Logger.log("오늘 현장 T-map 버튼 URL: " + tmapWebUrl2);
  Logger.log("올바른 URL인가? " + (tmapWebUrl2.startsWith("https://tmapapi.sktelecom.com")));
  
  Logger.log("=== 테스트 완료 ===");
}

function getRedirectUrl(address) {
  // GAS를 거치지 않고 T-map 웹 지도로 직접 이동
  if (!address) {
    return "https://tmapapi.sktelecom.com/main/map.html";
  }
  const encodedAddr = encodeURIComponent(address);
  return `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
}

