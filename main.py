# main.py (게임화 출퇴근 및 급여 정산 시스템)

import os
import logging
import json
import textwrap
import re
import random
from datetime import datetime
from urllib.parse import quote

import requests

# Google Cloud Tasks (선택적 - Render에서는 사용 안 함)
try:
    from google.cloud import tasks_v2
    TASKS_AVAILABLE = True
except ImportError:
    tasks_v2 = None
    TASKS_AVAILABLE = False
    logging.warning("google-cloud-tasks not available. Cloud Tasks features disabled.")

# GCF 표준 라이브러리 (선택적 - Render에서는 사용 안 함)
try:
    import functions_framework
    FUNCTIONS_FRAMEWORK_AVAILABLE = True
except ImportError:
    functions_framework = None
    FUNCTIONS_FRAMEWORK_AVAILABLE = False

from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

# 프로젝트 내 다른 파일 import
import sheets_handler 
from config import SLACK_BOT_TOKEN 
import worker_main
from datetime import timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# 관리자 Slack ID (환경 변수에서 가져오거나 하드코딩)
ADMIN_SLACK_IDS = os.environ.get("ADMIN_SLACK_IDS", "").split(",") if os.environ.get("ADMIN_SLACK_IDS") else []

# Cloud Tasks / Worker 설정 (Render에서는 직접 호출 사용)
PROJECT_ID = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
TASKS_LOCATION = os.environ.get("TASKS_LOCATION", "asia-northeast3")
TASKS_QUEUE_ID = os.environ.get("TASKS_QUEUE_ID", "attendance-queue")
# Render 환경에서는 RENDER_SERVICE_URL을 사용, 없으면 WORKER_URL 환경 변수 사용
RENDER_SERVICE_URL = os.environ.get("RENDER_SERVICE_URL", "")
WORKER_URL = os.environ.get("WORKER_URL") or (f"{RENDER_SERVICE_URL.rstrip('/')}/worker" if RENDER_SERVICE_URL else None)

# Cloud Tasks 클라이언트 (선택적)
if TASKS_AVAILABLE and PROJECT_ID:
    try:
        tasks_client = tasks_v2.CloudTasksClient()
        QUEUE_PATH = tasks_client.queue_path(PROJECT_ID, TASKS_LOCATION, TASKS_QUEUE_ID)
    except Exception as e:
        logging.warning(f"Failed to initialize Cloud Tasks client: {e}")
        tasks_client = None
        QUEUE_PATH = None
else:
    tasks_client = None
    QUEUE_PATH = None


# 1. Slack 앱 초기화
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
    # 모달/인터랙션 안정성을 위해 Bolt에게 응답을 먼저 맡긴다.
    process_before_response=True,
)
handler = SlackRequestHandler(slack_app)

# ------------------------------------------------
# 유틸리티 함수
# ------------------------------------------------

def _get_today_site_address():
    """오늘 날짜의 Google Calendar 일정에서 현장 주소를 가져옵니다.
    
    Returns:
        str: 현장 주소. 일정이 없거나 주소가 없으면 SITE_ADDRESS 환경 변수 값 반환.
    """
    site_address = os.environ.get("SITE_ADDRESS", "")
    google_calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "")
    
    if not google_calendar_id:
        logging.info("GOOGLE_CALENDAR_ID not set; using SITE_ADDRESS")
        return site_address
    
    try:
        # 서비스 계정 인증
        json_str = os.environ.get("GCF_CREDENTIALS")
        if not json_str:
            logging.warning("GCF_CREDENTIALS not set; using SITE_ADDRESS")
            return site_address
        
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
                calendarId=google_calendar_id,
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
            return site_address
        
        # 첫 번째 일정의 location 가져오기
        first_event = events[0]
        location = first_event.get("location", "").strip()
        
        if location:
            logging.info(f"Found today's site address from calendar: {location}")
            return location
        else:
            logging.info("First event has no location; using SITE_ADDRESS")
            return site_address
            
    except HttpError as e:
        logging.error(f"Google Calendar API error: {e}")
        return site_address
    except Exception as e:
        logging.exception(f"Error getting today's site address: {e}")
        return site_address


# ------------------------------------------------
# View 핸들러 (모든 action 핸들러보다 먼저 등록 - 중요!)
# ------------------------------------------------

@slack_app.view("material_quantity_submit")
def handle_material_quantity_submit(ack, body, client):
    """사용량 입력 제출 → 기록 후 다음 방으로"""
    logging.info("material_quantity_submit view received: user=%s, metadata=%s", 
                 body["user"]["id"], body["view"].get("private_metadata"))
    ack()
    
    user_id = body["user"]["id"]
    values = body["view"]["state"]["values"]
    private_metadata = body["view"]["private_metadata"]
    
    # 사용량 가져오기
    quantity_str = values["quantity_input"]["quantity"]["value"].strip()
    try:
        quantity = float(quantity_str)
        if quantity <= 0:
            raise ValueError("사용량은 0보다 커야 합니다.")
    except ValueError as e:
        # 모달 대신 DM으로 오류 안내
        client.chat_postMessage(
            channel=user_id,
            text=f"❌ 자재사용대장: 올바른 숫자를 입력해주세요. ({e})",
        )
        return
    
    # private_metadata 파싱
    metadata_parts = private_metadata.split("|")
    room = metadata_parts[0]
    color = metadata_parts[1]
    room_index = int(metadata_parts[2])
    selected_rooms = metadata_parts[3].split(",") if metadata_parts[3] else []
    
    # 사용자 이름 가져오기
    user_name = body["user"]["name"]
    user_info = sheets_handler.get_user_info(body["user"]["id"])
    if user_info:
        user_name = user_info["name"]
    
    # 스프레드시트에 기록
    success, message = sheets_handler.record_material_usage(user_name, room, color, quantity)
    
    if not success:
        client.chat_postMessage(
            channel=user_id,
            text=f"❌ 자재사용대장 기록 실패: {message}",
        )
        return
    
    # 다음 방으로 이동
    next_room_index = room_index + 1
    completed_rooms = selected_rooms[:next_room_index]
    
    if next_room_index < len(selected_rooms):
        # 현재 방 기록 완료 안내를 DM으로 전송 (새로운 형식)
        room_emoji = get_room_emoji(room)
        completion_text = (
            f"──────────────\n"
            f"👌 **입력 확인!**\n"
            f"──────────────\n\n"
            f"깔끔하게 장부에 적어두었습니다.\n\n"
            f"──────────────\n"
            f"＊ **기록 내용**\n\n"
            f"1. {room_emoji} {room} [ {color}번 색상 ] -  {quantity}g 사용"
        )
        client.chat_postMessage(
            channel=user_id,
            text="입력 확인",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": completion_text
                    }
                }
            ]
        )

        # 다음 방 색상 선택용 버튼을 DM으로 전송
        next_room = selected_rooms[next_room_index]
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"📋 **자재사용대장**\n\n"
                        f"✅ 완료: {', '.join(completed_rooms)}\n\n"
                        f"다음 방: **{next_room}**\n색상을 선택해주세요."
                    )
                }
            }
        ]

        color_buttons = []
        for c in MATERIAL_COLORS:
            if c == "기타":
                # 기타는 별도 액션으로 처리 (정규식 핸들러와 충돌 방지)
                color_buttons.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "기타"
                    },
                    "action_id": "select_custom_color",
                    "value": f"{next_room}|custom|{next_room_index}|{','.join(selected_rooms)}"
                })
            else:
                color_buttons.append({
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": c
                    },
                    "action_id": f"select_color_{c}",
                    "value": f"{next_room}|{c}|{next_room_index}|{','.join(selected_rooms)}"
                })

        for i in range(0, len(color_buttons), 2):
            row_buttons = color_buttons[i:i+2]
            blocks.append({
                "type": "actions",
                "elements": row_buttons
            })

        client.chat_postMessage(
            channel=body["user"]["id"],  # DM으로 전송
            text=f"다음 방: {next_room}",
            blocks=blocks,
        )
    else:
        # 마지막 방까지 모두 완료 → DM으로 최종 안내 (새로운 형식)
        room_emoji = get_room_emoji(room)
        completion_text = (
            f"──────────────\n"
            f"👌 **입력 확인!**\n"
            f"──────────────\n\n"
            f"깔끔하게 장부에 적어두었습니다.\n\n"
            f"──────────────\n"
            f"＊ **기록 내용**\n\n"
            f"1. {room_emoji} {room} [ {color}번 색상 ] -  {quantity}g 사용"
        )
        client.chat_postMessage(
            channel=user_id,
            text="입력 확인",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": completion_text
                    }
                }
            ]
        )


