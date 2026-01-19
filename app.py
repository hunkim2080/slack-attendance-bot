"""
Render 배포용 메인 진입점
worker_main.py의 worker 함수를 Flask 앱으로 래핑
"""
import os
from flask import Flask, request
import worker_main

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "ok", "service": "slack-attendance-worker"}, 200

@app.route('/worker', methods=['POST'])
def worker_endpoint():
    """워커 엔드포인트 - worker_main.worker를 호출"""
    # functions_framework의 request 객체를 Flask request로 변환
    class FlaskRequest:
        def get_json(self, silent=False):
            return request.get_json(silent=silent)
    
    flask_request = FlaskRequest()
    return worker_main.worker(flask_request)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
