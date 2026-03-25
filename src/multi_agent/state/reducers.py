def clear_or_add(existing_list: list, new_elements: list) -> list:

    if new_elements == ["CLEAR"]:
        return []
    
    if existing_list is None:
        return new_elements
        
    return existing_list + new_elements
