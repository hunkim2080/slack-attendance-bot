# Slack 출결 봇 GAS 전환 PRD (Product Requirements Document)

## 1. 프로젝트 개요

### 1.1 프로젝트명
**게임화 출퇴근 및 급여 정산 시스템 (Slack Bot)**

### 1.2 프로젝트 목적
- 현장 근무자의 출퇴근 기록 자동화
- 게임화 요소를 통한 근무 동기 부여 (레벨, 경험치, 각성 단계)
- 급여 정산 자동화 (계단식 일당 적용)
- 자재 사용 대장 관리
- 발주 관리 시스템

### 1.3 전환 목표
**Google Cloud Functions (Python) → Google Apps Script (GAS) 전환**

**전환 이유:**
- 비용 절감 (GAS는 무료 할당량 제공)
- 유지보수 간소화 (코드가 Google Workspace 내부에 위치)
- 배포 프로세스 단순화
- Google Sheets와의 네이티브 통합

---

## 2. 현재 시스템 아키텍처

### 2.1 현재 기술 스택
- **언어**: Python 3.x
- **프레임워크**: 
  - Slack Bolt (Slack 앱 프레임워크)
  - Flask (HTTP 서버)
  - Google Cloud Functions
- **주요 라이브러리**:
  - `slack-bolt`: Slack 앱 개발
  - `google-api-python-client`: Google API 클라이언트
  - `google-cloud-tasks`: 비동기 작업 큐
  - `requests`: HTTP 요청
  - `pytz`: 시간대 처리
- **인프라**: Google Cloud Functions (2세대)
- **데이터 저장소**: Google Sheets

### 2.2 현재 시스템 구조
```
slack-attendance-bot/
├── main.py              # Slack 앱 메인 (GCF 진입점)
├── worker_main.py       # 비동기 작업 처리 (출퇴근 기록, 메시지 전송)
├── sheets_handler.py    # Google Sheets 연동 로직
├── config.py            # 설정 파일
└── env.yaml             # 환경 변수
```

### 2.3 데이터 흐름
1. **Slack 사용자** → Slack 명령어/액션 입력
2. **GCF (main.py)** → 요청 수신 및 검증
3. **Cloud Tasks** → 비동기 작업 큐에 등록 (선택적)
4. **GCF (worker_main.py)** → 실제 처리 (Sheets 기록, 메시지 전송)
5. **Google Sheets** → 데이터 저장/조회
6. **Slack** → 결과 메시지 전송

---

## 3. 기능 명세서

### 3.1 Slack 명령어 (Slash Commands)

#### 3.1.1 `/출근`
**기능**: 출근 기록 및 게임화 메시지 전송

**처리 흐름**:
1. 사용자 인증 (Slack ID → UserMaster 시트에서 한글 이름 조회)
2. Google Calendar에서 오늘 일정의 현장 주소 조회
3. 날씨 정보 조회 (기상청 API)
4. AttendanceLog 시트에 출근 기록 추가
5. 게임화 정보 조회 (레벨, 각성 단계, 칭호, 이번 달 근무일수 등)
6. Block Kit 메시지 생성 및 전송 (T-map 버튼 포함)

**메시지 구성 요소**:
- 출근 확인 메시지
- 날씨 정보 (강수확률, 강수형태)
- 현장 주소 (여러 개일 경우 모두 표시)
- 이번 달 기록 (출동 횟수, 정산일 D-Day)
- 등급 정보 (각성 단계, 레벨, 칭호)
- T-map 버튼 (현장 주소로 이동)

**관련 함수**:
- `handle_check_in()` (main.py)
- `_handle_check_in()` (worker_main.py)
- `record_check_in()` (sheets_handler.py)
- `_get_today_site_addresses()` (worker_main.py)
- `_get_weather_forecast()` (worker_main.py)

---

#### 3.1.2 `/퇴근`
**기능**: 퇴근 기록 및 게임화 메시지 전송

**처리 흐름**:
1. 사용자 인증
2. AttendanceLog 시트에 퇴근 기록 추가
3. 레벨업 체크 (이전 근무일수 vs 현재 근무일수)
4. 각성 단계 달성 체크 (45일, 90일, 135일, 180일, 225일, 270일)
5. 레벨업/각성 달성 시 DM 발송
6. 일급 계산 및 게임화 메시지 전송
7. 버튼 추가 (귀환스킬발동, 자재사용대장, 현장사진 업로드)

**메시지 구성 요소**:
- 퇴근 확인 메시지
- 일급 정보
- 각성 경험치 진행률
- 버튼 (귀환스킬발동, 자재사용대장, 현장사진 업로드)

**특수 기능**:
- 레벨업 시 DM 발송
- 각성 단계 달성 시 컷신 메시지 DM 발송

