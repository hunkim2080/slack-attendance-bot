/**
 * 게임화 시스템 함수들
 */

// ==========================================
// 1. 레벨 계산
// ==========================================
function calculateLevel(totalDays) {
  return Math.floor(totalDays / 3);
}

// ==========================================
// 2. 칭호 시스템
// ==========================================
function getUserTitle(totalDays) {
  const level = calculateLevel(totalDays);
  const titles = {
    1: "현장 참관자", 2: "작업 보조", 3: "도구 전달자", 4: "정리 담당", 5: "준비 인원",
    6: "초급 보조", 7: "현장 적응 중", 8: "기본 작업 보조", 9: "반복 작업 가능", 10: "현장 투입 인원",
    11: "초급 시공 보조", 12: "줄눈 보조 작업자", 13: "단순 구간 담당", 14: "보조 시공 인력", 15: "초급 줄눈 작업자",
    16: "기본 시공 가능", 17: "단독 보조 수행", 18: "작업 지시 이해", 19: "현장 루틴 숙지", 20: "시공 참여 인력",
    21: "공정 이해자", 22: "작업 순서 인지", 23: "재료 구분 가능", 24: "기본 판단 가능", 25: "시공 흐름 이해",
    26: "문제 인지 가능", 27: "수정 작업 수행", 28: "실수 관리 가능", 29: "현장 대응 인력", 30: "부분 책임자",
    31: "안정 시공 인력", 32: "단독 구간 담당", 33: "기본 마감 가능", 34: "반복 품질 유지", 35: "클레임 최소화",
    36: "작업 속도 확보", 37: "일정 준수 인력", 38: "품질 유지 담당", 39: "현장 신뢰 인력", 40: "독립 작업 가능",
    41: "줄눈 기술자", 42: "현장 판단 가능자", 43: "공정 조율 가능", 44: "문제 해결 인력", 45: "기준 준수 기술자",
    46: "시공 완성도 관리", 47: "작업 설계 가능", 48: "현장 주력 인력", 49: "신뢰 기술자", 50: "중급 줄눈 기술자",
    51: "숙련 시공 인력", 52: "고난도 대응 가능", 53: "품질 기준 유지자", 54: "작업 안정화 담당", 55: "현장 핵심 인력",
    56: "복합 구간 담당", 57: "속도·품질 병행", 58: "작업 리듬 유지자", 59: "기준 공유 인력", 60: "숙련 줄눈공",
    61: "현장 중심 기술자", 62: "시공 리더급", 63: "팀 작업 주도", 64: "후배 가이드 가능", 65: "품질 책임 인력",
    66: "공정 관리 가능", 67: "현장 총괄 보조", 68: "작업 기준 전달자", 69: "팀 안정화 인력", 70: "현장 리더",
    71: "고급 줄눈 기술자", 72: "고난도 전담 인력", 73: "결과 예측 가능", 74: "기준 유지 장인", 75: "현장 신뢰 핵심",
    76: "재시공 최소화", 77: "품질 기준점", 78: "기술 기준자", 79: "이름이 품질", 80: "줄눈 장인",
    81: "최상급 기술자", 82: "현장 완성도 책임자", 83: "대체 불가 인력", 84: "기술 정점 인물", 85: "교육 가능 수준",
    86: "기준 설계자", 87: "기술 전수 가능", 88: "현장 상징 인물", 89: "팀 핵심 축", 90: "마스터 기술자",
    91: "줄눈 최고 숙련자", 92: "기술 기준 보유자", 93: "현장 설계 인력", 94: "품질 철학 보유", 95: "시스템 이해자",
    96: "기술 총괄급", 97: "기준 창출자", 98: "장인 중의 장인", 99: "최종 단계", 100: "줄눈 마스터"
  };
  
  return titles[level] || (level <= 100 ? `Lv.${level}` : "줄눈 마스터");
}

// ==========================================
// 3. 각성 단계 시스템
// ==========================================
function getAwakeningStage(totalDays) {
  for (let i = AWAKENING_STAGES.length - 1; i >= 0; i--) {
    if (totalDays >= AWAKENING_STAGES[i].days) {
      return AWAKENING_STAGES[i];
    }
  }
  return AWAKENING_STAGES[0];
}

