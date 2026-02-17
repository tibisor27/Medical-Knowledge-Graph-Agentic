from langchain_core.tools import tool
import json
import logging
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from src.services.results_formatter import clean_results
from src.services.entity_resolver import get_entity_resolver
 
logger = logging.getLogger(__name__)
 
@tool
def symptom_investigation(symptom: str) -> str:
    """Investigate what could cause a symptom - which nutrient deficiencies or medications might be responsible.
    Use when user reports a symptom and you want to find possible causes.
    Use this tool ONLY when the user has NOT mentioned a specific medication to check against.
    If user has mentioned both a medication AND a symptom, use connection_validation instead.
   
    Args:
        symptom: The symptom to investigate (e.g., 'fatigue', 'numbness', 'headache')
    """
    neo4j = get_neo4j_client()
    resolver = get_entity_resolver()
   
    # Resolve symptom
    resolved = resolver.resolve_symptom(symptom)
    if resolved:
        logger.info(f"Symptom investigation for '{symptom}' resolved to '{resolved.resolved_name}' (method: {resolved.match_method})")
    else:
        return json.dumps({
            "error": False,
            "message": f"No symptom matching '{symptom}' found in the knowledge graph.",
            "symptom_investigated": symptom
        }, ensure_ascii=False)
   
    results = neo4j.run_safe_query(
        CypherQueries.SYMPTOM_INVESTIGATION,
        {"symptom": resolved.resolved_name}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        logger.error(f"Database error during symptom investigation: {results}")
        return json.dumps({
            "error": True,
            "message": "I encountered a technical issue accessing the database. Please try again.",
            "symptom_investigated": symptom,
            "resolution_status": "retry_needed"
        }, ensure_ascii=False)
   
    cleaned = clean_results(results)
    if not cleaned:
        return json.dumps({
            "error": False,
            "message": f"Symptom '{resolved.resolved_name}' was found but no causes are linked to it in the database.",
            "symptom_found": resolved.resolved_name,
            "causes_found": []
        }, ensure_ascii=False)
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)