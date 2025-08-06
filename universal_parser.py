import csv
import json
import re
from datetime import datetime
from types import SimpleNamespace

def _parse_body_recursive(body_io):
    items = []
    try:
        format_code = body_io.read(1)
        if not format_code: return items
        length_byte = int.from_bytes(body_io.read(1), 'big')
        if format_code == b'\x01':
            items.append(SimpleNamespace(type='L', value=[item for _ in range(length_byte) for item in _parse_body_recursive(body_io)]))
        elif format_code == b'\x21':
            items.append(SimpleNamespace(type='U1', value=int.from_bytes(body_io.read(length_byte), 'big')))
        elif format_code == b'\x41':
            items.append(SimpleNamespace(type='A', value=body_io.read(length_byte).decode('ascii')))
    except (IndexError, __import__('struct').error):
        pass
    return items

def parse_log_with_profile(log_filepath, profile):
    """Parses a complex, multi-line log file using a user-defined profile with deep, detailed logging."""
    parsed_log = {'secs': [], 'json': [], 'debug_log': []}
    debug = parsed_log['debug_log'].append

    debug("--- Starting Universal Parser (Deep Logging) ---")

    with open(log_filepath, 'r', newline='', encoding='utf-8') as f:
        lines = f.readlines()

    headers = []
    required_headers = list(profile.get('column_mapping', {}).values())
    
    header_line_index = -1
    header_found = False
    for i, line in enumerate(lines):
        if all(f'"{h}"' in line for h in required_headers):
            try:
                headers = next(csv.reader([line]))
                header_line_index = i
                header_found = True
                debug(f"Header row found on line {i + 1}: {headers}")
                break
            except StopIteration:
                continue
    
    if not header_found:
        debug("CRITICAL ERROR: Could not find the header row.")
        return parsed_log

    try:
        col_map = {name: headers.index(col_name) for name, col_name in profile.get('column_mapping', {}).items()}
    except ValueError as e:
        debug(f"CRITICAL ERROR: Column name from profile not in header: {e}")
        return parsed_log

    log_entry_starters = tuple(f'"{cat}"' for cat in ["Info", "Debug", "Com", "Error"])
    entry_buffer = []
    
    data_start_index = header_line_index + 2 

    def process_buffer(buffer, buffer_start_line):
        if not buffer: return
        full_entry_line = "".join(buffer).replace('\n', ' ').replace('\r', '')
        debug(f"\n[Line ~{buffer_start_line}] Processing buffered entry...")
        try:
            row = next(csv.reader([full_entry_line]))
            if len(row) < len(headers):
                debug(f"[Line ~{buffer_start_line}] SKIPPING: Row has fewer columns than header.")
                return

            msg_type = None
            for rule in profile.get('type_rules', []):
                col_idx = col_map.get(rule['column'])
                if col_idx is not None and row[col_idx] == rule['value']:
                    msg_type = rule['type']
                    debug(f"[Line ~{buffer_start_line}] Matched type rule: '{rule['column']}' is '{rule['value']}'. Identified as '{msg_type}'.")
                    break
            
            if not msg_type:
                debug(f"[Line ~{buffer_start_line}] SKIPPING: No type rule matched.")
                return

            if msg_type == 'secs':
                ascii_data = row[col_map['ascii_data']]
                msg = None
                for rule in profile.get('text_to_message_rules', []):
                    if rule['text_contains'] in ascii_data:
                        msg = rule['message_name']
                        debug(f"[Line ~{buffer_start_line}] Matched text rule: Found '{rule['text_contains']}'. Deduced message is '{msg}'.")
                        break
                if msg:
                    raw_body_hex = row[col_map['secs_body']]
                    if raw_body_hex:
                        body_obj = _parse_body_recursive(__import__('io').BytesIO(bytes.fromhex(raw_body_hex)))
                        parsed_log['secs'].append({'msg': msg, 'body': body_obj})
                        debug(f"[Line ~{buffer_start_line}] SUCCESS: Parsed SECS message with body.")
                    else:
                        parsed_log['secs'].append({'msg': msg, 'body': []})
                        debug(f"[Line ~{buffer_start_line}] SUCCESS: Added SECS message with empty body.")


            elif msg_type == 'json':
                json_str_raw = row[col_map['json_body']]
                start_index = json_str_raw.find('{')
                if start_index != -1:
                    brace_count = 0; end_index = -1
                    for char_idx in range(start_index, len(json_str_raw)):
                        if json_str_raw[char_idx] == '{': brace_count += 1
                        elif json_str_raw[char_idx] == '}': brace_count -= 1
                        if brace_count == 0: end_index = char_idx + 1; break
                    if end_index != -1:
                        json_str = json_str_raw[start_index:end_index]
                        json_data = json.loads(json_str)
                        parsed_log['json'].append({'entry': json_data})
                        debug(f"[Line ~{buffer_start_line}] SUCCESS: Parsed JSON message.")
        except Exception as e:
            debug(f"[Line ~{buffer_start_line}] ERROR: Skipping buffered entry due to error: {e}")

    buffer_start_line = data_start_index + 1
    for i in range(data_start_index, len(lines)):
        line = lines[i]
        if not line.strip(): continue

        if line.startswith(log_entry_starters):
            process_buffer(entry_buffer, buffer_start_line)
            entry_buffer = [line]
            buffer_start_line = i + 1
        else:
            entry_buffer.append(line)
    
    process_buffer(entry_buffer, buffer_start_line)

    debug(f"\n--- Parser Finished: Found {len(parsed_log['secs'])} SECS and {len(parsed_log['json'])} JSON messages. ---")
    return parsed_log