# ------------------------------------------------
# Cloud Tasks 헬퍼
# ------------------------------------------------


def enqueue_task(action: str, body: dict):
    """출근/퇴근 처리를 비동기로 처리하기 위한 작업 큐 등록.
    
    Render에서는 Cloud Tasks 대신 직접 HTTP 요청으로 worker를 호출합니다.
    """
    user_id = body.get("user_id")
    user_name = body.get("user_name")
    channel_id = body.get("channel_id", user_id)

    payload = {
        "action": action,
        "user_id": user_id,
        "user_name": user_name,
        "channel_id": channel_id,
    }

    # Render 환경에서는 직접 HTTP 요청으로 worker 호출
    if WORKER_URL:
        try:
            import requests
            response = requests.post(
                WORKER_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            logging.info(
                "Worker called directly: action=%s user=%s channel=%s status=%s",
                action, user_name, channel_id, response.status_code
            )
            return
        except Exception as e:
            logging.error(f"Failed to call worker directly: {e}")
            # 폴백: 동기 처리
            pass
    
    # Cloud Tasks 사용 (GCP 환경에서만)
    if TASKS_AVAILABLE and tasks_client and QUEUE_PATH:
        try:
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": WORKER_URL,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload).encode("utf-8"),
                }
            }
            tasks_client.create_task(parent=QUEUE_PATH, task=task)
            logging.info(
                "Enqueued task: action=%s user=%s channel=%s", action, user_name, channel_id
            )
            return
        except Exception as e:
            logging.warning(f"Failed to enqueue task via Cloud Tasks: {e}")
    
    # 최종 폴백: 동기 처리 (worker_main 직접 호출)
    logging.warning("Using synchronous fallback for action=%s", action)
    try:
        class MockRequest:
            def get_json(self, silent=False):
                return payload
        worker_main.worker(MockRequest())
    except Exception as e:
        logging.error(f"Failed to process synchronously: {e}")
        # 최후의 수단: 기본 기록만 수행
        user_name = body.get("user_name")
        if action == "check_in":
            sheets_handler.record_check_in(user_name)
        elif action == "check_out":
            sheets_handler.record_check_out(user_name)


# ------------------------------------------------
# 2. /hello 명령어 핸들러 (연결 테스트용)
# ------------------------------------------------
@slack_app.command("/hello")
def handle_hello(ack, body, client):
    ack("GCF 서버에 도달했습니다! (인증 테스트 중...)")
    
    user_id = body['user_id']
    try:
        # Sheets 핸들러를 사용하여 연결 테스트 (실제 Sheets 기록은 하지 않음)
        service = sheets_handler._build_service()
        logging.info("Google Sheets 연결 성공: %s", service)
        client.chat_postMessage(
            channel=user_id,
            text=f"✅ 최종 성공! <@{user_id}>님, GCF와 Slack이 완벽하게 연결되었습니다."
        )
    except Exception as e:
        logging.error(f"Error handling /hello: {e}")
        client.chat_postMessage(
            channel=user_id,
            text=f"🚨 최종 오류: Sheets 인증 과정에서 실패했습니다. 로그 확인 필요: {e}"
        )

# ------------------------------------------------
# 2-1. /netcheck 명령어 핸들러 (네트워크 진단용, 관리자 전용)
# ------------------------------------------------
@slack_app.command("/netcheck")
def handle_netcheck(ack, body, client):
    user_id = body["user_id"]

    # 관리자 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        ack("❌ 관리자만 사용할 수 있습니다.")
        return

    url = "https://oauth2.googleapis.com/token"
    try:
        resp = requests.get(url, timeout=10)
        result = f"✅ 핸드셰이크 OK, 응답 코드 {resp.status_code}"
    except Exception as e:
        result = f"🚨 요청 실패: {e}"

    # slash command 응답은 기본적으로 요청자에게만 표시(Ephemeral)
    ack(f"네트워크 테스트 결과: {result}")


# ------------------------------------------------
# 3. /출근 명령어 핸들러 (게임화 버전)
# ------------------------------------------------
@slack_app.command("/출근")
def handle_check_in(ack, body, client):
    # 1. 3초 타임아웃 방지를 위해 즉시 응답 (랜덤 멘트)
    messages = [
        "출근 처리 중... 📡 오늘도 안전 운전이 제일 중요한 거 아시죠? 출발! 🛡️",
        "위치 확인 완료! 📍 시동 걸기 전, 안전벨트부터 '찰칵' 해주세요 🤙",
        "오늘 업무를 시작합니다 ⏳ 급할수록 천천히! 여유를 가지고 달려요 😎",
        "출근 기록 중이에요 📝 오늘도 무사고 기록 갱신! 기분 좋게 시동 걸까요? 🚙",
        "데이터 전송 중... 📶 졸릴 땐 꼭 쉬어가기! 오늘도 당신의 안전을 응원해요 💪",
        "출근 도장 꾹! 🐾 빵빵! 오늘도 무사고 기록 갱신 가보자고! 🚙",
        "출근 등록 중입니다 📝 안전이 1순위! 마음은 가볍게, 운전은 신중하게 🛡️",
        "출근 확인 중... 📡 시동 걸기 전, 안전벨트부터 '찰칵' 하셨나요? 🤙",
        "오늘의 시작을 기록해요 ✅ 자, 이제 안전하게 달려볼까요? 출발! 🚕",
    ]
    ack(random.choice(messages))
    
    user_id = body["user_id"]
    channel_id = body.get("channel_id", user_id)
    
    # user_name 추출 (Slack body에서)
    user_name = body.get("user", {}).get("name", "")

    # 실제 처리(시트 기록, 게임화 메시지)는 워커에서 수행
    try:
        # body에 user_name 추가
        task_body = body.copy()
        task_body["user_name"] = user_name
        enqueue_task("check_in", task_body)
    except Exception as e:
        logging.error(f"Error enqueueing /출근 task: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"🚨 출근 작업 큐 등록 중 서버 오류가 발생했습니다: {e}",
        )
        return