**관련 함수**:
- `handle_check_out()` (main.py)
- `_handle_check_out()` (worker_main.py)
- `record_check_out()` (sheets_handler.py)
- `check_level_up()` (sheets_handler.py)
- `get_awakening_cutscene()` (sheets_handler.py)

---

#### 3.1.3 `/급여정산` (관리자 전용)
**기능**: 월별 급여 정산 및 명세서 발송

**파라미터**:
- 없음: 현재 년월
- `YYYY-MM`: 특정 년월 (예: `/급여정산 2024-12`)

**처리 흐름**:
1. 관리자 권한 체크
2. 년월 파싱
3. 모든 사용자의 급여 계산:
   - 기본 급여 (일자별 단가 적용)
   - 인센티브 (격려금)
   - 교통비 (근무일수 × 10,000원)
4. 미리보기 메시지 표시 (Ephemeral)
5. "전 직원 발송" 버튼 클릭 시 각 직원에게 DM 발송

**급여 계산 로직**:
- 일당은 계단식 인상 (총 근무일수 기준)
- 월 중간에 단가가 오르는 경우 일자별로 계산
- PAY_RATES 배열 참조

**관련 함수**:
- `handle_payroll_settlement()` (main.py)
- `handle_send_payrolls()` (main.py)
- `calculate_all_payrolls()` (sheets_handler.py)
- `calculate_monthly_payroll()` (sheets_handler.py)
- `get_commission()` (sheets_handler.py)
- `get_commission_details()` (sheets_handler.py)

---

#### 3.1.4 `/출근로그` (관리자 전용)
**기능**: 특정 사용자의 출근 로그 조회

**처리 흐름**:
1. 관리자 권한 체크
2. 사용자 선택 메뉴 표시 (UserMaster에서 모든 사용자 조회)
3. 선택된 사용자의 출근 기록 조회
4. 출근 로그 목록 표시 (Ephemeral)

**관련 함수**:
- `handle_attendance_logs()` (main.py)
- `handle_select_user_attendance()` (main.py)
- `get_attendance_logs()` (sheets_handler.py)

---

#### 3.1.5 `/정산내역` (관리자 전용)
**기능**: 특정 사용자의 모든 급여 명세서 조회

**처리 흐름**:
1. 관리자 권한 체크
2. 사용자 선택 메뉴 표시
3. 선택된 사용자의 모든 월별 급여 내역 조회
4. 정산 내역 목록 표시 (Ephemeral)

**관련 함수**:
- `handle_payroll_history()` (main.py)
- `handle_select_user_payroll()` (main.py)
- `get_user_payroll_history()` (sheets_handler.py)

---

#### 3.1.6 `/발주목록` (관리자 전용)
**기능**: 미처리 발주 목록 조회 및 관리

**처리 흐름**:
1. 관리자 권한 체크
2. 현재 월의 미처리 발주 목록 조회 (발주완료 처리시간이 비어있는 항목)
3. 발주 목록 표시 및 버튼 제공:
   - "문자 발송 후 목록 최신화"
   - "목록 최신화"
4. 발주 완료 번호 입력 후 최신화

**관련 함수**:
- `handle_order_list()` (main.py)
- `handle_send_order_message()` (main.py)
- `handle_refresh_order_list()` (main.py)
- `handle_update_order_list()` (main.py)
- `get_pending_material_orders()` (sheets_handler.py)
- `mark_orders_completed()` (sheets_handler.py)

---

#### 3.1.7 `/hello` (테스트용)
**기능**: 연결 테스트

**관련 함수**:
- `handle_hello()` (main.py)

---

#### 3.1.8 `/netcheck` (관리자 전용, 테스트용)
**기능**: 네트워크 진단

**관련 함수**:
- `handle_netcheck()` (main.py)

---

### 3.2 Slack 액션 (Interactive Components)

#### 3.2.1 자재사용대장 관련 액션

##### `open_material_log`
**기능**: 자재사용대장 버튼 클릭 → 방 선택 화면 표시

**처리 흐름**:
1. 방 선택 체크박스 표시 (Ephemeral)
2. "사용량 기록시작" 버튼 제공

**방 목록**:
- 거실 화장실
- 안방 화장실
- 거실
- 세탁실
- 베란다
- 현관

**관련 함수**:
- `handle_open_material_log()` (main.py)

---

##### `select_rooms`
**기능**: 방 체크박스 선택 (단순 ack)

**관련 함수**:
- `handle_select_rooms()` (main.py)

---

##### `start_material_input`
**기능**: 입력 시작 버튼 클릭 → 첫 번째 방의 색상 선택 화면 표시

**처리 흐름**:
1. 선택된 방 목록 가져오기
2. 첫 번째 방의 색상 선택 화면 표시

