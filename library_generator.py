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

        # Handle content variations for S2F41 (RCMD)
        if msg_name == 'S2F41' and body:
            rcmd = None
            if body[0].type == 'A':
                rcmd = body[0].value
            elif body[0].type == 'L' and body[0].value and body[0].value[0].type == 'A':
                 rcmd = body[0].value[0].value
            
            if rcmd:
                sanitized_rcmd = rcmd.replace(" ", "_")
                final_msg_name = f"{prefix}{msg_name}_{sanitized_rcmd}"
        
        # NEW: Handle content variations for S6F11 (CEID)
        elif msg_name == 'S6F11' and body:
            ceid = None
            # S6F11 body is typically L[CEID, L[...reports...]]
            # We assume the CEID is the first item in the body list.
            if body[0].type == 'L' and body[0].value:
                ceid_item = body[0].value[0]
                # Check for integer types like U1, U2, U4 etc.
                if 'U' in ceid_item.type:
                    ceid = ceid_item.value

            if ceid is not None:
                final_msg_name = f"{prefix}{msg_name}_CEID{ceid}"

        # Add to library only if this unique name hasn't been seen before
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
    """Analyzes a parsed JSON log and generates a schema of unique events."""
    schema = {}
    for log_entry in parsed_json_log:
        event_name = log_entry.get('entry', {}).get('event')
        if event_name and event_name not in schema:
            data_schema = {}
            for key, value in log_entry.get('entry', {}).get('data', {}).items():
                data_schema[key] = str(type(value).__name__)
            schema[event_name] = data_schema
    return schema