# ------------------------------------------------
# 4. /퇴근 명령어 핸들러 (게임화 버전)
# ------------------------------------------------
@slack_app.command("/퇴근")
def handle_check_out(ack, body, client):
    # 1. 3초 타임아웃 방지를 위해 즉시 응답 (랜덤 멘트)
    messages = [
        "퇴근 처리 중... 💾 오늘 하루 정말 고생 많으셨어요! 집까지 안전하게 모시겠습니다 🏠",
        "업무를 종료합니다 🏁 피곤하실 텐데 졸음운전 조심! 창문 열고 환기 한 번 하고 출발해요 🌬️",
        "데이터 저장 완료! 📥 무거운 장비는 내려놓고, 이제 가벼운 마음으로 핸들 잡아보세요 😌",
        "퇴근 도장 쾅! 🔨 오늘 흘린 땀방울만큼 꿀맛 같은 휴식이 기다리고 있어요! 고고! 🍯",
        "수고하셨습니다! 🙌 어두운 퇴근길, 갈 때보다 더 주의해서 안전 운전! 아시죠? 🚘",
        "오늘 일과 끝! 🔚 집에 도착할 때까지가 업무의 연장입니다. 끝까지 방어 운전 부탁해요 🛡️",
        "퇴근 기록 저장 중... ⏳ 배터리가 방전되셨나요? 🪫 얼른 집 가서 풀충전하러 가시죠! ⚡️",
        "위치 확인 종료 📍 사랑하는 가족이 기다리는 집으로! 과속하지 말고 천천히 가요 👨‍👩‍👧‍👦",
        "오늘도 무사히 마쳤습니다 ✅ 긴장 풀지 말고 안전하게 귀가하기! 내일 또 웃으며 만나요 👋",
    ]
    ack(random.choice(messages))
    
    user_id = body["user_id"]
    channel_id = body.get("channel_id", user_id)
    
    # user_name 추출 (Slack body에서)
    user_name = body.get("user", {}).get("name", "")

    # 실제 처리(시트 기록, 게임화 메시지)는 워커에서 수행
    try:
        # body에 user_name 추가
        task_body = body.copy()
        task_body["user_name"] = user_name
        enqueue_task("check_out", task_body)
    except Exception as e:
        logging.error(f"Error enqueueing /퇴근 task: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"🚨 퇴근 작업 큐 등록 중 서버 오류가 발생했습니다: {e}",
        )

# ------------------------------------------------
# 5. /급여정산 명령어 핸들러 (관리자 전용)
# ------------------------------------------------
@slack_app.command("/급여정산")
def handle_payroll_settlement(ack, body, client):
    user_id = body['user_id']
    
    # 관리자 권한 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        ack("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    # 명령어 파싱: /급여정산 2024-12 또는 /급여정산
    text = body.get('text', '').strip()
    
    try:
        if text:
            # YYYY-MM 형식 파싱
            year, month = map(int, text.split('-'))
        else:
            # 기본값: 이번 달
            now = datetime.now(sheets_handler.KST)
            year = now.year
            month = now.month
        
        # 급여 계산
        payrolls = sheets_handler.calculate_all_payrolls(year, month)
        
        if not payrolls:
            ack(f"❌ {year}년 {month}월 근무 기록이 없습니다.")
            return
        
        # 미리보기 메시지 구성
        total_amount = sum(p['total_pay'] for p in payrolls)
        total_work_days = sum(p['work_days'] for p in payrolls)
        
        preview_text = f"📊 **{year}년 {month}월 급여 정산 미리보기**\n\n"
        preview_text += f"• 총 인원: {len(payrolls)}명\n"
        preview_text += f"• 총 근무일수: {total_work_days}일\n"
        preview_text += f"• 총 급여액: {total_amount:,}원\n\n"
        preview_text += "**상세 내역:**\n"
        
        for p in payrolls:
            preview_text += f"• {p['name']}: {p['work_days']}일, {p['total_pay']:,}원\n"
        
        # 즉시 응답 (Ephemeral)
        ack()
        
        # Block Kit으로 버튼 포함 메시지 전송 (Ephemeral)
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": preview_text
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ 전 직원 발송"
                        },
                        "style": "primary",
                        "action_id": "send_payrolls",
                        "value": f"{year}-{month}"
                    }
                ]
            }
        ]
        
        client.chat_postEphemeral(
            channel=body['channel_id'],
            user=user_id,
            text=preview_text,
            blocks=blocks
        )
        
    except ValueError:
        ack("❌ 날짜 형식이 올바르지 않습니다. 예: /급여정산 2024-12")
    except Exception as e:
        logging.error(f"Error handling /급여정산: {e}")
        ack(f"🚨 급여 정산 중 오류가 발생했습니다: {e}")

# ------------------------------------------------
# 6. 관리자용 출근 로그 조회
# ------------------------------------------------
@slack_app.command("/출근로그")
def handle_attendance_logs(ack, body, client):
    """관리자 전용: 특정 사용자의 출근 로그 조회"""
    user_id = body['user_id']
    
    # 관리자 권한 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        ack("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    ack()
    
    try:
        # 모든 사용자 목록 가져오기
        users = sheets_handler.get_all_users()
        if not users:
            client.chat_postEphemeral(
                channel=body['channel_id'],
                user=user_id,
                text="❌ 사용자 목록을 가져올 수 없습니다."
            )
            return
        
        # 사용자 선택 메뉴 생성
        options = []
        for user in users:
            if user.get("name"):
                options.append({
                    "text": {
                        "type": "plain_text",
                        "text": user["name"]
                    },
                    "value": user["name"]
                })
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📋 **출근 로그 조회**\n\n조회할 사용자를 선택하세요:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "사용자 선택"
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "사용자 선택"
                    },
                    "options": options,
                    "action_id": "select_user_attendance"
                }
            }
        ]
        
        client.chat_postEphemeral(
            channel=body['channel_id'],
            user=user_id,
            text="출근 로그 조회",
            blocks=blocks
        )
    except Exception as e:
        logging.error(f"Error handling /출근로그: {e}")
        client.chat_postEphemeral(
            channel=body['channel_id'],
            user=user_id,
            text=f"🚨 출근 로그 조회 중 오류가 발생했습니다: {e}"
        )


@slack_app.action("select_user_attendance")
def handle_select_user_attendance(ack, body, client, logger):
    """출근 로그 조회 - 사용자 선택 후"""
    user_id = body['user']['id']
    
    # 관리자 권한 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        ack()
        return
    
    ack()
    
    try:
        selected_name = body['actions'][0]['selected_option']['value']
        channel_id = body.get('channel', {}).get('id') or body.get('channel_id', user_id)
        
        # 출근 로그 조회
        logs = sheets_handler.get_attendance_logs(selected_name)
        
        if not logs:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ {selected_name}님의 출근 기록이 없습니다."
            )
            return
        
        # 메시지 구성
        msg = f"📋 **{selected_name}님 출근 로그**\n\n"
        msg += f"총 {len(logs)}건의 출근 기록\n\n"
        
        for log in logs:
            date_str = log.get("date", "")
            time_str = log.get("time", "")
            remarks = log.get("remarks", "")
            msg += f"• {date_str} {time_str}"
            if remarks:
                msg += f" ({remarks})"
            msg += "\n"
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=msg
        )
    except Exception as e:
        logger.exception("Error in select_user_attendance: %s", e)
        client.chat_postEphemeral(
            channel=body.get('channel', {}).get('id') or body.get('channel_id', user_id),
            user=user_id,
            text="❌ 출근 로그 조회 중 오류가 발생했습니다."
        )


# ------------------------------------------------
# 7. 관리자용 정산 내역 조회
# ------------------------------------------------
@slack_app.command("/정산내역")
def handle_payroll_history(ack, body, client):
    """관리자 전용: 특정 사용자의 모든 급여 명세서 조회"""
    user_id = body['user_id']
    
    # 관리자 권한 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        ack("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    ack()
    
    try:
        # 모든 사용자 목록 가져오기
        users = sheets_handler.get_all_users()
        if not users:
            client.chat_postEphemeral(
                channel=body['channel_id'],
                user=user_id,
                text="❌ 사용자 목록을 가져올 수 없습니다."
            )
            return
        
        # 사용자 선택 메뉴 생성
        options = []
        for user in users:
            if user.get("name"):
                options.append({
                    "text": {
                        "type": "plain_text",
                        "text": user["name"]
                    },
                    "value": user["name"]
                })
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "💰 **정산 내역 조회**\n\n조회할 사용자를 선택하세요:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "사용자 선택"
                },
                "accessory": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "사용자 선택"
                    },
                    "options": options,
                    "action_id": "select_user_payroll"
                }
            }
        ]
        
        client.chat_postEphemeral(
            channel=body['channel_id'],
            user=user_id,
            text="정산 내역 조회",
            blocks=blocks
        )
    except Exception as e:
        logging.error(f"Error handling /정산내역: {e}")
        client.chat_postEphemeral(
            channel=body['channel_id'],
            user=user_id,
            text=f"🚨 정산 내역 조회 중 오류가 발생했습니다: {e}"
        )