**관련 함수**:
- `handle_start_material_input()` (main.py)
- `_open_color_selection_modal()` (main.py)

---

##### `select_color_{색상코드}` (정규식)
**기능**: 색상 선택 → 사용량 입력 화면 표시

**색상 코드**:
- 110, 111, 112, 113, 130, 기타

**처리 흐름**:
1. 색상 선택
2. 사용량 입력 화면 표시 (Ephemeral)
3. "저장" 버튼 제공

**관련 함수**:
- `handle_select_color()` (main.py)

---

##### `select_custom_color`
**기능**: "기타" 색상 선택 → 색상 직접 입력 화면 표시

**관련 함수**:
- `handle_select_custom_color()` (main.py)

---

##### `confirm_custom_color`
**기능**: 기타 색상 확인 → 사용량 입력으로 진행

**관련 함수**:
- `handle_confirm_custom_color()` (main.py)

---

##### `save_material_usage`
**기능**: 사용량 저장 → MaterialLog 시트에 기록

**처리 흐름**:
1. 사용량 입력값 검증
2. MaterialLog 시트에 기록
3. 현재 방 완료 안내
4. 다음 방이 있으면 색상 선택 화면 표시
5. 모든 방 완료 시 발주 필요 여부 확인 화면 표시

**관련 함수**:
- `handle_save_material_usage()` (main.py)
- `record_material_usage()` (sheets_handler.py)

---

##### `material_order_required`
**기능**: 발주 필요 - 있음 버튼 클릭 → 발주 내용 입력 화면 표시

**관련 함수**:
- `handle_material_order_required()` (main.py)

---

##### `material_order_not_required`
**기능**: 발주 필요 - 없음 버튼 클릭 → 폴더 생성 버튼 표시

**관련 함수**:
- `handle_material_order_not_required()` (main.py)

---

##### `save_material_order`
**기능**: 발주 내용 저장 → MaterialOrder 시트에 기록

**관련 함수**:
- `handle_save_material_order()` (main.py)
- `record_material_order()` (sheets_handler.py)

---

#### 3.2.2 현장사진 관련 액션

##### `create_photo_folder`
**기능**: 현장사진 폴더 생성 → Google Drive에 폴더 생성

**처리 흐름**:
1. 오늘 날짜의 Google Calendar에서 현장 주소 조회
2. Google Drive에 폴더 생성 (폴더명: `YYYY.MM.DD 건물명`)
3. 폴더 URL과 버튼 제공:
   - "현장사진 업로드" (폴더 URL 링크)
   - "경험치 획득(퇴근)" (퇴근 처리)

**관련 함수**:
- `handle_create_photo_folder()` (main.py)
- `create_site_photo_folder()` (sheets_handler.py)

---

##### `check_out_from_photo`
**기능**: 경험치 획득(퇴근) 버튼 클릭 → 퇴근 처리

**관련 함수**:
- `handle_check_out_from_photo()` (main.py)

---

#### 3.2.3 발주 관리 관련 액션

##### `send_order_message`
**기능**: 문자 발송 후 목록 최신화 버튼 클릭 → 관리자에게 발주 메시지 DM 발송

**관련 함수**:
- `handle_send_order_message()` (main.py)

---

##### `refresh_order_list`
**기능**: 목록 최신화 버튼 클릭 → 발주 완료 번호 입력 화면 표시

**관련 함수**:
- `handle_refresh_order_list()` (main.py)

---

##### `update_order_list`
**기능**: 발주 완료 번호 입력 후 최신화 → MaterialOrder 시트 업데이트

**처리 흐름**:
1. 완료 번호 파싱 (예: "1,3" → [1, 3])
2. 해당 행의 발주완료 처리시간 업데이트
3. 잔여 발주 목록 표시

**관련 함수**:
- `handle_update_order_list()` (main.py)
- `mark_orders_completed()` (sheets_handler.py)

---

##### `confirm_order_update`
**기능**: 확인 버튼 클릭 → 완료 메시지

**관련 함수**:
- `handle_confirm_order_update()` (main.py)

---

#### 3.2.4 급여 정산 관련 액션

##### `send_payrolls`
**기능**: 전 직원 발송 버튼 클릭 → 각 직원에게 급여 명세서 DM 발송

**관련 함수**:
- `handle_send_payrolls()` (main.py)

---

##### `select_user_attendance`
**기능**: 출근 로그 조회 - 사용자 선택

**관련 함수**:
- `handle_select_user_attendance()` (main.py)

---

##### `select_user_payroll`
**기능**: 정산 내역 조회 - 사용자 선택

**관련 함수**:
- `handle_select_user_payroll()` (main.py)

---

### 3.3 View 제출 핸들러

