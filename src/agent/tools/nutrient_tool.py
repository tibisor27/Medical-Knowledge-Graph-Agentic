import json
from langchain_core.tools import tool
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from src.services.entity_resolver import get_entity_resolver
from src.services.results_formatter import clean_results
import logging
 
logger = logging.getLogger(__name__)
 
@tool
def nutrient_lookup(nutrient: str) -> str:
    """Get detailed information about a nutrient - what it does, RDA, food sources, supplementation forms.
    Use when user wants to learn about a specific vitamin or mineral.
   
    Args:
        nutrient: The nutrient to learn about (e.g., 'Vitamin B12', 'Magnesium', 'Iron')
    """
    resolver = get_entity_resolver()
    neo4j = get_neo4j_client()
 
    resolved = resolver.resolve_nutrient(nutrient)
    if resolved:
        logger.info(f"Nutrient lookup for '{nutrient}' resolved to '{resolved.resolved_name}' (method: {resolved.match_method})")
    else:
        logger.warning(f"Nutrient lookup for '{nutrient}' could not be resolved to any known entity.")
        return json.dumps({    #convert json to json string
            "error": False,
            "message": f"No nutrient found matching '{nutrient}' in the knowledge graph. Please check the spelling.",
            "nutrient_searched": nutrient
        }, ensure_ascii=False)
   
    results = neo4j.run_safe_query(
        CypherQueries.NUTRIENT_LOOKUP,
        {"nutrients": [resolved.resolved_name]}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        logger.error(f"Database error during nutrient lookup: {results}")
        return json.dumps({
            "error": True,
            "message": "I encountered a technical issue accessing the database. Please try again.",
            "nutrient_searched": nutrient,
            "resolution_status": "retry_needed"
        }, ensure_ascii=False)
   
    cleaned = clean_results(results)
    if not cleaned:
        return json.dumps({
            "error": False,
            "message": f"Nutrient '{resolved.resolved_name}' was found but has no detailed information.",
            "nutrient_found": resolved.resolved_name,
            "original_query": nutrient,
            "details": []
        }, ensure_ascii=False)
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)