@slack_app.action("select_user_payroll")
def handle_select_user_payroll(ack, body, client, logger):
    """정산 내역 조회 - 사용자 선택 후"""
    user_id = body['user']['id']
    
    # 관리자 권한 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        ack()
        return
    
    ack()
    
    try:
        selected_name = body['actions'][0]['selected_option']['value']
        channel_id = body.get('channel', {}).get('id') or body.get('channel_id', user_id)
        
        # 급여 내역 조회
        payrolls = sheets_handler.get_user_payroll_history(selected_name)
        
        if not payrolls:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ {selected_name}님의 급여 기록이 없습니다."
            )
            return
        
        # 메시지 구성
        msg = f"💰 **{selected_name}님 정산 내역**\n\n"
        msg += f"총 {len(payrolls)}개월의 급여 기록\n\n"
        
        for payroll in payrolls:
            year = payroll['year']
            month = payroll['month']
            work_days = payroll['work_days']
            total_pay = payroll['total_pay']
            base_pay = payroll['base_pay']
            commission = payroll['commission']
            transportation = payroll['transportation']
            
            msg += f"━━━━━━━━━━━━━━━━━━━━\n"
            msg += f"📋 **{year}년 {month}월**\n\n"
            msg += f"• 근무일수: {work_days}일\n"
            msg += f"• 기본급: {base_pay:,}원\n"
            if commission > 0:
                msg += f"• 인센티브: {commission:,}원\n"
            msg += f"• 교통비: {transportation:,}원\n"
            msg += f"• **총 급여: {total_pay:,}원**\n\n"
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=msg
        )
    except Exception as e:
        logger.exception("Error in select_user_payroll: %s", e)
        client.chat_postEphemeral(
            channel=body.get('channel', {}).get('id') or body.get('channel_id', user_id),
            user=user_id,
            text="❌ 정산 내역 조회 중 오류가 발생했습니다."
        )


# ------------------------------------------------
# 8. 버튼 액션 핸들러 (전 직원 발송)
# ------------------------------------------------
@slack_app.action("send_payrolls")
def handle_send_payrolls(ack, body, client):
    ack()  # 버튼 클릭 즉시 응답
    
    user_id = body['user']['id']
    
    # 관리자 권한 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        client.chat_postEphemeral(
            channel=body['channel']['id'],
            user=user_id,
            text="❌ 이 작업은 관리자만 수행할 수 있습니다."
        )
        return
    
    try:
        # 버튼 값에서 년월 추출
        year_month = body['actions'][0]['value']
        year, month = map(int, year_month.split('-'))
        
        # 모든 직원의 급여 계산
        payrolls = sheets_handler.calculate_all_payrolls(year, month)
        
        if not payrolls:
            client.chat_postEphemeral(
                channel=body['channel']['id'],
                user=user_id,
                text=f"❌ {year}년 {month}월 근무 기록이 없습니다."
            )
            return
        
        # 각 직원에게 DM 발송
        success_count = 0
        fail_count = 0
        
        for payroll in payrolls:
            slack_id = payroll['slack_id']
            if not slack_id:
                fail_count += 1
                continue
            
            try:
                # 개인별 급여 명세서 생성
                name = payroll['name']
                work_days = payroll['work_days']
                base_pay = payroll['base_pay']
                commission = payroll['commission']
                transportation = payroll['transportation']
                total_pay = payroll['total_pay']
                
                # 총 근무일수 조회
                total_days = sheets_handler.get_total_work_days(name)
                
                # 평균 일당 계산
                avg_daily_pay = base_pay // work_days if work_days > 0 else 0
                avg_daily_pay_manwon = avg_daily_pay // 10000
                
                # 다음 일당 인상일 계산
                next_raise_days = None
                for start, end, rate in sheets_handler.PAY_RATES:
                    if total_days < end:
                        next_raise_days = end + 1
                        break
                
                # 인센티브 상세 내역 조회
                commission_details = sheets_handler.get_commission_details(name, year, month)
                
                # 메시지 구성
                msg = f"📋 **[{name}님 {year}년 {month}월 급여 명세서]**\n\n"
                msg += f"💰 **총 지급액: {total_pay // 10000}만원**\n\n"
                msg += f"📅 **근무 내역**\n"
                if next_raise_days:
                    msg += f"일당: {avg_daily_pay_manwon}만원({next_raise_days}일 근무시 인상)\n"
                else:
                    msg += f"일당: {avg_daily_pay_manwon}만원\n"
                msg += f"총 출근일수: {work_days}일\n"
                msg += f"계산: {avg_daily_pay_manwon}만원 × {work_days}일 = {base_pay // 10000}만원\n"
                msg += f"교통비: {transportation // 10000}만원\n"
                # 격려금은 별도 시트에서 가져와야 함 (현재는 생략)
                msg += "\n"
                
                if commission > 0:
                    msg += f"💎 **인센티브**\n"
                    # 총 인센티브와 반분 금액 표시 (반분은 총액의 절반)
                    commission_half = commission // 2
                    msg += f"총 인센티브: {commission // 10000}만원 ({commission_half // 10000}만원)\n\n"
                    
                    if commission_details:
                        msg += f"📆 **상세 내역**\n"
                        for detail in commission_details:
                            date_str = detail["date"]
                            date_display = date_str.replace("-", ".") if "-" in date_str else date_str
                            total_amount = detail["total"]
                            half_amount = total_amount // 2
                            msg += f"⭐ {date_display} [{total_amount // 10000}만원 ({half_amount // 10000}만원)]\n"
                            for item in detail["items"]:
                                if item["description"]:
                                    msg += f" ㆍ{item['description']} {item['amount'] // 10000}만원\n"
                        msg += "\n"
                
                msg += f"🙌 한 달 동안 고생 많으셨습니다!"
                
                client.chat_postMessage(
                    channel=slack_id,
                    text=msg
                )
                success_count += 1
                
            except Exception as e:
                logging.error(f"Error sending payroll to {name} ({slack_id}): {e}")
                fail_count += 1
        
        # 관리자에게 결과 알림
        result_msg = f"✅ **급여 명세서 발송 완료**\n\n"
        result_msg += f"• 성공: {success_count}명\n"
        if fail_count > 0:
            result_msg += f"• 실패: {fail_count}명\n"
        
        client.chat_postEphemeral(
            channel=body['channel']['id'],
            user=user_id,
            text=result_msg
        )
        
    except Exception as e:
        logging.error(f"Error in send_payrolls action: {e}")
        client.chat_postEphemeral(
            channel=body['channel']['id'],
            user=user_id,
            text=f"🚨 급여 명세서 발송 중 오류가 발생했습니다: {e}"
        )

# ------------------------------------------------
# 7. 자재사용대장 핸들러
# ------------------------------------------------

# 방 목록
MATERIAL_ROOMS = [
    "거실화장실 - 바닥",
    "거실화장실 - 벽",
    "안방화장실 - 바닥",
    "안방화장실 - 벽",
    "거실",
    "세탁실",
    "베란다",
    "현관"
]

