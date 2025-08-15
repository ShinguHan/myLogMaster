# file: rules/verify_state.py

def execute(log_data, rule_params):
    """
    특정 이벤트 발생 시, 특정 객체의 상태가 기대하는 상태와 일치하는지 검증합니다.
    """
    object_id = rule_params.get('object_id')
    event_contains = rule_params.get('event_contains')
    expected_state = rule_params.get('expected_state')
    identity_key = rule_params.get('identity_key', 'carrierId') # 시나리오에서 키를 지정할 수 있도록 확장

    stateful_log = log_data.get('stateful_log', [])

    event_found = False
    for entry in stateful_log:
        # 이벤트 내용과 객체 ID가 모두 일치하는 로그 항목을 찾음
        if event_contains in str(entry) and entry.get(identity_key) == object_id:
            event_found = True
            actual_state = entry.get('state')
            if actual_state == expected_state:
                return {
                    "result": "Pass",
                    "details": f"Event '{event_contains}' for '{object_id}' occurred in expected state '{expected_state}'."
                }
            else:
                return {
                    "result": "Fail",
                    "details": f"Event '{event_contains}' for '{object_id}' occurred, but state was '{actual_state}' instead of '{expected_state}'."
                }

    if not event_found:
        return {
            "result": "Fail",
            "details": f"Event '{event_contains}' for object '{object_id}' was not found in the log."
        }
    
    # 이 부분은 실행되지 않지만, 만약을 위해 남겨둠
    return {
        "result": "Fail",
        "details": "An unknown error occurred in the verify_state rule."
    }