import json
import logging
import os
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode

import requests
import pytz
from slack_sdk import WebClient
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import sheets_handler

KST = pytz.timezone('Asia/Seoul')

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
slack_client = WebClient(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None
SITE_ADDRESS = os.environ.get("SITE_ADDRESS", "")
GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "slack-480914")
TASKS_LOCATION = os.environ.get("TASKS_LOCATION", "asia-northeast3")
OPEN_TMAP_BASE_URL = f"https://{TASKS_LOCATION}-{GCP_PROJECT}.cloudfunctions.net/open_tmap_handler"
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")


def _address_to_grid(address: str):
    """주소를 기상청 격자 좌표(nx, ny)로 변환합니다.
    
    Args:
        address: 주소 문자열 (예: "서울시 강남구 테헤란로 123")
    
    Returns:
        tuple: (nx, ny) 격자 좌표. 실패 시 None, None
    """
    if not address:
        return None, None
    
    # 주소에서 주요 지역명 추출하여 좌표 매핑
    # 주요 서울/경기 지역 좌표 (기상청 격자 좌표)
    region_coords = {
        # 서울
        "서울": (60, 127), "강남": (61, 126), "강북": (60, 128), "강동": (62, 126),
        "강서": (58, 126), "관악": (59, 125), "광진": (62, 126), "구로": (58, 125),
        "금천": (58, 125), "노원": (61, 129), "도봉": (61, 129), "동대문": (61, 127),
        "동작": (59, 125), "마포": (59, 126), "서대문": (59, 127), "서초": (61, 125),
        "성동": (61, 127), "성북": (61, 128), "송파": (62, 126), "양천": (58, 126),
        "영등포": (58, 125), "용산": (60, 126), "은평": (59, 128), "종로": (60, 127),
        "중구": (60, 127), "중랑": (62, 128),
        # 경기
        "수원": (60, 121), "성남": (62, 123), "고양": (57, 129), "용인": (64, 119),
        "부천": (56, 125), "안산": (58, 121), "안양": (59, 123), "평택": (58, 114),
        "시흥": (57, 123), "김포": (55, 128), "의정부": (61, 130), "광명": (58, 125),
        "광주": (65, 123), "군포": (59, 122), "하남": (64, 126), "오산": (62, 118),
        "이천": (68, 121), "안성": (65, 115), "화성": (57, 119), "양평": (69, 125),
        "구리": (62, 127), "남양주": (64, 128), "파주": (56, 131), "의왕": (60, 122),
        "과천": (60, 124), "광교": (61, 121), "테헤란로": (61, 126),
    }
    
    # 주소에서 지역명 매칭
    address_lower = address.lower()
    for region, coords in region_coords.items():
        if region in address or region.lower() in address_lower:
            return coords
    
    # 매칭 실패 시 서울 기본값
    return (60, 127)


