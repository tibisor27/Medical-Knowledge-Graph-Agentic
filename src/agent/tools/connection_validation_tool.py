import json
from langchain_core.tools import tool
from src.services.results_formatter import clean_results
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from src.services.entity_resolver import get_entity_resolver
import logging
 
logger = logging.getLogger(__name__)
 
@tool
def connection_validation(medication: str, symptom: str) -> str:
    """Check if there's a connection between a specific medication and a specific symptom through nutrient depletion.
    Use when user asks if their medication could be causing their symptom.
    Call this tool ONCE per medication-symptom pair.
   
    Args:
        medication: The medication to check (e.g., "Metformin")
        symptom: The symptom to validate (e.g., "fatigue")
    """
    neo4j = get_neo4j_client()
    resolver = get_entity_resolver()
   
    # Resolve both entities
    resolved_med = resolver.resolve_medication(medication)
    if not resolved_med:
        logger.warning(f"Medication lookup for '{medication}' could not be resolved to any known entity.")
        return json.dumps({
            "connection_found": False,
            "medication": medication,
            "symptom": symptom,
            "message": f"Medication '{medication}' not found in knowledge graph"
        }, ensure_ascii=False)
   
    logger.info(f"Medication lookup for '{medication}' resolved to '{resolved_med.resolved_name}' (method: {resolved_med.match_method})")
    resolved_sym = resolver.resolve_symptom(symptom)
    if not resolved_sym:
        logger.warning(f"Symptom lookup for '{symptom}' could not be resolved to any known entity.")
        return json.dumps({
            "connection_found": False,
            "medication": resolved_med.resolved_name,
            "symptom": symptom,
            "message": f"Symptom '{symptom}' not found in knowledge graph"
        }, ensure_ascii=False)
   
    logger.info(f"Symptom lookup for '{symptom}' resolved to '{resolved_sym.resolved_name}' (method: {resolved_sym.match_method})")
    results = neo4j.run_safe_query(
        CypherQueries.CONNECTION_VALIDATION,
        {"medications": [resolved_med.resolved_name], "symptoms": [resolved_sym.resolved_name]}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        return f"Error validating connection: {results}"
   
    cleaned = clean_results(results)
    if not cleaned:
        return json.dumps({
            "connection_found": False,
            "medication": resolved_med.resolved_name,
            "symptom": resolved_sym.resolved_name,
            "message": "No connection found between this medication and symptom in the knowledge graph"
        }, ensure_ascii=False)
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)