/**
 * 디테일라인 통합 관리 시스템 (GAS Ver 2.0)
 * 기반: Slack 출결 봇 GAS 전환 PRD
 */

// ==========================================
// 1. 설정 및 상수 정의
// ==========================================
const SS = SpreadsheetApp.getActiveSpreadsheet();
const PROPERTIES = PropertiesService.getScriptProperties();

// 시트 이름 상수
const SHEET_NAMES = {
  ATTENDANCE_LOG: "AttendanceLog",
  USER_MASTER: "UserMaster",
  MATERIAL_LOG: "MaterialLog",
  MATERIAL_ORDER: "MaterialOrder",
  INCENTIVE: "Incentive"
};

// 급여 테이블 (PRD 5.3.1 기준)
const PAY_RATES = [
  { min: 1, max: 45, rate: 130000 },
  { min: 46, max: 90, rate: 150000 },
  { min: 91, max: 135, rate: 170000 },
  { min: 136, max: 180, rate: 190000 },
  { min: 181, max: 225, rate: 210000 },
  { min: 226, max: 270, rate: 230000 },
  { min: 271, max: 99999, rate: 250000 }
];

// 각성 단계 정의 (PRD 5.2 기준)
const AWAKENING_STAGES = [
  { days: 0, emoji: "🟤", title: "브론즈", num: 0 },
  { days: 45, emoji: "⚪", title: "실버", num: 1 },
  { days: 90, emoji: "🟡", title: "골드", num: 2 },
  { days: 135, emoji: "🔵", title: "플래티넘", num: 3 },
  { days: 180, emoji: "🟣", title: "다이아", num: 4 },
  { days: 225, emoji: "🔴", title: "레전드", num: 5 },
  { days: 270, emoji: "👑", title: "마스터", num: 6 }
];

// 방 목록
const MATERIAL_ROOMS = ["거실 화장실", "안방 화장실", "거실", "세탁실", "베란다", "현관"];

// 색상 코드 목록
const MATERIAL_COLORS = ["110", "111", "112", "113", "130", "기타"];

// 스킬 획득 구간
const SKILL_MILESTONES = [45, 90, 135, 180, 225, 270];