#### `material_quantity_submit`
**기능**: 사용량 입력 모달 제출 (현재는 사용하지 않음, 에러 방지용)

**관련 함수**:
- `handle_material_quantity_submit()` (main.py)

---

## 4. 데이터 구조 (Google Sheets)

### 4.1 시트 구조

#### 4.1.1 `AttendanceLog` (출퇴근 기록)
**컬럼 구조**:
| A | B | C | D | E |
|---|---|---|---|---|
| 날짜 | 이름 | 시간 | 구분 | 비고 |

**데이터 예시**:
```
2024-12-17 | 제이쓴 | 08:30:00 | 출근 | 서울시 강남구 테헤란로 123
2024-12-17 | 제이쓴 | 18:00:00 | 퇴근 | 
```

**주요 기능**:
- 출퇴근 기록 추가
- 날짜별 출퇴근 쌍 확인 (근무일수 계산)
- 월별 근무일수 계산

---

#### 4.1.2 `UserMaster` (사용자 마스터)
**컬럼 구조**:
| A | B | C | F |
|---|---|---|---|
| 이름 | Slack_ID | 기본근무일수 | 주소 |

**데이터 예시**:
```
제이쓴 | U059H02UNF9 | 0 | 서울시 강남구 역삼동
```

**주요 기능**:
- Slack ID → 한글 이름 매핑
- 사용자 정보 조회
- 모든 사용자 목록 조회

---

#### 4.1.3 `MaterialLog` (자재 사용 기록)
**컬럼 구조**:
| A | B | C | D | E |
|---|---|---|---|---|
| 날짜시간 | 이름 | 방 이름 | 색상 코드 | 사용량 |

**데이터 예시**:
```
2024-12-17 14:30:00 | 제이쓴 | 거실 화장실 | 110 | 200
```

**주요 기능**:
- 자재 사용량 기록
- 방별, 색상별 사용량 집계

---

#### 4.1.4 `MaterialOrder` (발주 관리)
**컬럼 구조**:
| A | B | C | D |
|---|---|---|---|
| 날짜시간 | 이름 | 발주내용 | 발주완료 처리시간 |

**데이터 예시**:
```
2024-12-17 15:00:00 | 제이쓴 | 빅라이언 100, 짤주머니 한 박스 | 
2024-12-17 16:00:00 | 제이쓴 | 빅라이언 100, 짤주머니 한 박스 | 2024-12-17 18:00:00
```

**주요 기능**:
- 발주 요청 기록
- 발주 완료 처리 (D열 업데이트)
- 미처리 발주 목록 조회

---

#### 4.1.5 `Incentive` (인센티브/격려금)
**컬럼 구조**:
| A | B | C | D |
|---|---|---|---|
| 날짜 | 이름 | 금액 | 내용 |

**데이터 예시**:
```
2024-12-17 | 제이쓴 | 50000 | 특별 보너스
```

**주요 기능**:
- 월별 인센티브 총액 계산
- 인센티브 상세 내역 조회

---

## 5. 게임화 시스템

### 5.1 레벨 시스템
**계산식**: `레벨 = int(총 근무일수 / 3)`

**레벨별 칭호**:
- 1~5: 현장 참관자, 작업 보조, 도구 전달자, 정리 담당, 준비 인원
- 6~10: 초급 보조, 현장 적응 중, 기본 작업 보조, 반복 작업 가능, 현장 투입 인원
- ... (100단계까지)
- 100: 줄눈 마스터

**레벨업 체크**:
- 퇴근 시에만 체크 (출근은 0.5일, 퇴근해야 1일 완성)
- 레벨업 시 DM 발송

---

### 5.2 각성 단계 시스템
**단계별 구간**:
- 🟤 브론즈: 0~44일
- ⚪ 실버: 45~89일
- 🟡 골드: 90~134일
- 🔵 플래티넘: 135~179일
- 🟣 다이아: 180~224일
- 🔴 레전드: 225~269일
- 👑 마스터: 270일 이상

**각성 단계 달성 시**:
- 컷신 메시지 DM 발송
- 일당 인상 적용

---

### 5.3 급여 시스템

#### 5.3.1 일당 계단식 인상
**PAY_RATES 배열**:
```python
[
    (1, 45, 130000),      # 1~45일: 130,000원
    (45, 90, 150000),    # 45~90일: 150,000원
    (90, 135, 170000),   # 90~135일: 170,000원
    (135, 180, 190000),  # 135~180일: 190,000원
    (180, 225, 210000),   # 180~225일: 210,000원
    (225, 270, 230000),   # 225~270일: 230,000원
    (270, float('inf'), 250000),  # 270일~: 250,000원
]
```

**계산 로직**:
- 월 중간에 단가가 오르는 경우 일자별로 계산
- 각 근무일의 총 근무일수 기준으로 일당 결정

