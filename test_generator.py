def generate_scenario_from_log(parsed_secs_log, scenario_name="Generated Scenario"):
    """
    Analyzes a parsed SECS log and generates a professional, specific scenario dictionary.
    """
    steps = []
    for log_entry in parsed_secs_log:
        direction = log_entry.get('direction', '')
        base_message = log_entry.get('msg', '')
        body = log_entry.get('body')

        # --- NEW: Intelligent Message Naming Logic ---
        final_message_name = base_message
        
        # Un-prefix the message name if it came from a prefixed library
        if "_" in base_message:
            parts = base_message.split('_')
            if len(parts) > 1 and parts[-1].startswith('S') and 'F' in parts[-1]:
                 base_message = parts[-1] 
        
        if base_message == 'S6F11' and body:
            ceid = None
            # FIX: .get()을 직접 속성 접근으로 변경
            if body and body[0].type == 'L' and len(body[0].value) > 1:
                ceid_item = body[0].value[1]
                if 'U' in ceid_item.type:
                    ceid = ceid_item.value
            if ceid is not None:
                final_message_name = f"{base_message}_CEID{ceid}"
        
        elif base_message == 'S2F41' and body:
            rcmd = None
            # FIX: .get()을 직접 속성 접근으로 변경
            if body and body[0].type == 'A':
                rcmd = body[0].value
            elif body and body[0].type == 'L' and body[0].value and body[0].value[0].type == 'A':
                 rcmd = body[0].value[0].value
            if rcmd:
                sanitized_rcmd = rcmd.replace(" ", "_")
                final_message_name = f"{base_message}_{sanitized_rcmd}"
        # --- END of new logic ---

        if "Host ->" in direction:
            steps.append({"action": "send", "message": final_message_name})
        elif "Equip ->" in direction:
            steps.append({"action": "expect", "message": final_message_name})
            
    return {
        "name": scenario_name,
        "steps": steps
    }