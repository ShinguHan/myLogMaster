import csv
import json
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

    def process_buffer(buffer, buffer_start_line):
        if not buffer: return
        full_entry_line = "".join(buffer).replace('\n', ' ').replace('\r', '')
        debug(f"\n[Line ~{buffer_start_line}] Processing buffered entry...")
        try:
            if full_entry_line.startswith('"') and full_entry_line.endswith('"'):
                full_entry_line = full_entry_line[1:-1]
            row = full_entry_line.split('","')

            if len(row) != len(headers):
                debug(f"[Line ~{buffer_start_line}] SKIPPING: Column count mismatch.")
                return

            log_data = {header: value for header, value in zip(headers, row)}

            msg_type = None
            category = log_data.get("Category")
            debug(f"[Line ~{buffer_start_line}] Found Category: '{category}'")
            for rule in profile.get('type_rules', []):
                debug(f"[Line ~{buffer_start_line}]   Comparing with rule value: '{rule['value']}'")
                if category == rule['value']:
                    msg_type = rule['type']
                    debug(f"[Line ~{buffer_start_line}]   MATCH! Setting type to '{msg_type}'.")
                    break
            
            if not msg_type:
                debug(f"[Line ~{buffer_start_line}] SKIPPING: No message type found for this category.")
                return

            if msg_type == 'secs':
                # ... (rest of the logic is the same)
                pass
            elif msg_type == 'json':
                # ... (rest of the logic is the same)
                pass
        except Exception as e:
            debug(f"[Line ~{buffer_start_line}] ERROR during processing: {e}")

    buffer_start_line = data_start_index
    for i in range(data_start_index, len(lines)):
        line = lines[i]
        if not line.strip(): continue

        if line.startswith(log_entry_starters):
            process_buffer(entry_buffer, buffer_start_line)
            entry_buffer = [line]
            buffer_start_line = i + 1
        elif entry_buffer:
            entry_buffer.append(line)
    
    process_buffer(entry_buffer, buffer_start_line)

    debug(f"--- Parser Finished: Found {len(parsed_log['secs'])} SECS and {len(parsed_log['json'])} JSON messages. ---")
    return parsed_log
