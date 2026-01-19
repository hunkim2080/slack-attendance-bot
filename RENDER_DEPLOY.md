# Render 배포 가이드

## 📋 사전 준비

1. **Render 계정 생성**
   - https://render.com 에서 가입
   - 무료 플랜 사용 가능 (제한 있음)

2. **GitHub 저장소 준비**
   - 코드를 GitHub에 푸시해야 함
   - Render는 GitHub와 연동하여 배포

## 🚀 배포 단계

### 1단계: GitHub에 코드 푸시

```bash
cd slack-attendance-bot
git add .
git commit -m "Render 배포 준비"
git push origin main
```

### 2단계: Render에서 Web Service 생성

1. **Render 대시보드 접속**
   - https://dashboard.render.com

2. **"New +" 버튼 클릭 → "Web Service" 선택**

3. **GitHub 저장소 연결**
   - "Connect GitHub" 클릭
   - 저장소 선택: `slack-attendance-bot`

4. **서비스 설정**
   - **Name**: `slack-attendance-worker` (원하는 이름)
   - **Region**: `Singapore` (한국과 가까움)
   - **Branch**: `main`
   - **Root Directory**: `slack-attendance-bot` (저장소 루트가 프로젝트 루트면 비워두기)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: 다음 중 하나 선택:
     - `python app.py` (간단한 방법)
     - `gunicorn app:app --bind 0.0.0.0:$PORT` (프로덕션 권장)
     - 비워두기 (Procfile 자동 사용)
   - **Plan**: `Free` (무료 플랜)

### 3단계: 환경 변수 설정

Render 대시보드에서 "Environment" 탭으로 이동하여 다음 환경 변수들을 추가:

#### 필수 환경 변수

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SPREADSHEET_KEY=your-google-sheets-id
```

#### Google Sheets 인증 (선택 1: 서비스 계정 JSON)

```
GCF_CREDENTIALS={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
```

**주의**: JSON을 한 줄로 만들어야 함 (줄바꿈 제거)

#### Google Sheets 인증 (선택 2: OAuth2 - 더 간단)

서비스 계정 대신 OAuth2를 사용하려면 `sheets_handler.py`를 수정해야 할 수 있습니다.

#### 선택적 환경 변수

```
SITE_ADDRESS=기본 현장 주소
GOOGLE_CALENDAR_ID=캘린더 ID (선택)
WEATHER_API_KEY=기상청 API 키 (선택)
ADMIN_SLACK_IDS=U123456,U789012 (관리자 Slack ID, 쉼표 구분)
GCP_PROJECT=your-gcp-project (선택)
TASKS_LOCATION=asia-northeast3 (선택)
```

### 4단계: 배포 확인

1. **배포 로그 확인**
   - Render 대시보드에서 "Logs" 탭 확인
   - 빌드 및 실행 로그 확인

2. **서비스 URL 확인**
   - Render 대시보드에서 서비스 URL 확인
   - 예: `https://slack-attendance-worker.onrender.com`

3. **헬스 체크**
   - 브라우저에서 `https://your-service-url.onrender.com` 접속
   - 404 또는 빈 응답이 나오면 정상 (worker는 POST만 받음)

### 5단계: Slack Webhook URL 업데이트

**중요**: `main.py`에서 `WORKER_URL` 환경 변수를 설정해야 합니다.

1. **Render 서비스 URL 복사**
   - 예: `https://slack-attendance-worker.onrender.com`

2. **main.py의 WORKER_URL 설정**
   - Google Cloud Functions에서 환경 변수로 설정
   - 또는 `main.py`에서 직접 설정

```python
WORKER_URL = os.environ.get("WORKER_URL", "https://slack-attendance-worker.onrender.com/worker")
```

3. **Slack 앱 설정 확인**
   - Slack 앱의 Webhook URL이 `main.py`를 가리키는지 확인
   - `main.py`는 Cloud Tasks를 통해 Render worker를 호출

## 🔧 문제 해결

### 문제 1: 배포 실패

**증상**: 빌드 실패

**해결**:
- `requirements.txt` 확인
- Python 버전 확인 (`runtime.txt`)
- 로그에서 에러 메시지 확인

### 문제 2: 서비스가 시작되지 않음

**증상**: 서비스가 계속 재시작됨

**해결**:
- `Procfile`의 Start Command 확인
- 포트가 `$PORT` 환경 변수를 사용하는지 확인
- 로그에서 에러 메시지 확인

### 문제 3: 환경 변수 오류

**증상**: Google Sheets 연결 실패

**해결**:
- `GCF_CREDENTIALS`가 올바른 JSON 형식인지 확인
- JSON이 한 줄로 되어 있는지 확인 (줄바꿈 없음)
- 서비스 계정 이메일이 Google Sheets에 공유되어 있는지 확인

### 문제 4: 무료 플랜 슬립 모드

**증상**: 첫 요청이 느림

**원인**: Render 무료 플랜은 15분 동안 요청이 없으면 슬립 모드로 전환

**해결**:
- 첫 요청은 약 30초 정도 걸릴 수 있음 (정상)
- 항상 켜두려면 유료 플랜 필요 ($7/월)

## 💰 비용

### 무료 플랜
- ✅ 무료
- ⚠️ 15분 비활성 시 슬립 모드
- ⚠️ 첫 요청 지연 (30초 정도)
- ✅ 직원 2명 규모면 충분

### 유료 플랜 ($7/월)
- ✅ 항상 켜져 있음
- ✅ 빠른 응답
- ✅ 더 많은 리소스

## 📝 참고사항

1. **무료 플랜 제한**
   - 월 750시간 무료 (하루 24시간 = 720시간이므로 거의 항상 켜둘 수 있음)
   - 슬립 모드: 15분 비활성 시 자동 슬립
   - 첫 요청 지연: 슬립 모드에서 깨어날 때 약 30초 소요

2. **보안**
   - 환경 변수는 Render 대시보드에서만 관리
   - GitHub에 민감한 정보 커밋하지 않기

3. **모니터링**
   - Render 대시보드에서 로그 확인
   - 에러 발생 시 알림 설정 가능

## 🔄 업데이트 방법

코드를 수정한 후:

```bash
git add .
git commit -m "업데이트 내용"
git push origin main
```

Render가 자동으로 감지하여 재배포합니다.
