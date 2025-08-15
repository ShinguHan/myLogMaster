import json
from types import SimpleNamespace

def _parsed_body_to_def(parsed_items):
    """Recursively converts a parsed body object back into a library definition list."""
    def_list = []
    for item in parsed_items:
        item_def = {"name": f"Item_{item.type}", "format": item.type}
        if item.type == 'L':
            item_def["value"] = _parsed_body_to_def(item.value)
        else:
            item_def["value"] = item.value
        def_list.append(item_def)
    return def_list

def generate_library_from_log(parsed_secs_log, device_id=""):
    """
    Analyzes a parsed SECS log and generates a message library dictionary.
    """
    library = {}
    prefix = f"{device_id}_" if device_id else ""

    for log_entry in parsed_secs_log:
        msg_name = log_entry.get('msg')
        body = log_entry.get('body')
        
        final_msg_name = f"{prefix}{msg_name}"

        if msg_name == 'S2F41' and body:
            rcmd = None
            if body and body[0].type == 'A':
                rcmd = body[0].value
            elif body and body[0].type == 'L' and body[0].value and body[0].value[0].type == 'A':
                 rcmd = body[0].value[0].value
            
            if rcmd:
                sanitized_rcmd = rcmd.replace(" ", "_")
                final_msg_name = f"{prefix}{msg_name}_{sanitized_rcmd}"
        
        elif msg_name == 'S6F11' and body:
            ceid = None
            if body and body[0].type == 'L' and len(body[0].value) > 1:
                ceid_item = body[0].value[1]
                if 'U' in ceid_item.type:
                    ceid = ceid_item.value

            if ceid is not None:
                final_msg_name = f"{prefix}{msg_name}_CEID{ceid}"

        if final_msg_name not in library:
            try:
                s, f = int(msg_name[1]), int(msg_name[3:])
                
                library[final_msg_name] = {
                    "name": f"Generated {final_msg_name}",
                    "stream": s,
                    "function": f,
                    "body_definition": _parsed_body_to_def(body)
                }
            except (ValueError, IndexError):
                continue

    return library

def generate_schema_from_json_log(parsed_json_log):
    """Analyzes a parsed JSON log and generates a schema of unique events with real values."""
    schema = {}
    for log_entry in parsed_json_log:
        entry_data = log_entry.get('entry', {})
        event_name = entry_data.get('actID')
        
        if event_name and event_name not in schema:
            # Generate a schema for the ENTIRE message entry, not just the payload.
            full_schema = _get_json_schema_with_values(entry_data)
            schema[event_name] = full_schema
            
    return schema

def _get_json_schema_with_values(data):
    """
    Helper function to recursively generate a schema from JSON data,
    but using the actual values instead of just the types.
    """
    if isinstance(data, dict):
        return {key: _get_json_schema_with_values(value) for key, value in data.items()}
    elif isinstance(data, list):
        # If the list is not empty, generate schema from the first element
        if data:
            return [_get_json_schema_with_values(data[0])]
        else:
            return []
    else:
        # Return the actual value itself
        return data
