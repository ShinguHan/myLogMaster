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
        # This logic mirrors the intelligence from our library_generator
        final_message_name = base_message
        
        # Un-prefix the message name if it came from a prefixed library
        # This is a placeholder for a more robust name matching system
        if "_" in base_message:
            parts = base_message.split('_')
            if len(parts) > 1 and parts[-1].startswith('S') and 'F' in parts[-1]:
                 base_message = parts[-1] # e.g., "MyDevice_S6F11" -> "S6F11"
        
        if base_message == 'S6F11' and body:
            ceid = None
            # The body is now a dictionary, so we use .get()
            if body and body[0].get('type') == 'L' and len(body[0].get('value', [])) > 1:
                ceid_item = body[0]['value'][1]
                if 'U' in ceid_item.get('type'):
                    ceid = ceid_item.get('value')
            if ceid is not None:
                final_message_name = f"{base_message}_CEID{ceid}"
        
        elif base_message == 'S2F41' and body:
            rcmd = None
            if body and body[0].get('type') == 'A':
                rcmd = body[0].get('value')
            elif body and body[0].get('type') == 'L' and body[0].get('value') and body[0]['value'][0].get('type') == 'A':
                 rcmd = body[0]['value'][0].get('value')
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
