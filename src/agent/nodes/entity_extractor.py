import logging
from typing import Dict, Any, Tuple, Optional, List
from src.agent.state import (
    MedicalAgentState, 
    ResolvedEntity,
    add_to_execution_path
)
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherEntityValidationQueries
from src.services.embeddings_service import get_embedding

logger = logging.getLogger(__name__)


def _try_fulltext_search(search_term: str, entity_type: str, neo4j_client) -> Optional[dict]:

    query_map = {
        "MEDICATION": CypherEntityValidationQueries.MEDICATION_FULLTEXT_QUERY,
        "NUTRIENT": CypherEntityValidationQueries.NUTRIENT_FULLTEXT_QUERY,
        "SYMPTOM": CypherEntityValidationQueries.SYMPTOM_QUERY
        }
    params = {"search_term": search_term}
    query = query_map.get(entity_type)
    if not query:
        return None
    
    try:
        results = neo4j_client.run_safe_query(query, params)
        if results and isinstance(results, list) and len(results) > 0:
            return results[0]
    except Exception as e:
        logger.error(f"Full-text search failed for '{search_term}': {e}")
    
    return None


def _try_direct_match(search_term: str, entity_type: str, neo4j_client) -> Optional[dict]:

    params = {"search_term": search_term}
    
    query_map = {
        "MEDICATION": CypherEntityValidationQueries.MEDICATION_DIRECT_QUERY,
        "NUTRIENT": CypherEntityValidationQueries.NUTRIENT_DIRECT_QUERY,
        "DRUG_CLASS": CypherEntityValidationQueries.PHARMACOLOGIC_CLASS_DIRECT_QUERY,
    }
    
    query = query_map.get(entity_type)
    if not query:
        return None
    
    try:
        results = neo4j_client.run_safe_query(query, params)
        if results and isinstance(results, list) and len(results) > 0:
            return results[0]
    except Exception as e:
        logger.error(f"Direct match failed for '{search_term}': {e}")
    
    return None


def _try_embeddings_search(search_term: str, entity_type: str, neo4j_client) -> Optional[dict]:

    if entity_type != "SYMPTOM":
        logger.debug(f"Embeddings search not implemented for {entity_type}, skipping")
        return None
    
    # Step 1: Generate embedding for search_term
    embedding_vector = get_embedding(search_term)

    if not embedding_vector:
        logger.error(f"Failed to generate embedding for '{search_term}'")
        return None
    
    # Step 2: Query Neo4j vector index
    query = CypherEntityValidationQueries.SYMPTOM_EMBEDDINGS_QUERY
    params = {
        "embedding_vector": embedding_vector,
        "top_k": 5,  # Search top 5 similar symptoms
        "similarity_threshold": 0.75  # Minimum similarity score (cosine similarity)
    }
    
    try:
        results = neo4j_client.run_safe_query(query, params)
        
        if results and isinstance(results, list) and len(results) > 0:
            best_match = results[0]
            similarity_score = best_match.get("similarity", 0.0)
            
            logger.info(f"Embeddings match for '{search_term}': {best_match.get('name')} (similarity: {similarity_score:.3f})")
            return best_match
        else:
            logger.debug(f"No embeddings match found for '{search_term}' (threshold: 0.75)")
            return None
            
    except Exception as e:
        logger.error(f"Embeddings search failed for '{search_term}': {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RESOLUTION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_entity(
    text: str, 
    entity_type: str, 
    neo4j_client
) -> Tuple[bool, Optional[ResolvedEntity]]:
    
    # Strategy 1: Direct match
    result = _try_direct_match(text, entity_type, neo4j_client)
    if result:
        return True, ResolvedEntity(
            original_text=text,
            resolved_name=result.get("name", text),
            node_type=result.get("node_type", entity_type),
            match_score=float(result.get("score", 1.0)),
            match_method="direct"
        )

    # Strategy 2: Full-text search
    result = _try_fulltext_search(text, entity_type, neo4j_client)
    if result and result.get("score", 0) > 0.3:
        return True, ResolvedEntity(
            original_text=text,
            resolved_name=result.get("name", text),
            node_type=result.get("node_type", entity_type),
            match_score=float(result.get("score", 1.0)),
            match_method="fulltext"
        )
    
    # Strategy 3: Embeddings
    result = _try_embeddings_search(text, entity_type, neo4j_client)
    
    if result and result.get("similarity", 0) > 0.45:
        return True, ResolvedEntity(
            original_text=text,
            resolved_name=result.get("name", text),
            node_type=result.get("node_type", entity_type),
            match_score=float(result.get("similarity", 0.0)),
            match_method="embeddings"
        )
    
    # No match found
    logger.error(f"Could not resolve '{text}' ({entity_type})")
    return False, None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def entity_extractor_node(state: MedicalAgentState) -> Dict[str, Any]:
    
    neo4j_client = get_neo4j_client()
    analysis = state.get("conversation_analysis")
    
    if not analysis:
        logger.warning("No conversation analysis, skipping entity resolution")
        return {
            **state,
            "resolved_entities": [],
            "execution_path": add_to_execution_path(state, "entity_extractor")
        }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PRIORITIZE query_* entities (specific for THIS query) over accumulated_*
    # query_* = exact entities AI wants to use for the current Cypher query
    # accumulated_* = all entities from the entire conversation (for context)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # Get query-specific entities (prioritized)
    query_medications = analysis.query_medications
    query_symptoms = analysis.query_symptoms
    query_nutrients = analysis.query_nutrients
    
    
    
    # Collect all entities to resolve
    entities_to_resolve: List[Tuple[str, str]] = []  # (text, type)
    
    for med in query_medications:
        entities_to_resolve.append((med, "MEDICATION"))
    
    for symptom in query_symptoms:
        entities_to_resolve.append((symptom, "SYMPTOM"))
    
    for nutrient in query_nutrients:
        entities_to_resolve.append((nutrient, "NUTRIENT"))
    
    logger.info(f"Entities to resolve: {len(entities_to_resolve)}")
    for text, entity_type in entities_to_resolve:
        logger.info(f"      - '{text}' ({entity_type})")
    
    # Resolve each entity
    resolved_entities: List[ResolvedEntity] = []
    
    for text, entity_type in entities_to_resolve:
        was_resolved, resolved = resolve_entity(text, entity_type, neo4j_client)
        
        if was_resolved and resolved:
            resolved_entities.append(resolved)
            logger.info(f"'{text}' → '{resolved.resolved_name}' ({resolved.match_method})")

    return {
        **state,
        "resolved_entities": resolved_entities,
        "execution_path": add_to_execution_path(state, "entity_extractor")
    }
