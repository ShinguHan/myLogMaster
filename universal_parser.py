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
    """
    Parses a complex, multi-line log file using the Director's final, proven logic.
    """
    parsed_log = {'secs': [], 'json': [], 'debug_log': []}
    debug = parsed_log['debug_log'].append

    debug("--- Starting Universal Parser (Final Logic) ---")

    with open(log_filepath, 'r', newline='', encoding='utf-8') as f:
        lines = f.readlines()

    headers = []
    required_headers = list(profile.get('column_mapping', {}).values())
    
    header_line_index = -1
    for i, line in enumerate(lines):
        if all(f'"{h}"' in line for h in required_headers):
            try:
                headers = next(csv.reader([line]))
                header_line_index = i
                debug(f"Header row found on line {i + 1}: {headers}")
                break
            except StopIteration:
                continue
    
    if header_line_index == -1:
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

    def process_buffer(buffer):
        if not buffer: return
        full_entry_line = "".join(buffer).replace('\n', ' ').replace('\r', '')
        try:
            if full_entry_line.startswith('"') and full_entry_line.endswith('"'):
                full_entry_line = full_entry_line[1:-1]
            row = full_entry_line.split('","')

            if len(row) != len(headers): return

            log_data = {header: value for header, value in zip(headers, row)}

            msg_type = None
            category = log_data.get("Category").replace('"', '')
            
            for rule in profile.get('type_rules', []):
                if category == rule['value']:
                    msg_type = rule['type']
                    break
            
            if not msg_type: return

            if msg_type == 'secs':
                ascii_data = log_data.get('AsciiData', '')
                msg = None
                for rule in profile.get('text_to_message_rules', []):
                    if rule['text_contains'] in ascii_data:
                        msg = rule['message_name']
                        break
                if msg:
                    raw_body_hex = log_data.get('BinaryData', '')
                    body_obj = _parse_body_recursive(__import__('io').BytesIO(bytes.fromhex(raw_body_hex))) if raw_body_hex else []
                    parsed_log['secs'].append({'msg': msg, 'body': body_obj})

            elif msg_type == 'json':
                json_str_raw = log_data.get('AsciiData', '')
                start_index = json_str_raw.find('{')
                if start_index != -1:
                    brace_count = 0; end_index = -1
                    for char_idx in range(start_index, len(json_str_raw)):
                        if json_str_raw[char_idx] == '{': brace_count += 1
                        elif json_str_raw[char_idx] == '}': brace_count -= 1
                        if brace_count == 0: end_index = char_idx + 1; break
                    if end_index != -1:
                        json_str = json_str_raw[start_index:end_index]
                        # FIX: Clean the string of non-breaking spaces before parsing
                        cleaned_json_str = json_str.replace('\xa0', ' ')
                        json_data = json.loads(cleaned_json_str)
                        parsed_log['json'].append({'entry': json_data})
        except Exception:
            pass

    for i in range(data_start_index, len(lines)):
        line = lines[i]
        if not line.strip(): continue

        if line.startswith(log_entry_starters):
            process_buffer(entry_buffer)
            entry_buffer = [line]
        elif entry_buffer:
            entry_buffer.append(line)
    
    process_buffer(entry_buffer)

    debug(f"--- Parser Finished: Found {len(parsed_log['secs'])} SECS and {len(parsed_log['json'])} JSON messages. ---")
    return parsed_log