#### 5.3.2 교통비
**계산식**: `근무일수 × 10,000원`

#### 5.3.3 인센티브
- Incentive 시트에서 월별 합계 계산
- 상세 내역 제공

---

### 5.4 경험치 진행률
**다음 레벨까지 진행률**:
- 현재 레벨에서 진행된 일수 / 레벨당 필요한 일수
- 진행바: `■■■■■■■■■■` (10칸)

**다음 각성까지 진행률**:
- 현재 단계에서 진행된 일수 / 다음 단계까지 필요한 일수
- 진행바: `■■■■■■■■■■` (10칸)

---

## 6. 외부 API 연동

### 6.1 Slack API
**사용 기능**:
- Slash Commands
- Interactive Components (Buttons, Select Menus, Modals)
- Chat API (메시지 전송)
- Users API (사용자 정보 조회)

**인증**:
- Bot Token (xoxb-)
- Signing Secret (요청 검증)

---

### 6.2 Google Sheets API
**사용 기능**:
- 시트 읽기/쓰기
- 범위 업데이트
- 행 추가

**인증**:
- 서비스 계정 (GCF_CREDENTIALS)

---

### 6.3 Google Calendar API
**사용 기능**:
- 일정 조회 (오늘 날짜)
- Location 필드에서 현장 주소 추출

**인증**:
- 서비스 계정 (GCF_CREDENTIALS)

---

### 6.4 Google Drive API
**사용 기능**:
- 폴더 생성
- 폴더 URL 생성

**인증**:
- 서비스 계정 (GCF_CREDENTIALS)

---

### 6.5 기상청 단기예보 API
**사용 기능**:
- 오후 시간대(12시~18시) 강수확률 조회
- 강수형태 조회 (비, 눈, 없음)

**API 엔드포인트**:
```
http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst
```

**파라미터**:
- serviceKey: WEATHER_API_KEY
- base_date: YYYYMMDD
- base_time: HH00
- nx, ny: 격자 좌표
- dataType: JSON

**인증**:
- API Key (WEATHER_API_KEY)

---

### 6.6 T-map 딥링크
**기능**:
- Android: Intent URL
- iOS: URL Scheme
- Fallback: 웹 지도

**URL 형식**:
```
Android: intent://search?name={주소}#Intent;scheme=tmap;package=com.skt.tmap.ku;end;
iOS: tmap://search?name={주소}
Web: https://tmapapi.sktelecom.com/main/map.html?q={주소}
```

---

## 7. GAS 전환 계획

### 7.1 기술 스택 비교

| 항목 | 현재 (GCF + Python) | 전환 후 (GAS) |
|------|---------------------|---------------|
| 언어 | Python 3.x | JavaScript (ES6+) |
| 프레임워크 | Slack Bolt, Flask | GAS Web App |
| 배포 | Google Cloud Functions | Google Apps Script |
| 비용 | Cloud Functions 요금 | 무료 (할당량 내) |
| 인증 | 서비스 계정 JSON | GAS 내장 인증 |
| Sheets API | google-api-python-client | SpreadsheetApp (네이티브) |
| Calendar API | google-api-python-client | CalendarApp (네이티브) |
| Drive API | google-api-python-client | DriveApp (네이티브) |
| HTTP 요청 | requests | UrlFetchApp |
| 환경 변수 | os.environ | PropertiesService |
| 비동기 처리 | Cloud Tasks | Utilities.sleep() 또는 트리거 |

---

### 7.2 파일 구조 (GAS)

```
attendance-bot.gs (메인 파일)
├── doPost()                    # Slack 요청 진입점
├── handleSlashCommand()         # Slash Command 처리
├── handleInteractive()          # Interactive Component 처리
├── handleViewSubmission()       # View 제출 처리
└── 유틸리티 함수들

sheets-handler.gs
├── recordCheckIn()             # 출근 기록
├── recordCheckOut()            # 퇴근 기록
├── getTotalWorkDays()          # 총 근무일수 계산
├── calculateLevel()            # 레벨 계산
├── getUserTitle()              # 칭호 조회
├── calculateMonthlyPayroll()   # 월급 계산
├── getCommission()             # 인센티브 조회
├── recordMaterialUsage()       # 자재 사용 기록
├── recordMaterialOrder()      # 발주 기록
├── getPendingMaterialOrders()  # 미처리 발주 조회
├── markOrdersCompleted()       # 발주 완료 처리
├── createSitePhotoFolder()     # 폴더 생성
└── 기타 Sheets 관련 함수들

worker.gs
├── handleCheckIn()             # 출근 처리 (메시지 전송)
├── handleCheckOut()            # 퇴근 처리 (메시지 전송)
├── getTodaySiteAddresses()     # 오늘 현장 주소 조회
├── getWeatherForecast()        # 날씨 정보 조회
├── sendSlackMessage()           # Slack 메시지 전송
├── sendSlackWithButtons()      # 버튼 포함 메시지 전송
├── sendSlackWithTmap()         # T-map 버튼 포함 메시지 전송
└── 기타 메시지 전송 함수들

config.gs
├── getConfig()                 # 설정 조회 (PropertiesService)
└── 상수 정의

game-system.gs
├── PAY_RATES                   # 급여 단가 배열
├── SKILL_MILESTONES            # 스킬 획득 구간
├── calculateDailyPay()         # 일당 계산
├── getAwakeningStage()         # 각성 단계 조회
├── getAwakeningProgress()      # 각성 진행률 계산
├── checkLevelUp()              # 레벨업 체크
├── getAwakeningCutscene()      # 각성 컷신 메시지
└── 기타 게임화 관련 함수들
```

