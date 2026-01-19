/**
 * Google Sheets 연동 핸들러
 */

// ==========================================
// 1. 출퇴근 기록
// ==========================================
function recordCheckIn(userName, siteAddress) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.ATTENDANCE_LOG);
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    
    sheet.appendRow([
      Utilities.formatDate(kst, "GMT+9", "yyyy-MM-dd"),
      userName,
      Utilities.formatDate(kst, "GMT+9", "HH:mm:ss"),
      "출근",
      siteAddress || ""
    ]);
    
    return { success: true, message: "출근 기록이 정상적으로 저장되었습니다." };
  } catch(e) {
    Logger.log("Error in recordCheckIn: " + e);
    return { success: false, message: "출근 기록 오류: " + e.toString() };
  }
}

function recordCheckOut(userName) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.ATTENDANCE_LOG);
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    
    sheet.appendRow([
      Utilities.formatDate(kst, "GMT+9", "yyyy-MM-dd"),
      userName,
      Utilities.formatDate(kst, "GMT+9", "HH:mm:ss"),
      "퇴근",
      ""
    ]);
    
    return { success: true, message: "퇴근 기록이 정상적으로 저장되었습니다." };
  } catch(e) {
    Logger.log("Error in recordCheckOut: " + e);
    return { success: false, message: "퇴근 기록 오류: " + e.toString() };
  }
}

// ==========================================
// 2. 총 근무일수 계산
// ==========================================
function getTotalWorkDays(userName) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.ATTENDANCE_LOG);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return 0;
    
    // 날짜별로 출근/퇴근 기록 추적
    const dateRecords = {};
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 4) continue;
      
      const date = row[0] ? row[0].toString() : "";
      const name = row[1] ? row[1].toString() : "";
      const recordType = row[3] ? row[3].toString() : "";
      
      if (name === userName && date) {
        if (!dateRecords[date]) {
          dateRecords[date] = { 출근: false, 퇴근: false };
        }
        
        if (recordType === "출근") {
          dateRecords[date].출근 = true;
        } else if (recordType === "퇴근") {
          dateRecords[date].퇴근 = true;
        }
      }
    }
    
    // 출근과 퇴근이 모두 있는 날짜만 카운트
    let count = 0;
    for (let date in dateRecords) {
      if (dateRecords[date].출근 && dateRecords[date].퇴근) {
        count++;
      }
    }
    
    return count;
  } catch(e) {
    Logger.log("Error in getTotalWorkDays: " + e);
    return 0;
  }
}

// ==========================================
// 3. 월별 근무일수 계산
// ==========================================
function getMonthlyWorkCount(userName, year, month) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.ATTENDANCE_LOG);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return 0;
    
    const targetMonth = `${year}-${String(month).padStart(2, '0')}`;
    const workDates = new Set();
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 4) continue;
      
      const dateStr = row[0] ? row[0].toString() : "";
      const name = row[1] ? row[1].toString() : "";
      const recordType = row[3] ? row[3].toString() : "";
      
      if (name === userName && recordType === "출근" && dateStr.startsWith(targetMonth)) {
        workDates.add(dateStr);
      }
    }
    
    return workDates.size;
  } catch(e) {
    Logger.log("Error in getMonthlyWorkCount: " + e);
    return 0;
  }
}

// ==========================================
// 4. 사용자 정보 조회
// ==========================================
function getUserInfo(userKey) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.USER_MASTER);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return null;
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 2) continue;
      
      const name = row[0] ? row[0].toString().trim() : "";
      const slackId = row[1] ? row[1].toString().trim() : "";
      const baseDays = row[2] ? (Number(row[2]) || 0) : 0;
      const userType = row[3] ? row[3].toString().trim() : "정규직";  // D열: 구분(사용자타입)
      const address = row[5] ? row[5].toString().trim() : "";
      
      if ((slackId && slackId === userKey) || (name && name === userKey)) {
        return {
          name: name,
          slack_id: slackId,
          base_work_days: baseDays,
          user_type: userType,
          address: address
        };
      }
    }
    
    return null;
  } catch(e) {
    Logger.log("Error in getUserInfo: " + e);
    return null;
  }
}

function getAllUsers() {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.USER_MASTER);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return [];
    
    const users = [];
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 2) continue;
      
      const name = row[0] ? row[0].toString().trim() : "";
      if (!name) continue;
      
      const slackId = row[1] ? row[1].toString().trim() : "";
      const baseDays = row[2] ? (Number(row[2]) || 0) : 0;
      const userType = row[3] ? row[3].toString().trim() : "정규직";  // D열: 구분(사용자타입)
      const address = row[5] ? row[5].toString().trim() : "";
      
      users.push({
        name: name,
        slack_id: slackId,
        base_work_days: baseDays,
        user_type: userType,
        address: address
      });
    }
    
    return users;
  } catch(e) {
    Logger.log("Error in getAllUsers: " + e);
    return [];
  }
}

// ==========================================
// 5. 자재 사용 기록
// ==========================================
function recordMaterialUsage(userName, room, color, quantity) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.MATERIAL_LOG);
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    
    sheet.appendRow([
      Utilities.formatDate(kst, "GMT+9", "yyyy-MM-dd HH:mm:ss"),
      userName,
      room,
      color,
      quantity
    ]);
    
    return { success: true, message: "자재 사용량이 정상적으로 저장되었습니다." };
  } catch(e) {
    Logger.log("Error in recordMaterialUsage: " + e);
    return { success: false, message: "자재 기록 오류: " + e.toString() };
  }
}