# 방별 이모지 매핑
def get_room_emoji(room):
    """방 이름에 따른 이모지 반환"""
    room_emojis = {
        "거실화장실 - 바닥": "🚽",
        "거실화장실 - 벽": "🧱",
        "안방화장실 - 바닥": "🚽",
        "안방화장실 - 벽": "🧱",
        "거실": "🏠",
        "세탁실": "💧",
        "베란다": "☀️",
        "현관": "👟"
    }
    return room_emojis.get(room, "📍")

# 색상 코드 목록
MATERIAL_COLORS = ["110", "111", "112", "113", "130", "기타"]


@slack_app.action("open_material_log")
def handle_open_material_log(ack, body, client):
    """자재사용대장 버튼 클릭 → 방 선택 화면 표시"""
    logging.info("open_material_log action received: %s", body)
    ack()
    
    user_id = body["user"]["id"]
    channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
    
    # 방 선택 화면 (체크박스)
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "📋 **자재사용대장**\n\n작업한 구역을 선택하고 자재 사용량을 기록해주세요."
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": " "
            },
            "accessory": {
                "type": "checkboxes",
                "options": [
                    {"text": {"type": "plain_text", "text": f"{get_room_emoji(room)} {room}"}, "value": room}
                    for room in MATERIAL_ROOMS
                ],
                "action_id": "select_rooms"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ 사용량 기록시작"
                    },
                    "action_id": "start_material_input",
                    "style": "primary"
                }
            ]
        }
    ]
    
    client.chat_postEphemeral(
        channel=channel_id,
        user=user_id,
        text="자재사용대장",
        blocks=blocks
    )


@slack_app.action("select_rooms")
def handle_select_rooms(ack, body, logger):
    """방 체크박스 클릭 시 발생하는 액션을 단순히 ack 해서 404 경고를 막기 위한 핸들러."""
    logger.info("select_rooms action: %s", body.get("actions"))
    ack()


@slack_app.action("start_material_input")
def handle_start_material_input(ack, body, client, logger):
    """입력 시작 버튼 클릭 → 선택된 방들의 체크박스 값 가져오기"""
    logger.info("start_material_input action received: %s", body)
    ack()
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)

        # 선택된 방 가져오기
        selected_rooms = []
        if "state" in body and "values" in body["state"]:
            for block_id, block_values in body["state"]["values"].items():
                if "select_rooms" in block_values:
                    checkboxes = block_values["select_rooms"]["selected_options"]
                    selected_rooms = [opt["value"] for opt in checkboxes]

        logger.info("start_material_input selected_rooms=%s", selected_rooms)

        if not selected_rooms:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 방을 최소 1개 이상 선택해주세요."
            )
            return

        # 첫 번째 방의 색상 선택 화면: 그냥 에페메랄로 새로 그려도 됨 (trigger_id는 block action 기준)
        _open_color_selection_modal(client, body, selected_rooms, 0)
    except Exception as e:
        logger.exception("Error in start_material_input: %s", e)


def _open_color_selection_modal(client, body, selected_rooms, room_index):
    """색상 선택용 버튼을 에페메랄 메시지로 보여준다."""
    if room_index >= len(selected_rooms):
        # 모든 방 입력 완료
        client.chat_postEphemeral(
            channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
            user=body["user"]["id"],
            text="✅ 모든 방의 자재 사용 기록이 완료되었습니다!"
        )
        return
    
    room = selected_rooms[room_index]
    completed_rooms = selected_rooms[:room_index]
    
    # 모달 뷰 구성
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📋 **자재사용대장**\n\n**{room}**을 선택하셨습니다.\n빅라이언 어떤 색상을 사용하셨나요?"
            }
        }
    ]
    
    # 색상 버튼들 (2열로 배치) - action_id는 색상별로 유니크하게
    color_buttons = []
    for color in MATERIAL_COLORS:
        if color == "기타":
            # 기타 버튼은 별도 액션으로 처리 (정규식 핸들러와 충돌 방지)
            color_buttons.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "기타"
                },
                "action_id": "select_custom_color",
                "value": f"{room}|custom|{room_index}|{','.join(selected_rooms)}"
            })
        else:
            color_buttons.append({
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": color
                },
                "action_id": f"select_color_{color}",
                "value": f"{room}|{color}|{room_index}|{','.join(selected_rooms)}"
            })
    
    # 2열로 나누기
    for i in range(0, len(color_buttons), 2):
        row_buttons = color_buttons[i:i+2]
        blocks.append({
            "type": "actions",
            "elements": row_buttons
        })
    
    # 완료된 방 표시
    if completed_rooms:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"✅ 완료: {', '.join(completed_rooms)}"
            }
        })
    
    # 에페메랄 메시지로 색상 버튼 표시
    channel_id = body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"])
    client.chat_postEphemeral(
        channel=channel_id,
        user=body["user"]["id"],
        text="자재 색상을 선택해주세요.",
        blocks=blocks,
    )


@slack_app.action(re.compile("^select_color_"))
def handle_select_color(ack, body, client, logger):
    """색상 선택 → 사용량 입력 에페메랄 표시 (모달 없이 처리)."""
    logger.info(
        "select_color action received: action_id=%s, value=%s",
        body["actions"][0].get("action_id"),
        body["actions"][0].get("value"),
    )
    ack()

    try:
        # value 파싱: "room|color|room_index|selected_rooms"
        value_parts = body["actions"][0]["value"].split("|")
        room = value_parts[0]
        color = value_parts[1]
        room_index = int(value_parts[2])
        selected_rooms = value_parts[3].split(",") if len(value_parts) > 3 and value_parts[3] else []

        # 사용량 입력용 에페메랄 블록 구성
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"])
        room_emoji = get_room_emoji(room)
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"──────────────\n📋 **자재사용대장**\n──────────────\n\n{room_emoji} {room} [ {color}번 색상 ]\n\n이 구역에 투입된 용량을 입력해주세요.",
                },
            },
            {
                "type": "input",
                "block_id": "qty_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "qty",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "예: 200",
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": "사용량",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "save_material_usage",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ 저장",
                        },
                        "style": "primary",
                        "value": f"{room}|{color}|{room_index}|{','.join(selected_rooms)}",
                    }
                ],
            },
        ]

        client.chat_postEphemeral(
            channel=channel_id,
            user=body["user"]["id"],
            text="자재 사용량을 입력해주세요.",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Modal push error: %s", e)


@slack_app.action("select_custom_color")
def handle_select_custom_color(ack, body, client, logger):
    """기타 색상 선택 → 색상 입력 모달 표시"""
    logger.info("select_custom_color action received: %s", body)
    ack()
    
    try:
        # value 파싱: "room|custom|room_index|selected_rooms"
        value_parts = body["actions"][0]["value"].split("|")
        room = value_parts[0]
        room_index = int(value_parts[2])
        selected_rooms = value_parts[3].split(",") if len(value_parts) > 3 and value_parts[3] else []
        
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"])
        
        # 색상 입력용 에페메랄 블록 구성
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📋 **자재사용대장**\n\n**{room}**의 색상을 직접 입력해주세요:",
                },
            },
            {
                "type": "input",
                "block_id": "color_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "custom_color",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "예: 187, 200, 기타색상",
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": "색상",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "confirm_custom_color",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ 확인",
                        },
                        "style": "primary",
                        "value": f"{room}|{room_index}|{','.join(selected_rooms)}",
                    }
                ],
            },
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=body["user"]["id"],
            text="색상을 입력해주세요.",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in select_custom_color: %s", e)