def _get_weather_forecast(site_address: str = None):
    """기상청 단기예보 API를 사용하여 오후 시간대의 날씨 정보를 가져옵니다.
    
    Args:
        site_address: 현장 주소. 제공 시 해당 지역의 날씨를 조회합니다.
    
    Returns:
        tuple: (강수확률(int), 강수형태(str), 에러 메시지 또는 None)
        예: (70, "비", None) 또는 (None, None, "날씨 정보를 가져올 수 없습니다")
    """
    if not WEATHER_API_KEY:
        logging.warning("WEATHER_API_KEY가 설정되지 않았습니다.")
        return None, None, None
    
    try:
        # KST 시간 기준
        kst = datetime.now(KST)
        today = kst.strftime("%Y%m%d")
        current_hour = kst.hour
        
        # 단기예보 발표시각: 02, 05, 08, 11, 14, 17, 20, 23시
        # 현재 시간 이전의 가장 최근 발표시각 사용
        base_times = [23, 20, 17, 14, 11, 8, 5, 2]
        base_time_hour = None
        for bt in base_times:
            if current_hour >= bt or (bt == 23 and current_hour < 2):
                base_time_hour = bt
                break
        
        if base_time_hour is None:
            base_time_hour = 23  # 기본값 (전날 23시 발표)
            # 전날로 계산
            yesterday = (kst - timedelta(days=1)).strftime("%Y%m%d")
            base_date = yesterday
        else:
            base_date = today
        
        base_time = f"{base_time_hour:02d}00"
        
        # 현장 주소에서 격자 좌표 계산
        if site_address:
            nx, ny = _address_to_grid(site_address)
            if nx is None:
                logging.warning(f"주소에서 좌표를 찾을 수 없음: {site_address}, 서울 기본값 사용")
                nx, ny = 60, 127
            else:
                logging.info(f"현장 주소 '{site_address}' -> 격자 좌표 ({nx}, {ny})")
        else:
            # 서울 좌표 (기본값)
            nx = 60
            ny = 127
        
        # API 호출
        api_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
        params = {
            "serviceKey": WEATHER_API_KEY,
            "numOfRows": 100,
            "pageNo": 1,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # 응답 확인
        if data.get("response", {}).get("header", {}).get("resultCode") != "00":
            error_msg = data.get("response", {}).get("header", {}).get("resultMsg", "알 수 없는 오류")
            logging.warning(f"날씨 API 오류: {error_msg}")
            return None, None, None
        
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not items:
            logging.warning("날씨 데이터가 없습니다.")
            return None, None, None
        
        # 오후 시간대(12시~18시)의 강수확률과 강수형태 조회
        pop_values = []  # 강수확률 리스트
        pty_values = []  # 강수형태 리스트
        
        forecast_date = kst.strftime("%Y%m%d")
        for item in items:
            fcst_date = item.get("fcstDate", "")
            fcst_time = item.get("fcstTime", "")
            category = item.get("category", "")
            fcst_value = item.get("fcstValue", "")
            
            # 오늘 날짜이고, 오후 시간대(12시~18시)만 필터링
            if fcst_date == forecast_date and fcst_time[:2] in ["12", "13", "14", "15", "16", "17", "18"]:
                if category == "POP":  # 강수확률
                    try:
                        pop_values.append(int(fcst_value))
                    except (ValueError, TypeError):
                        pass
                elif category == "PTY":  # 강수형태
                    try:
                        pty_code = int(fcst_value)
                        pty_map = {
                            0: "없음",
                            1: "비",
                            2: "비/눈",
                            3: "눈",
                            4: "소나기"
                        }
                        pty_values.append(pty_map.get(pty_code, "없음"))
                    except (ValueError, TypeError):
                        pass
        
        # 오후 시간대의 평균 강수확률 계산 (또는 최대값 사용)
        if pop_values:
            avg_pop = sum(pop_values) // len(pop_values)
            max_pop = max(pop_values)
            # 최대값과 평균 중 더 큰 값 사용 (보수적으로)
            pop = max(avg_pop, max_pop)
        else:
            pop = None
        
        # 강수형태 확인 (비가 있는지)
        pty = "없음"
        if pty_values:
            if any(p != "없음" for p in pty_values):
                # 비 관련 형태가 하나라도 있으면 "비"로 표시
                if any("비" in p for p in pty_values):
                    pty = "비"
                elif any("눈" in p for p in pty_values):
                    pty = "눈"
        
        return pop, pty, None
        
    except requests.exceptions.RequestException as e:
        logging.error(f"날씨 API 요청 오류: {e}")
        return None, None, None
    except Exception as e:
        logging.error(f"날씨 정보 파싱 오류: {e}")
        return None, None, None


def _get_today_site_addresses():
    """오늘 날짜의 구글 캘린더 일정에서 모든 일정의 주소(location)를 가져옵니다.
    
    Returns:
        list: 현장 주소 리스트. 일정이 없거나 주소가 없으면 SITE_ADDRESS를 포함한 리스트 반환.
    """
    if not GOOGLE_CALENDAR_ID:
        logging.warning("GOOGLE_CALENDAR_ID not set; using SITE_ADDRESS")
        return [SITE_ADDRESS] if SITE_ADDRESS else []
    
    try:
        # 서비스 계정 인증
        json_str = os.environ.get("GCF_CREDENTIALS")
        if not json_str:
            logging.warning("GCF_CREDENTIALS not set; using SITE_ADDRESS")
            return [SITE_ADDRESS] if SITE_ADDRESS else []
        
        credentials_dict = json.loads(json_str)
        creds = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"]
        )
        
        # Calendar API 서비스 생성
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        
        # 오늘 날짜의 시작/끝 시간 계산 (KST 기준)
        now = datetime.now(sheets_handler.KST)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # ISO 8601 형식으로 변환
        time_min = start_of_day.isoformat()
        time_max = end_of_day.isoformat()
        
        # 오늘 일정 조회
        events_result = (
            service.events()
            .list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        
        events = events_result.get("items", [])
        
        if not events:
            logging.info("No events found for today; using SITE_ADDRESS")
            return [SITE_ADDRESS] if SITE_ADDRESS else []
        
        # 모든 일정의 location 가져오기
        addresses = []
        for event in events:
            location = event.get("location", "").strip()
            if location:
                addresses.append(location)
        
        if addresses:
            logging.info(f"Found {len(addresses)} site address(es) from calendar: {addresses}")
            return addresses
        else:
            logging.info("No location in events; using SITE_ADDRESS")
            return [SITE_ADDRESS] if SITE_ADDRESS else []
            
    except HttpError as e:
        logging.error(f"Google Calendar API error: {e}")
        return [SITE_ADDRESS] if SITE_ADDRESS else []
    except Exception as e:
        logging.exception(f"Error getting today's site addresses: {e}")
        return [SITE_ADDRESS] if SITE_ADDRESS else []




def worker(request):
    """Cloud Tasks에서 호출하는 워커 엔드포인트.

    payload 예시:
    {
        "action": "check_in" | "check_out",
        "user_id": "...",
        "user_name": "...",
        "channel_id": "..."
    }
    """
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    user_id = data.get("user_id")
    user_name = data.get("user_name")
    channel_id = data.get("channel_id") or user_id

    logging.info("worker start: action=%s user=%s channel=%s", action, user_name, channel_id)

    try:
        if action == "check_in":
            _handle_check_in(user_id, user_name, channel_id)
        elif action == "check_out":
            _handle_check_out(user_id, user_name, channel_id)
        else:
            logging.warning("Unknown action in task payload: %s", action)
        return ("", 200)
    except Exception as e:
        logging.exception("Error in worker: %s", e)
        return ("", 500)


def _handle_check_in(user_id: str, user_name: str, channel_id: str):
    """실제 출근 기록 및 게임화 메시지 전송.

    user_id (Slack_ID)를 우선 사용하여 UserMaster 조회 후,
    한글 이름으로 치환해서 사용한다.
    """
    # Slack_ID (user_id)를 우선 사용하여 UserMaster 조회
    user_info = sheets_handler.get_user_info(user_id) if user_id else None
    # Slack_ID로 못 찾으면 user_name(핸들)로 재시도
    if not user_info and user_name:
        user_info = sheets_handler.get_user_info(user_name)

    # 시트 기록용 이름 (항상 한글 이름 사용을 시도)
    if user_info and user_info.get("name"):
        name_for_log = user_info["name"]
    else:
        # user_name이 비어있으면 Slack 멘션 형태로 fallback
        name_for_log = user_name or f"<@{user_id}>"

    # 화면 표시용 이름 (한글 이름 → 핸들 → 멘션 순으로 우선)
    if user_info and user_info.get("name"):
        display_name = user_info["name"]
    elif user_name:
        display_name = user_name
    else:
        display_name = f"<@{user_id}>"

    prev_total_days = sheets_handler.get_total_work_days(name_for_log)

    # 오늘 일정에서 현장 주소 가져오기 (출근 기록에 포함하기 위해 먼저 조회)
    site_addresses = _get_today_site_addresses()
    # 출근 기록에는 첫 번째 주소만 사용 (기존 호환성 유지)
    site_address = site_addresses[0] if site_addresses else SITE_ADDRESS

    # 출근 기록 (비고란에 현장 주소 포함)
    success, msg = sheets_handler.record_check_in(name_for_log, site_address)
    if not success:
        _send_slack(
            channel_id,
            f"❌ **출근 기록 실패:** {msg}",
        )
        return

    now = datetime.now(sheets_handler.KST)
    current_year = now.year
    current_month = now.month

    # 출근 기록 후 총 근무일수 계산
    # 출근은 0.5일의 개념이므로, 출근만 한 상태에서는 완전한 근무일이 아닙니다.
    # 따라서 get_total_work_days로 조회 (출근+퇴근이 모두 있는 날만 카운트)
    current_total_days = sheets_handler.get_total_work_days(name_for_log)
    current_level = sheets_handler.calculate_level(current_total_days)
    monthly_count = sheets_handler.get_monthly_work_count(
        name_for_log, current_year, current_month
    )
    
    # 출근 시에는 레벨업 체크를 하지 않음 (출근은 0.5일, 퇴근해야 1일 완성)
    # 레벨업 및 각성 단계 체크는 퇴근 시에만 수행
    
    # 새로운 정보 조회
    awakening_emoji, awakening_num = sheets_handler.get_awakening_stage_with_number(current_total_days)
    awakening_stage_text = f"{awakening_emoji} [각성 {awakening_num}단계]" if awakening_num > 0 else "🟤 [초보]"
    user_title = sheets_handler.get_user_title(current_total_days)
    days_until_settlement = sheets_handler.get_days_until_settlement()
    
    # 이번 달 총 급여 계산
    base_pay, _, _ = sheets_handler.calculate_monthly_payroll(name_for_log, current_year, current_month)
    commission = sheets_handler.get_commission(name_for_log, current_year, current_month)
    transportation = sheets_handler.calculate_transportation_allowance(monthly_count)
    monthly_total_pay = base_pay + commission + transportation
    
    # 날씨 정보 조회 (첫 번째 현장 주소 기준)
    pop, pty, weather_error = _get_weather_forecast(site_address)
    
    # 메시지 구성 (새로운 형식)
    parts = [
        f"✅ [{name_for_log}님, 출근 기록 완료!]",
        "오늘도 활기차게 시동 걸어볼까요? 🚛",
        "",
    ]
    
    # 날씨 정보 추가
    if pop is not None and pop > 0:
        weather_emoji = "☔️" if pty == "비" else "🌨️" if pty == "눈" else "🌦️"
        parts.append(f"{weather_emoji} 오후 예보 (강수확률 {pop}%)")
        if pty != "없음":
            parts.append(f"💡 {pty} 올 수 있으니 조심하세요! 우산 챙기셨나요?")
        else:
            parts.append(f"💡 가볍게 스쳐갈 수 있어요. 우산 준비하세요!")
    elif pop is not None and pop == 0:
        parts.append("🌤️ 오후 날씨 맑음 예보")
        parts.append("☀️ 좋은 날씨네요! 안전 운전하세요!")
    else:
        # 날씨 정보를 가져오지 못한 경우
        parts.append("🌤️ 날씨 정보 조회 중...")
    
    parts.append("──────────────")
    parts.append("")
    
    # 현장 주소 (여러 개인 경우 각각 표시)
    if site_addresses:
        if len(site_addresses) == 1:
            parts.append("📍 오늘의 현장")
            parts.append(f":: {site_addresses[0]}")
        else:
            for idx, addr in enumerate(site_addresses, 1):
                if idx == 1:
                    parts.append("📍 첫번째 현장")
                elif idx == 2:
                    parts.append("📍 두번째 현장")
                else:
                    parts.append(f"📍 {idx}번째 현장")
                parts.append(f":: {addr}")
        parts.append("")
    
    parts.append("──────────────")
    parts.append("")
    parts.append(f"📊 {current_month}월의 기록")
    parts.append(f" • 현황: {monthly_count}번째 출동 | 정산일 D-{days_until_settlement}")
    parts.append(f" • 등급: {awakening_stage_text} (Lv.{current_level})")
    parts.append(f" • 칭호: {user_title}")
    parts.append("")
    parts.append("──────────────")
    parts.append("")
    parts.append('"오늘도 안전하게, 돈 많이 벌어오세요! 출발! 💸"')

    _send_slack_with_tmap(channel_id, "\n".join(parts), site_addresses)


def _handle_check_out(user_id: str, user_name: str, channel_id: str):
    """실제 퇴근 기록 및 게임화 메시지 전송."""
    # Slack_ID (user_id)를 우선 사용하여 UserMaster 조회
    user_info = sheets_handler.get_user_info(user_id) if user_id else None
    # Slack_ID로 못 찾으면 user_name(핸들)로 재시도
    if not user_info and user_name:
        user_info = sheets_handler.get_user_info(user_name)
    name_for_log = user_info["name"] if user_info else user_name

    prev_total_days = sheets_handler.get_total_work_days(name_for_log)
    
    # 주소 정보는 나중에 사용하므로 user_info 유지

    success, msg = sheets_handler.record_check_out(name_for_log)
    if not success:
        _send_slack(
            channel_id,
            f"❌ **퇴근 기록 실패:** {msg}",
        )
        return

    now = datetime.now(sheets_handler.KST)
    current_year = now.year
    current_month = now.month

    current_total_days = sheets_handler.get_total_work_days(name_for_log)
    
    # 퇴근 시 레벨업 및 각성 단계 체크 (퇴근해야 1일 완성)
    level_up, new_level, old_level = sheets_handler.check_level_up(current_total_days, prev_total_days)
    awakening_cutscene, cutscene_msg = sheets_handler.get_awakening_cutscene(current_total_days, prev_total_days)
    
    # 오늘 일급 계산 (퇴근 전 총 근무일수 기준으로 일당 계산)
    user_type = user_info.get("user_type", "정규직") if user_info else "정규직"
    daily_pay = sheets_handler.calculate_daily_pay(prev_total_days, user_type)
    today_pay = daily_pay
    
    # 각성 경험치 진행률 계산
    awakening_progress_bar, awakening_percentage, days_to_next_awakening, _ = sheets_handler.get_awakening_progress(current_total_days)
    
    # 레벨업 또는 각성 단계 달성 시 DM 발송 (퇴근 시에만)
    if level_up:
        user_title = sheets_handler.get_user_title(current_total_days)
        level_up_msg = f"🎉 **레벨업!**\n\n"
        level_up_msg += f"Lv.{old_level} → Lv.{new_level}\n\n"
        level_up_msg += f"🎖 **새로운 칭호:** {user_title}\n\n"
        level_up_msg += f"현재 총 근무일수: {current_total_days}일"
        _send_slack(user_id, level_up_msg)
    
    if awakening_cutscene:
        _send_slack(user_id, cutscene_msg)
    
    parts = [
        f"✅ [{name_for_log}님, 퇴근 기록 완료!]",
        "오늘 흘린 땀방울이 멋진 결과로 쌓였습니다. 👏",
        "",
        "──────────────",
        "",
        f"💰일급 {today_pay:,}원 획득!",
        "",
        "──────────────",
        "",
        "⚔️ 각성 경험치",
        f"• 총 근무일수: {current_total_days}일째 중",
        f"• 경험치: {awakening_progress_bar} ({awakening_percentage}%)",
        f"(다음 각성까지 {days_to_next_awakening}일 남음)",
        "",
        "──────────────",
        "",
        f'"오늘 저녁은 맛있는 거 드세요!\n🍖 내일도 {name_for_log}님의 안전을 기원합니다. 퇴근!"',
    ]

    # 사용자 주소 가져오기 (귀환스킬발동용)
    user_address = user_info.get("address", "") if user_info else ""
    
    # 퇴근 메시지에 버튼 추가
    _send_slack_with_buttons(
        channel_id, 
        "\n".join(parts),
        home_address=user_address
    )


def _send_slack(channel: str, text: str):
    """슬랙 메시지 전송."""
    if not slack_client:
        logging.warning("SLACK_BOT_TOKEN not set; skip sending Slack message")
        return
    try:
        slack_client.chat_postMessage(channel=channel, text=text)
        logging.info("Slack message sent to %s", channel)
    except Exception as e:
        logging.exception("Failed to send Slack message to %s: %s", channel, e)


def _send_slack_with_buttons(channel: str, text: str, home_address: str = None):
    """버튼이 포함된 슬랙 메시지 전송 (퇴근 메시지용).
    
    Args:
        channel: Slack 채널 ID
        text: 메시지 텍스트
        home_address: 집 주소 (귀환스킬발동용)
    """
    if not slack_client:
        logging.warning("SLACK_BOT_TOKEN not set; skip sending Slack message")
        return
    
    try:
        # Block Kit으로 메시지 구성
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
        
        # 버튼 추가
        buttons = []
        
        # 1. 귀환스킬발동 버튼 (집주소로 t-map)
        if home_address:
            encoded_address = quote(home_address)
            tmap_button_url = f"{OPEN_TMAP_BASE_URL}?addr={encoded_address}"
            buttons.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "🏠 귀환스킬발동"
                },
                "url": tmap_button_url,
                "style": "primary"
            })
        
        # 2. 자재사용대장 버튼
        buttons.append({
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "📋 자재사용대장"
            },
            "action_id": "open_material_log",
            "value": "start"
        })
        
        # 3. 현장사진 업로드 버튼 (폴더 생성부터 시작)
        buttons.append({
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "📷 현장사진 업로드"
            },
            "action_id": "create_photo_folder",
            "value": "create"
        })
        
        if buttons:
            blocks.append({
                "type": "actions",
                "elements": buttons
            })
        
        # WebClient를 사용하여 메시지 전송
        slack_client.chat_postMessage(
            channel=channel,
            text=text,
            blocks=blocks
        )
        logging.info("Slack message with buttons sent to %s", channel)
    except Exception as e:
        logging.exception("Failed to send Slack message with buttons to %s: %s", channel, e)


