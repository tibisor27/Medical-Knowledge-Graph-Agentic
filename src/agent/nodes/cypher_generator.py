"""
Schema-Aware Cypher Generator Node.

This node generates Cypher queries based on:
1. The detected user intent
2. Resolved entities from the knowledge graph
3. The exact schema of the Neo4j database
"""

import json
import re
from typing import Dict, Any, List
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.agent.state import (
    MedicalAgentState, 
    ResolvedEntity,
    CypherGeneratorResponse,
    add_to_execution_path
)
from src.config import (
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_API_KEY, 
    OPENAI_API_VERSION,
    validate_config
)
from src.agent.state import print_state_debug
from src.prompts import (
    CYPHER_SYSTEM_PROMPT as SYSTEM_PROMPT, 
    GRAPH_SCHEMA, 
    CYPHER_EXAMPLES, 
    CYPHER_USER_PROMPT as USER_PROMPT_TEMPLATE
)

# ═══════════════════════════════════════════════════════════════════════════════
# CYPHER VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

FORBIDDEN_KEYWORDS = ["CREATE", "DELETE", "SET", "MERGE", "REMOVE", "DROP", "DETACH"]
VALID_NODE_LABELS = ["Medicament", "Nutrient", "DepletionEvent", "Symptom", "Study", 
                     "PharmacologicClass", "FoodSource", "SideEffect"]
VALID_RELATIONSHIPS = ["CAUSES", "DEPLETES", "Has_Symptom", "HAS_EVIDENCE", 
                       "Belongs_To", "Found_In", "Has_Side_Effect"]