@slack_app.action("confirm_custom_color")
def handle_confirm_custom_color(ack, body, client, logger):
    """기타 색상 확인 → 사용량 입력으로 진행"""
    logger.info("confirm_custom_color action received: %s", body)
    ack()
    
    try:
        # value 파싱: "room|room_index|selected_rooms"
        value_parts = body["actions"][0]["value"].split("|")
        room = value_parts[0]
        room_index = int(value_parts[1])
        selected_rooms = value_parts[2].split(",") if len(value_parts) > 2 and value_parts[2] else []
        
        # state에서 색상 읽기
        values = body.get("state", {}).get("values", {})
        color_block = values.get("color_input", {})
        custom_color = ""
        for _, v in color_block.items():
            custom_color = v.get("value", "").strip()
        
        if not custom_color:
            client.chat_postEphemeral(
                channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
                user=body["user"]["id"],
                text="❌ 자재사용대장: 색상을 입력해주세요.",
            )
            return
        
        # 사용량 입력으로 진행
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"])
        room_emoji = get_room_emoji(room)
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"──────────────\n📋 **자재사용대장**\n──────────────\n\n{room_emoji} {room} [ {custom_color}번 색상 ]\n\n이 구역에 투입된 용량을 입력해주세요.",
                },
            },
            {
                "type": "input",
                "block_id": "qty_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "qty",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "예: 5",
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": "사용량",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "save_material_usage",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ 저장",
                        },
                        "style": "primary",
                        "value": f"{room}|{custom_color}|{room_index}|{','.join(selected_rooms)}",
                    }
                ],
            },
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=body["user"]["id"],
            text="자재 사용량을 입력해주세요.",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in confirm_custom_color: %s", e)


@slack_app.action("material_order_required")
def handle_material_order_required(ack, body, client, logger):
    """발주 필요 - 있음 버튼 클릭 → 발주 내용 입력 에페메랄 표시"""
    logger.info("material_order_required action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"──────────────\n"
                        f"🛒 **자재 발주 요청**\n"
                        f"──────────────\n\n"
                        f"필요하신 물품과 수량을 적어주세요.\n"
                        f"바로 발주 넣을 수 있게 준비하겠습니다."
                    )
                }
            },
            {
                "type": "input",
                "block_id": "order_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "order_text",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "예: 빅라이언 100, 짤주머니 한 박스 등"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "발주 내용"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ 저장"
                        },
                        "action_id": "save_material_order",
                        "style": "primary"
                    }
                ]
            }
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="발주 필요 자재 입력",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in material_order_required: %s", e)


@slack_app.action("material_order_not_required")
def handle_material_order_not_required(ack, body, client, logger):
    """발주 필요 - 없음 버튼 클릭 → 완료 메시지"""
    logger.info("material_order_not_required action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        done_rooms = body["actions"][0].get("value", "")
        
        # 폴더 생성 버튼 포함 메시지
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"✅ 모든 방의 자재 사용 기록이 완료되었습니다!\n"
                        f"완료된 방: {done_rooms}\n\n"
                        f"📦 발주 필요 자재 없음"
                    )
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "**아래 버튼을 클릭하면 현장 사진 폴더가 생성됩니다.**"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📁 현장사진 폴더생성"
                        },
                        "action_id": "create_photo_folder",
                        "style": "primary",
                        "value": "create"
                    }
                ]
            }
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="자재 사용 기록 완료",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in material_order_not_required: %s", e)


@slack_app.action("save_material_order")
def handle_save_material_order(ack, body, client, logger):
    """발주 내용 저장 버튼 클릭 → 시트 기록"""
    logger.info("save_material_order action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        # state에서 발주 내용 읽기
        values = body.get("state", {}).get("values", {})
        order_block = values.get("order_input", {})
        order_text = ""
        for _, v in order_block.items():
            order_text = v.get("value", "") or ""
        order_text = order_text.strip()
        
        if not order_text:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 발주 내용을 입력해주세요.",
            )
            return
        
        # 사용자 한글 이름 조회
        user_name = body["user"]["name"]
        user_info = sheets_handler.get_user_info(user_id)
        if user_info:
            user_name = user_info["name"]
        
        # 시트에 발주 기록 (sheets_handler에 함수 추가 필요)
        success, message = sheets_handler.record_material_order(user_name, order_text)
        if not success:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ 발주 기록 실패: {message}",
            )
            return
        
        # 폴더 생성 버튼 포함 메시지
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"✅ 발주 내용이 기록되었습니다!\n\n"
                        f"📦 **발주 내용:**\n{order_text}"
                    )
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "**아래 버튼을 클릭하면 현장 사진 폴더가 생성됩니다.**"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📁 현장사진 폴더생성"
                        },
                        "action_id": "create_photo_folder",
                        "style": "primary",
                        "value": "create"
                    }
                ]
            }
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="발주 기록 완료",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in save_material_order: %s", e)
        client.chat_postEphemeral(
            channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
            user=body["user"]["id"],
            text="❌ 발주 기록 중 오류가 발생했습니다. 다시 시도해 주세요.",
        )


@slack_app.action("create_photo_folder")
def handle_create_photo_folder(ack, body, client, logger):
    """현장사진 폴더 생성 버튼 클릭 → Google Drive 폴더 생성"""
    logger.info("create_photo_folder action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        # 생성 중 메시지 전송
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="📁 드라이브를 생성중입니다...",
        )
        
        # 현장 주소 가져오기
        site_address = _get_today_site_address()
        
        # Google Drive 폴더 생성
        success, result, folder_url = sheets_handler.create_site_photo_folder(site_address)
        
        if not success:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ {result}",  # result가 에러 메시지
            )
            return
        
        # 폴더 ID와 URL 받기
        folder_id = result
        
        # 사진 업로드 버튼 포함 완료 메시지
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "✅ 드라이브가 생성되었습니다!\n현장사진 업로드가 끝난 후, 경험치 획득 버튼을 클릭해주세요."
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📷 현장사진 업로드"
                        },
                        "url": folder_url,
                        "action_id": "upload_photos",
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "⭐ 경험치 획득(퇴근)"
                        },
                        "action_id": "check_out_from_photo",
                        "style": "primary",
                        "value": "check_out"
                    }
                ]
            }
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="폴더 생성 완료",
            blocks=blocks,
        )
        
    except Exception as e:
        logger.exception("Error in create_photo_folder: %s", e)
        client.chat_postEphemeral(
            channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
            user=body["user"]["id"],
            text="❌ 폴더 생성 중 오류가 발생했습니다. 다시 시도해 주세요.",
        )


# ------------------------------------------------
# 9. /발주목록 명령어 핸들러
# ------------------------------------------------
@slack_app.command("/발주목록")
def handle_order_list(ack, body, client):
    """발주 목록 조회 및 관리"""
    user_id = body["user_id"]
    channel_id = body.get("channel_id", user_id)
    
    # 관리자 권한 체크
    if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
        ack("❌ 이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    ack("📦 발주 목록을 조회 중입니다...")
    
    try:
        now = datetime.now(sheets_handler.KST)
        success, result = sheets_handler.get_pending_material_orders(now.year, now.month)
        
        if not success:
            client.chat_postMessage(
                channel=channel_id,
                text=f"❌ 발주 목록 조회 실패: {result}",
            )
            return
        
        orders = result if isinstance(result, list) else []
        
        if not orders:
            client.chat_postMessage(
                channel=channel_id,
                text=f"📦 {now.month}월 발주 목록이 비어있습니다.",
            )
            return
        
        # 발주 목록 메시지 구성
        order_list_text = "\n".join([f"{idx+1}. {order['content']}" for idx, order in enumerate(orders)])
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"──────────────\n"
                        f"📦 **{now.month}월 자재 발주 요청서 [Total: {len(orders)}건]**\n"
                        f"({now.strftime('%Y-%m-%d')} 기준)\n"
                        f"──────────────\n\n"
                        f"{order_list_text}\n\n"
                        f"❗ 발주 넣은 항목의 번호를 입력하면 목록에서 지워집니다.\n"
                        f"❗ 발주가 처리 된 목록은 숫자로 입력해주세요.\n"
                        f"-> 입력 (예시: 1,3)"
                    )
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📤 문자 발송 후 목록 최신화"
                        },
                        "action_id": "send_order_message",
                        "style": "primary",
                        "value": json.dumps([{"row_index": o["row_index"], "content": o["content"]} for o in orders])
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔄 목록 최신화"
                        },
                        "action_id": "refresh_order_list",
                        "value": json.dumps([{"row_index": o["row_index"], "content": o["content"]} for o in orders])
                    }
                ]
            }
        ]
        
        client.chat_postMessage(
            channel=channel_id,
            text=f"📦 {now.month}월 자재 발주 요청서",
            blocks=blocks,
        )
    except Exception as e:
        logging.exception(f"Error in handle_order_list: {e}")
        client.chat_postMessage(
            channel=channel_id,
            text=f"🚨 발주 목록 조회 중 오류가 발생했습니다: {e}",
        )


