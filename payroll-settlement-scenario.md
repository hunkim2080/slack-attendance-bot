# /급여정산 명령어 시나리오

## 전체 흐름

### 1단계: 명령어 실행
```
관리자 → /급여정산 또는 /급여정산 2024-12
```

### 2단계: 권한 및 파라미터 확인
- ✅ 관리자 권한 체크 (ADMIN_SLACK_IDS)
- ✅ 날짜 파싱:
  - 인자가 있으면: `/급여정산 2024-12` → 2024년 12월
  - 인자가 없으면: 현재 년월 (예: 2024년 12월)

### 3단계: 급여 계산
```python
payrolls = sheets_handler.calculate_all_payrolls(year, month)
```

**계산 항목:**
- `get_all_users()`: UserMaster 시트에서 모든 사용자 조회
- 각 사용자별로:
  - `calculate_monthly_payroll()`: 기본 급여 계산 (일자별 단가 적용)
  - `get_commission()`: 인센티브(격려금) 계산
  - `calculate_transportation_allowance()`: 교통비 계산 (근무일수 × 10,000원)
  - `total_pay = base_pay + commission + transportation`

### 4단계: 미리보기 메시지 표시 (Ephemeral - 관리자에게만 표시)
```
📊 **2024년 12월 급여 정산 미리보기**

• 총 인원: 3명
• 총 근무일수: 25일
• 총 급여액: 5,000,000원

**상세 내역:**
• 제이쓴: 10일, 1,400,000원
• 조세연: 8일, 1,040,000원
• 이동환: 7일, 910,000원

[✅ 전 직원 발송] 버튼
```

### 5단계: "✅ 전 직원 발송" 버튼 클릭
- `handle_send_payrolls` 액션 핸들러 실행

### 6단계: 각 직원에게 DM 발송

**각 직원별로:**
1. Slack_ID 확인 (`payroll['slack_id']`)
2. 개인별 급여 명세서 메시지 생성:
   - 총 지급액
   - 근무 내역 (일당, 총 출근일수, 계산식, 교통비)
   - 인센티브 (총액, 상세 내역)
   - 다음 일당 인상일 정보
3. `client.chat_postMessage(channel=slack_id, ...)` 로 DM 발송

**DM 메시지 예시:**
```
📋 **[제이쓴님 2024년 12월 급여 명세서]**

💰 **총 지급액: 140만원**

📅 **근무 내역**
일당: 13만원(45일 근무시 인상)
총 출근일수: 10일
계산: 13만원 × 10일 = 130만원
교통비: 10만원

💎 **인센티브**
총 인센티브: 0만원 (0만원)

🙌 한 달 동안 고생 많으셨습니다!
```

### 7단계: 발송 결과 요약 (관리자에게 Ephemeral)
```
✅ 급여 명세서 발송 완료!
• 성공: 3명
• 실패: 0명
```

## 코드 흐름도

```
/급여정산
  ↓
handle_payroll_settlement()
  ├─ 관리자 권한 체크
  ├─ 년월 파싱
  ├─ calculate_all_payrolls(year, month)
  │   ├─ get_all_users()
  │   └─ 각 사용자별:
  │       ├─ calculate_monthly_payroll()
  │       ├─ get_commission()
  │       └─ calculate_transportation_allowance()
  ├─ 미리보기 메시지 생성
  └─ Ephemeral 메시지 + 버튼 전송
      ↓
  [✅ 전 직원 발송] 버튼 클릭
      ↓
handle_send_payrolls()
  ├─ 관리자 권한 체크
  ├─ calculate_all_payrolls() 재계산
  └─ 각 직원별:
      ├─ 급여 명세서 메시지 생성
      ├─ get_total_work_days() (다음 인상일 계산용)
      ├─ get_commission_details() (인센티브 상세)
      └─ chat_postMessage() → DM 발송
  └─ 발송 결과 요약 전송
```

## 주요 함수 설명

### `calculate_all_payrolls(year, month)`
- **위치**: `sheets_handler.py`
- **기능**: 모든 사용자의 급여를 계산
- **반환값**: `[{"name": str, "slack_id": str, "work_days": int, "base_pay": int, "commission": int, "transportation": int, "total_pay": int}, ...]`

### `calculate_monthly_payroll(user_name, year, month)`
- **위치**: `sheets_handler.py`
- **기능**: 개별 사용자의 월급 계산 (일자별 단가 적용)
- **반환값**: `(total_pay, work_days, daily_breakdown)`

### `get_commission(user_name, year, month)`
- **위치**: `sheets_handler.py`
- **기능**: 특정 월의 인센티브 총액 조회
- **반환값**: `int` (금액)

### `calculate_transportation_allowance(work_days)`
- **위치**: `sheets_handler.py`
- **기능**: 교통비 계산 (근무일수 × 10,000원)
- **반환값**: `int` (금액)

## 사용 예시

### 예시 1: 이번 달 급여 정산
```
/급여정산
```
→ 현재 년월의 급여를 계산하고 미리보기 표시

### 예시 2: 특정 월 급여 정산
```
/급여정산 2024-11
```
→ 2024년 11월의 급여를 계산하고 미리보기 표시

## 주의사항

1. **관리자 전용**: ADMIN_SLACK_IDS에 등록된 사용자만 사용 가능
2. **근무일이 0인 사용자는 제외**: `calculate_all_payrolls()`에서 `work_days == 0`인 경우 건너뜀
3. **Slack_ID가 없는 사용자는 DM 발송 실패**: `fail_count`에 포함
4. **Ephemeral 메시지**: 미리보기와 결과 요약은 명령어 실행자에게만 표시됨









