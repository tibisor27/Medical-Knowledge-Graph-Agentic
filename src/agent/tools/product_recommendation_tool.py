from langchain_core.tools import tool
import json
import logging
from src.database.cypher_queries import CypherQueries
from typing import List
from src.services.entity_resolver import get_entity_resolver
from src.database.neo4j_client import get_neo4j_client
from src.services.results_formatter import clean_results
 
logger = logging.getLogger(__name__)
 
@tool
def product_recommendation(nutrients: List[str]) -> str:
    """Find BeLife supplement products that contain specific nutrients.
    Use ONLY after nutrients have been identified through previous tool calls,
    and user explicitly asks for a recommendation.
   
    Args:
        nutrients: List of nutrient names to find products for (e.g., ['Vitamin B12', 'Folic Acid'])
    """
    neo4j = get_neo4j_client()
    resolver = get_entity_resolver()
   
    # Resolve each nutrient
    resolved_nutrients = []
    for nut in nutrients:
        resolved = resolver.resolve_nutrient(nut)
        if resolved:
            logger.info(f"Nutrient lookup for '{nut}' resolved to '{resolved.resolved_name}' (method: {resolved.match_method})")
            resolved_nutrients.append(resolved.resolved_name)
        else:
            logger.warning(f"Nutrient lookup for '{nut}' could not be resolved to any known entity.")
            return json.dumps({    #convert json to json string
                "error": False,
                "message": f"No nutrient found matching '{nut}' in the knowledge graph. Please check the spelling.",
                "nutrient_searched": nut
            }, ensure_ascii=False)
   
    if not resolved_nutrients:
        return f"None of the specified nutrients ({nutrients}) were found in the knowledge graph."
   
    results = neo4j.run_safe_query(
        CypherQueries.PRODUCT_RECOMMENDATION,
        {"nutrients": resolved_nutrients}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        return f"Error finding products: {results}"
   
    cleaned = clean_results(results)
    if not cleaned:
        return f"No BeLife products found for nutrients: {resolved_nutrients}"
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)