---

### 7.3 주요 전환 작업

#### 7.3.1 Slack 요청 처리
**현재 (Python)**:
```python
@functions_framework.http
def slack_handler(request):
    return handler.handle(request)
```

**GAS**:
```javascript
function doPost(e) {
  // Slack 요청 검증
  const requestBody = JSON.parse(e.postData.contents);
  
  // Slash Command 처리
  if (requestBody.command) {
    return handleSlashCommand(requestBody);
  }
  
  // Interactive Component 처리
  if (requestBody.payload) {
    return handleInteractive(JSON.parse(requestBody.payload));
  }
  
  // View 제출 처리
  if (requestBody.type === 'view_submission') {
    return handleViewSubmission(requestBody);
  }
}
```

---

#### 7.3.2 환경 변수 관리
**현재 (Python)**:
```python
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SPREADSHEET_KEY = os.environ.get("SPREADSHEET_KEY")
```

**GAS**:
```javascript
function getConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    SLACK_BOT_TOKEN: props.getProperty('SLACK_BOT_TOKEN'),
    SLACK_SIGNING_SECRET: props.getProperty('SLACK_SIGNING_SECRET'),
    SPREADSHEET_KEY: props.getProperty('SPREADSHEET_KEY'),
    WEATHER_API_KEY: props.getProperty('WEATHER_API_KEY'),
    GOOGLE_DRIVE_PARENT_FOLDER_ID: props.getProperty('GOOGLE_DRIVE_PARENT_FOLDER_ID'),
    GOOGLE_CALENDAR_ID: props.getProperty('GOOGLE_CALENDAR_ID'),
    ADMIN_SLACK_IDS: props.getProperty('ADMIN_SLACK_IDS').split(','),
    SITE_ADDRESS: props.getProperty('SITE_ADDRESS')
  };
}
```

---

#### 7.3.3 Google Sheets 연동
**현재 (Python)**:
```python
service = build("sheets", "v4", credentials=creds)
service.spreadsheets().values().append(...)
```

**GAS**:
```javascript
function recordCheckIn(userName, siteAddress) {
  const sheet = SpreadsheetApp.openById(SPREADSHEET_KEY)
    .getSheetByName('AttendanceLog');
  
  const now = new Date();
  const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000)); // UTC+9
  
  sheet.appendRow([
    Utilities.formatDate(kst, 'Asia/Seoul', 'yyyy-MM-dd'),
    userName,
    Utilities.formatDate(kst, 'Asia/Seoul', 'HH:mm:ss'),
    '출근',
    siteAddress
  ]);
}
```

---

#### 7.3.4 Google Calendar 연동
**현재 (Python)**:
```python
service = build("calendar", "v3", credentials=creds)
events = service.events().list(...)
```

**GAS**:
```javascript
function getTodaySiteAddresses() {
  const calendarId = getConfig().GOOGLE_CALENDAR_ID;
  const calendar = CalendarApp.getCalendarById(calendarId);
  
  const now = new Date();
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const endOfDay = new Date(startOfDay);
  endOfDay.setDate(endOfDay.getDate() + 1);
  
  const events = calendar.getEvents(startOfDay, endOfDay);
  const addresses = events
    .map(event => event.getLocation())
    .filter(location => location && location.trim() !== '');
  
  return addresses.length > 0 ? addresses : [getConfig().SITE_ADDRESS];
}
```

---

#### 7.3.5 Google Drive 연동
**현재 (Python)**:
```python
service = build("drive", "v3", credentials=creds)
folder = service.files().create(...)
```

