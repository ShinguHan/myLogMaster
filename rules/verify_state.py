# file: rules/verify_state.py

def execute(log_data, rule_params):
    """
    Verifies that a specific message occurred while the equipment
    was in the expected state.
    """
    msg_to_check = rule_params.get('message')
    expected_state = rule_params.get('state')
    
    # The engine provides a pre-computed stateful log
    stateful_secs_log = log_data.get('stateful_secs', [])

    for entry in stateful_secs_log:
        if entry.get('msg') == msg_to_check:
            actual_state = entry.get('state')
            if actual_state == expected_state:
                return {
                    "result": "Pass",
                    "details": f"Message '{msg_to_check}' correctly found in state '{expected_state}'."
                }
            else:
                return {
                    "result": "Fail",
                    "details": f"Message '{msg_to_check}' found, but state was '{actual_state}' instead of '{expected_state}'."
                }

    return {
        "result": "Fail",
        "details": f"Message '{msg_to_check}' was not found in the log."
    }
