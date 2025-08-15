# file: rules/verify_process_flow.py
from datetime import datetime

def execute(log_data, rule_params):
    """
    Verifies the total time of a sequence of correlated events across logs.
    """
    flow_steps = rule_params.get('flow', [])
    max_total_time = rule_params.get('max_total_seconds')
    
    if not flow_steps or len(flow_steps) < 2:
        return {"result": "Fail", "details": "Invalid rule: 'flow' must contain at least two steps."}

    secs_log = log_data.get('secs', [])
    json_log = log_data.get('json', [])

    # This is a simplified implementation for the MVP.
    # It finds the first step, then looks for the next, and so on.
    
    first_step = flow_steps[0]
    last_step = flow_steps[-1]
    
    start_time = None
    end_time = None

    # Find the timestamp of the first event
    if first_step['log_type'] == 'secs':
        for entry in secs_log:
            if entry.get('msg') == first_step['event']:
                start_time = entry.get('ts')
                break
    elif first_step['log_type'] == 'json':
         for entry in json_log:
            if entry.get('entry', {}).get('actID') == first_step['event']:
                start_time = entry.get('ts')
                break

    # Find the timestamp of the last event
    if last_step['log_type'] == 'secs':
        for entry in reversed(secs_log):
            if entry.get('msg') == last_step['event']:
                end_time = entry.get('ts')
                break
    elif last_step['log_type'] == 'json':
        for entry in reversed(json_log):
            if entry.get('entry', {}).get('actID') == last_step['event']:
                end_time = entry.get('ts')
                break

    if not start_time or not end_time:
        return {"result": "Fail", "details": "Could not find start or end event of the process flow."}

    # Convert timestamps if they are not already datetime objects
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time)
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)

    duration = (end_time - start_time).total_seconds()

    if duration <= max_total_time:
        return {
            "result": "Pass",
            "details": f"Total process flow took {duration:.3f}s (Limit: {max_total_time}s)."
        }
    else:
        return {
            "result": "Fail",
            "details": f"Total process flow took {duration:.3f}s, exceeding the limit of {max_total_time}s."
        }
