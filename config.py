"""슬랙 출결 봇 설정 값."""
import os

# Slack 설정
# [필수]: Slack Bot Token (xoxb-로 시작)
# 환경 변수에서 가져오거나 실제 값으로 변경하세요
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "xoxb-your-bot-token-here")

# [필수]: Slack Signing Secret
# 환경 변수에서 가져오거나 실제 값으로 변경하세요
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "your-signing-secret-here")

# Google Sheets 설정
# [필수]: 시트 URL에서 /d/ 뒤와 /edit 앞 사이에 있는 긴 문자열을 입력
# 환경 변수에서 가져오거나 실제 값으로 변경하세요
SPREADSHEET_KEY = os.environ.get("SPREADSHEET_KEY", "your-spreadsheet-key-here")

# [필수]: 서비스 계정 키 파일 경로 (프로젝트 루트에 두는 것을 권장)
# GCF 환경에서는 환경 변수나 Secret Manager를 사용하는 것을 권장합니다.
GOOGLE_JSON_KEY_PATH = "client_secret.json"
