import json
import logging
from langchain_core.tools import tool
from src.services import get_medication_service
 
logger = logging.getLogger(__name__)
 
@tool
def medication_lookup(medication: str) -> str:
    """
    Queries the knowledge graph for nutrient depletions caused by a medication.
    Returns the list of nutrients depleted and the associated deficiency symptoms
    for each nutrient
   
    Args:
        medication: Name of the medication (e.g., "Metformin", "Lisinopril", "Aspirin")
    """

    medication_service = get_medication_service()
    results = medication_service.get_medication_info(medication)

    if results.is_success:
        return json.dumps(results.data, indent=2, ensure_ascii=False)
    
    if results.is_not_found:
        return json.dumps({
            "error": False,
            "action_required": "retry_with_correction",
            "message":(
                f"The medication '{medication}' was not found in the knowledge graph. "
                f"The user may have misspeled the name. Try to correct the spelling and call this tool againa"
                f"The term might reffer to a BeLife produt or ingredient instead of a medication"
            ),
            "medication_searched": medication,
        }, ensure_ascii=False)

    if results.is_empty:
        return json.dumps({
            "error":False,
            "message": f"Medication '{results.entity_found}' was found, but it does not have any associated nutrient depletions in the knowledge graph.",
            "medication_searched": medication,
            "depletions": results.data
        }, ensure_ascii=False)

    if results.is_error:
        return json.dumps({
            "error":True,
            "message": f"A database error occurred while searching for medication '{medication}'. Please try again later.",
            "medication_searched": medication,
        }, ensure_ascii=False)
        
    
    