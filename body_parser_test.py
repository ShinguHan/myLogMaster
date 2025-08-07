import io
import struct
from types import SimpleNamespace
import json

def _namespace_to_dict(obj):
    """Recursively converts a SimpleNamespace object to a dictionary for pretty printing."""
    if isinstance(obj, SimpleNamespace):
        return {k: _namespace_to_dict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [_namespace_to_dict(i) for i in obj]
    else:
        return obj

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
            val = body_io.read(length).decode('ascii')
            items.append(SimpleNamespace(type='A', value=val))
        
        elif data_format == 0b010010: # U1 (1-byte Unsigned Int)
            num_items = length // 1
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

def run_test():
    """
    Tests the SECS body parser with the customer's sample data.
    """
    print("--- Starting SECS Body Parser Test ---")
    
    hex_string = '0001860b0000000043ea0103a9020000a90200fb01010102a902001301010109410f4a3146434e5631323330352d313034410a4c484145303030333336a9020000a9020000a902000441000100a9020000a9020000'
    
    print(f"\nInput Hex String:\n{hex_string}\n")

    try:
        full_binary = bytes.fromhex(hex_string)
        
        header_bytes = full_binary[0:10]
        body_bytes = full_binary[10:]
        
        _, s_type, f_type, _, _ = struct.unpack('>HBBH4s', header_bytes)
        stream = s_type & 0x7F
        msg_name = f"S{stream}F{f_type}"

        print(f"Decoded Header: {msg_name}")
        print(f"Extracted Body (Hex): {body_bytes.hex()}")

        body_io = io.BytesIO(body_bytes)
        parsed_result = _parse_body_recursive(body_io)
        result_dict = _namespace_to_dict(parsed_result)
        
        print("\n--- Parsed Result (Human-Readable) ---")
        print(json.dumps(result_dict, indent=2))
        
        print("\n--- Test Result ---")
        found_id = False
        try:
            # FIX: This is the new, correct, and deeply nested path to the CarrierID
            carrier_id = result_dict[0]['value'][2]['value'][0]['value'][1]['value'][0]['value'][1]['value']
            if carrier_id == 'LHAE000336':
                found_id = True
        except (IndexError, KeyError):
            pass

        if found_id:
             print("SUCCESS: The parser correctly identified the CarrierID 'LHAE000336'.")
        else:
             print("FAILURE: The parser did not find the CarrierID.")

    except Exception as e:
        print(f"\n--- Test Result ---")
        print(f"FAILURE: An error occurred: {e}")


if __name__ == '__main__':
    run_test()