// ==========================================
// 2. 메인 진입점 (Dispatcher)
// ==========================================
function doPost(e) {
  try {
    // e가 undefined인 경우 처리 (에디터에서 직접 실행 시)
    if (!e) {
      Logger.log("WARN: e is undefined - this is normal when running from editor");
      return ContentService.createTextOutput("");
    }

    // 공통 로깅 (상세)
    var contentType = e.postData && e.postData.type ? e.postData.type : "";
    Logger.log("=== doPost 호출됨 ===");
    Logger.log("Content-Type: " + contentType);
    Logger.log("Parameter keys: " + (e.parameter ? Object.keys(e.parameter).join(", ") : "none"));
    if (e.parameter) {
      Logger.log("Parameter values: " + JSON.stringify(e.parameter));
    }
    if (e.postData) {
      Logger.log("PostData type: " + e.postData.type);
      Logger.log("PostData length: " + (e.postData.contents ? e.postData.contents.length : 0));
      if (e.postData.contents && e.postData.contents.length < 500) {
        Logger.log("PostData contents: " + e.postData.contents);
      }
    }

    var payloadObj = null;

    // 1) Events API: application/json
    if (contentType.indexOf("application/json") !== -1) {
      try {
        payloadObj = JSON.parse(e.postData.contents);
        
        // URL 검증(이벤트 구독 최초) 처리
        if (payloadObj.type === "url_verification") {
          Logger.log("URL verification challenge received");
          return ContentService
            .createTextOutput(payloadObj.challenge)
            .setMimeType(ContentService.MimeType.TEXT);
        }

        Logger.log("Event subscription received: " + (payloadObj.type || "unknown"));
        return handleEventSubscription(payloadObj);
      } catch(parseError) {
        Logger.log("Error parsing JSON payload: " + parseError);
        return ContentService.createTextOutput("");
      }
    }

    // 2) x-www-form-urlencoded (Slash Command 또는 Interactive Actions)
    // Content-Type이 없어도 e.parameter가 있으면 처리 (Slack Slash Command는 때때로 Content-Type이 없을 수 있음)
    if (contentType.indexOf("application/x-www-form-urlencoded") !== -1 || 
        (!contentType && e.parameter)) {
      Logger.log("Processing x-www-form-urlencoded or parameter-based request");
      
      // Interactive Actions 인지 Slash Command 인지 구분
      if (e.parameter && e.parameter.payload) {
        // Interactive Actions
        try {
          payloadObj = JSON.parse(e.parameter.payload);
          Logger.log("Interactive action received: " + (payloadObj.type || "unknown"));
          return handleInteractive(payloadObj);
        } catch(parseError) {
          Logger.log("Error parsing Interactive payload: " + parseError);
          Logger.log("Payload string: " + (e.parameter.payload ? e.parameter.payload.substring(0, 200) : "null"));
          return ContentService.createTextOutput("");
        }
      } else if (e.parameter && e.parameter.command) {
        // Slash Command
        Logger.log("✅ Slash command detected: " + e.parameter.command);
        Logger.log("Command text: " + (e.parameter.text || "empty"));
        Logger.log("User ID: " + (e.parameter.user_id || "none"));
        return handleSlashCommand(e.parameter);
      } else {
        Logger.log("⚠️ WARN: x-www-form-urlencoded but no payload/command");
        Logger.log("Parameter keys: " + (e.parameter ? Object.keys(e.parameter).join(", ") : "none"));
        Logger.log("Full parameter object: " + JSON.stringify(e.parameter));
        return ContentService.createTextOutput("");
      }
    }

    // 그 외 Content-Type
    Logger.log("WARN: Unsupported Content-Type: " + contentType);
    return ContentService.createTextOutput("");

  } catch (error) {
    Logger.log("Error in doPost: " + error + "\n" + (error.stack || "no stack"));
    // Slack은 200만 받으면 되므로, 에러 상황에서도 빈 200 리턴
    return ContentService.createTextOutput("");
  }
}

// Slash Command 핸들러
function handleSlashCommand(params) {
  try {
    var command = params.command;      // "/출근"
    var text = params.text || "";      // 인자
    var userId = params.user_id;
    var channelId = params.channel_id;

    Logger.log("Handling command: " + command + ", text: " + text);

    // 커맨드 라우팅
    if (command === "/출근") {
      handleCheckIn(params);
      return ContentService.createTextOutput(""); // 즉시 응답
    } else if (command === "/퇴근") {
      handleCheckOut(params);
      return ContentService.createTextOutput("");
    } else if (command === "/급여정산") {
      handlePayrollSettlement(params);
      return ContentService.createTextOutput("");
    } else if (command === "/출근로그") {
      handleAttendanceLogs(params);
      return ContentService.createTextOutput("");
    } else if (command === "/정산내역") {
      handlePayrollHistory(params);
      return ContentService.createTextOutput("");
    } else if (command === "/발주목록") {
      handleOrderList(params);
      return ContentService.createTextOutput("");
    } else if (command === "/hello") {
      handleHello(params);
      return ContentService.createTextOutput("");
    } else if (command === "/netcheck") {
      handleNetcheck(params);
      return ContentService.createTextOutput("");
    }

    Logger.log("Unknown command: " + command);
    return ContentService.createTextOutput("");
  } catch(error) {
    Logger.log("Error in handleSlashCommand: " + error);
    return ContentService.createTextOutput("");
  }
}

