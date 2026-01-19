# sheets_handler.py (게임화 출퇴근 및 급여 정산 시스템)

import os
import json
import time
import ssl
import functools
import random
import logging
from datetime import datetime, timedelta
from calendar import monthrange
from typing import List, Dict, Any

import pytz
import requests
from requests.adapters import HTTPAdapter, Retry
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# 환경 변수에서 시트 키를 가져옵니다.
SPREADSHEET_KEY = os.environ.get("SPREADSHEET_KEY")
KST = pytz.timezone('Asia/Seoul')

# 급여 단가 설정 (일당 계단식 인상)
# GAS 버전 attendance-bot.gs와 일치하도록 경계값 수정
PAY_RATES = [
    (1, 45, 130000),       # 1~45일: 130,000원 (13만원)
    (46, 90, 150000),      # 46~90일: 150,000원 (15만원)
    (91, 135, 170000),     # 91~135일: 170,000원 (17만원)
    (136, 180, 190000),    # 136~180일: 190,000원 (19만원)
    (181, 225, 210000),    # 181~225일: 210,000원 (21만원)
    (226, 270, 230000),    # 226~270일: 230,000원 (23만원)
    (271, float('inf'), 250000),  # 271일~: 250,000원 (25만원, 최대)
]

# 스킬 획득 구간 (급여 인상 구간)
SKILL_MILESTONES = [45, 90, 135, 180, 225, 270]

# 스킬 이름 매핑
SKILL_NAMES = {
    45: "고글 없이 그라인더 작업하기",
    91: "안전장비 착용 습관화",
    136: "현장 리더십 발휘",
    181: "마스터 크래프트맨"
}

# 교통비 단가 (근무일당)
TRANSPORTATION_RATE = 10000