// ==========================================
// 6. 발주 기록
// ==========================================
function recordMaterialOrder(userName, orderText) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.MATERIAL_ORDER);
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    
    sheet.appendRow([
      Utilities.formatDate(kst, "GMT+9", "yyyy-MM-dd HH:mm:ss"),
      userName,
      orderText,
      "" // 발주완료 처리시간은 공란
    ]);
    
    return { success: true, message: "발주 내용이 정상적으로 저장되었습니다." };
  } catch(e) {
    Logger.log("Error in recordMaterialOrder: " + e);
    return { success: false, message: "발주 기록 오류: " + e.toString() };
  }
}

function getPendingMaterialOrders(year, month) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.MATERIAL_ORDER);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return [];
    
    const orders = [];
    const targetMonthStr = `${year}-${String(month).padStart(2, '0')}`;
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 3) continue;
      
      const dateStr = row[0] ? row[0].toString() : "";
      const completedTime = row[3] ? row[3].toString() : "";
      
      // 날짜 부분만 추출
      const datePart = dateStr.split(" ")[0];
      
      // 발주완료 처리시간이 비어있고, 해당 월의 데이터인 경우만
      if (!completedTime && datePart && datePart.startsWith(targetMonthStr)) {
        orders.push({
          row_index: i + 1,
          date: dateStr,
          name: row[1] ? row[1].toString() : "",
          content: row[2] ? row[2].toString() : ""
        });
      }
    }
    
    return orders;
  } catch(e) {
    Logger.log("Error in getPendingMaterialOrders: " + e);
    return [];
  }
}

function markOrdersCompleted(rowIndices) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.MATERIAL_ORDER);
    const now = new Date();
    const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
    const completedTime = Utilities.formatDate(kst, "GMT+9", "yyyy-MM-dd HH:mm:ss");
    
    rowIndices.forEach(rowIdx => {
      sheet.getRange(rowIdx, 4).setValue(completedTime); // D열에 완료 시간
    });
    
    return { success: true, message: `${rowIndices.length}건의 발주가 완료 처리되었습니다.` };
  } catch(e) {
    Logger.log("Error in markOrdersCompleted: " + e);
    return { success: false, message: "발주 완료 처리 오류: " + e.toString() };
  }
}

// ==========================================
// 7. 인센티브 조회
// ==========================================
function getCommission(userName, year, month) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.INCENTIVE);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return 0;
    
    let total = 0;
    const targetMonthStr = `${year}-${String(month).padStart(2, '0')}`;
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 3) continue;
      
      const name = row[1] ? row[1].toString() : "";
      const dateStr = row[0] ? row[0].toString() : "";
      
      if (name === userName && dateStr.startsWith(targetMonthStr)) {
        const amount = Number(row[2]) || 0;
        total += amount;
      }
    }
    
    return total;
  } catch(e) {
    Logger.log("Error in getCommission: " + e);
    return 0;
  }
}

function getCommissionDetails(userName, year, month) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.INCENTIVE);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return [];
    
    const detailsByDate = {};
    const targetMonthStr = `${year}-${String(month).padStart(2, '0')}`;
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 3) continue;
      
      const name = row[1] ? row[1].toString() : "";
      const dateStr = row[0] ? row[0].toString() : "";
      
      if (name === userName && dateStr.startsWith(targetMonthStr)) {
        const date = dateStr.split(" ")[0]; // 날짜 부분만
        const amount = Number(row[2]) || 0;
        const description = row[3] ? row[3].toString() : "";
        
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
    
    return Object.values(detailsByDate);
  } catch(e) {
    Logger.log("Error in getCommissionDetails: " + e);
    return [];
  }
}

// ==========================================
// 8. 출근 로그 조회
// ==========================================
function getAttendanceLogs(userName) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.ATTENDANCE_LOG);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return [];
    
    const logs = [];
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 4) continue;
      
      const name = row[1] ? row[1].toString() : "";
      const recordType = row[3] ? row[3].toString() : "";
      
      if (name === userName && recordType === "출근") {
        logs.push({
          date: row[0] ? row[0].toString() : "",
          time: row[2] ? row[2].toString() : "",
          remarks: row[4] ? row[4].toString() : ""
        });
      }
    }
    
    return logs;
  } catch(e) {
    Logger.log("Error in getAttendanceLogs: " + e);
    return [];
  }
}

// ==========================================
// 9. Google Drive 폴더 생성
// ==========================================
function createSitePhotoFolder(siteAddress) {
  try {
    const parentFolderId = PROPERTIES.getProperty("GOOGLE_DRIVE_PARENT_FOLDER_ID");
    if (!parentFolderId) {
      return { success: false, message: "GOOGLE_DRIVE_PARENT_FOLDER_ID 환경 변수가 설정되지 않았습니다.", folderId: null, folderUrl: null };
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
    
    return { 
      success: true, 
      message: "폴더가 생성되었습니다.", 
      folderId: newFolder.getId(), 
      folderUrl: folderUrl 
    };
  } catch(e) {
    Logger.log("Error in createSitePhotoFolder: " + e);
    return { success: false, message: "폴더 생성 오류: " + e.toString(), folderId: null, folderUrl: null };
  }
}

