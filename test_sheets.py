# test_sheets.py

import os
import sys
import sheets_handler
import datetime

# Windows 콘솔 인코딩 설정
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def run_test():
    """Google Sheets 연동 테스트 함수"""
    print("--- Google Sheets 연동 테스트 시작 ---")
    
    # 서비스 계정 키 파일 확인
    from config import GOOGLE_JSON_KEY_PATH
    if not os.path.exists(GOOGLE_JSON_KEY_PATH):
        print(f"[오류] 서비스 계정 키 파일을 찾을 수 없습니다: {GOOGLE_JSON_KEY_PATH}")
        print("Google Cloud Console에서 서비스 계정 키를 다운로드하여 프로젝트 루트에 배치하세요.")
        return
    
    # 1. 시트에서 모든 사용자 정보 읽기 테스트
    print("\n[1단계] UserMaster 탭 읽기 테스트...")
    try:
        spreadsheet = sheets_handler.get_sheets_client()
        if spreadsheet:
            user_sheet = spreadsheet.worksheet('UserMaster')
            # 헤더 행 읽기
            headers = user_sheet.row_values(1)
            print(f"[성공] UserMaster 탭 접근 성공!")
            print(f"   헤더: {headers}")
            
            # 데이터 읽기
            users = sheets_handler.get_all_users_data()
            if users:
                print(f"   데이터 레코드: {len(users)}개")
                print(f"   첫 번째 사용자 데이터: {users[0]}")
            else:
                print("   [정보] 데이터 행이 없습니다 (헤더만 존재).")
        else:
            print("[실패] 스프레드시트 접근 실패.")
    except Exception as e:
        print(f"[실패] UserMaster 탭 읽기 오류: {e}")
        
    # 2. 출근 기록 추가 테스트
    print("\n[2단계] 출근 기록 추가 테스트...")
    test_slack_id = "U12345678" # 테스트용 슬랙 ID
    test_in_time = datetime.datetime.now().strftime('%H:%M:%S')
    test_site_name = "테스트 현장 (로컬)"
    
    success = sheets_handler.record_attendance_in(
        slack_id=test_slack_id, 
        in_time=test_in_time, 
        site_name=test_site_name
    )

    if success:
        print(f"[성공] AttendanceLog 기록 추가 성공!")
        print(f"   시트를 확인하여 [{test_slack_id}] 기록이 추가되었는지 확인하세요.")
    else:
        print("[실패] AttendanceLog 기록 추가 실패.")

if __name__ == '__main__':
    run_test()