# ----------------------------------------------------
# 1. Sheets 서비스 생성 (요청 단위로 생성)
# ----------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _build_service():
    json_str = os.environ.get("GCF_CREDENTIALS")
    if not json_str:
        raise ValueError("GCF_CREDENTIALS 환경 변수가 설정되지 않았습니다.")

    credentials_dict = json.loads(json_str)
    creds = service_account.Credentials.from_service_account_info(
        credentials_dict,
        scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def execute_with_retry(func, max_retries=3, backoff_factor=1):
    """재시도 로직이 포함된 함수 실행"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff_factor * (2 ** attempt)
            logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)


# ----------------------------------------------------
# 2. 출퇴근 기록
# ----------------------------------------------------
def record_check_in(user_name: str, site_address: str = ""):
    """출근 기록을 시트에 추가합니다."""
    try:
        def _task():
            service = _build_service()
            now_kst = datetime.now(KST)
            body = {
                "values": [[
                    now_kst.strftime("%Y-%m-%d"),
                    user_name,
                    now_kst.strftime("%H:%M:%S"),
                    "출근",
                    site_address  # 비고란에 현장 주소 포함
                ]]
            }
            request = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_KEY,
                range="AttendanceLog!A:E",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            )
            return request.execute()

        execute_with_retry(_task)
        return True, "출근 기록이 정상적으로 저장되었습니다."
    except Exception as e:
        return False, f"출근 기록 오류: {str(e)}"


def record_check_out(user_name: str):
    """퇴근 기록을 시트에 추가합니다."""
    try:
        def _task():
            service = _build_service()
            now_kst = datetime.now(KST)
            body = {
                "values": [[
                    now_kst.strftime("%Y-%m-%d"),
                    user_name,
                    now_kst.strftime("%H:%M:%S"),
                    "퇴근",
                    ""  # 비고란은 빈 값
                ]]
            }
            request = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_KEY,
                range="AttendanceLog!A:E",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            )
            return request.execute()

        execute_with_retry(_task)
        return True, "퇴근 기록이 정상적으로 저장되었습니다."
    except Exception as e:
        return False, f"퇴근 기록 오류: {str(e)}"


# ----------------------------------------------------
# 3. 총 근무일수 계산
# ----------------------------------------------------
def get_total_work_days(user_name: str):
    """사용자의 총 근무일수를 계산합니다.
    
    하루에 출근과 퇴근이 모두 있어야 근무일수로 카운트됩니다.
    """
    try:
        def _task():
            service = _build_service()
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="AttendanceLog!A:E"
            ).execute()
            all_values = resp.get("values", [])
            if len(all_values) < 2:
                return 0

            # 날짜별로 출근/퇴근 기록을 추적
            date_records = {}  # {날짜: {"출근": bool, "퇴근": bool}}
            
            for row in all_values[1:]:
                if len(row) < 4:
                    continue
                
                date = row[0] if len(row) > 0 else ""
                name = row[1] if len(row) > 1 else ""
                record_type = row[3] if len(row) > 3 else ""
                
                if name == user_name and date:
                    if date not in date_records:
                        date_records[date] = {"출근": False, "퇴근": False}
                    
                    if record_type == "출근":
                        date_records[date]["출근"] = True
                    elif record_type == "퇴근":
                        date_records[date]["퇴근"] = True
            
            # 출근과 퇴근이 모두 있는 날짜만 카운트
            count = 0
            for date, records in date_records.items():
                if records["출근"] and records["퇴근"]:
                    count += 1
            
            return count

        return execute_with_retry(_task)
    except Exception as e:
        logging.exception(f"Error getting total work days for {user_name}: {e}")
        return 0


# ----------------------------------------------------
# 4. 레벨 계산
# ----------------------------------------------------
def calculate_level(total_days):
    """총 근무일수에 따른 레벨을 계산합니다.
    레벨 계산식: int(근무일수 / 3)
    """
    return int(total_days / 3)


# ----------------------------------------------------
# 5. 칭호 시스템
# ----------------------------------------------------
def get_title_by_level(level):
    """레벨에 따른 칭호를 반환합니다."""
    titles = {
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
    }
    return titles.get(level, f"Lv.{level}") if level <= 100 else "줄눈 마스터"


def get_user_title(total_days):
    """총 근무일수에 따른 칭호를 반환합니다."""
    level = calculate_level(total_days)
    return get_title_by_level(level)


def get_days_until_settlement():
    """이번 달 말일까지 남은 일수 계산"""
    now = datetime.now(KST)
    last_day = monthrange(now.year, now.month)[1]
    days_left = last_day - now.day
    return days_left

# ----------------------------------------------------
# 7. EXP 진행바 생성
# ----------------------------------------------------
def get_exp_progress(total_days):
    """
    다음 레벨까지의 EXP 진행바를 생성합니다.
    반환: (progress_bar, percentage, days_to_next_level)
    """
    current_level = calculate_level(total_days)
    next_level = current_level + 1
    
    # 현재 레벨에 필요한 일수
    current_level_days = current_level * 3
    # 다음 레벨에 필요한 일수
    next_level_days = next_level * 3
    # 레벨당 필요한 일수
    level_required_days = next_level_days - current_level_days
    
    # 현재 레벨에서 진행된 일수
    progress_days = total_days - current_level_days
    
    # 진행률 계산
    if level_required_days > 0:
        percentage = int((progress_days / level_required_days) * 100)
    else:
        percentage = 100
    
    # 진행바 생성 (10칸)
    filled = int(percentage / 10)
    progress_bar = "■" * filled + "□" * (10 - filled)
    
    # 다음 레벨까지 남은 일수
    days_to_next = next_level_days - total_days
    
    return progress_bar, percentage, days_to_next

# ----------------------------------------------------
# 8. 스킬 획득 체크
# ----------------------------------------------------
def check_skill_acquisition(total_days, previous_days):
    """
    급여 인상 구간을 돌파했는지 확인합니다.
    반환: (acquired, skill_name) 또는 (False, None)
    """
    for milestone in SKILL_MILESTONES:
        if previous_days < milestone <= total_days:
            return True, SKILL_NAMES.get(milestone, f"{milestone}일 달성")
    return False, None


def get_awakening_cutscene(total_days, previous_days):
    """
    각성 단계별 컷신 메시지를 반환합니다.
    45일, 90일, 135일, 180일, 225일, 270일 달성 시 발송
    
    Returns:
        tuple: (발송 여부(bool), 메시지(str)) 또는 (False, None)
    """
    awakening_milestones = [45, 90, 135, 180, 225, 270]
    
    for milestone in awakening_milestones:
        if previous_days < milestone <= total_days:
            if milestone == 45:
                # 브론즈(🟤) → 실버(⚪) 각성
                return True, """⚪ 1단계 각성 (45일) - 실버
포지션: 진영 합류

🎖 칭호
「진영에 이름을 올린 자」

첫 전투를 끝까지 치렀다.

아직 능력을 논할 단계는 아니지만
이 진영에 남을 수 있다는 건 증명했다.

오늘부로
명단에 이름이 오른다.

💰 내일부터 일당 15만원 적용"""
            elif milestone == 90:
                # 실버(⚪) → 골드(🟡) 각성
                return True, """🟡 2단계 각성 (90일) - 골드
포지션: 실무 장교

🎖 칭호
「명령을 이해하는 자」

명령을 듣는 것과
명령을 이해하는 건 다르다.

이 단계부터는
지시가 줄어든다.

왜냐하면
맥락을 읽기 시작했기 때문이다.

💰 내일부터 일당 17만원 적용"""
            elif milestone == 135:
                # 골드(🟡) → 플래티넘(🔵) 각성
                return True, """🔵 3단계 각성 (135일) - 플래티넘
포지션: 핵심 전력

🎖 칭호
「전장을 맡길 수 있는 장수」

모든 전장에
같은 장수를 보내지는 않는다.

이 단계부터는
중요한 자리에 배치된다.

실력 때문이 아니라
전장을 망치지 않는다는 이유로.

💰 내일부터 일당 19만원 적용"""
            elif milestone == 180:
                # 플래티넘(🔵) → 다이아(🟣) 각성
                return True, """🟣 4단계 각성 (180일) - 다이아
포지션: 중핵 장수

🎖 칭호
「진영의 기준을 아는 자」

전략은 말로 전해지지 않는다.

여러 전장을 함께 거치며
자연스럽게 공유된다.

이 단계부터는
같은 판단을 내리기 시작한다.

💰 내일부터 일당 21만원 적용"""
            elif milestone == 225:
                # 다이아(🟣) → 레전드(🔴) 각성
                return True, """🔴 5단계 각성 (225일) - 레전드
포지션: 핵심 참전 인물

🎖 칭호
「빠지면 전력이 달라지는 인물」

이쯤 되면
자리가 보인다.

없으면 돌아가긴 하지만
있으면 전투가 달라진다.

그래서
이 진영의 핵심 전력으로 분류된다.

💰 내일부터 일당 23만원 적용"""
            elif milestone == 270:
                # 레전드(🔴) → 마스터(👑) 각성
                return True, """👑 6단계 각성 (270일) - 마스터
포지션: 진영 핵심

🎖 칭호
「이 진영의 장수」

어느 진영에 속할지는
각자의 선택이다.

다만 여기까지 온 사람은
이 진영의 전투를
가장 잘 이해하고 있다.

오늘부로
이 진영의 장수로 기록된다.

💰 최종 일당 25만원 적용"""
    
    return False, None


def check_level_up(total_days, previous_days):
    """
    레벨업 여부를 확인합니다.
    레벨 계산식: int(근무일수 / 3)
    
    Returns:
        tuple: (레벨업 여부(bool), 현재 레벨(int), 이전 레벨(int)) 또는 (False, 현재 레벨, 이전 레벨)
    """
    current_level = calculate_level(total_days)
    previous_level = calculate_level(previous_days)
    
    if current_level > previous_level:
        return True, current_level, previous_level
    return False, current_level, previous_level

# ----------------------------------------------------
# 9. 해당 월 근무일수 계산
# ----------------------------------------------------
def get_monthly_work_count(user_name, year, month):
    """
    특정 월의 근무일수를 계산합니다.
    """
    try:
        def _task():
            service = _build_service()
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="AttendanceLog!A:E"
            ).execute()
            all_values = resp.get("values", [])
            if len(all_values) < 2:
                return 0

            headers = all_values[0]
            date_idx = headers.index("날짜") if "날짜" in headers else 0
            name_idx = headers.index("이름") if "이름" in headers else 1
            type_idx = headers.index("구분") if "구분" in headers else 3

            work_dates = []
            target_month = f"{year}-{month:02d}"

            for row in all_values[1:]:
                if len(row) > date_idx and len(row) > name_idx and len(row) > type_idx:
                    if row[name_idx] == user_name and row[type_idx] == "출근":
                        date_str = row[date_idx]
                        if date_str.startswith(target_month):
                            work_dates.append(date_str)

            return len(set(work_dates))

        return execute_with_retry(_task)
    except Exception as e:
        logging.exception(f"Error getting monthly work count for {user_name}: {e}")
        return 0


# ----------------------------------------------------
# 10. 일당 계산 (계단식)
# ----------------------------------------------------
def calculate_daily_pay(total_days):
    """
    총 근무일수에 따른 일당을 계산합니다.
    """
    for min_days, max_days, rate in PAY_RATES:
        if min_days <= total_days <= max_days:
            return rate
    return 250000  # 기본값 (270일 이상)

# ----------------------------------------------------
# 11. 월급 계산 (일자별 단가 적용)
# ----------------------------------------------------
def calculate_monthly_payroll(user_name, year, month):
    """
    월급을 계산합니다. 월 중간에 단가가 오르는 경우를 반영하여 일자별로 계산합니다.
    반환: (total_pay, work_days, daily_pay_breakdown)
    """
    try:
        def _task():
            service = _build_service()
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="AttendanceLog!A:E"
            ).execute()
            all_values = resp.get("values", [])
            if len(all_values) < 2:
                return 0, 0, []

            headers = all_values[0]
            date_idx = headers.index("날짜") if "날짜" in headers else 0
            name_idx = headers.index("이름") if "이름" in headers else 1
            type_idx = headers.index("구분") if "구분" in headers else 3

            work_dates = []
            target_month = f"{year}-{month:02d}"

            for row in all_values[1:]:
                if len(row) > date_idx and len(row) > name_idx and len(row) > type_idx:
                    if row[name_idx] == user_name and row[type_idx] == "출근":
                        date_str = row[date_idx]
                        if date_str.startswith(target_month):
                            work_dates.append(date_str)

            if not work_dates:
                return 0, 0, []

            user_info = get_user_info(user_name)
            base_days = user_info.get("base_work_days", 0) if user_info else 0

            # 이전 달까지의 근무일수 계산
            previous_work_dates = set()  # 변수 초기화 추가
            for row in all_values[1:]:
                if len(row) > date_idx and len(row) > name_idx and len(row) > type_idx:
                    if row[name_idx] == user_name and row[type_idx] == "출근":
                        date_str = row[date_idx]
                        if date_str < target_month:
                            previous_work_dates.add(date_str)

            previous_days = base_days + len(previous_work_dates)

            total_pay = 0
            daily_breakdown = []
            work_dates_sorted = sorted(set(work_dates))

            for work_date in work_dates_sorted:
                current_total_days = previous_days + work_dates_sorted.index(work_date) + 1
                daily_pay = calculate_daily_pay(current_total_days)
                total_pay += daily_pay
                daily_breakdown.append({
                    "date": work_date,
                    "cumulative_days": current_total_days,
                    "daily_pay": daily_pay
                })

            return total_pay, len(work_dates_sorted), daily_breakdown

        return execute_with_retry(_task)
    except Exception as e:
        return 0, 0, []

# ----------------------------------------------------
# 12. 인센티브 조회
# ----------------------------------------------------
def get_commission(user_name, year, month):
    """
    특정 월의 인센티브(격려금) 총액을 조회합니다.
    """
    try:
        def _task():
            service = _build_service()
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="Incentive!A:F"
            ).execute()
            all_values = resp.get("values", [])
            if len(all_values) < 2:
                return 0

            headers = all_values[0]
            date_idx = headers.index("날짜") if "날짜" in headers else 0
            name_idx = headers.index("이름") if "이름" in headers else 1
            amount_idx = headers.index("금액") if "금액" in headers else 2

            total = 0
            target_month = f"{year}-{month:02d}"

            for row in all_values[1:]:
                if len(row) > date_idx and len(row) > name_idx and len(row) > amount_idx:
                    if row[name_idx] == user_name:
                        date_str = row[date_idx]
                        if date_str.startswith(target_month):
                            try:
                                amount = int(float(row[amount_idx]))
                                total += amount
                            except (ValueError, IndexError):
                                continue

            return total

        return execute_with_retry(_task)
    except Exception as e:
        logging.exception(f"Error getting commission for {user_name}: {e}")
        return 0


def get_commission_details(user_name, year, month):
    """
    특정 월의 인센티브 상세 내역을 조회합니다.
    반환: [{"date": str, "total": int, "items": [{"description": str, "amount": int}]}, ...]
    """
    try:
        def _task():
            service = _build_service()
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="Incentive!A:F"
            ).execute()
            all_values = resp.get("values", [])
            if len(all_values) < 2:
                return []

            headers = all_values[0]
            date_idx = headers.index("날짜") if "날짜" in headers else 0
            name_idx = headers.index("이름") if "이름" in headers else 1
            amount_idx = headers.index("금액") if "금액" in headers else 2
            description_idx = headers.index("내용") if "내용" in headers else 3

            details_by_date = {}
            target_month = f"{year}-{month:02d}"

            for row in all_values[1:]:
                if len(row) > date_idx and len(row) > name_idx and len(row) > amount_idx:
                    if row[name_idx] == user_name:
                        date_str = row[date_idx]
                        if date_str.startswith(target_month):
                            try:
                                amount = int(float(row[amount_idx]))
                                description = row[description_idx] if len(row) > description_idx else ""
                                
                                if date_str not in details_by_date:
                                    details_by_date[date_str] = {
                                        "date": date_str,
                                        "total": 0,
                                        "items": []
                                    }
                                
                                details_by_date[date_str]["total"] += amount
                                details_by_date[date_str]["items"].append({
                                    "description": description,
                                    "amount": amount
                                })
                            except (ValueError, IndexError):
                                continue

            return list(details_by_date.values())

        return execute_with_retry(_task)
    except Exception as e:
        logging.exception(f"Error getting commission details for {user_name}: {e}")
        return []


# ----------------------------------------------------
# 13. 교통비 계산
# ----------------------------------------------------
def calculate_transportation_allowance(work_days):
    """
    교통비를 계산합니다.
    계산식: 근무일수 × 10,000원
    """
    return work_days * TRANSPORTATION_RATE


# ----------------------------------------------------
# 14. 각성 단계 시스템
# ----------------------------------------------------
def get_awakening_stage(total_days):
    """
    총 근무일수에 따른 각성 단계를 반환합니다.
    반환: (왕관 이모지, 단계명)
    """
    if total_days < 45:
        return "🟤", "브론즈"
    elif total_days < 90:
        return "⚪", "실버"
    elif total_days < 135:
        return "🟡", "골드"
    elif total_days < 180:
        return "🔵", "플래티넘"
    elif total_days < 225:
        return "🟣", "다이아"
    elif total_days < 270:
        return "🔴", "레전드"
    else:
        return "👑", "마스터"


def get_awakening_stage_with_number(total_days):
    """
    총 근무일수에 따른 각성 단계를 숫자와 함께 반환합니다.
    반환: (왕관 이모지, 단계 번호)
    """
    if total_days < 45:
        return "🟤", 0
    elif total_days < 90:
        return "⚪", 1
    elif total_days < 135:
        return "🟡", 2
    elif total_days < 180:
        return "🔵", 3
    elif total_days < 225:
        return "🟣", 4
    elif total_days < 270:
        return "🔴", 5
    else:
        return "👑", 6


def get_awakening_progress(total_days):
    """
    다음 각성 단계까지의 진행률을 계산합니다.
    반환: (progress_bar, percentage, days_to_next, next_milestone)
    """
    milestones = [45, 90, 135, 180, 225, 270]
    
    # 현재 단계 찾기
    current_milestone = 0
    next_milestone = 45
    
    for milestone in milestones:
        if total_days >= milestone:
            current_milestone = milestone
        else:
            next_milestone = milestone
            break
    
    if total_days >= 270:
        # 최대 단계 달성
        return "■■■■■■■■■■", 100, 0, None
    
    # 진행률 계산
    progress_days = total_days - current_milestone
    required_days = next_milestone - current_milestone
    
    if required_days > 0:
        percentage = int((progress_days / required_days) * 100)
    else:
        percentage = 100
    
    # 진행바 생성 (10칸)
    filled = int(percentage / 10)
    progress_bar = "■" * filled + "□" * (10 - filled)
    
    # 다음 각성까지 남은 일수
    days_to_next = next_milestone - total_days
    
    return progress_bar, percentage, days_to_next, next_milestone


# ----------------------------------------------------
# 15. 사용자 정보 조회
# ----------------------------------------------------
def get_user_info(user_key):
    """
    UserMaster 시트에서 사용자 정보를 조회합니다.
    user_key는 Slack_ID 또는 한글 이름일 수 있습니다.
    
    Returns:
        dict: {"name": str, "base_work_days": int, "address": str} 또는 None
    """
    try:
        def _task():
            service = _build_service()
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="UserMaster!A:F"  # A: 이름, B: Slack_ID, C: 기본근무일수, F: 주소
            ).execute()
            all_values = resp.get("values", [])
            if len(all_values) < 2:
                return None

            # 헤더 제외
            for row in all_values[1:]:
                if len(row) >= 2:
                    name = row[0].strip() if len(row) > 0 else ""  # A열: 이름
                    slack_id = row[1].strip() if len(row) > 1 else ""  # B열: Slack_ID
                    base_days = 0
                    address = ""
                    
                    # 기본근무일수 (C열)
                    if len(row) > 2 and row[2]:
                        try:
                            base_days = int(float(row[2]))
                        except (ValueError, TypeError):
                            base_days = 0
                    
                    # 주소 (F열)
                    if len(row) > 5 and row[5]:
                        address = row[5].strip()
                    
                    # Slack_ID 또는 이름으로 매칭
                    if slack_id and slack_id == user_key:
                        return {
                            "name": name,
                            "base_work_days": base_days,
                            "address": address
                        }
                    elif name and name == user_key:
                        return {
                            "name": name,
                            "base_work_days": base_days,
                            "address": address
                        }
            
            return None

        return execute_with_retry(_task)
    except Exception as e:
        logging.exception(f"Error getting user info for {user_key}: {e}")
        return None


def get_all_users():
    """
    UserMaster 시트에서 모든 사용자 목록을 조회합니다.
    
    Returns:
        List[Dict]: [{"name": str, "slack_id": str, "base_work_days": int, "address": str}, ...]
    """
    try:
        def _task():
            service = _build_service()
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="UserMaster!A:F"  # A: 이름, B: Slack_ID, C: 기본근무일수, F: 주소
            ).execute()
            all_values = resp.get("values", [])
            if len(all_values) < 2:
                return []
            
            users = []
            # 헤더 제외
            for row in all_values[1:]:
                if len(row) >= 2:
                    name = row[0].strip() if len(row) > 0 else ""
                    slack_id = row[1].strip() if len(row) > 1 else ""
                    
                    if not name:  # 이름이 없으면 건너뛰기
                        continue
                    
                    base_days = 0
                    address = ""
                    
                    # 기본근무일수 (C열)
                    if len(row) > 2 and row[2]:
                        try:
                            base_days = int(float(row[2]))
                        except (ValueError, TypeError):
                            base_days = 0
                    
                    # 주소 (F열)
                    if len(row) > 5 and row[5]:
                        address = row[5].strip()
                    
                    users.append({
                        "name": name,
                        "slack_id": slack_id,
                        "base_work_days": base_days,
                        "address": address
                    })
            
            return users
        
        return execute_with_retry(_task)
    except Exception as e:
        logging.exception(f"Error getting all users: {e}")
        return []


def calculate_all_payrolls(year, month):
    """
    모든 사용자의 급여를 계산합니다.
    
    Args:
        year: 연도
        month: 월
    
    Returns:
        List[Dict]: [{"name": str, "slack_id": str, "work_days": int, "base_pay": int, 
                     "commission": int, "transportation": int, "total_pay": int}, ...]
    """
    try:
        users = get_all_users()
        if not users:
            return []
        
        payrolls = []
        for user in users:
            name = user["name"]
            slack_id = user["slack_id"]
            
            # 기본 급여 계산
            base_pay, work_days, _ = calculate_monthly_payroll(name, year, month)
            
            # 근무일이 0이면 건너뛰기
            if work_days == 0:
                continue
            
            # 인센티브 계산
            commission = get_commission(name, year, month)
            
            # 교통비 계산
            transportation = calculate_transportation_allowance(work_days)
            
            # 총 급여
            total_pay = base_pay + commission + transportation
            
            payrolls.append({
                "name": name,
                "slack_id": slack_id,
                "work_days": work_days,
                "base_pay": base_pay,
                "commission": commission,
                "transportation": transportation,
                "total_pay": total_pay
            })
        
        return payrolls
    except Exception as e:
        logging.exception(f"Error calculating all payrolls: {e}")
        return []


# ----------------------------------------------------
# 16. 자재 사용 기록
# ----------------------------------------------------
def record_material_usage(user_name: str, room: str, color: str, quantity: float):
    """자재 사용량을 MaterialLog 시트에 기록.
    
    Args:
        user_name: 사용자 한글 이름
        room: 방 이름
        color: 색상 코드
        quantity: 사용량
    
    Returns:
        (success: bool, message: str)
    """
    try:
        def _task():
            service = _build_service()
            now_kst = datetime.now(KST)
            body = {
                "values": [[
                    now_kst.strftime("%Y-%m-%d %H:%M:%S"),  # 날짜시간
                    user_name,                             # 이름
                    room,                                  # 방 이름
                    color,                                 # 색상 코드
                    quantity                               # 사용량
                ]]
            }
            request = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_KEY,
                range="MaterialLog!A:E",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            )
            return request.execute()

        execute_with_retry(_task)
        return True, "자재 사용량이 정상적으로 저장되었습니다."
    except Exception as e:
        return False, f"자재 기록 오류: {str(e)}"


def record_material_order(user_name: str, order_text: str):
    """발주 필요 자재를 MaterialOrder 시트에 기록.
    
    Args:
        user_name: 사용자 한글 이름
        order_text: 발주 내용 (텍스트)
    
    Returns:
        (success: bool, message: str)
    """
    try:
        def _task():
            service = _build_service()
            now_kst = datetime.now(KST)
            body = {
                "values": [[
                    now_kst.strftime("%Y-%m-%d %H:%M:%S"),
                    user_name,
                    order_text
                ]]
            }
            request = service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_KEY,
                range="MaterialOrder!A:C",  # 날짜시간, 이름, 발주내용
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body
            )
            return request.execute()

        execute_with_retry(_task)
        return True, "발주 내용이 정상적으로 저장되었습니다."
    except Exception as e:
        return False, f"발주 기록 오류: {str(e)}"


def get_pending_material_orders(year: int = None, month: int = None):
    """미처리 발주 목록 조회 (발주완료 처리시간이 비어있는 항목)
    
    Args:
        year: 연도 (None이면 현재 연도)
        month: 월 (None이면 현재 월)
    
    Returns:
        (success: bool, orders: List[Dict] or error_message: str)
        orders: [{"row_index": int, "date": str, "name": str, "content": str}, ...]
    """
    try:
        # 외부 스코프에서 미리 값을 할당 (중첩 함수에서 참조하기 위해)
        now_kst = datetime.now(KST)
        target_year = year if year is not None else now_kst.year
        target_month = month if month is not None else now_kst.month
        
        def _task():
            service = _build_service()
            
            # MaterialOrder 시트 전체 조회
            resp = service.spreadsheets().values().get(
                spreadsheetId=SPREADSHEET_KEY,
                range="MaterialOrder!A:D"  # 날짜시간, 이름, 발주내용, 발주완료 처리시간
            ).execute()
            
            all_values = resp.get("values", [])
            if len(all_values) < 2:  # 헤더만 있거나 없음
                return []
            
            # 헤더 제외
            orders = []
            target_month_str = f"{target_year}-{target_month:02d}"
            
            logging.info(f"get_pending_material_orders: target_month_str={target_month_str}, year={target_year}, month={target_month}")
            
            for idx, row in enumerate(all_values[1:], start=2):  # 2행부터 (헤더 제외)
                if len(row) < 3:
                    continue
                
                date_str = row[0] if len(row) > 0 else ""
                name = row[1] if len(row) > 1 else ""
                content = row[2] if len(row) > 2 else ""
                completed_time = row[3] if len(row) > 3 else ""
                
                # 날짜 문자열에서 날짜 부분만 추출 (예: "2025-12-17 1:01:03" -> "2025-12-17")
                date_part = date_str.split()[0] if date_str and " " in date_str else date_str
                
                # 발주완료 처리시간이 비어있고, 해당 월의 데이터인 경우만
                if not completed_time and date_part.startswith(target_month_str):
                    logging.info(f"Found pending order: row={idx}, date={date_str}, name={name}, content={content}")
                    orders.append({
                        "row_index": idx,
                        "date": date_str,
                        "name": name,
                        "content": content
                    })
            
            logging.info(f"get_pending_material_orders: found {len(orders)} pending orders")
            
            return orders
        
        orders = execute_with_retry(_task)
        return True, orders
    except Exception as e:
        return False, f"발주 목록 조회 오류: {str(e)}"


def mark_orders_completed(row_indices: List[int]):
    """발주 완료 처리 (발주완료 처리시간 업데이트)
    
    Args:
        row_indices: 완료 처리할 행 번호 리스트 (시트의 실제 행 번호, 1-based)
    
    Returns:
        (success: bool, message: str)
    """
    try:
        def _task():
            service = _build_service()
            now_kst = datetime.now(KST)
            completed_time = now_kst.strftime("%Y-%m-%d %H:%M:%S")
            
            # 각 행의 D열에 처리시간 업데이트
            for row_idx in row_indices:
                range_name = f"MaterialOrder!D{row_idx}"
                body = {
                    "values": [[completed_time]]
                }
                service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_KEY,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()
            
            return True
        
        execute_with_retry(_task)
        return True, f"{len(row_indices)}건의 발주가 완료 처리되었습니다."
    except Exception as e:
        return False, f"발주 완료 처리 오류: {str(e)}"


def _build_drive_service():
    """Google Drive API 서비스 생성"""
    json_str = os.environ.get("GCF_CREDENTIALS")
    if not json_str:
        raise ValueError("GCF_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
    
    credentials_dict = json.loads(json_str)
    creds = service_account.Credentials.from_service_account_info(
        credentials_dict,
        scopes=DRIVE_SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def create_site_photo_folder(site_address: str):
    """
    현장 사진 폴더를 Google Drive에 생성합니다.
    
    Args:
        site_address: 현장 주소
    
    Returns:
        (success: bool, folder_id: str or error_message: str, folder_url: str)
    """
    try:
        def _task():
            service = _build_drive_service()
            service = _build_drive_service()
            now_kst = datetime.now(KST)
            # 폴더명: YYYY.MM.DD 건물명 (점 제거, 공백으로 구분)
            date_str = now_kst.strftime("%Y.%m.%d")
            # 주소에서 건물명 추출 (예: "서울시 강남구 테헤란로 123" -> "테헤란로 123")
            address_parts = site_address.split() if site_address else []
            building_name = " ".join(address_parts[-2:]) if len(address_parts) >= 2 else site_address
            folder_name = f"{date_str} {building_name}"
            
            # 부모 폴더 ID (환경 변수에서 가져오거나 하드코딩)
            parent_folder_id = os.environ.get("GOOGLE_DRIVE_PARENT_FOLDER_ID", "")
            if not parent_folder_id:
                return None, "GOOGLE_DRIVE_PARENT_FOLDER_ID 환경 변수가 설정되지 않았습니다.", ""
            
            # 폴더 생성
            file_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_folder_id]
            }
            
            folder = service.files().create(
                body=file_metadata,
                fields="id, name, webViewLink"
            ).execute()
            
            folder_id = folder.get("id")
            folder_url = folder.get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")
            
            return folder_id, folder_url
        
        folder_id, folder_url = execute_with_retry(_task)
        if folder_id:
            return True, folder_id, folder_url
        else:
            return False, folder_url, ""  # folder_url이 에러 메시지
    except Exception as e:
        logging.exception(f"Error creating site photo folder: {e}")
        return False, f"폴더 생성 오류: {str(e)}", ""
