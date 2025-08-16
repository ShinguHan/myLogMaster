import pandas as pd

def analyze(logs, result):
    events = []
    # Carrier ID와 이벤트 종류, 시간만 추출
    for index, row in logs.iterrows():
        if 'CarrierIDRead' in row['AsciiData']:
            events.append({'ID': row['TrackingID'], 'Event': 'Read', 'Time': row['SystemDate_dt']})
        elif 'CarrierWaitIn' in row['AsciiData']:
            events.append({'ID': row['TrackingID'], 'Event': 'WaitIn', 'Time': row['SystemDate_dt']})

    if not events:
        result.set_summary("분석할 이벤트가 없습니다.")
        return

    # 이벤트 목록으로 새 데이터프레임 생성
    event_df = pd.DataFrame(events)
    
    # 이벤트 종류별로 데이터를 분리하고 ID를 기준으로 합침
    read_times = event_df[event_df['Event'] == 'Read'].rename(columns={'Time': 'ReadTime'})
    wait_times = event_df[event_df['Event'] == 'WaitIn'].rename(columns={'Time': 'WaitInTime'})
    merged_df = pd.merge(read_times, wait_times, on='ID')
    
    # 시간 차이 계산
    merged_df['Duration'] = merged_df['WaitInTime'] - merged_df['ReadTime']
    
    result.set_summary("ID Read ~ WaitIn 사이의 시간 차이 계산 완료.")
    # 새로 생성된 분석 결과를 별도의 창으로 보여줌
    result.show_dataframe(merged_df[['ID', 'Duration']], title="Read to WaitIn Duration")