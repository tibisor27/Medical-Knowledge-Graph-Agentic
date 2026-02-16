import json
import logging
from langchain_core.tools import tool
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from src.services.results_formatter import clean_results
from src.services.entity_resolver import get_entity_resolver
 
logger = logging.getLogger(__name__)
 
@tool
def medication_lookup(medication: str) -> str:
    """Look up what nutrients a medication depletes and what symptoms might occur.
    Use when user mentions a medication they take.
   
    Args:
        medication: Name of the medication (e.g., "Metformin", "Lisinopril", "Aspirin")
    """
    neo4j = get_neo4j_client()
    resolver = get_entity_resolver()
   
    resolved = resolver.resolve_medication(medication)
    if resolved:
        logger.info(f"Medication lookup for '{medication}' resolved to '{resolved.resolved_name}' (method: {resolved.match_method})")
    else:
        logger.warning(f"Medication lookup for '{medication}' could not be resolved to any known entity.")
        return json.dumps({    #convert json to json string
            "error": False,
            "message": f"No medication found matching '{medication}' in the knowledge graph. Please check the spelling.",
            "medication_searched": medication
        }, ensure_ascii=False)
   
    results = neo4j.run_safe_query(
        CypherQueries.MEDICATION_LOOKUP,
        {"medications": [resolved.resolved_name]}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        logger.error(f"Database error during medication lookup: {results}")
        return json.dumps({
            "error": True,
            "message": "I encountered a technical issue accessing the database. Please try again.",
            "medication_searched": medication,
            "resolution_status": "retry_needed"
        }, ensure_ascii=False)
   
    cleaned = clean_results(results)
    if not cleaned:
        return json.dumps({
            "error": False,
            "message": f"Medication '{resolved.resolved_name}' was found but has no nutrient depletion data.",
            "medication_found": resolved.resolved_name,
            "original_query": medication,
            "depletions": []
        }, ensure_ascii=False)
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)