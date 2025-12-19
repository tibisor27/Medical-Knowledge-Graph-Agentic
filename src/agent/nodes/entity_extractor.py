"""
Entity Extractor + Graph Validator Node.

This node:
1. Extracts medical entities from the user's query using LLM
2. Validates each entity against the Neo4j knowledge graph using Full-Text Index
3. Returns both resolved (found in graph) and unresolved entities
"""

import json
from typing import Dict, Any, List, Tuple
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder 
from langchain_core.messages import HumanMessage

from src.agent.state import (
    MedicalAgentState, 
    ExtractedEntity, 
    ResolvedEntity,
    add_to_execution_path,
    EntityExtractionResponse
)
from src.database.neo4j_client import get_neo4j_client
from src.config import (
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_API_KEY, 
    OPENAI_API_VERSION,
    validate_config
)

from src.prompts import ENTITY_EXTRACTION_SYSTEM_PROMPT
from src.prompts import MEDICATION_FULLTEXT_QUERY, NUTRIENT_FULLTEXT_QUERY, PHARMACOLOGIC_CLASS_FULLTEXT_QUERY, PHARMACOLOGIC_CLASS_DIRECT_QUERY, MEDICATION_DIRECT_QUERY,NUTRIENT_DIRECT_QUERY, SYMPTOM_QUERY

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_llm():
    """Get the Azure OpenAI LLM instance."""
    validate_config()
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION,
        azure_deployment='gpt-4.1-mini',
        temperature=0.0
    )


def resolve_entity_in_graph(entity: ExtractedEntity, neo4j_client) -> Tuple[bool, ResolvedEntity | None]:

    search_term = entity.text
    entity_type = entity.type
    
    results = []
    match_method = "unknown"
    
    try:
        # Choose query based on entity type
        if entity_type == "MEDICATION":
            # Try fulltext first, fall back to direct
            params = {"search_term": search_term}
            try:
                results = neo4j_client.run_safe_query(MEDICATION_FULLTEXT_QUERY, params)
                match_method = "fulltext"
            except Exception:
                pass
                # Fallback to direct query if fulltext fails
                
            if not results or isinstance(results, str):
                try:
                    results = neo4j_client.run_safe_query(MEDICATION_DIRECT_QUERY, params)
                    match_method = "direct"
                except Exception as e:
                    print(f"Error with medication direct query for '{search_term}': {e}")
                    results = None
                    match_method = "error"

                
        elif entity_type == "NUTRIENT":
            params = {"search_term": search_term}
            try:
                results = neo4j_client.run_safe_query(NUTRIENT_FULLTEXT_QUERY, params)
                match_method = "fulltext"
            except Exception:
                pass
                
            if not results or isinstance(results, str):
                try:
                    results = neo4j_client.run_safe_query(NUTRIENT_DIRECT_QUERY, params)
                    match_method = "direct"
                except Exception as e:
                    print(f"Error with nutrient direct query for '{search_term}': {e}")
                    results = None
                    match_method = "error"  
                
        elif entity_type == "SYMPTOM":
            params = {"search_term": search_term}
            try:
                results = neo4j_client.run_safe_query(SYMPTOM_QUERY, params)
                match_method = "fulltext"
            except Exception:
                pass
            if not results or isinstance(results, str):
                result = None
                
        elif entity_type == "DRUG_CLASS":
            params = {"search_term": search_term}
            try:
                results = neo4j_client.run_safe_query(PHARMACOLOGIC_CLASS_FULLTEXT_QUERY, params)
                match_method = "fulltext"
            except Exception:
                pass
                
            if not results or isinstance(results, str):
                try:
                    results = neo4j_client.run_safe_query(PHARMACOLOGIC_CLASS_DIRECT_QUERY, params)
                    match_method = "direct"
                except Exception as e:
                    print(f"Error with drug class direct query for '{search_term}': {e}")
                    results = None
                    match_method = "error"
        
        # Check if we got valid results
        if results and isinstance(results, list) and len(results) > 0:
            best_match = results[0]
            return True, ResolvedEntity(
                original_text=search_term,
                resolved_name=best_match.get("name", search_term),
                node_type=best_match.get("node_type", entity_type),
                match_score=float(best_match.get("score", 1.0)),
                match_method=match_method
            )
            
    except Exception as e:
        print(f"Error resolving entity '{search_term}': {e}")
    
    return False, None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def entity_extractor_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Extract entities from the query and validate them against the knowledge graph.

    1. Validates each entity against Neo4j using Full-Text Index
    2. Separates resolved (found) from unresolved (not found) entities
    """

    print(f"\n********* NODE 2: ENTITY EXTRACTION *********\n")
    llm = get_llm()
    analysis = state.get("conversation_analysis")
    
    candidates = []
    # Access fields from Pydantic model or use defaults
    if analysis is not None:
        step_by_step_reasoning = analysis.step_by_step_reasoning
        medications = [ExtractedEntity(text=medication, type="MEDICATION") for medication in analysis.accumulated_medications]
        nutrients = [ExtractedEntity(text=nutrient, type="NUTRIENT") for nutrient in analysis.accumulated_nutrients]
        symptoms = [ExtractedEntity(text=symptom, type="SYMPTOM") for symptom in analysis.accumulated_symptoms]
        candidates = medications + nutrients + symptoms
        step_by_step_reasoning = analysis.step_by_step_reasoning
    else:
        step_by_step_reasoning = "No conversation analysis found"
        candidates = []
    
    print(f"Searching for entities in the graph: {candidates}")
    
    resolved_entities = []
    unresolved_entities = []
    
    neo4j_client = get_neo4j_client()
    
    for entity in candidates:
        was_resolved, resolved_entity = resolve_entity_in_graph(entity, neo4j_client)
        
        if was_resolved and resolved_entity:
            resolved_entities.append(resolved_entity)
        else:
            unresolved_entities.append(entity)

     # DEBUG: Print what we have from analysis
    print(f"\n----> DEBUG: Intent from analysis: '{analysis.detected_intent}'")
    print(f"----> DEBUG: Accumulated medications: {analysis.accumulated_medications}")
    print(f"----> DEBUG: Accumulated nutrients: {analysis.accumulated_nutrients}")
    print(f"----> DEBUG: Accumulated symptoms: {analysis.accumulated_symptoms}")
    print(f"----> DEBUG: Already extracted texts: {candidates}")
    print(f"\n----> Final entities after adding accumulated: {resolved_entities}")
    print(f"----> DEBUG: Unresolved entities: {unresolved_entities}")
    
    return {
        **state,
        "resolved_entities": resolved_entities,
        "unresolved_entities": unresolved_entities,
        "execution_path": add_to_execution_path(state, "entity_extractor")
    }