// Interactive Actions 핸들러
function handleInteractive(payload) {
  try {
    var type = payload.type; // "block_actions", "view_submission" 등
    var user = payload.user && payload.user.id;
    var actions = payload.actions || [];

    Logger.log("Interactive type: " + type);

    if (type === "block_actions" && actions.length > 0) {
      var action = actions[0];
      var actionId = action.action_id || action.name;
      var value = action.value;

      Logger.log("Action ID: " + actionId + ", value: " + (value || "none"));

      // 자재사용대장 관련
      if (actionId === "open_material_log") {
        openMaterialLog(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "select_rooms") {
        return ContentService.createTextOutput("");
      } else if (actionId === "start_material_input") {
        startMaterialInput(payload);
        return ContentService.createTextOutput("");
      } else if (actionId && actionId.startsWith("select_color_")) {
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
      if (actionId === "send_order_message") {
        handleSendOrderMessage(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "refresh_order_list") {
        handleRefreshOrderList(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "update_order_list") {
        handleUpdateOrderList(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "confirm_order_update") {
        handleConfirmOrderUpdate(payload);
        return ContentService.createTextOutput("");
      }
      
      // 급여 정산 관련
      if (actionId === "send_payrolls") {
        handleSendPayrolls(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "select_user_attendance") {
        handleSelectUserAttendance(payload);
        return ContentService.createTextOutput("");
      } else if (actionId === "select_user_payroll") {
        handleSelectUserPayroll(payload);
        return ContentService.createTextOutput("");
      }

      Logger.log("Unknown action_id: " + actionId);
      return ContentService.createTextOutput("");
    }

    // View Submission 처리
    if (type === "view_submission") {
      var callbackId = payload.view && payload.view.callback_id;
      if (callbackId === "material_quantity_submit") {
        handleMaterialQuantitySubmit(payload);
        return ContentService.createTextOutput("");
      }
      return ContentService.createTextOutput("");
    }

    // 특별히 응답할 메시지가 없을 경우에도 200은 리턴
    return ContentService.createTextOutput("");
  } catch(error) {
    Logger.log("Error in handleInteractive: " + error);
    return ContentService.createTextOutput("");
  }
}

// Event Subscription 핸들러
function handleEventSubscription(eventBody) {
  try {
    // eventBody.type === "event_callback" 등
    Logger.log("Event subscription: " + (eventBody.type || "unknown"));
    // 필요시 구현, 없다면 빈 200 리턴
    return ContentService.createTextOutput("");
  } catch(error) {
    Logger.log("Error in handleEventSubscription: " + error);
    return ContentService.createTextOutput("");
  }
}

// T-map 리다이렉트용 GET 핸들러 (PRD 6.6)
// GAS의 제한을 우회하기 위해 T-map 웹 지도로 직접 리다이렉트
// 웹 지도에서 사용자가 직접 앱을 열 수 있음
// T-map 리다이렉트용 GET 핸들러
// Python 코드와 동일한 방식: 플랫폼 감지 후 앱 딥링크로 리다이렉트
function doGet(e) {
  const addr = e && e.parameter && e.parameter.addr;
  if (!addr) {
    return HtmlService.createHtmlOutput("주소가 없습니다.").setTitle("T-map 열기");
  }
  
  const encodedAddr = encodeURIComponent(addr);
  
  // T-map 앱 딥링크 (Python 코드와 동일)
  // Android용 Intent URL
  const androidIntent = `intent://search?name=${encodedAddr}#Intent;scheme=tmap;package=com.skt.tmap.ku;end;`;
  
  // iOS용 URL Scheme
  const iosScheme = `tmap://search?name=${encodedAddr}`;
  
  // Fallback: 웹 지도
  const fallbackWeb = `https://tmapapi.sktelecom.com/main/map.html?q=${encodedAddr}`;
  
  // 플랫폼 감지 및 리다이렉트 (Python 코드와 동일한 로직)
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
          // 1.5초 안에 앱이 안 뜬다고 가정하고 웹 fallback
          setTimeout(function() {
            if (tried) {
              window.location.href = "${fallbackWeb}";
            } else {
              // 데스크톱이면 바로 웹으로
              window.location.href = "${fallbackWeb}";
            }
          }, 1500);
        }
        window.onload = openApp;
      </script>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 40px 20px; margin: 0; background: #f5f5f5;">
      <div style="max-width: 400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <p style="font-size: 18px; margin-bottom: 20px; color: #333;">T-map 앱을 여는 중입니다...</p>
        <p style="font-size: 14px; color: #666; margin-bottom: 20px;">
          자동으로 열리지 않으면 아래 버튼을 클릭해주세요.
        </p>
        <button id="tmapBtn" 
                style="display: inline-block; padding: 12px 24px; background: #0066cc; color: white; border: none; border-radius: 4px; font-weight: bold; font-size: 16px; cursor: pointer; width: 100%;">
          T-map 열기
        </button>
        <p style="font-size: 12px; color: #999; margin-top: 20px;">
          <a href="${fallbackWeb}" style="color: #0066cc;">또는 여기를 클릭하세요</a>
        </p>
      </div>
      <script>
        // 버튼 클릭 시 강제 리다이렉트 (모바일 호환성)
        (function() {
          var btn = document.getElementById('tmapBtn');
          var fallback = "${fallbackWeb}";
          if (btn) {
            btn.addEventListener('click', function() {
              window.location.href = fallback;
            });
            btn.addEventListener('touchend', function(e) {
              e.preventDefault();
              window.location.href = fallback;
            });
          }
        })();
      </script>
      </div>
    </body>
    </html>
  `;
  
  return HtmlService.createHtmlOutput(html)
    .setTitle("T-map 열기")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// ==========================================
// 3. Slack 요청 검증
// ==========================================
function verifySlackRequest(timestamp, body, signature) {
  const signingSecret = PROPERTIES.getProperty("SLACK_SIGNING_SECRET");
  if (!signingSecret) {
    Logger.log("SLACK_SIGNING_SECRET not set");
    return false;
  }
  
  const baseString = `v0:${timestamp}:${body}`;
  const hmac = Utilities.computeHmacSha256Signature(baseString, signingSecret);
  const computedSignature = 'v0=' + hmac.map(b => ('0' + (b & 0xFF).toString(16)).slice(-2)).join('');
  
  return computedSignature === signature;
}

// ==========================================
// 4. 핵심 기능 핸들러 - Slash Commands
// ==========================================

// 4.1 출근 핸들러 (/출근)
function handleCheckIn(payload) {
  try {
    Logger.log("=== handleCheckIn 시작 ===");
    const userId = payload.user_id;
    const channelId = payload.channel_id || userId;
    
    const userInfo = getUserInfo(userId);
    if (!userInfo) {
      sendSlackMessage(channelId, "❌ 사용자 정보가 없습니다. 관리자에게 문의하세요.");
      return;
    }
    
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    
    // 현장 주소 가져오기 (에러 처리)
    let siteAddresses = [];
    let siteAddress = "";
    try {
      siteAddresses = getTodaySiteAddresses();
      siteAddress = siteAddresses.length > 0 ? siteAddresses[0] : "";
      Logger.log("현장 주소 조회 완료: " + siteAddress);
    } catch(e) {
      Logger.log("Error getting site addresses: " + e);
      siteAddresses = [PROPERTIES.getProperty("SITE_ADDRESS") || "현장정보 없음"];
      siteAddress = siteAddresses[0];
    }
    
    // 출근 기록 (에러 처리)
    try {
      recordCheckIn(userInfo.name, siteAddress);
      Logger.log("출근 기록 완료");
    } catch(e) {
      Logger.log("Error recording check-in: " + e);
      // 기록 실패해도 계속 진행
    }
    
    // 게임화 정보 조회 (에러 처리)
    let totalDays = 0;
    let level = 0;
    let monthlyCount = 0;
    let awakening = { emoji: "🟤", title: "브론즈", num: 0 };
    let userTitle = "Lv.0";
    let daysUntilSettlement = 0;
    
    try {
      totalDays = getTotalWorkDays(userInfo.name);
      level = calculateLevel(totalDays);
      monthlyCount = getMonthlyWorkCount(userInfo.name, kst.getFullYear(), kst.getMonth() + 1);
      awakening = getAwakeningStage(totalDays);
      userTitle = getUserTitle(totalDays);
      daysUntilSettlement = getDaysUntilSettlement();
      Logger.log("게임화 정보 조회 완료");
    } catch(e) {
      Logger.log("Error getting game stats: " + e);
      // 기본값 사용
    }
    
    // 날씨 정보 조회 (에러 처리, 타임아웃 방지)
    let weather = { pop: null, pty: "없음", error: null };
    try {
      // 날씨 API는 타임아웃이 발생할 수 있으므로 별도 처리
      weather = getWeatherForecast(siteAddress);
      Logger.log("날씨 정보 조회 완료");
    } catch(e) {
      Logger.log("Error getting weather: " + e);
      weather = { pop: null, pty: "없음", error: "조회 실패" };
    }
    
    // 메시지 구성
    let msg = `✅ [${userInfo.name}님, 출근 기록 완료!]\n오늘도 활기차게 시동 걸어볼까요? 🚛\n\n`;
    
    // 날씨 정보
    if (weather.pop !== null && weather.pop > 0) {
      const weatherEmoji = weather.pty === "비" ? "☔️" : (weather.pty === "눈" ? "🌨️" : "🌦️");
      msg += `${weatherEmoji} 오후 예보 (강수확률 ${weather.pop}%)\n`;
      if (weather.pty !== "없음") {
        msg += `💡 ${weather.pty} 올 수 있으니 조심하세요! 우산 챙기셨나요?\n`;
      } else {
        msg += `💡 가볍게 스쳐갈 수 있어요. 우산 준비하세요!\n`;
      }
    } else if (weather.pop !== null && weather.pop === 0) {
      msg += `🌤️ 오후 날씨 맑음 예보\n☀️ 좋은 날씨네요! 안전 운전하세요!\n`;
    } else {
      msg += `🌤️ 날씨 정보 조회 중...\n`;
    }
    
    msg += `──────────────\n\n`;
    
    // 현장 주소
    if (siteAddresses.length === 1) {
      msg += `📍 오늘의 현장\n:: ${siteAddresses[0]}\n\n`;
    } else if (siteAddresses.length > 1) {
      siteAddresses.forEach((addr, idx) => {
        if (idx === 0) msg += `📍 첫번째 현장\n:: ${addr}\n`;
        else if (idx === 1) msg += `📍 두번째 현장\n:: ${addr}\n`;
        else msg += `📍 ${idx + 1}번째 현장\n:: ${addr}\n`;
      });
      msg += `\n`;
    }
    
    msg += `──────────────\n\n`;
    msg += `📊 ${kst.getMonth() + 1}월의 기록\n`;
    msg += ` • 현황: ${monthlyCount}번째 출동 | 정산일 D-${daysUntilSettlement}\n`;
    msg += ` • 등급: ${awakening.emoji} [각성 ${awakening.num}단계] (Lv.${level})\n`;
    msg += ` • 칭호: ${userTitle}\n\n`;
    msg += `──────────────\n\n`;
    msg += `"오늘도 안전하게, 돈 많이 벌어오세요! 출발! 💸"`;
    
    // T-map 버튼 포함 메시지 전송 (에러 처리)
    try {
      sendSlackWithTmap(channelId, msg, siteAddresses);
      Logger.log("메시지 전송 완료");
    } catch(e) {
      Logger.log("Error sending message: " + e);
      // 메시지 전송 실패 시 간단한 메시지라도 전송
      try {
        sendSlackMessage(channelId, `✅ [${userInfo.name}님, 출근 기록 완료!]\n오늘도 활기차게 시동 걸어볼까요? 🚛`);
      } catch(e2) {
        Logger.log("Error sending fallback message: " + e2);
      }
    }
    
    Logger.log("=== handleCheckIn 완료 ===");
    
  } catch(error) {
    Logger.log("Error in handleCheckIn: " + error);
    Logger.log("Error stack: " + (error.stack || "no stack"));
    try {
      sendSlackMessage(payload.channel_id || payload.user_id, "❌ 출근 처리 중 오류가 발생했습니다. 관리자에게 문의하세요.");
    } catch(e) {
      Logger.log("Error sending error message: " + e);
    }
  }
}

// 4.2 퇴근 핸들러 (/퇴근)
function handleCheckOut(payload) {
  try {
    Logger.log("=== handleCheckOut 시작 ===");
    const userId = payload.user_id;
    const channelId = payload.channel_id || userId;
    
    const userInfo = getUserInfo(userId);
    if (!userInfo) {
      sendSlackMessage(channelId, "❌ 사용자 정보가 없습니다.");
      return;
    }
    
    const prevTotalDays = getTotalWorkDays(userInfo.name);
    
    // 퇴근 기록
    recordCheckOut(userInfo.name);
    
    const currentTotalDays = getTotalWorkDays(userInfo.name);
    
    // 레벨업/각성 체크 (퇴근 시에만)
    checkLevelUpAndAwakening(userInfo, prevTotalDays, currentTotalDays);
    
    // 일급 계산
    const userType = userInfo.user_type || "정규직";
    const dailyPay = calculateDailyPay(prevTotalDays, userType);
    
    // 각성 경험치 진행률
    const awakeningProgress = getAwakeningProgress(currentTotalDays);
    
    // 메시지 구성
    let msg = `✅ [${userInfo.name}님, 퇴근 기록 완료!]\n오늘 흘린 땀방울이 멋진 결과로 쌓였습니다. 👏\n\n`;
    msg += `──────────────\n\n`;
    msg += `💰일급 ${dailyPay.toLocaleString()}원 획득!\n\n`;
    msg += `──────────────\n\n`;
    msg += `⚔️ 각성 경험치\n`;
    msg += `• 총 근무일수: ${currentTotalDays}일째 중\n`;
    msg += `• 경험치: ${awakeningProgress.progressBar} (${awakeningProgress.percentage}%)\n`;
    if (awakeningProgress.daysToNext > 0) {
      msg += `(다음 각성까지 ${awakeningProgress.daysToNext}일 남음)\n`;
    }
    msg += `\n──────────────\n\n`;
    msg += `"오늘 저녁은 맛있는 거 드세요!\n🍖 내일도 ${userInfo.name}님의 안전을 기원합니다. 퇴근!"`;
    
    // 버튼 포함 메시지 전송
    sendSlackWithButtons(channelId, msg, userInfo.address);
    
  } catch(error) {
    Logger.log("Error in handleCheckOut: " + error);
    sendSlackMessage(payload.channel_id || payload.user_id, "❌ 퇴근 처리 중 오류가 발생했습니다.");
  }
}

// 4.3 급여 정산 핸들러 (/급여정산)
function handlePayrollSettlement(payload) {
  if (!isAdmin(payload.user_id)) {
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 이 명령어는 관리자만 사용할 수 있습니다.");
    return;
  }
  
  try {
    // 년월 파싱
    const text = payload.text ? payload.text.trim() : "";
    let year, month;
    if (text) {
      const parts = text.split("-");
      year = parseInt(parts[0]);
      month = parseInt(parts[1]);
    } else {
      const now = new Date();
      year = now.getFullYear();
      month = now.getMonth() + 1;
    }
    
    const payrolls = calculateAllPayrolls(year, month);
    
    if (payrolls.length === 0) {
      sendSlackEphemeral(payload.channel_id, payload.user_id, `❌ ${year}년 ${month}월 근무 기록이 없습니다.`);
      return;
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
    
  } catch(error) {
    Logger.log("Error in handlePayrollSettlement: " + error);
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 급여 정산 중 오류가 발생했습니다.");
  }
}

// 4.4 출근 로그 조회 (/출근로그)
function handleAttendanceLogs(payload) {
  if (!isAdmin(payload.user_id)) {
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 이 명령어는 관리자만 사용할 수 있습니다.");
    return;
  }
  
  try {
    const users = getAllUsers();
    if (users.length === 0) {
      sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 사용자 목록을 가져올 수 없습니다.");
      return;
    }
    
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
    
    sendSlackEphemeral(payload.channel_id, payload.user_id, "출근 로그 조회", blocks);
    
  } catch(error) {
    Logger.log("Error in handleAttendanceLogs: " + error);
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 출근 로그 조회 중 오류가 발생했습니다.");
  }
}

// 4.5 정산 내역 조회 (/정산내역)
function handlePayrollHistory(payload) {
  if (!isAdmin(payload.user_id)) {
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 이 명령어는 관리자만 사용할 수 있습니다.");
    return;
  }
  
  try {
    const users = getAllUsers();
    if (users.length === 0) {
      sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 사용자 목록을 가져올 수 없습니다.");
      return;
    }
    
    const options = users.map(user => ({
      text: { type: "plain_text", text: user.name },
      value: user.name
    }));
    
    const blocks = [
      {
        type: "section",
        text: { type: "mrkdwn", text: "💰 **정산 내역 조회**\n\n조회할 사용자를 선택하세요:" }
      },
      {
        type: "section",
        text: { type: "mrkdwn", text: "사용자 선택" },
        accessory: {
          type: "static_select",
          placeholder: { type: "plain_text", text: "사용자 선택" },
          options: options,
          action_id: "select_user_payroll"
        }
      }
    ];
    
    sendSlackEphemeral(payload.channel_id, payload.user_id, "정산 내역 조회", blocks);
    
  } catch(error) {
    Logger.log("Error in handlePayrollHistory: " + error);
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 정산 내역 조회 중 오류가 발생했습니다.");
  }
}

// 4.6 발주 목록 조회 (/발주목록)
function handleOrderList(payload) {
  if (!isAdmin(payload.user_id)) {
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 이 명령어는 관리자만 사용할 수 있습니다.");
    return;
  }
  
  try {
    const now = new Date();
    const orders = getPendingMaterialOrders(now.getFullYear(), now.getMonth() + 1);
    
    if (orders.length === 0) {
      sendSlackMessage(payload.channel_id, `📦 ${now.getMonth() + 1}월 발주 목록이 비어있습니다.`);
      return;
    }
    
    let orderListText = orders.map((order, idx) => `${idx + 1}. ${order.content}`).join("\n");
    
    const blocks = [
      {
        type: "section",
        text: { type: "mrkdwn", text: `──────────────\n📦 **${now.getMonth() + 1}월 자재 발주 요청서 [Total: ${orders.length}건]**\n(${Utilities.formatDate(now, "GMT+9", "yyyy-MM-dd")} 기준)\n──────────────\n\n${orderListText}\n\n❗ 발주 넣은 항목의 번호를 입력하면 목록에서 지워집니다.\n❗ 발주가 처리 된 목록은 숫자로 입력해주세요.\n-> 입력 (예시: 1,3)` }
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
    
  } catch(error) {
    Logger.log("Error in handleOrderList: " + error);
    sendSlackMessage(payload.channel_id, "❌ 발주 목록 조회 중 오류가 발생했습니다.");
  }
}

// 4.7 테스트 명령어
function handleHello(payload) {
  sendSlackMessage(payload.channel_id, "✅ GCF 서버에 도달했습니다! (인증 테스트 중...)");
}

function handleNetcheck(payload) {
  if (!isAdmin(payload.user_id)) {
    sendSlackEphemeral(payload.channel_id, payload.user_id, "❌ 관리자만 사용할 수 있습니다.");
    return;
  }
  
  try {
    const response = UrlFetchApp.fetch("https://oauth2.googleapis.com/token", { muteHttpExceptions: true });
    const result = `✅ 핸드셰이크 OK, 응답 코드 ${response.getResponseCode()}`;
    sendSlackEphemeral(payload.channel_id, payload.user_id, `네트워크 테스트 결과: ${result}`);
  } catch(e) {
    sendSlackEphemeral(payload.channel_id, payload.user_id, `🚨 요청 실패: ${e}`);
  }
}

