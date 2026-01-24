import json
import logging
from typing import Dict, Any, List, Tuple
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import MedicalAgentState, add_to_execution_path, RetrievalType
from src.utils.get_llm import get_llm_4_1_mini as get_llm
from src.config import (
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_API_KEY, 
    OPENAI_API_VERSION,
    validate_config,
    MAX_ENTITIES_DETAILED,
    MAX_RESPONSE_WORDS
)
from src.prompts import SYNTHESIZER_PROMPT, NO_RETRIEVAL_PROMPT, PRODUCT_RECOMMENDATION_PROMPT

logger = logging.getLogger(__name__)

def build_response_with_history(state: MedicalAgentState, final_response: str, extra_updates: Dict = None) -> Dict[str, Any]:
    user_message = state.get("user_message", "")
    
    new_messages = [
        HumanMessage(content=user_message),
        AIMessage(content=final_response)
    ]
    
    result = {
        **state,
        "final_response": final_response,
        "conversation_history": new_messages,
        "execution_path": add_to_execution_path(state, "response_synthesizer")
    }
    
    if extra_updates:
        result.update(extra_updates)
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def response_synthesizer_node(state: MedicalAgentState) -> Dict[str, Any]:

    analysis = state.get("conversation_analysis")
    graph_results = state.get("graph_results", [])
    user_message = state.get("user_message", "")
    logger.info(f"GRAPH RESULTS: {graph_results}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 1: Handle missing analysis
    # ═══════════════════════════════════════════════════════════════════════════
    if not analysis: # sa trimit la nodul de raspuns llm default sau hardcodat??
        logger.error("No analysis found, returning default response")
        default_response = (
            "I'm sorry, I couldn't understand your question. "
            "I specialize in understanding how medications affect nutrient levels. "
            "Could you tell me what medications you're taking or what symptoms you're experiencing?"
        )
        return build_response_with_history(state, default_response)
    
    logger.info(f"CONVERSATION ANALYSIS: {analysis}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 2: Check for clarification question FIRST!
    # ═══════════════════════════════════════════════════════════════════════════
    needs_clarification = getattr(analysis, 'needs_clarification', False)
    clarification_question = getattr(analysis, 'clarification_question', None)
    
    if needs_clarification:
        if clarification_question:
            logger.info(f"CLARIFICATION NEEDED - Returning question: {clarification_question}")
            return build_response_with_history(state, clarification_question)
        else:
            # Fallback if needs_clarification=True but no question provided
            logger.info("CLARIFICATION NEEDED - No question provided, using fallback")
            fallback_question = "Could you please provide more details? What medications are you currently taking, or what symptoms are you experiencing?"
            return build_response_with_history(state, fallback_question)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 3: Handle NO_RETRIEVAL cases
    # ═══════════════════════════════════════════════════════════════════════════
    retrieval_type = getattr(analysis, 'retrieval_type', None)
    
    # Convert to comparable format
    if hasattr(retrieval_type, 'value'):
        retrieval_type_str = retrieval_type.value
    else:
        retrieval_type_str = str(retrieval_type) if retrieval_type else "NO_RETRIEVAL"

    if retrieval_type_str == "NO_RETRIEVAL" or retrieval_type == RetrievalType.NO_RETRIEVAL:
        logger.info("NO_RETRIEVAL - Generating conversational response")
        return handle_no_retrieval_response(state, analysis, user_message)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 4: Handle PRODUCT_RECOMMENDATION
    # ═══════════════════════════════════════════════════════════════════════════
    if retrieval_type_str == "PRODUCT_RECOMMENDATION" or retrieval_type == RetrievalType.PRODUCT_RECOMMENDATION:
        logger.info("PRODUCT_RECOMMENDATION - Generating product recommendation")
        return handle_product_recommendation(state, analysis, graph_results, user_message)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 5: Normal flow - synthesize from graph results
    # ═══════════════════════════════════════════════════════════════════════════
    return handle_graph_based_response(state, analysis, graph_results, user_message, retrieval_type_str)


def handle_no_retrieval_response(state: MedicalAgentState, analysis, user_message: str) -> Dict[str, Any]:
    logger.info("Generating NO_RETRIEVAL response...")
    
    # Get context from analysis
    medications = getattr(analysis, 'accumulated_medications', []) or []
    symptoms = getattr(analysis, 'accumulated_symptoms', []) or []
    reasoning = getattr(analysis, 'step_by_step_reasoning', 'No reasoning available')

    
    logger.info(f"Accumulated meds: {medications}")
    logger.info(f"Accumulated symptoms: {symptoms}")
    logger.info(f"Step by step reasoning: {reasoning}")
    
    llm = get_llm()
    
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", NO_RETRIEVAL_PROMPT)
        ])

        
        formatted_prompt = prompt.format_messages(
            user_message=user_message,
            medications=", ".join(medications) if medications else "None confirmed yet",
            symptoms=", ".join(symptoms) if symptoms else "None reported yet",
            step_by_step_reasoning=reasoning,
        )
        
        response = llm.invoke(formatted_prompt)
        final_response = response.content
        
        return build_response_with_history(state, final_response)
        
    except Exception as e:
        logger.error(f"Error generating NO_RETRIEVAL response: {e}")
        
        # Smart fallback based on context
        if symptoms and not medications:
            fallback = f"I understand you're experiencing {', '.join(symptoms)}. To help identify if this might be related to nutrient deficiencies, could you tell me what medications you're currently taking?"
        elif medications and not symptoms:
            fallback = f"Thanks for letting me know about your medications. Are you experiencing any symptoms you'd like me to check for possible nutrient connections?"
        else:
            fallback = "I can help you understand how medications affect nutrient levels. What medications are you currently taking, or what symptoms are you experiencing?"
        
        return build_response_with_history(state, fallback)


