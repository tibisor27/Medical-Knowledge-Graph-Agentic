import json
import logging
from typing import List, Optional
from langchain_core.tools import tool
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries, CypherEntityValidationQueries
from src.services.embeddings_service import get_embeddings
 
logger = logging.getLogger(__name__)
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY RESOLUTION HELPERS (embedded in tools)
# ═══════════════════════════════════════════════════════════════════════════════
 
def _resolve_medication(name: str, neo4j_client) -> Optional[str]:
    """Resolve medication name to canonical graph name."""
    # Strategy 1: Direct match
    result = neo4j_client.run_safe_query(
        CypherEntityValidationQueries.MEDICATION_DIRECT_QUERY,
        {"search_term": name}
    )
    if result and isinstance(result, list) and len(result) > 0:
        resolved = result[0].get("name", name)
        logger.info(f"Medication resolved (direct): '{name}' → '{resolved}'")
        return resolved
   
    # Strategy 2: Fulltext
    result = neo4j_client.run_safe_query(
        CypherEntityValidationQueries.MEDICATION_FULLTEXT_QUERY,
        {"search_term": name}
    )
    if result and isinstance(result, list) and len(result) > 0:
        resolved = result[0].get("name", name)
        logger.info(f"Medication resolved (fulltext): '{name}' → '{resolved}'")
        return resolved
   
    logger.warning(f"Could not resolve medication: '{name}'")
    return None
 
 
def _resolve_nutrient(name: str, neo4j_client) -> Optional[str]:
    """Resolve nutrient name to canonical graph name."""
    # Strategy 1: Direct match
    result = neo4j_client.run_safe_query(
        CypherEntityValidationQueries.NUTRIENT_DIRECT_QUERY,
        {"search_term": name}
    )
    if result and isinstance(result, list) and len(result) > 0:
        resolved = result[0].get("name", name)
        logger.info(f"Nutrient resolved (direct): '{name}' → '{resolved}'")
        return resolved
   
    # Strategy 2: Fulltext
    result = neo4j_client.run_safe_query(
        CypherEntityValidationQueries.NUTRIENT_FULLTEXT_QUERY,
        {"search_term": name}
    )
    if result and isinstance(result, list) and len(result) > 0:
        resolved = result[0].get("name", name)
        logger.info(f"Nutrient resolved (fulltext): '{name}' → '{resolved}'")
        return resolved
   
    logger.warning(f"Could not resolve nutrient: '{name}'")
    return None
 
 
def _resolve_symptom(name: str, neo4j_client) -> Optional[str]:
    """Resolve symptom name to canonical graph name. Uses fulltext + embeddings."""
    # Strategy 1: Fulltext
    result = neo4j_client.run_safe_query(
        CypherEntityValidationQueries.SYMPTOM_FULLTEXT_QUERY,
        {"search_term": name}
    )
    if result and isinstance(result, list) and len(result) > 0:
        resolved = result[0].get("name", name)
        score = result[0].get("score", 0)
        logger.info(f"Symptom resolved (fulltext, score={score:.2f}): '{name}' → '{resolved}'")
        return resolved
   
    # Strategy 2: Embeddings
    embedding_vector = get_embeddings(name)
    if embedding_vector:
        result = neo4j_client.run_safe_query(
            CypherEntityValidationQueries.SYMPTOM_EMBEDDINGS_QUERY,
            {"embedding_vector": embedding_vector, "top_k": 5, "similarity_threshold": 0.80}
        )
        if result and isinstance(result, list) and len(result) > 0:
            resolved = result[0].get("name", name)
            similarity = result[0].get("similarity", 0)
            logger.info(f"Symptom resolved (embeddings, sim={similarity:.3f}): '{name}' → '{resolved}'")
            return resolved
   
    logger.warning(f"Could not resolve symptom: '{name}'")
    return None
 
 
def _clean_results(results) -> list:
    """Clean None/empty values from results."""
    if not results or not isinstance(results, list):
        return []
    cleaned = []
    for record in results:
        if isinstance(record, dict):
            clean = {k: v for k, v in record.items() if v is not None and v != "" and v != []}
            if clean:
                cleaned.append(clean)
        else:
            cleaned.append(record)
    return cleaned
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH TOOLS (ReAct Agent Tools)
# ═══════════════════════════════════════════════════════════════════════════════
 
