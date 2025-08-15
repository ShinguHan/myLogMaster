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

    def _format_item(self, item_def, context):
        # This is now a recursive function that takes context
        format_char = item_def['format']
        value = item_def['value']

        # If the value is a string and looks like an expression, evaluate it
        if isinstance(value, str) and 'context' in value:
            try:
                value = eval(value, {"context": context})
            except Exception:
                # Keep original value if eval fails
                pass

        if format_char == 'L':
            list_body = b''.join(self._format_item(sub_item, context) for sub_item in value)
            return b'\x01' + struct.pack('>B', len(value)) + list_body
        elif format_char == 'A':
            return b'\x41' + struct.pack('>B', len(str(value))) + str(value).encode('ascii')
        elif format_char == 'U1':
            return b'\x21' + struct.pack('>B', 1) + struct.pack('>B', int(value))
        return b''

    def create(self, name, context={}, **kwargs):
        spec = self.library.get(name)
        if not spec: raise ValueError(f"Message '{name}' not found in library.")
        
        # Deep copy the definition to avoid modifying the original library
        import copy
        body_def = copy.deepcopy(spec.get('body_definition', []))

        # Substitute params into the body definition before formatting
        if 'params' in kwargs:
            # This is a simplified substitution for the demo
            # A real version would traverse the entire structure
            if body_def and body_def[0]['name'] in kwargs['params']:
                body_def[0]['value'] = kwargs['params'][body_def[0]['name']]

        stream = spec['stream'] | (0x80 if kwargs.get('w_bit', True) else 0)
        header = struct.pack('>HBBH', 0, stream, spec['function'], 0) + struct.pack('>I', int(__import__('time').time()))
        body = b''.join(self._format_item(item_def, context) for item_def in body_def)
        return struct.pack('>I', len(body)) + header + body