def handle_product_recommendation(state: MedicalAgentState, analysis, graph_results: List[Dict], user_message: str) -> Dict[str, Any]:
    logger.info("Generating product recommendation response...")
    
    # Get context from analysis
    medications = getattr(analysis, 'accumulated_medications', []) or []
    symptoms = getattr(analysis, 'accumulated_symptoms', []) or []
    nutrients = getattr(analysis, 'accumulated_nutrients', []) or []
    
    # Format graph results (products)
    if graph_results and len(graph_results) > 0:
        results_text = "BeLife Products Found:\n"
        for i, result in enumerate(graph_results, 1):
            results_text += f"\n--- Product {i} ---\n"
            if isinstance(result, dict):
                rec = result.get('recommendation', result)
                if isinstance(rec, dict):
                    product = rec.get('recommended_product', {})
                    target = rec.get('target_nutrient', {})
                    results_text += f"  Product Name: {product.get('name', 'N/A')}\n"
                    results_text += f"  Category: {product.get('primary_category', 'N/A')}\n"
                    results_text += f"  Target Benefit: {product.get('target_benefit', 'N/A')}\n"
                    results_text += f"  Description: {product.get('scientific_description', 'N/A')}\n"
                    results_text += f"  Dosage: {product.get('dosage_per_day', 'N/A')}\n"
                    results_text += f"  Timing: {product.get('dosage_timing', 'N/A')}\n"
                    results_text += f"  Precautions: {product.get('precautions', 'None')}\n"
                    results_text += f"  Target Nutrient: {target.get('name', 'N/A')} ({target.get('amount_in_product', '')} {target.get('unit', '')})\n"
                else:
                    for key, value in result.items():
                        results_text += f"  {key}: {value}\n"
            else:
                results_text += f"  {result}\n"
    else:
        results_text = "NO BELIFE PRODUCTS FOUND for the specified nutrients. Apologize and suggest consulting a healthcare provider."
    
    print(f"   Found {len(graph_results)} products")
    print(f"   Nutrients to address: {nutrients}")
    
    llm = get_llm()
    
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", PRODUCT_RECOMMENDATION_PROMPT)
        ])
        
        formatted_prompt = prompt.format_messages(
            graph_results=results_text,
            medications=", ".join(medications) if medications else "None mentioned",
            symptoms=", ".join(symptoms) if symptoms else "None mentioned",
            nutrients=", ".join(nutrients) if nutrients else "None identified",
            user_message=user_message
        )
        
        response = llm.invoke(formatted_prompt)
        final_response = response.content
        
        return build_response_with_history(state, final_response)
        
    except Exception as e:
        logger.error(f"Error generating product recommendation: {e}")
        
        # Fallback response
        if graph_results and len(graph_results) > 0:
            first_product = graph_results[0].get('recommendation', {}).get('recommended_product', {})
            product_name = first_product.get('name', 'un supliment BeLife')
            fallback = f"Bazat pe nevoile tale, îți recomand {product_name}. Te rog să consulți un medic sau farmacist înainte de a începe orice supliment."
        else:
            fallback = "Din păcate, nu am găsit un produs BeLife potrivit pentru această nevoie. Te recomand să consulți un specialist."
        
        return build_response_with_history(state, fallback)


def handle_graph_based_response(state: MedicalAgentState, analysis, graph_results: List[Dict], user_message: str, retrieval_type_str: str) -> Dict[str, Any]:
    

    all_nutrients = set(getattr(analysis, 'accumulated_nutrients', []) or [])
    
    # Format graph results
    if graph_results and len(graph_results) > 0:
        results_text = "Results found:\n"
        for i, result in enumerate(graph_results, 1):
            results_text += f"\n--- Result {i} ---\n"
            for key, value in result.items():
                results_text += f"  {key}: {value}\n"
    else:
        results_text = "NO RESULTS FOUND IN DATABASE - Do not invent any information. Say you don't have data about this."
    
    # Get analysis attributes safely
    chain_of_thought = getattr(analysis, 'step_by_step_reasoning', 
                               getattr(analysis, 'chain_of_thought', 'No analysis available'))
    medications = getattr(analysis, 'accumulated_medications', []) or []
    symptoms = getattr(analysis, 'accumulated_symptoms', []) or []
    
    # Format lists
    medications_str = ", ".join(medications) if medications else "None mentioned"
    symptoms_str = ", ".join(symptoms) if symptoms else "None mentioned"
    nutrients_str = ", ".join(all_nutrients) if all_nutrients else "None mentioned"
    
    llm = get_llm()
    
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYNTHESIZER_PROMPT)
        ])
        
        formatted_prompt = prompt.format_messages(
            chain_of_thought=chain_of_thought,
            medications=medications_str,
            symptoms=symptoms_str,
            nutrients=nutrients_str,
            graph_results=results_text,
            user_message=user_message,
            retrieval_type=retrieval_type_str
        )
        
        response = llm.invoke(formatted_prompt)
        final_response = response.content
        
        return build_response_with_history(state, final_response)
        
    except Exception as e:
        logger.error(f"Error in response synthesis: {e}")
        return build_response_with_history(state, "I apologize, but I encountered an error processing your request. Could you tell me what medications you're taking? I can help identify if they might be affecting your nutrient levels.")
