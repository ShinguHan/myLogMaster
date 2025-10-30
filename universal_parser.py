import csv
import json
import io
import struct
from types import SimpleNamespace

def _parse_body_recursive(body_io):
    # 이 함수는 원본과 동일하게 유지됩니다.
    items = []
    try:
        format_code_byte = body_io.read(1)
        if not format_code_byte: return items
        
        format_char = format_code_byte[0]
        length_bits = format_char & 0b00000011
        num_length_bytes = length_bits

        if num_length_bytes == 0:
            length = 0
        else:
            length_bytes = body_io.read(num_length_bytes)
            length = int.from_bytes(length_bytes, 'big')

        data_format = format_char >> 2
        
        if data_format == 0b000000: # L (List)
            list_items = []
            for _ in range(length):
                list_items.extend(_parse_body_recursive(body_io))
            items.append(SimpleNamespace(type='L', value=list_items))
        
        elif data_format == 0b010000: # A (ASCII)
            val = body_io.read(length).decode('ascii', errors='ignore')
            items.append(SimpleNamespace(type='A', value=val))
        
        elif data_format == 0b010010: # U1 (1-byte Unsigned Int)
            num_itemgis = length // 1
            for _ in range(num_items):
                val = int.from_bytes(body_io.read(1), 'big')
                items.append(SimpleNamespace(type='U1', value=val))

        elif data_format == 0b101010: # U2 (2-byte Unsigned Int)
            num_items = length // 2
            for _ in range(num_items):
                val = int.from_bytes(body_io.read(2), 'big')
                items.append(SimpleNamespace(type='U2', value=val))

        elif data_format == 0b101011: # U4 (4-byte Unsigned Int)
            num_items = length // 4
            for _ in range(num_items):
                val = int.from_bytes(body_io.read(4), 'big')
                items.append(SimpleNamespace(type='U4', value=val))
        
        else:
            if length > 0:
                body_io.read(length)

    except (IndexError, struct.error):
        pass
    return items

def parse_log_with_profile(log_filepath, profile):
    """
    제너레이터를 사용하여 대용량 로그 파일을 메모리 효율적으로 파싱합니다.
    기존의 `process_buffer` 함수 구조는 유지하여 로직의 안정성을 보장합니다.
    """
    parsed_entries = []
    
    # --- 1. 헤더 찾기 ---
    headers = []
    required_headers = list(profile.get('column_mapping', {}).values())
    data_start_line_num = 0
    
    try:
        with open(log_filepath, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if all(f'"{h}"' in line for h in required_headers):
                    try:
                        headers = next(csv.reader([line]))
                        # 데이터는 헤더 라인 2줄 아래부터 시작
                        data_start_line_num = i + 2
                        break
                    except StopIteration:
                        continue
    except Exception as e:
        print(f"Error finding headers: {e}")
        return []

    if not headers:
        print("Could not find a valid header line.")
        return []

    log_entry_starters = tuple(f'"{cat}"' for cat in ["Info", "Debug", "Com", "Error", "Warn"])
    entry_buffer = []

    def process_buffer(buffer):
        # 이 함수는 기존 코드와 완전히 동일합니다. (로직 변경 없음)
        if not buffer: return
        full_entry_line = "".join(buffer).replace('\n', ' ').replace('\r', '')
        try:
            row = next(csv.reader([full_entry_line]))

            if len(row) != len(headers): return

            log_data = {header: value for header, value in zip(headers, row)}
            log_data['ParsedBody'] = None
            log_data['ParsedBodyObject'] = None

            msg_type = None
            category = log_data.get("Category", "").replace('"', '')
            for rule in profile.get('type_rules', []):
                if category == rule['value']:
                    msg_type = rule['type']; break
            
            if not msg_type:
                log_data['ParsedType'] = 'Log'
                parsed_entries.append(log_data)
                return

            if msg_type == 'secs':
                log_data['ParsedType'] = 'SECS'
                raw_full_hex = log_data.get('BinaryData', '')
                if raw_full_hex and len(raw_full_hex) >= 20:
                    full_binary = bytes.fromhex(raw_full_hex)
                    header_bytes = full_binary[0:10]
                    _, s_type, f_type, _, _ = struct.unpack('>HBBH4s', header_bytes)
                    stream = s_type & 0x7F
                    msg = f"S{stream}F{f_type}"
                    log_data['ParsedBody'] = msg
                    body_bytes = full_binary[10:]
                    log_data['ParsedBodyObject'] = _parse_body_recursive(io.BytesIO(body_bytes))

            elif msg_type == 'json':
                log_data['ParsedType'] = 'JSON'
                json_str_raw = log_data.get('AsciiData', '')
                start_index = json_str_raw.find('{')
                if start_index != -1:
                    brace_count = 0; end_index = -1
                    for char_idx in range(start_index, len(json_str_raw)):
                        if json_str_raw[char_idx] == '{': brace_count += 1
                        elif json_str_raw[char_idx] == '}': brace_count -= 1
                        if brace_count == 0:
                            end_index = char_idx + 1; break
                    if end_index != -1:
                        json_str = json_str_raw[start_index:end_index].replace('\xa0', ' ')
                        try:
                            json_data = json.loads(json_str)
                            log_data['ParsedBodyObject'] = json_data
                            log_data['ParsedBody'] = json_data.get('actID', 'JSON Data')
                        except json.JSONDecodeError:
                            log_data['ParsedBody'] = "Invalid JSON"
                            log_data['ParsedBodyObject'] = json_str
            
            parsed_entries.append(log_data)

        except Exception:
            pass
    
    # --- 2. 데이터 처리 (제너레이터 사용) ---
    try:
        with open(log_filepath, 'r', encoding='utf-8') as f:
            # 데이터 시작점까지 파일 포인터를 이동시킵니다.
            for _ in range(data_start_line_num):
                next(f)
            
            # 한 줄씩 읽어서 처리합니다.
            for line in f:
                if not line.strip(): continue

                if line.startswith(log_entry_starters):
                    process_buffer(entry_buffer)
                    entry_buffer = [line]
                elif entry_buffer:
                    entry_buffer.append(line)
            
            # 마지막에 남아있는 버퍼 처리
            process_buffer(entry_buffer)
    except Exception as e:
        print(f"Error during file processing: {e}")

    return parsed_entries