function getAwakeningStageWithNumber(totalDays) {
  const stage = getAwakeningStage(totalDays);
  return { emoji: stage.emoji, num: stage.num };
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

// ==========================================
// 4. 레벨업 체크
// ==========================================
function checkLevelUp(prevTotalDays, currentTotalDays) {
  const prevLevel = calculateLevel(prevTotalDays);
  const currentLevel = calculateLevel(currentTotalDays);
  
  return {
    levelUp: currentLevel > prevLevel,
    currentLevel: currentLevel,
    previousLevel: prevLevel
  };
}

// ==========================================
// 5. 각성 컷신 메시지
// ==========================================
function getAwakeningCutscene(prevTotalDays, currentTotalDays) {
  const milestones = [45, 90, 135, 180, 225, 270];
  
  for (let milestone of milestones) {
    if (prevTotalDays < milestone && currentTotalDays >= milestone) {
      if (milestone === 45) {
        // 브론즈(🟤) → 실버(⚪) 각성
        return {
          shouldSend: true,
          message: `⚪ 1단계 각성 (45일) - 실버\n포지션: 진영 합류\n\n🎖 칭호\n「진영에 이름을 올린 자」\n\n첫 전투를 끝까지 치렀다.\n\n아직 능력을 논할 단계는 아니지만\n이 진영에 남을 수 있다는 건 증명했다.\n\n오늘부로\n명단에 이름이 오른다.\n\n💰 내일부터 일당 15만원 적용`
        };
      } else if (milestone === 90) {
        // 실버(⚪) → 골드(🟡) 각성
        return {
          shouldSend: true,
          message: `🟡 2단계 각성 (90일) - 골드\n포지션: 실무 장교\n\n🎖 칭호\n「명령을 이해하는 자」\n\n명령을 듣는 것과\n명령을 이해하는 건 다르다.\n\n이 단계부터는\n지시가 줄어든다.\n\n왜냐하면\n맥락을 읽기 시작했기 때문이다.\n\n💰 내일부터 일당 17만원 적용`
        };
      } else if (milestone === 135) {
        // 골드(🟡) → 플래티넘(🔵) 각성
        return {
          shouldSend: true,
          message: `🔵 3단계 각성 (135일) - 플래티넘\n포지션: 핵심 전력\n\n🎖 칭호\n「전장을 맡길 수 있는 장수」\n\n모든 전장에\n같은 장수를 보내지는 않는다.\n\n이 단계부터는\n중요한 자리에 배치된다.\n\n실력 때문이 아니라\n전장을 망치지 않는다는 이유로.\n\n💰 내일부터 일당 19만원 적용`
        };
      } else if (milestone === 180) {
        // 플래티넘(🔵) → 다이아(🟣) 각성
        return {
          shouldSend: true,
          message: `🟣 4단계 각성 (180일) - 다이아\n포지션: 중핵 장수\n\n🎖 칭호\n「진영의 기준을 아는 자」\n\n전략은 말로 전해지지 않는다.\n\n여러 전장을 함께 거치며\n자연스럽게 공유된다.\n\n이 단계부터는\n같은 판단을 내리기 시작한다.\n\n💰 내일부터 일당 21만원 적용`
        };
      } else if (milestone === 225) {
        // 다이아(🟣) → 레전드(🔴) 각성
        return {
          shouldSend: true,
          message: `🔴 5단계 각성 (225일) - 레전드\n포지션: 핵심 참전 인물\n\n🎖 칭호\n「빠지면 전력이 달라지는 인물」\n\n이쯤 되면\n자리가 보인다.\n\n없으면 돌아가긴 하지만\n있으면 전투가 달라진다.\n\n그래서\n이 진영의 핵심 전력으로 분류된다.\n\n💰 내일부터 일당 23만원 적용`
        };
      } else if (milestone === 270) {
        // 레전드(🔴) → 마스터(👑) 각성
        return {
          shouldSend: true,
          message: `👑 6단계 각성 (270일) - 마스터\n포지션: 진영 핵심\n\n🎖 칭호\n「이 진영의 장수」\n\n어느 진영에 속할지는\n각자의 선택이다.\n\n다만 여기까지 온 사람은\n이 진영의 전투를\n가장 잘 이해하고 있다.\n\n오늘부로\n이 진영의 장수로 기록된다.\n\n💰 최종 일당 25만원 적용`
        };
      }
    }
  }
  
  return { shouldSend: false, message: null };
}

// ==========================================
// 6. 레벨업 및 각성 체크 (통합)
// ==========================================
function checkLevelUpAndAwakening(userInfo, prevTotalDays, currentTotalDays) {
  // 레벨업 체크
  const levelUpResult = checkLevelUp(prevTotalDays, currentTotalDays);
  if (levelUpResult.levelUp) {
    const userTitle = getUserTitle(currentTotalDays);
    const levelUpMsg = `🎉 **레벨업!**\n\n` +
                       `Lv.${levelUpResult.previousLevel} → Lv.${levelUpResult.currentLevel}\n\n` +
                       `🎖 **새로운 칭호:** ${userTitle}\n\n` +
                       `현재 총 근무일수: ${currentTotalDays}일`;
    sendSlackMessage(userInfo.slack_id, levelUpMsg);
  }
  
  // 각성 단계 달성 체크
  const cutscene = getAwakeningCutscene(prevTotalDays, currentTotalDays);
  if (cutscene.shouldSend) {
    sendSlackMessage(userInfo.slack_id, cutscene.message);
  }
}

// ==========================================
// 7. 경험치 진행률
// ==========================================
function getExpProgress(totalDays) {
  const currentLevel = calculateLevel(totalDays);
  const nextLevel = currentLevel + 1;
  const currentLevelDays = currentLevel * 3;
  const nextLevelDays = nextLevel * 3;
  const levelRequiredDays = nextLevelDays - currentLevelDays;
  const progressDays = totalDays - currentLevelDays;
  
  const percentage = levelRequiredDays > 0 ? Math.floor((progressDays / levelRequiredDays) * 100) : 100;
  const filled = Math.floor(percentage / 10);
  const progressBar = "■".repeat(filled) + "□".repeat(10 - filled);
  const daysToNext = nextLevelDays - totalDays;
  
  return { progressBar, percentage, daysToNext };
}

function getProgressBar(totalDays) {
  const progress = getExpProgress(totalDays);
  return progress.progressBar;
}

// ==========================================
// 8. 급여 계산
// ==========================================
function calculateDailyPay(totalDays) {
  for (let rate of PAY_RATES) {
    if (totalDays >= rate.min && totalDays <= rate.max) {
      return rate.rate;
    }
  }
  return 250000; // 기본값
}

function calculateMonthlyPayroll(userName, year, month) {
  try {
    const userInfo = getUserInfo(userName);
    const baseDays = userInfo ? userInfo.base_work_days : 0;
    
    const sheet = SS.getSheetByName(SHEET_NAMES.ATTENDANCE_LOG);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return { totalPay: 0, workDays: 0, dailyBreakdown: [] };
    
    // 이전 달까지의 총 근무일수 계산
    let previousDays = baseDays;
    const targetMonth = `${year}-${String(month).padStart(2, '0')}`;
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 4) continue;
      
      const name = row[1] ? row[1].toString() : "";
      const recordType = row[3] ? row[3].toString() : "";
      const dateStr = row[0] ? row[0].toString() : "";
      
      if (name === userName && recordType === "퇴근" && dateStr < targetMonth) {
        previousDays++;
      }
    }
    
    // 해당 월의 출근일 추출
    const workDates = [];
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 4) continue;
      
      const name = row[1] ? row[1].toString() : "";
      const recordType = row[3] ? row[3].toString() : "";
      const dateStr = row[0] ? row[0].toString() : "";
      
      if (name === userName && recordType === "출근" && dateStr.startsWith(targetMonth)) {
        workDates.push(dateStr);
      }
    }
    
    // 중복 제거 및 정렬
    const uniqueDates = [...new Set(workDates)].sort();
    
    // 일자별로 단가 계산
    let totalPay = 0;
    const dailyBreakdown = [];
    
    uniqueDates.forEach((workDate, index) => {
      const currentTotalDays = previousDays + index + 1;
      const dailyPay = calculateDailyPay(currentTotalDays);
      totalPay += dailyPay;
      dailyBreakdown.push({
        date: workDate,
        cumulativeDays: currentTotalDays,
        dailyPay: dailyPay
      });
    });
    
    return {
      totalPay: totalPay,
      workDays: uniqueDates.length,
      dailyBreakdown: dailyBreakdown
    };
  } catch(e) {
    Logger.log("Error in calculateMonthlyPayroll: " + e);
    return { totalPay: 0, workDays: 0, dailyBreakdown: [] };
  }
}

