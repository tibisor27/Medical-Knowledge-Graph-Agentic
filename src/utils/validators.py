from typing import List
import re

FORBIDDEN_KEYWORDS = ["CREATE", "DELETE", "SET", "MERGE", "REMOVE", "DROP", "DETACH"]
VALID_NODE_LABELS = ["Medicament", "Nutrient", "DepletionEvent", "Symptom", "Study", 
                     "PharmacologicClass", "FoodSource", "SideEffect"]
VALID_RELATIONSHIPS = ["CAUSES", "DEPLETES", "Has_Symptom", "HAS_EVIDENCE", 
                       "Belongs_To", "Found_In", "Has_Side_Effect"]

def validate_cypher(cypher: str) -> tuple[bool, List[str]]:

    errors = []
    
    if not cypher or not cypher.strip():
        return False, ["EMPTY CYPHER QUERY"]
    
    cypher_upper = cypher.upper()
    
    # Check for forbidden write operations
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in cypher_upper:
            errors.append(f"Forbidden keyword '{keyword}' found - only READ operations allowed")
    
    # Check for LIMIT clause
    if "LIMIT" not in cypher_upper:
        errors.append("Missing LIMIT clause - all queries must have a LIMIT")
    
    # Check for RETURN clause
    if "RETURN" not in cypher_upper:
        errors.append("Missing RETURN clause")
    
    # Check that we're not returning entire nodes (bad practice)
    # This is a simple heuristic - look for "RETURN n" without properties
    return_match = re.search(r'RETURN\s+(\w+)\s*(?:,|\s*LIMIT|$)', cypher, re.IGNORECASE)
    if return_match:
        var_name = return_match.group(1)
        if not re.search(rf'{var_name}\.\w+', cypher):
            # Variable is returned without any property access
            pass  # This is actually okay in some cases, so we won't error
    
    return len(errors) == 0, errors
