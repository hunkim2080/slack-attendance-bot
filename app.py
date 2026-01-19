"""
Render 배포용 메인 진입점
main.py의 모든 기능을 Flask 앱으로 통합
"""
import os
import sys
from flask import Flask, request

# main.py를 모듈로 import
# main.py가 functions_framework를 사용하지만, 우리는 Flask로 래핑할 것
app = Flask(__name__)

# main.py를 import하기 전에 환경 설정
# main.py의 slack_handler를 Flask로 래핑

@app.route('/', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "ok", "service": "slack-attendance-worker"}, 200

@app.route('/slack/events', methods=['POST'])
@app.route('/slack/commands', methods=['POST'])
@app.route('/slack/interactive', methods=['POST'])
def slack_handler():
    """Slack 모든 요청 처리"""
    # main.py의 handler를 사용
    # main.py를 import하면 자동으로 핸들러가 등록됨
    try:
        # main.py를 동적으로 import
        import importlib.util
        spec = importlib.util.spec_from_file_location("main", "main.py")
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        
        # Flask request를 main.py의 handler가 기대하는 형식으로 변환
        class FlaskRequestWrapper:
            def __init__(self, flask_request):
                self.flask_request = flask_request
                self.method = flask_request.method
                self.args = flask_request.args
                
            def get_json(self, silent=False):
                return self.flask_request.get_json(silent=silent)
        
        wrapped_request = FlaskRequestWrapper(request)
        return main.handler.handle(wrapped_request)
    except Exception as e:
        import logging
        logging.error(f"Error handling Slack request: {e}")
        return ("Error", 500)

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

# main.py를 import하여 모든 핸들러 등록
# 이렇게 하면 main.py의 @slack_app.command, @slack_app.action 등이 자동으로 등록됨
try:
    # main.py를 import (하지만 functions_framework 부분은 실행되지 않음)
    import main
    # main.py의 slack_app을 사용하도록 설정
    # 하지만 이미 위에서 handler.handle()을 사용하므로 자동으로 작동함
except Exception as e:
    import logging
    logging.warning(f"Could not fully import main.py: {e}")
    logging.info("Some features may not work. Using worker_main only.")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