def _send_slack_with_tmap(channel: str, text: str, site_addresses=None):
    """T-map 버튼이 포함된 슬랙 메시지 전송 (출근 메시지용).
    
    Args:
        channel: Slack 채널 ID
        text: 메시지 텍스트
        site_addresses: 현장 주소 리스트 (없으면 SITE_ADDRESS 환경 변수 사용)
    """
    if not slack_client:
        logging.warning("SLACK_BOT_TOKEN not set; skip sending Slack message")
        return
    
    try:
        # 현장 주소 결정
        if site_addresses is None:
            addresses = [SITE_ADDRESS] if SITE_ADDRESS else []
        elif isinstance(site_addresses, str):
            # 기존 호환성을 위해 문자열도 리스트로 변환
            addresses = [site_addresses] if site_addresses.strip() else []
        else:
            addresses = [addr.strip() for addr in site_addresses if addr and addr.strip()]
        
        # Block Kit으로 메시지 구성
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            }
        ]
        
        # T-map 버튼 추가
        buttons = []
        if len(addresses) == 1:
            # 현장이 1개인 경우
            encoded_address = quote(addresses[0])
            tmap_button_url = f"{OPEN_TMAP_BASE_URL}?addr={encoded_address}"
            buttons.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "🚩 오늘 현장 T-map 열기"
                },
                "url": tmap_button_url,
                "style": "primary"
            })
        elif len(addresses) >= 2:
            # 현장이 2개 이상인 경우
            for idx, address in enumerate(addresses[:2], 1):  # 최대 2개만
                encoded_address = quote(address)
                tmap_button_url = f"{OPEN_TMAP_BASE_URL}?addr={encoded_address}"
                if idx == 1:
                    button_text = "🚩 첫번째 현장 T-map 열기"
                else:
                    button_text = "🚩 두번째 현장 T-map 열기"
                buttons.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": button_text
                    },
                    "url": tmap_button_url,
                    "style": "primary"
                })
        
        # 자재사용대장 버튼은 제거 (출근 메시지에는 T-map만 표시)
        
        if buttons:
            blocks.append({
                "type": "actions",
                "elements": buttons
            })
        
        # WebClient를 사용하여 메시지 전송
        slack_client.chat_postMessage(
            channel=channel,
            text=text,
            blocks=blocks
        )
        logging.info("Slack message with T-map button(s) sent to %s", channel)
    except Exception as e:
        logging.exception("Failed to send Slack message with T-map to %s: %s", channel, e)