@slack_app.action("send_order_message")
def handle_send_order_message(ack, body, client, logger):
    """문자 발송 후 목록 최신화 버튼 클릭 → 관리자에게 DM 발송"""
    logger.info("send_order_message action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        # 관리자 권한 체크
        if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 이 작업은 관리자만 수행할 수 있습니다.",
            )
            return
        
        # value에서 주문 목록 파싱
        orders_data = json.loads(body["actions"][0]["value"])
        
        # 발주 메시지 구성
        order_list_text = "\n".join([f"{idx+1}. {order['content']}" for idx, order in enumerate(orders_data)])
        
        message_text = (
            "---\n"
            "안녕하세요.\n"
            "디테일라인입니다.\n\n"
            f"{order_list_text}\n\n"
            "택배 발송 부탁드립니다.\n"
            "감사합니다.\n"
            "---"
        )
        
        # 관리자에게 DM 발송
        for admin_id in ADMIN_SLACK_IDS:
            if admin_id:
                client.chat_postMessage(
                    channel=admin_id,
                    text=message_text,
                )
        
        # 메시지 전송 후 발주 완료 번호 입력 화면 표시
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "✅ 관리자에게 발주 메시지가 전송되었습니다.\n\n발주 완료된 항목의 번호를 입력해주세요. (예: 1,3)"
                }
            },
            {
                "type": "input",
                "block_id": "completed_numbers_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "completed_numbers",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "예: 1,3"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "발주 완료 번호"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ 최신화"
                        },
                        "action_id": "update_order_list",
                        "style": "primary",
                        "value": body["actions"][0]["value"]  # orders_data 전달
                    }
                ]
            }
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="발주 완료 번호를 입력해주세요.",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in send_order_message: %s", e)
        client.chat_postEphemeral(
            channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
            user=body["user"]["id"],
            text="❌ 발주 메시지 전송 중 오류가 발생했습니다.",
        )


@slack_app.action("refresh_order_list")
def handle_refresh_order_list(ack, body, client, logger):
    """목록 최신화 버튼 클릭 → 발주 완료 번호 입력 화면 표시"""
    logger.info("refresh_order_list action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        # 관리자 권한 체크
        if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 이 작업은 관리자만 수행할 수 있습니다.",
            )
            return
        
        # value에서 주문 목록 파싱
        orders_data = json.loads(body["actions"][0]["value"])
        
        # 발주 완료 번호 입력 화면
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "발주 완료된 항목의 번호를 입력해주세요. (예: 1,3)"
                }
            },
            {
                "type": "input",
                "block_id": "completed_numbers_input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "completed_numbers",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "예: 1,3"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": "발주 완료 번호"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ 최신화"
                        },
                        "action_id": "update_order_list",
                        "style": "primary",
                        "value": body["actions"][0]["value"]  # orders_data 전달
                    }
                ]
            }
        ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="발주 완료 번호를 입력해주세요.",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in refresh_order_list: %s", e)


@slack_app.action("update_order_list")
def handle_update_order_list(ack, body, client, logger):
    """발주 완료 번호 입력 후 최신화 → 시트 업데이트 및 잔여 목록 표시"""
    logger.info("update_order_list action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        # 관리자 권한 체크
        if ADMIN_SLACK_IDS and user_id not in ADMIN_SLACK_IDS:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 이 작업은 관리자만 수행할 수 있습니다.",
            )
            return
        
        # state에서 완료 번호 읽기
        values = body.get("state", {}).get("values", {})
        numbers_block = values.get("completed_numbers_input", {})
        completed_numbers_str = ""
        for _, v in numbers_block.items():
            completed_numbers_str = v.get("value", "").strip()
        
        if not completed_numbers_str:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 발주 완료 번호를 입력해주세요.",
            )
            return
        
        # 번호 파싱 (예: "1,3" -> [1, 3])
        try:
            completed_indices = [int(x.strip()) - 1 for x in completed_numbers_str.split(",")]  # 0-based로 변환
        except ValueError:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 올바른 형식으로 입력해주세요. (예: 1,3)",
            )
            return
        
        # value에서 주문 목록 파싱
        orders_data = json.loads(body["actions"][0]["value"])
        
        # 완료 처리할 행 번호 추출
        row_indices_to_complete = []
        for idx in completed_indices:
            if 0 <= idx < len(orders_data):
                row_indices_to_complete.append(orders_data[idx]["row_index"])
        
        if not row_indices_to_complete:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 유효한 발주 번호를 입력해주세요.",
            )
            return
        
        # 시트에 완료 처리
        success, message = sheets_handler.mark_orders_completed(row_indices_to_complete)
        if not success:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ 발주 완료 처리 실패: {message}",
            )
            return
        
        # 잔여 발주 목록 구성
        remaining_orders = [order for idx, order in enumerate(orders_data) if idx not in completed_indices]
        
        if remaining_orders:
            remaining_list_text = "\n".join([f"{idx+1}. {order['content']}" for idx, order in enumerate(remaining_orders)])
            
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"──────────────\n"
                            f"👌 **발주 목록을 최신화 합니다.**\n"
                            f"──────────────\n\n"
                            f"아래 항목은 잔여 발주 목록 입니다.\n\n"
                            f"{remaining_list_text}\n\n"
                            f"(잔여 발주: {len(remaining_orders)}건 남음)"
                        )
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ 확인"
                            },
                            "action_id": "confirm_order_update",
                            "style": "primary"
                        }
                    ]
                }
            ]
        else:
            # 모든 발주 완료
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"──────────────\n"
                            f"👌 **발주 목록을 최신화 합니다.**\n"
                            f"──────────────\n\n"
                            f"✅ 모든 발주가 완료 처리되었습니다!"
                        )
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ 확인"
                            },
                            "action_id": "confirm_order_update",
                            "style": "primary"
                        }
                    ]
                }
            ]
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="발주 목록 최신화 완료",
            blocks=blocks,
        )
    except Exception as e:
        logger.exception("Error in update_order_list: %s", e)
        client.chat_postEphemeral(
            channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
            user=body["user"]["id"],
            text="❌ 발주 목록 최신화 중 오류가 발생했습니다.",
        )


@slack_app.action("confirm_order_update")
def handle_confirm_order_update(ack, body, client, logger):
    """확인 버튼 클릭 → 완료 메시지"""
    logger.info("confirm_order_update action received")
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="감사합니다. 추가 요청이 있으면 말씀해주세요.",
        )
    except Exception as e:
        logger.exception("Error in confirm_order_update: %s", e)