**GAS**:
```javascript
function createSitePhotoFolder(siteAddress) {
  const parentFolderId = getConfig().GOOGLE_DRIVE_PARENT_FOLDER_ID;
  const parentFolder = DriveApp.getFolderById(parentFolderId);
  
  const now = new Date();
  const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
  const dateStr = Utilities.formatDate(kst, 'Asia/Seoul', 'yyyy.MM.dd');
  
  const addressParts = siteAddress.split(' ');
  const buildingName = addressParts.slice(-2).join(' ');
  const folderName = `${dateStr} ${buildingName}`;
  
  const folder = parentFolder.createFolder(folderName);
  return {
    success: true,
    folderId: folder.getId(),
    folderUrl: folder.getUrl()
  };
}
```

---

#### 7.3.6 HTTP 요청
**현재 (Python)**:
```python
response = requests.get(url, params=params, timeout=10)
```

**GAS**:
```javascript
function getWeatherForecast(siteAddress) {
  const apiKey = getConfig().WEATHER_API_KEY;
  const url = 'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst';
  
  const params = {
    serviceKey: apiKey,
    numOfRows: 100,
    pageNo: 1,
    dataType: 'JSON',
    base_date: getBaseDate(),
    base_time: getBaseTime(),
    nx: getGridX(siteAddress),
    ny: getGridY(siteAddress)
  };
  
  const queryString = Object.keys(params)
    .map(key => `${key}=${encodeURIComponent(params[key])}`)
    .join('&');
  
  const response = UrlFetchApp.fetch(`${url}?${queryString}`, {
    method: 'get',
    muteHttpExceptions: true
  });
  
  return JSON.parse(response.getContentText());
}
```

---

#### 7.3.7 Slack 메시지 전송
**현재 (Python)**:
```python
slack_client.chat_postMessage(
    channel=channel_id,
    text=text,
    blocks=blocks
)
```

**GAS**:
```javascript
function sendSlackMessage(channel, text, blocks) {
  const config = getConfig();
  const url = 'https://slack.com/api/chat.postMessage';
  
  const payload = {
    channel: channel,
    text: text,
    blocks: blocks
  };
  
  const options = {
    method: 'post',
    headers: {
      'Authorization': `Bearer ${config.SLACK_BOT_TOKEN}`,
      'Content-Type': 'application/json'
    },
    payload: JSON.stringify(payload)
  };
  
  const response = UrlFetchApp.fetch(url, options);
  return JSON.parse(response.getContentText());
}
```

---

#### 7.3.8 비동기 처리
**현재 (Python)**:
- Cloud Tasks를 사용한 비동기 처리

**GAS**:
- GAS는 기본적으로 동기 처리
- 긴 작업의 경우:
  1. 즉시 응답 후 ScriptProperties에 작업 정보 저장
  2. 시간 기반 트리거로 작업 처리
  3. 또는 Utilities.sleep() 사용 (최대 6분)

**권장 방식**:
```javascript
function handleCheckIn(userId, userName, channelId) {
  // 즉시 응답
  return {
    response_type: 'ephemeral',
    text: '출근 처리 중...'
  };
  
  // 실제 처리는 별도 함수로 (또는 트리거 사용)
  processCheckInAsync(userId, userName, channelId);
}

function processCheckInAsync(userId, userName, channelId) {
  // 출근 기록 및 메시지 전송
  // ...
}
```

---

### 7.4 Slack 요청 검증

**현재 (Python)**:
- Slack Bolt가 자동으로 처리

**GAS**:
```javascript
function verifySlackRequest(timestamp, body, signature) {
  const config = getConfig();
  const signingSecret = config.SLACK_SIGNING_SECRET;
  
  const baseString = `v0:${timestamp}:${body}`;
  const hmac = Utilities.computeHmacSha256Signature(baseString, signingSecret);
  const computedSignature = 'v0=' + hmac.map(b => ('0' + (b & 0xFF).toString(16)).slice(-2)).join('');
  
  return computedSignature === signature;
}

function doPost(e) {
  const timestamp = e.parameter.X-Slack-Request-Timestamp;
  const signature = e.parameter.X-Slack-Signature;
  const body = e.postData.contents;
  
  if (!verifySlackRequest(timestamp, body, signature)) {
    return ContentService.createTextOutput('Invalid signature').setMimeType(ContentService.MimeType.TEXT);
  }
  
  // 요청 처리...
}
```

---

### 7.5 시간대 처리

**현재 (Python)**:
```python
import pytz
KST = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(KST)
```

**GAS**:
```javascript
function getKSTNow() {
  const now = new Date();
  // GAS는 기본적으로 서버 시간대 사용
  // Asia/Seoul로 변환
  const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000));
  return kst;
}

// 또는 Utilities.formatDate 사용
function formatKSTDate(date, format) {
  return Utilities.formatDate(date, 'Asia/Seoul', format);
}
```

---

## 8. 구현 우선순위

