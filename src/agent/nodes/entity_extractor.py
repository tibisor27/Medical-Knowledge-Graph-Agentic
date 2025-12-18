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


# ═══════════════════════════════════════════════════════════════════════════════
# USER PROMPT TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

USER_PROMPT_TEMPLATE = """
    === PREVIOUS ANALYZED STATE (Reference) ===
    The previous analysis identified these entities:
    Accumulated medications: {accumulated_medications}
    Accumulated symptoms: {accumulated_symptoms}
    Accumulated nutrients: {accumulated_nutrients}

    === NEW USER MESSAGE ===
    {query}
    
    Extract ALL medical entities from the NEW USER QUERY above. 
    Resolve pronouns using the Context and Conversation History.
    """


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH VALIDATION QUERIES
# ═══════════════════════════════════════════════════════════════════════════════

MEDICATION_FULLTEXT_QUERY = """
CALL db.index.fulltext.queryNodes("medicament_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN node.name AS name, score, "Medicament" AS node_type
ORDER BY score DESC
LIMIT 3
"""

NUTRIENT_FULLTEXT_QUERY = """
CALL db.index.fulltext.queryNodes("nutrient_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN node.name AS name, score, "Nutrient" AS node_type
ORDER BY score DESC
LIMIT 3
"""

PHARMACOLOGIC_CLASS_FULLTEXT_QUERY = """
CALL db.index.fulltext.queryNodes("pharmacologic_class_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN p.pharmacologic_class AS name, score, "PharmacologicClass" AS node_type
ORDER BY score DESC
LIMIT 3
"""

PHARMACOLOGIC_CLASS_DIRECT_QUERY = """
MATCH (p:PharmacologicClass)
WHERE toLower(p.pharmacologic_class) CONTAINS toLower($search_term)
RETURN p.pharmacologic_class AS name, 1.0 AS score, "PharmacologicClass" AS node_type
LIMIT 3
"""

# Fallback: Direct match queries (if fulltext index doesn't exist)
MEDICATION_DIRECT_QUERY = """
MATCH (m:Medicament)
WHERE toLower(m.name) CONTAINS toLower($search_term)
   OR ANY(brand IN m.brand_names WHERE toLower(brand) CONTAINS toLower($search_term))
   OR ANY(syn IN m.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
RETURN m.name AS name, 1.0 AS score, "Medicament" AS node_type
LIMIT 3
"""

NUTRIENT_DIRECT_QUERY = """
MATCH (n:Nutrient)
WHERE toLower(n.name) CONTAINS toLower($search_term)
   OR ANY(syn IN n.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
RETURN n.name AS name, 1.0 AS score, "Nutrient" AS node_type
LIMIT 3
"""

