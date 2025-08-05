import json
from types import SimpleNamespace

def _parsed_body_to_def(parsed_items):
    """Recursively converts a parsed body object back into a library definition list."""
    def_list = []
    for item in parsed_items:
        # For this generator, we'll create generic names
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
        
        # Start with the base name
        final_msg_name = f"{prefix}{msg_name}"

        # FIX: Check for S2F41 and create a unique name *before* the duplicate check
        if msg_name == 'S2F41' and body:
            # This logic assumes the RCMD is the first ASCII item in the body or a nested list
            rcmd = None
            if body[0].type == 'A':
                rcmd = body[0].value
            elif body[0].type == 'L' and body[0].value and body[0].value[0].type == 'A':
                 rcmd = body[0].value[0].value
            
            if rcmd:
                # Sanitize rcmd for use in a name (e.g., remove spaces)
                sanitized_rcmd = rcmd.replace(" ", "_")
                final_msg_name = f"{prefix}{msg_name}_{sanitized_rcmd}"

        # Add to library only if this unique name hasn't been seen before
        if final_msg_name not in library:
            try:
                # In a real app, we'd need a reverse lookup for stream/function
                # For now, we'll hardcode for simplicity
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
    """Analyzes a parsed JSON log and generates a schema of unique events."""
    schema = {}
    for log_entry in parsed_json_log:
        event_name = log_entry.get('entry', {}).get('event')
        if event_name and event_name not in schema:
            # Create a schema by replacing values with their types
            data_schema = {}
            for key, value in log_entry.get('entry', {}).get('data', {}).items():
                data_schema[key] = str(type(value).__name__)
            schema[event_name] = data_schema
    return schema