function calculateAllPayrolls(year, month) {
  try {
    const users = getAllUsers();
    if (users.length === 0) return [];
    
    const payrolls = [];
    
    users.forEach(user => {
      const name = user.name;
      const slackId = user.slack_id;
      
      // 기본 급여 계산
      const payrollResult = calculateMonthlyPayroll(name, year, month);
      const basePay = payrollResult.totalPay;
      const workDays = payrollResult.workDays;
      
      // 근무일이 0이면 건너뛰기
      if (workDays === 0) return;
      
      // 인센티브 계산
      const commission = getCommission(name, year, month);
      
      // 교통비 계산 (근무일수 × 10,000원)
      const transportation = workDays * 10000;
      
      // 총 급여
      const totalPay = basePay + commission + transportation;
      
      payrolls.push({
        name: name,
        slack_id: slackId,
        work_days: workDays,
        base_pay: basePay,
        commission: commission,
        transportation: transportation,
        total_pay: totalPay
      });
    });
    
    return payrolls;
  } catch(e) {
    Logger.log("Error in calculateAllPayrolls: " + e);
    return [];
  }
}

function getUserPayrollHistory(userName) {
  try {
    const sheet = SS.getSheetByName(SHEET_NAMES.ATTENDANCE_LOG);
    const data = sheet.getDataRange().getValues();
    
    if (data.length < 2) return [];
    
    // 모든 월별 근무 기록 추출
    const monthlyRecords = {};
    
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row.length < 4) continue;
      
      const name = row[1] ? row[1].toString() : "";
      const recordType = row[3] ? row[3].toString() : "";
      const dateStr = row[0] ? row[0].toString() : "";
      
      if (name === userName && recordType === "출근" && dateStr) {
        const date = new Date(dateStr);
        const year = date.getFullYear();
        const month = date.getMonth() + 1;
        const key = `${year}-${month}`;
        
        if (!monthlyRecords[key]) {
          monthlyRecords[key] = { year: year, month: month };
        }
      }
    }
    
    // 각 월별 급여 계산
    const payrolls = [];
    for (let key in monthlyRecords) {
      const { year, month } = monthlyRecords[key];
      const payrollResult = calculateMonthlyPayroll(userName, year, month);
      const commission = getCommission(userName, year, month);
      const transportation = payrollResult.workDays * 10000;
      
      payrolls.push({
        year: year,
        month: month,
        work_days: payrollResult.workDays,
        base_pay: payrollResult.totalPay,
        commission: commission,
        transportation: transportation,
        total_pay: payrollResult.totalPay + commission + transportation
      });
    }
    
    // 최신순으로 정렬
    payrolls.sort((a, b) => {
      if (a.year !== b.year) return b.year - a.year;
      return b.month - a.month;
    });
    
    return payrolls;
  } catch(e) {
    Logger.log("Error in getUserPayrollHistory: " + e);
    return [];
  }
}

// ==========================================
// 9. 정산일까지 남은 일수
// ==========================================
function getDaysUntilSettlement() {
  const now = new Date();
  const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
  const lastDay = new Date(kst.getFullYear(), kst.getMonth() + 1, 0).getDate();
  const daysLeft = lastDay - kst.getDate();
  return daysLeft;
}