### Phase 1: 핵심 기능 (필수)
1. ✅ Slack 요청 진입점 (doPost)
2. ✅ Slack 요청 검증
3. ✅ 환경 변수 관리 (PropertiesService)
4. ✅ `/출근` 명령어
5. ✅ `/퇴근` 명령어
6. ✅ Google Sheets 연동 (출퇴근 기록)

### Phase 2: 게임화 시스템
1. ✅ 레벨 계산
2. ✅ 각성 단계 계산
3. ✅ 경험치 진행률 계산
4. ✅ 레벨업/각성 달성 체크
5. ✅ 게임화 메시지 생성

### Phase 3: 관리 기능
1. ✅ `/급여정산` 명령어
2. ✅ `/출근로그` 명령어
3. ✅ `/정산내역` 명령어
4. ✅ 급여 계산 로직

### Phase 4: 자재 관리
1. ✅ 자재사용대장 기능
2. ✅ 발주 관리 기능
3. ✅ `/발주목록` 명령어

### Phase 5: 통합 기능
1. ✅ Google Calendar 연동
2. ✅ Google Drive 연동
3. ✅ 날씨 API 연동
4. ✅ T-map 딥링크

---

## 9. 테스트 계획

### 9.1 단위 테스트
- 각 함수별 테스트
- GAS 테스트 함수 작성

### 9.2 통합 테스트
- Slack 명령어 테스트
- Interactive Component 테스트
- Sheets 연동 테스트

### 9.3 사용자 테스트
- 실제 사용자 시나리오 테스트
- 성능 테스트 (응답 시간)

---

## 10. 배포 계획

### 10.1 GAS 프로젝트 생성
1. Google Apps Script 프로젝트 생성
2. 파일 구조 생성
3. 설정 값 입력 (PropertiesService)

### 10.2 Slack App 설정
1. Webhook URL 업데이트 (GAS Web App URL)
2. Slash Commands 등록
3. Interactive Components 활성화

### 10.3 권한 설정
1. Google Sheets 접근 권한
2. Google Calendar 접근 권한
3. Google Drive 접근 권한

### 10.4 트리거 설정 (필요시)
- 시간 기반 트리거 (비동기 작업용)

---

## 11. 마이그레이션 체크리스트

### 11.1 코드 전환
- [ ] Slack 요청 처리 (doPost)
- [ ] Slack 요청 검증
- [ ] Slash Commands 핸들러
- [ ] Interactive Components 핸들러
- [ ] View 제출 핸들러
- [ ] Sheets 연동 함수
- [ ] Calendar 연동 함수
- [ ] Drive 연동 함수
- [ ] 날씨 API 연동 함수
- [ ] 게임화 시스템 함수
- [ ] 급여 계산 함수

### 11.2 설정 마이그레이션
- [ ] PropertiesService에 환경 변수 입력
- [ ] Slack App Webhook URL 업데이트
- [ ] 권한 설정 확인

### 11.3 테스트
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] 사용자 테스트

### 11.4 문서화
- [ ] 코드 주석
- [ ] 사용자 가이드
- [ ] 관리자 가이드

---

## 12. 주의사항 및 제약사항

### 12.1 GAS 제약사항
- **실행 시간 제한**: 6분 (일반), 30분 (G Suite Business 이상)
- **메모리 제한**: 250MB
- **URL Fetch 제한**: 20,000회/일
- **Sheets API 제한**: 300회/분

### 12.2 전환 시 고려사항
- **비동기 처리**: Cloud Tasks 대신 트리거 또는 즉시 처리
- **에러 처리**: try-catch로 모든 함수 감싸기
- **로깅**: Logger 서비스 사용
- **캐싱**: ScriptProperties 활용

### 12.3 성능 최적화
- Sheets 읽기 최소화 (배치 읽기)
- 불필요한 API 호출 제거
- 캐싱 활용

---

## 13. 참고 자료

### 13.1 현재 코드베이스
- `main.py`: Slack 앱 메인 로직
- `worker_main.py`: 비동기 작업 처리
- `sheets_handler.py`: Sheets 연동 로직
- `config.py`: 설정 파일

### 13.2 GAS 문서
- [Google Apps Script 가이드](https://developers.google.com/apps-script)
- [Slack API 문서](https://api.slack.com)
- [GAS 최적화 가이드](https://developers.google.com/apps-script/guides/support/best-practices)

### 13.3 관련 문서
- `payroll-settlement-scenario.md`: 급여 정산 시나리오
- `env.yaml`: 환경 변수 목록

---

## 14. 문의 및 지원

**프로젝트 담당자**: [담당자 정보]
**문의 채널**: [문의 채널]

---

**문서 버전**: 1.0
**최종 업데이트**: 2024-12-17
**작성자**: AI Assistant

