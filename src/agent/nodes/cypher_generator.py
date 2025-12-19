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
from langchain_core.prompts import ChatPromptTemplate

from src.agent.utils import format_resolved_entities
from src.utils.get_llm import get_llm_5_1_chat
from src.agent.state import (
    MedicalAgentState, 
    CypherGeneratorResponse,
    add_to_execution_path
)
from src.prompts import (
    CYPHER_SYSTEM_PROMPT as SYSTEM_PROMPT, 
    GRAPH_SCHEMA, 
    CYPHER_EXAMPLES, 
    CYPHER_USER_PROMPT as USER_PROMPT_TEMPLATE
)
from src.utils.validators import validate_cypher
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
    print(f"\n********* NODE 3: CYPHER GENERATOR *********\n")

    analysis_object = state['conversation_analysis']
    intent = analysis_object.detected_intent if analysis_object else "GENERAL_MEDICAL"

    resolved_entities = state.get('resolved_entities', [])
    unresolved_entities = state.get('unresolved_entities', [])
    user_message = state.get('user_message')
    
    # DEBUG: Print what we're working with
    print(f"----> DEBUG: Intent from analysis: {intent}")
    print(f"----> DEBUG: User message: {user_message}")
    print(f"----> DEBUG: Resolved entities: {resolved_entities}")
    
    if resolved_entities:
        for i, e in enumerate(resolved_entities):
            print(f"      Entity {i}: {e.resolved_name} ({e.node_type})")
    else:
        print("      ⚠️ NO RESOLVED ENTITIES!")
    
    # If no resolved entities, we can't generate a useful query
    if not resolved_entities:
        print("      ❌ ERROR: No entities to query the graph with!")
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