def validate_cypher(cypher: str) -> tuple[bool, List[str]]:
    """
    Validate a Cypher query for safety and correctness.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    if not cypher or not cypher.strip():
        return False, ["EMPTY CYPHER QUERY"]
    
    cypher_upper = cypher.upper()
    
    # Check for forbidden write operations
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in cypher_upper:
            errors.append(f"Forbidden keyword '{keyword}' found - only READ operations allowed")
    
    # Check for LIMIT clause
    if "LIMIT" not in cypher_upper:
        errors.append("Missing LIMIT clause - all queries must have a LIMIT")
    
    # Check for RETURN clause
    if "RETURN" not in cypher_upper:
        errors.append("Missing RETURN clause")
    
    # Check that we're not returning entire nodes (bad practice)
    # This is a simple heuristic - look for "RETURN n" without properties
    return_match = re.search(r'RETURN\s+(\w+)\s*(?:,|\s*LIMIT|$)', cypher, re.IGNORECASE)
    if return_match:
        var_name = return_match.group(1)
        if not re.search(rf'{var_name}\.\w+', cypher):
            # Variable is returned without any property access
            pass  # This is actually okay in some cases, so we won't error
    
    return len(errors) == 0, errors


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_llm_5_1_chat():
    """Get the Azure OpenAI LLM instance."""
    validate_config()
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION,
        azure_deployment='gpt-5.1-chat' # Deterministic for code generation
    )



def format_resolved_entities(entities: List[ResolvedEntity]) -> str:
    """Format resolved entities for the prompt."""
    if not entities:
        return "No entities were resolved from the graph."
    
    lines = []
    for entity in entities:
        lines.append(
            f"- '{entity.original_text}' → {entity.resolved_name} "
            f"(type: {entity.node_type}, match: {entity.match_method}, score: {entity.match_score:.2f})"
        )
    
    return "\n".join(lines)



# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def cypher_generator_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Generate a Cypher query based on intent and resolved entities.
    
    This node:
    1. Takes the detected intent and resolved entities
    2. Generates an appropriate Cypher query using LLM
    3. Validates the query for safety
    4. Returns the query ready for execution
    """
    print(f"\n********* NODE 4: CYPHER GENERATOR *********\n")
    # Get intent from conversation analysis (Pydantic model)
    analysis_object = state['conversation_analysis']
    intent = analysis_object.detected_intent if analysis_object else "GENERAL_MEDICAL"

    resolved_entities = state.get('resolved_entities', [])
    unresolved_entities = state.get('unresolved_entities', [])
    user_message = state.get('user_message')
    
    # DEBUG: Print what we're working with
    print(f"----> Intent: {intent}")
    print(f"----> User message: {user_message}")
    print(f"----> Resolved entities count: {len(resolved_entities) if resolved_entities else 0}")
    if resolved_entities:
        for i, e in enumerate(resolved_entities):
            print(f"      Entity {i}: {e.resolved_name} ({e.node_type})")
    else:
        print("      ⚠️ NO RESOLVED ENTITIES!")
    
    # If no resolved entities, we can't generate a useful query
    if not resolved_entities:
        print("❌ ERROR: No resolved entities to query!")
        return {
            **state,
            "generated_cypher": "",
            "cypher_params": {},
            "cypher_reasoning": "No entities were resolved from the graph",
            "cypher_is_valid": False,
            "cypher_errors": ["No resolved entities available"],
            "execution_path": add_to_execution_path(state, "cypher_generator")
        }
    
    # Build the prompt with optimized templates
    raw_prompt = ChatPromptTemplate.from_messages([ 
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT_TEMPLATE)
    ])

    
    try:
        print(f"----> Generating Cypher...\n")
        # Generate Cypher with LLM
        llm = get_llm_5_1_chat()

        chain = raw_prompt | llm.with_structured_output(CypherGeneratorResponse, method="function_calling")

        result = chain.invoke({
            "intent": intent,
            "resolved_entities": format_resolved_entities(resolved_entities),
            "query": user_message,
            "schema": GRAPH_SCHEMA,
            "examples": CYPHER_EXAMPLES
        })

        cypher = result.cypher
        params = result.params
        reasoning = result.reasoning
        errors = result.error

        if "$" in cypher and not params:
            print("⚠️ WARNING: LLM forgot params! Attempting auto-fix based on entities...")

            print(f"Cypher: {cypher}")
            print(f"Tipul entitatii 0: {type(resolved_entities[0])}")
            print(f"Entitatea 0: {resolved_entities[0]}")
            print(f"Resolved name: {resolved_entities[0].resolved_name}")
            
            # Luăm prima entitate rezolvată (cea mai relevantă)
            if resolved_entities and len(resolved_entities) > 0:
                top_entity = resolved_entities[-1].resolved_name # sau 'original_text'
                
                # Harta simplă de injectare în funcție de ce variabilă lipsește
                if "$symptom_name" in cypher:
                    params = {"symptom_name": top_entity}
                elif "$med_name" in cypher:
                    params = {"med_name": top_entity}
                elif "$nutrient_name" in cypher:
                    params = {"nutrient_name": top_entity}
                
                print(f"AUTO-FIXED PARAMS: {params}")
        
        print(f"----> GENERATED CYPHER: {cypher}\n")
        print(f"----> GENERATED PARAMS: {params}\n")
        print(f"----> GENERATED REASONING: {reasoning}\n")
        print(f"----> GENERATED ERRORS: {errors}\n")

        # Check for error in response
        if errors:
            return {
                **state,
                "generated_cypher": "",
                "cypher_params": {},
                "cypher_reasoning": reasoning,
                "cypher_is_valid": False,
                "cypher_errors": [errors],
                "execution_path": add_to_execution_path(state, "cypher_generator")
            }
        
        # Validate the generated Cypher
        is_valid, validation_errors = validate_cypher(cypher)
        
        return {
            **state,
            "generated_cypher": cypher,
            "cypher_reasoning": reasoning,
            "cypher_params": params,
            "cypher_is_valid": is_valid,
            "cypher_errors": validation_errors,
            "cypher_retry_count": state.get("cypher_retry_count", 0),
            "execution_path": add_to_execution_path(state, "cypher_generator")
        }
        
    except json.JSONDecodeError as e:
        return {
            **state,
            "generated_cypher": "",
            "cypher_params": {},
            "cypher_reasoning": "",
            "cypher_is_valid": False,
            "cypher_errors": [f"JSON parse error: {str(e)}"],
            "execution_path": add_to_execution_path(state, "cypher_generator"),
            "errors": state.get("errors", []) + [f"JSON parse error in cypher_generator: {str(e)}"]
        }
        
    except Exception as e:
        return {
            **state,
            "generated_cypher": "",
            "cypher_params": {},
            "cypher_reasoning": "",
            "cypher_is_valid": False,
            "cypher_errors": [f"Generation error: {str(e)}"],
            "execution_path": add_to_execution_path(state, "cypher_generator"),
            "errors": state.get("errors", []) + [f"Error in cypher_generator: {str(e)}"]
        }

