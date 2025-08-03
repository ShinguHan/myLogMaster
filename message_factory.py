import json
import struct

class MessageFactory:
    def __init__(self, filepath='message_library.json'):
        with open(filepath, 'r') as f: self.library = json.load(f)
        self._update_message_names()
    def _update_message_names(self): self.message_names = sorted(list(self.library.keys()))
    def add_from_file(self, filepath):
        with open(filepath, 'r') as f: external_lib = json.load(f)
        self.library.update(external_lib); self._update_message_names()
        return list(external_lib.keys())
    def _format_item(self, item_def):
        format_char, value = item_def['format'], item_def['value']
        if format_char == 'L': return b'\x01' + struct.pack('>B', len(value)) + b''.join(self._format_item(sub_item) for sub_item in value)
        elif format_char == 'A': return b'\x41' + struct.pack('>B', len(value)) + value.encode('ascii')
        elif format_char == 'U1': return b'\x21' + struct.pack('>B', 1) + struct.pack('>B', value)
        return b''
    def create(self, name, **kwargs):
        spec = self.library.get(name)
        # FIX: Check if the message spec was found before trying to use it
        if not spec:
            raise ValueError(f"Message '{name}' not found in library.")
        
        stream = spec['stream'] | (0x80 if kwargs.get('w_bit', True) else 0)
        header = struct.pack('>HBBH', 0, stream, spec['function'], 0) + struct.pack('>I', int(__import__('time').time()))
        body = b''.join(self._format_item(item_def) for item_def in spec.get('body_definition', []))
        return struct.pack('>I', len(body)) + header + body