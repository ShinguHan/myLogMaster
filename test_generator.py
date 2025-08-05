def generate_scenario_from_log(parsed_secs_log, scenario_name="Generated Scenario"):
    """
    Analyzes a parsed SECS log and generates a scenario dictionary.
    """
    steps = []
    for log_entry in parsed_secs_log:
        direction = log_entry.get('direction', '')
        message = log_entry.get('msg', '')
        
        if "Host ->" in direction:
            steps.append({"action": "send", "message": message})
        elif "Equip ->" in direction:
            steps.append({"action": "expect", "message": message})
            
    return {
        "name": scenario_name,
        "steps": steps
    }
