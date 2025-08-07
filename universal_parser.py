import csv
import json
import struct
from datetime import datetime
from types import SimpleNamespace
import io

def _parse_body_recursive(body_io):
    """
    A more robust, recursive parser for SECS-II message bodies.
    """
    items = []
    try:
        format_code_byte = body_io.read(1)
        if not format_code_byte: return items
        
        format_char = format_code_byte[0]
        length_bits = format_char & 0b00000011
        
        num_length_bytes = 0
        if length_bits == 1: num_length_bytes = 1
        elif length_bits == 2: num_length_bytes = 2
        elif length_bits == 3: num_length_bytes = 3

        length = 0
        if num_length_bytes > 0:
            length_bytes = body_io.read(num_length_bytes)
            length = int.from_bytes(length_bytes, 'big')

        data_format = format_char >> 2
        
        # Expanded data type handling
        if data_format == 0b000000: # L (List)
            list_items = []
            # For lists, length is the number of items
            for _ in range(length):
                list_items.extend(_parse_body_recursive(body_io))
            items.append(SimpleNamespace(type='L', value=list_items))
        
        elif data_format == 0b100000: # A (ASCII)
            val = body_io.read(length).decode('ascii')
            items.append(SimpleNamespace(type='A', value=val))
        
        elif data_format == 0b010010: # U1 (1-byte Unsigned Int)
            val = int.from_bytes(body_io.read(length), 'big')
            items.append(SimpleNamespace(type='U1', value=val))

        elif data_format == 0b101010: # U2 (2-byte Unsigned Int)
            # Length is number of bytes, so number of items is length / 2
            num_items = length // 2
            for _ in range(num_items):
                val = int.from_bytes(body_io.read(2), 'big')
                items.append(SimpleNamespace(type='U2', value=val))

        elif data_format == 0b101011: # U4 (4-byte Unsigned Int)
            num_items = length // 4
            for _ in range(num_items):
                val = int.from_bytes(body_io.read(4), 'big')
                items.append(SimpleNamespace(type='U4', value=val))
        
        else: # Skip any other types we don't recognize
            if length > 0:
                body_io.read(length)

    except (IndexError, struct.error):
        pass # Gracefully handle malformed data
    return items

def parse_log_with_profile(log_filepath, profile):
    """
    Parses a complex, multi-line log file using the final, proven logic.
    """
    parsed_log = {'secs': [], 'json': [], 'debug_log': []}
    debug = parsed_log['debug_log'].append

    debug("--- Starting Universal Parser (Final Version) ---")

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
        try:            # Use the robust manual parser from our successful test
            if full_entry_line.startswith('"') and full_entry_line.endswith('"'):
                full_entry_line = full_entry_line[1:-1]
            row = full_entry_line.split('","')

            if len(row) != len(headers): return

            log_data = {header: value for header, value in zip(headers, row)}

            msg_type = None
            category = log_data.get("Category", "").replace('"', '')
            for rule in profile.get('type_rules', []):
                if category == rule['value']:
                    msg_type = rule['type']
                    break
            
            if not msg_type: return

            if msg_type == 'secs':
                raw_full_hex = log_data.get('BinaryData', '')
                if raw_full_hex:
                    full_binary = bytes.fromhex(raw_full_hex)
                    
                    if len(full_binary) >= 10:
                        header_bytes = full_binary[0:10]
                        _, s_type, f_type, _, _ = struct.unpack('>HBBH4s', header_bytes)
                        stream = s_type & 0x7F
                        msg = f"S{stream}F{f_type}"
                        
                        body_bytes = full_binary[10:]
                        body_obj = _parse_body_recursive(io.BytesIO(body_bytes))
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
