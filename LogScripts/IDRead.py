# 테스트용 스크립트
def analyze(logs, result):
    # 시간순으로 정렬
    target_logs = logs.sort_values(by='SystemDate_dt')
    
    carrier_id = 'LHAE000336'
    id_read_found = False
    id_read_index = -1

    # 모든 로그를 시간 순서대로 하나씩 확인
    for index, row in target_logs.iterrows():
        # 아직 ID Read를 찾지 못했고, 현재 로그에 Carrier ID와 'IDRead'가 모두 있다면
        if not id_read_found and carrier_id in row['AsciiData'] and 'IDRead' in row['AsciiData']:
            id_read_found = True
            id_read_index = index
            result.add_marker(index, f"{carrier_id} ID Read 이벤트 발생", "lightblue")
            continue # 다음 로그로 넘어감

        # ID Read를 찾은 상태이고, 현재 로그에 Carrier ID와 'moveCancelled'가 있다면
        if id_read_found and carrier_id in row['AsciiData'] and 'moveCancelled' in row['AsciiData']:
            result.add_marker(index, "ID Read 이후 Canceled 이벤트 발생!", "salmon")
            id_read_found = False # 상태 초기화
            
    result.set_summary("Carrier 'LHAE000336'의 이동 시퀀스 분석 완료.")