def validate_message_recursive(spec_defs, parsed_items):
    """Recursively validates parsed items against their specifications."""
    if len(spec_defs) != len(parsed_items):
        return False, f"Mismatched item count. Expected {len(spec_defs)}, got {len(parsed_items)}."

    for i, (spec, item) in enumerate(zip(spec_defs, parsed_items)):
        spec_format = spec.get('format')
        item_type = item.type

        if spec_format != item_type:
            return False, f"Type mismatch at item {i+1}. Expected {spec_format}, got {item_type}."

        if spec_format == 'L':
            # Recursive call for nested lists
            is_valid, error = validate_message_recursive(spec.get('value', []), item.value)
            if not is_valid:
                return False, f"Invalid nested list at item {i+1}: {error}"
    
    return True, "Validation successful."

def validate_message(message_spec, parsed_body):
    """Entry point for message validation."""
    return validate_message_recursive(message_spec.get('body_definition', []), parsed_body)