@slack_app.action("check_out_from_photo")
def handle_check_out_from_photo(ack, body, client, logger):
    """경험치 획득(퇴근) 버튼 클릭 → 퇴근 처리"""
    logger.info("check_out_from_photo action received: %s", body)
    ack()
    
    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)
        
        # 퇴근 처리 (Cloud Task로 비동기 처리)
        # action body를 command body 형식으로 변환
        command_body = {
            "user_id": user_id,
            "channel_id": channel_id,
            "user": {
                "id": user_id,
                "name": body["user"].get("name", "")
            }
        }
        
        try:
            enqueue_task("check_out", command_body)
            # 즉시 응답 메시지
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="⭐ 퇴근 처리 중입니다... 잠시만 기다려주세요!",
            )
        except Exception as e:
            logger.exception("Error enqueueing check_out task: %s", e)
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"🚨 퇴근 작업 큐 등록 중 서버 오류가 발생했습니다: {e}",
            )
    except Exception as e:
        logger.exception("Error in check_out_from_photo: %s", e)
        client.chat_postEphemeral(
            channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
            user=body["user"]["id"],
            text="❌ 퇴근 처리 중 오류가 발생했습니다. 다시 시도해 주세요.",
        )


@slack_app.action("save_material_usage")
def handle_save_material_usage(ack, body, client, logger):
    """사용량 입력 저장 버튼 클릭 → 시트 기록 후 다음 방으로."""
    logger.info("save_material_usage action received: %s", body)
    ack()

    try:
        user_id = body["user"]["id"]
        channel_id = body.get("channel", {}).get("id") or body.get("channel_id", user_id)

        # state에서 수량 읽기
        values = body.get("state", {}).get("values", {})
        qty_block = values.get("qty_input", {})
        qty_str = ""
        for _, v in qty_block.items():
            qty_str = v.get("value", "") or ""
        qty_str = qty_str.strip()

        if not qty_str:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="❌ 자재사용대장: 사용량을 입력해주세요.",
            )
            return

        try:
            quantity = float(qty_str)
            if quantity <= 0:
                raise ValueError("사용량은 0보다 커야 합니다.")
        except ValueError as e:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ 자재사용대장: 올바른 숫자를 입력해주세요. ({e})",
            )
            return

        # 버튼 value에서 room / color / room_index / selected_rooms 파싱
        meta = body["actions"][0]["value"].split("|")
        room = meta[0]
        color = meta[1]
        room_index = int(meta[2]) if len(meta) > 2 and meta[2] else 0
        selected_rooms = meta[3].split(",") if len(meta) > 3 and meta[3] else []

        # 사용자 한글 이름 조회
        user_name = body["user"]["name"]
        user_info = sheets_handler.get_user_info(user_id)
        if user_info:
            user_name = user_info["name"]

        # 시트 기록
        success, message = sheets_handler.record_material_usage(user_name, room, color, quantity)
        if not success:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=f"❌ 자재사용대장 기록 실패: {message}",
            )
            return

        # 현재 방 완료 안내 (새로운 형식)
        room_emoji = get_room_emoji(room)
        completion_text = (
            f"──────────────\n"
            f"👌 **입력 확인!**\n"
            f"──────────────\n\n"
            f"깔끔하게 장부에 적어두었습니다.\n\n"
            f"──────────────\n"
            f"＊ **기록 내용**\n\n"
            f"1. {room_emoji} {room} [ {color}번 색상 ] -  {quantity}g 사용"
        )
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="입력 확인",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": completion_text
                    }
                }
            ]
        )

        # 다음 방이 있으면 계속, 없으면 발주 필요 여부 확인
        next_room_index = room_index + 1
        if next_room_index < len(selected_rooms):
            _open_color_selection_modal(client, body, selected_rooms, next_room_index)
        else:
            if selected_rooms:
                done_rooms = ", ".join(selected_rooms)
            else:
                done_rooms = room
            
            # 발주 필요 여부 확인 (새로운 형식)
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"──────────────\n"
                            f"✋ **잠깐! 자재가 비어가진 않나요?**\n"
                            f"──────────────"
                        )
                    }
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "발주 요청하기"
                            },
                            "action_id": "material_order_required",
                            "style": "primary",
                            "value": f"{done_rooms}"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "기록 종료하기(없음)"
                            },
                            "action_id": "material_order_not_required",
                            "value": f"{done_rooms}"
                        }
                    ]
                }
            ]
            
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="자재 사용 기록 완료",
                blocks=blocks,
            )
    except Exception as e:
        logger.exception("Error in save_material_usage: %s", e)
        client.chat_postEphemeral(
            channel=body.get("channel", {}).get("id") or body.get("channel_id", body["user"]["id"]),
            user=body["user"]["id"],
            text="❌ 자재사용대장: 알 수 없는 오류가 발생했습니다. 다시 시도해 주세요.",
        )


# ------------------------------------------------
# 8. GCF 2세대 표준 진입점 (선택적 - GCF에서만 사용)
# ------------------------------------------------
if FUNCTIONS_FRAMEWORK_AVAILABLE:
    @functions_framework.http
    def slack_handler(request):
        if request.method != "POST":
            return "Only POST requests are accepted", 405
        
        return handler.handle(request)

    @functions_framework.http
    def worker_handler(request):
        """Cloud Tasks가 호출하는 워커 HTTP 엔드포인트.

        실제 로직은 `worker_main.worker` 에서 처리한다.
        """
        return worker_main.worker(request)

    @functions_framework.http
    def open_tmap_handler(request):
        """T-map 앱을 열기 위한 중간 리다이렉트 페이지.
        
        Slack 버튼에서 호출되며, 플랫폼(Android/iOS)을 감지해서
        T-map 앱 딥링크로 리다이렉트합니다.
        """
        addr = request.args.get("addr", "")
        if not addr:
            return ("주소 파라미터가 필요합니다.", 400)
        
        encoded_addr = quote(addr)
        
        # T-map 검색 딥링크 (주소 검색 결과 바로 표시)
        # Android용 Intent URL
        android_intent = (
            f"intent://search?name={encoded_addr}"
            "#Intent;scheme=tmap;package=com.skt.tmap.ku;end;"
        )
        
        # iOS용 URL Scheme
        ios_scheme = f"tmap://search?name={encoded_addr}"
        
        # Fallback: 웹 지도
        fallback_web = f"https://tmapapi.sktelecom.com/main/map.html?q={encoded_addr}"
        
        html = textwrap.dedent(f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>T-map 열기</title>
          <script>
            function isAndroid() {{
              return /Android/i.test(navigator.userAgent);
            }}
            function isIOS() {{
              return /iPhone|iPad|iPod/i.test(navigator.userAgent);
            }}
            function openApp() {{
              var tried = false;
              if (isAndroid()) {{
                tried = true;
                window.location.href = "{android_intent}";
              }} else if (isIOS()) {{
                tried = true;
                window.location.href = "{ios_scheme}";
              }}
              // 1.5초 안에 앱이 안 뜬다고 가정하고 웹 fallback
              setTimeout(function() {{
                if (tried) {{
                  window.location.href = "{fallback_web}";
                }}
              }}, 1500);
            }}
            window.onload = openApp;
          </script>
        </head>
        <body style="font-family: sans-serif; text-align: center; padding: 20px;">
          <p>T-map 앱을 여는 중입니다...</p>
          <p>자동으로 열리지 않으면 <a href="{fallback_web}">여기</a>를 눌러주세요.</p>
        </body>
        </html>
        """)
        return (html, 200, {"Content-Type": "text/html; charset=utf-8"})
else:
    # Render 환경에서는 app.py의 tmap_redirect를 사용
    pass