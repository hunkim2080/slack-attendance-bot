"""
Render 배포용 메인 진입점
main.py의 모든 기능을 Flask 앱으로 통합
"""
import os
import logging
from flask import Flask, request

app = Flask(__name__)

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# main.py를 import하여 Slack 앱 초기화
# main.py에서 tasks_v2와 functions_framework는 선택적으로 처리됨
handler = None
try:
    logging.info("Attempting to import main.py...")
    import main
    logging.info("main.py imported successfully")
    
    # main.py의 handler를 사용
    if hasattr(main, 'handler'):
        handler = main.handler
        if handler is None:
            logging.error("main.handler exists but is None")
        else:
            logging.info("Successfully imported main.py and handler")
    else:
        logging.error("main.py imported but 'handler' attribute not found")
        logging.error(f"Available attributes in main: {dir(main)[:20]}")
except ImportError as e:
    logging.error(f"ImportError when importing main.py: {e}", exc_info=True)
    handler = None
except SyntaxError as e:
    logging.error(f"SyntaxError in main.py: {e}", exc_info=True)
    handler = None
except Exception as e:
    logging.error(f"Unexpected error when importing main.py: {type(e).__name__}: {e}", exc_info=True)
    handler = None

@app.route('/', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "ok", "service": "slack-attendance-worker"}, 200

@app.route('/slack/events', methods=['POST'])
@app.route('/slack/commands', methods=['POST'])
@app.route('/slack/interactive', methods=['POST'])
def slack_handler():
    """Slack 모든 요청 처리"""
    if not handler:
        logging.error("Handler not available")
        return ("Handler not initialized", 500)
    
    try:
        # Flask request를 SlackRequestHandler가 기대하는 형식으로 변환
        class FlaskRequestWrapper:
            def __init__(self, flask_request):
                self.flask_request = flask_request
                self.method = flask_request.method
                self.args = flask_request.args
                # query_string은 bytes이거나 string일 수 있음
                self.query_string = flask_request.query_string
                # Slack Bolt adapter가 headers 속성을 요구함
                self.headers = flask_request.headers
                
            def get_json(self, silent=False):
                return self.flask_request.get_json(silent=silent)
            
            def get_data(self, as_text=False):
                """Slack Bolt가 요구하는 get_data 메서드"""
                return self.flask_request.get_data(as_text=as_text)
        
        wrapped_request = FlaskRequestWrapper(request)
        return handler.handle(wrapped_request)
    except Exception as e:
        logging.error(f"Error handling Slack request: {e}", exc_info=True)
        return (f"Error: {str(e)}", 500)

@app.route('/worker', methods=['POST'])
def worker_endpoint():
    """워커 엔드포인트"""
    import worker_main
    class FlaskRequest:
        def get_json(self, silent=False):
            return request.get_json(silent=silent)
    result = worker_main.worker(FlaskRequest())
    if isinstance(result, tuple):
        return result
    return (result, 200)

@app.route('/tmap', methods=['GET'])
def tmap_redirect():
    """T-map 앱 리다이렉트 핸들러"""
    from urllib.parse import quote
    import textwrap
    from flask import Response
    
    addr = request.args.get("addr", "")
    if not addr:
        return ("주소 파라미터가 필요합니다.", 400)
    
    encoded_addr = quote(addr)
    android_intent = f"intent://search?name={encoded_addr}#Intent;scheme=tmap;package=com.skt.tmap.ku;end;"
    ios_scheme = f"tmap://search?name={encoded_addr}"
    fallback_web = f"https://tmapapi.sktelecom.com/main/map.html?q={encoded_addr}"
    
    html = textwrap.dedent(f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>T-map 열기</title>
      <script>
        function isAndroid() {{ return /Android/i.test(navigator.userAgent); }}
        function isIOS() {{ return /iPhone|iPad|iPod/i.test(navigator.userAgent); }}
        function openApp() {{
          var tried = false;
          if (isAndroid()) {{
            tried = true;
            window.location.href = "{android_intent}";
          }} else if (isIOS()) {{
            tried = true;
            window.location.href = "{ios_scheme}";
          }}
          setTimeout(function() {{
            window.location.href = "{fallback_web}";
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
    return Response(html, mimetype='text/html; charset=utf-8')

# main.py는 이미 위에서 import했으므로 여기서는 중복 import 제거
# handler가 None이면 에러 로깅
if handler is None:
    logging.error("CRITICAL: Handler is None. Slack events will fail!")
    logging.error("Please check the logs above for import errors.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
