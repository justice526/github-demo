def is_valid_number(input_str: str) -> bool:
    try:
        float(input_str)
        return True
    except ValueError:
        return False