SYMPTOM_QUERY = """
CALL db.index.fulltext.queryNodes("symptom_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN node.name AS name, score, "Symptom" AS node_type
ORDER BY score DESC
LIMIT 3
"""


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
        temperature=0.0 # More deterministic for extraction
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
    
    This node:
    1. Uses LLM to extract medical entities from the query
    2. Validates each entity against Neo4j using Full-Text Index
    3. Separates resolved (found) from unresolved (not found) entities
    """

    print(f"\n********* NODE 2: ENTITY EXTRACTION *********\n")
    llm = get_llm()
    analysis = state.get("conversation_analysis")
    conversation_history = state.get("conversation_history", [])
    
    # Access fields from Pydantic model or use defaults
    if analysis is not None:
        step_by_step_reasoning = analysis.step_by_step_reasoning
        accumulated_medications = analysis.accumulated_medications
        accumulated_symptoms = analysis.accumulated_symptoms
        accumulated_nutrients = analysis.accumulated_nutrients
    else:
        step_by_step_reasoning = "No conversation analysis found"
        accumulated_medications = []
        accumulated_symptoms = []
        accumulated_nutrients = []
    
    # Build the extraction prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", ENTITY_EXTRACTION_SYSTEM_PROMPT),

        MessagesPlaceholder(variable_name="conversation_history"),
        
        ("human", USER_PROMPT_TEMPLATE)
    ])

    chain = prompt | llm.with_structured_output(EntityExtractionResponse)

    response = chain.invoke({
        "conversation_history": conversation_history,
        "query": state.get("user_message", ""),
        "accumulated_medications": accumulated_medications,
        "accumulated_symptoms": accumulated_symptoms,
        "accumulated_nutrients": accumulated_nutrients
    })

    extracted_entities = list(response.entities)
    print(f"\n----> LLM extracted entities: {extracted_entities}")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ADD ACCUMULATED ENTITIES BASED ON INTENT
    # If intent is NUTRIENT_INFO, we need the nutrient from accumulated_nutrients
    # If intent is DRUG_INFO, we need the medication from accumulated_medications
    # ═══════════════════════════════════════════════════════════════════════════════
    
    intent = analysis.detected_intent if analysis else "GENERAL_MEDICAL"
    extracted_texts = {e.text.lower() for e in extracted_entities}
    
    # DEBUG: Print what we have from analysis
    print(f"\n----> DEBUG: Intent from analysis: '{intent}'")
    print(f"----> DEBUG: Accumulated medications: {accumulated_medications}")
    print(f"----> DEBUG: Accumulated nutrients: {accumulated_nutrients}")
    print(f"----> DEBUG: Accumulated symptoms: {accumulated_symptoms}")
    print(f"----> DEBUG: Already extracted texts: {extracted_texts}")
    
    # For NUTRIENT_INFO - add nutrients from context
    if intent in ["NUTRIENT_INFO", "DEFICIENCY_SYMPTOMS", "FOOD_SOURCES", "NUTRIENT_DEPLETED_BY"]:
        for nutrient in accumulated_nutrients:
            if nutrient.lower() not in extracted_texts:
                print(f"----> Adding accumulated nutrient for {intent}: {nutrient}")
                extracted_entities.append(ExtractedEntity(
                    text=nutrient,
                    type="NUTRIENT",
                    confidence=0.9
                ))
                extracted_texts.add(nutrient.lower())
    
    # For DRUG_INFO or DRUG_DEPLETES - add medications from context
    if intent in ["DRUG_INFO", "DRUG_DEPLETES_NUTRIENT"]:
        for med in accumulated_medications:
            if med.lower() not in extracted_texts:
                print(f"----> Adding accumulated medication for {intent}: {med}")
                extracted_entities.append(ExtractedEntity(
                    text=med,
                    type="MEDICATION",
                    confidence=0.9
                ))
                extracted_texts.add(med.lower())
    
    # For SYMPTOM_TO_DEFICIENCY - add symptoms from context
    if intent == "SYMPTOM_TO_DEFICIENCY":
        for symptom in accumulated_symptoms:
            if symptom.lower() not in extracted_texts:
                print(f"----> Adding accumulated symptom for {intent}: {symptom}")
                extracted_entities.append(ExtractedEntity(
                    text=symptom,
                    type="SYMPTOM",
                    confidence=0.9
                ))
                extracted_texts.add(symptom.lower())
    
    # For GENERAL_MEDICAL or unknown intents - add ALL accumulated entities
    # This handles vague queries like "Are there any side effects of taking these?"
    if intent in ["GENERAL_MEDICAL", "UNKNOWN"] or not extracted_entities or all(e.text.lower() in ["these", "this", "that", "it", "them"] for e in extracted_entities):
        print(f"----> GENERAL/VAGUE query detected - adding all accumulated entities")
        
        # Add all medications
        for med in accumulated_medications:
            if med.lower() not in extracted_texts:
                print(f"----> Adding accumulated medication: {med}")
                extracted_entities.append(ExtractedEntity(
                    text=med,
                    type="MEDICATION",
                    confidence=0.9
                ))
                extracted_texts.add(med.lower())
        
        # Add all nutrients
        for nutrient in accumulated_nutrients:
            if nutrient.lower() not in extracted_texts:
                print(f"----> Adding accumulated nutrient: {nutrient}")
                extracted_entities.append(ExtractedEntity(
                    text=nutrient,
                    type="NUTRIENT",
                    confidence=0.9
                ))
                extracted_texts.add(nutrient.lower())
        
        # Add all symptoms
        for symptom in accumulated_symptoms:
            if symptom.lower() not in extracted_texts:
                print(f"----> Adding accumulated symptom: {symptom}")
                extracted_entities.append(ExtractedEntity(
                    text=symptom,
                    type="SYMPTOM",
                    confidence=0.9
                ))
                extracted_texts.add(symptom.lower())
    
    # Remove pronoun entities (these, this, that, it, them) - they're not useful
    extracted_entities = [e for e in extracted_entities if e.text.lower() not in ["these", "this", "that", "it", "them"]]
    
    print(f"\n----> Final entities after adding accumulated: {extracted_entities}")
    
    resolved_entities = []
    unresolved_entities = []
    
    neo4j_client = get_neo4j_client()
    
    for entity in extracted_entities:
        was_resolved, resolved_entity = resolve_entity_in_graph(entity, neo4j_client)
        
        if was_resolved and resolved_entity:
            resolved_entities.append(resolved_entity)
        else:
            unresolved_entities.append(entity)
        
    return {
        **state,
        "extracted_entities": extracted_entities,
        "resolved_entities": resolved_entities,
        "unresolved_entities": unresolved_entities,
        "execution_path": add_to_execution_path(state, "entity_extractor")
    }


def test_entity_extractor():
    """Test the entity extractor node."""
    state = MedicalAgentState(
        user_message="What If I take that Nurofen? it will affect my sleep because of any nutrient depletion?",
        conversation_history=[HumanMessage(content="What nutrients does Acetaminophen deplete?")]
    )
    state = entity_extractor_node(state)
    print(f"----> State: {state}")
    print(f"----> Extracted entities: {state['extracted_entities']}")
    print(f"----> Resolved entities: {state['resolved_entities']}")
    print(f"----> Unresolved entities: {state['unresolved_entities']}")


if __name__ == "__main__":
    test_entity_extractor()