@tool
def medication_lookup(medication: str) -> str:
    """Look up what nutrients a medication depletes and what symptoms might occur.
    Use when user mentions a medication they take.
   
    Args:
        medication: Name of the medication (e.g., "Metformin", "Lisinopril", "Aspirin")
    """
    neo4j = get_neo4j_client()
   
    # Resolve entity first
    resolved_name = _resolve_medication(medication, neo4j)
    if not resolved_name:
        return json.dumps({
            "error": False,
            "message": f"No medication found matching '{medication}' in the knowledge graph. Please check the spelling.",
            "medication_searched": medication
        }, ensure_ascii=False)
   
    results = neo4j.run_safe_query(
        CypherQueries.MEDICATION_LOOKUP,
        {"medications": [resolved_name]}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        logger.error(f"Database error during medication lookup: {results}")
        return json.dumps({
            "error": True,
            "message": "I encountered a technical issue accessing the database. Please try again.",
            "medication_searched": medication,
            "resolution_status": "retry_needed"
        }, ensure_ascii=False)
   
    cleaned = _clean_results(results)
    if not cleaned:
        return json.dumps({
            "error": False,
            "message": f"Medication '{resolved_name}' was found but has no nutrient depletion data.",
            "medication_found": resolved_name,
            "depletions": []
        }, ensure_ascii=False)
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)
 
 
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
   
    # Resolve symptom
    resolved_name = _resolve_symptom(symptom, neo4j)
    if not resolved_name:
        return json.dumps({
            "error": False,
            "message": f"No symptom matching '{symptom}' found in the knowledge graph.",
            "symptom_investigated": symptom
        }, ensure_ascii=False)
   
    # Query uses single $symptom parameter (ReAct simplified version)
    results = neo4j.run_safe_query(
        CypherQueries.SYMPTOM_INVESTIGATION,
        {"symptom": resolved_name}
    )
   
    # Handle database errors separately
    if isinstance(results, str) and "ERROR" in results:
        logger.error(f"Database error during symptom investigation: {results}")
        return json.dumps({
            "error": True,
            "message": "I encountered a technical issue accessing the database. Please try again.",
            "symptom_investigated": symptom,
            "resolution_status": "retry_needed"
        }, ensure_ascii=False)
   
    cleaned = _clean_results(results)
    if not cleaned:
        return json.dumps({
            "error": False,
            "message": f"Symptom '{resolved_name}' was found but no causes are linked to it in the database.",
            "symptom_found": resolved_name,
            "causes_found": []
        }, ensure_ascii=False)
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)
 
 
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
   
    # Resolve both entities
    resolved_med = _resolve_medication(medication, neo4j)
    if not resolved_med:
        return json.dumps({
            "connection_found": False,
            "medication": medication,
            "symptom": symptom,
            "message": f"Medication '{medication}' not found in knowledge graph"
        }, ensure_ascii=False)
   
    resolved_sym = _resolve_symptom(symptom, neo4j)
    if not resolved_sym:
        return json.dumps({
            "connection_found": False,
            "medication": resolved_med,
            "symptom": symptom,
            "message": f"Symptom '{symptom}' not found in knowledge graph"
        }, ensure_ascii=False)
   
    results = neo4j.run_safe_query(
        CypherQueries.CONNECTION_VALIDATION,
        {"medications": [resolved_med], "symptoms": [resolved_sym]}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        return f"Error validating connection: {results}"
   
    cleaned = _clean_results(results)
    if not cleaned:
        return json.dumps({
            "connection_found": False,
            "medication": resolved_med,
            "symptom": resolved_sym,
            "message": "No connection found between this medication and symptom in the knowledge graph"
        }, ensure_ascii=False)
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)
 
 
@tool
def nutrient_education(nutrient: str) -> str:
    """Get detailed information about a nutrient - what it does, RDA, food sources, supplementation forms.
    Use when user wants to learn about a specific vitamin or mineral.
   
    Args:
        nutrient: The nutrient to learn about (e.g., 'Vitamin B12', 'Magnesium', 'Iron')
    """
    neo4j = get_neo4j_client()
   
    # Resolve nutrient
    resolved_name = _resolve_nutrient(nutrient, neo4j)
    if not resolved_name:
        return f"No nutrient matching '{nutrient}' found in the knowledge graph."
   
    results = neo4j.run_safe_query(
        CypherQueries.NUTRIENT_EDUCATION,
        {"nutrients": [resolved_name], "medications": []}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        return f"Error getting nutrient info: {results}"
   
    cleaned = _clean_results(results)
    if not cleaned:
        return f"Nutrient '{resolved_name}' was found but no detailed info available."
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)
 
 
@tool
def product_recommendation(nutrients: List[str]) -> str:
    """Find BeLife supplement products that contain specific nutrients.
    Use ONLY after nutrients have been identified through previous tool calls,
    and user explicitly asks for a recommendation.
   
    Args:
        nutrients: List of nutrient names to find products for (e.g., ['Vitamin B12', 'Folic Acid'])
    """
    neo4j = get_neo4j_client()
   
    if isinstance(nutrients, str):
        nutrients = [nutrients]
   
    # Resolve each nutrient
    resolved_nutrients = []
    for nut in nutrients:
        resolved = _resolve_nutrient(nut, neo4j)
        if resolved:
            resolved_nutrients.append(resolved)
        else:
            logger.warning(f"Could not resolve nutrient for recommendation: '{nut}'")
   
    if not resolved_nutrients:
        return f"None of the specified nutrients ({nutrients}) were found in the knowledge graph."
   
    results = neo4j.run_safe_query(
        CypherQueries.PRODUCT_RECOMMENDATION,
        {"nutrients": resolved_nutrients}
    )
   
    if isinstance(results, str) and "ERROR" in results:
        return f"Error finding products: {results}"
   
    cleaned = _clean_results(results)
    if not cleaned:
        return f"No BeLife products found for nutrients: {resolved_nutrients}"
   
    return json.dumps(cleaned, indent=2, ensure_ascii=False)
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# TOOLS REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════
 
ALL_TOOLS = [
    medication_lookup,
    symptom_investigation,
    connection_validation,
    nutrient_education,
    product_recommendation,
]