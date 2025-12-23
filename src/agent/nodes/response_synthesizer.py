"""
Response Synthesizer Node - Optimized for Concise, Contextual Responses.

This node generates natural language responses that:
1. Handle clarification questions FIRST
2. Are CONCISE (50-150 words) for optimal conversation history
3. Explicitly mention key entities for future reference
4. Offer relevant follow-up suggestions
5. Adapt to detected language
"""

import json
from typing import Dict, Any, List, Tuple
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import MedicalAgentState, add_to_execution_path, RetrievalType
from src.config import (
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_API_KEY, 
    OPENAI_API_VERSION,
    validate_config
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MAX_ENTITIES_DETAILED = 5
MAX_RESPONSE_WORDS = 150


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
        temperature=0.3,
    )


def build_response_with_history(state: MedicalAgentState, final_response: str, extra_updates: Dict = None) -> Dict[str, Any]:
    """Build the return dict and ADD messages to conversation_history."""
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
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

SYNTHESIZER_PROMPT = """You are a Medical Information Assistant specialized in identifying 
NUTRIENT DEFICIENCIES caused by medications.

═══════════════════════════════════════════════════════════════════════════════
🎯 YOUR PRIMARY GOAL
═══════════════════════════════════════════════════════════════════════════════

Guide the conversation toward:
1. Identifying which medications the user takes
2. Understanding which nutrients those medications deplete  
3. Connecting their symptoms to potential deficiencies
4. Naturally leading toward vitamin/supplement solutions

═══════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL RULES
═══════════════════════════════════════════════════════════════════════════════

1. **ONLY use information from the Database Results below**
   - If database results are empty, say "I don't have information about that in my database"
   - NEVER invent medical facts

2. **If no results, guide the conversation**
   - Ask what medications they take
   - Ask about their symptoms

3. **Always connect to nutrient solutions**
   - When discussing medication effects → mention the depleted nutrients
   - When discussing symptoms → mention which deficiencies cause them

4. **Be honest about limitations**
   - "Based on my database..." 
   - "According to the information I have..."

═══════════════════════════════════════════════════════════════════════════════
📊 DATABASE RESULTS (YOUR ONLY SOURCE OF TRUTH)
═══════════════════════════════════════════════════════════════════════════════

{graph_results}

═══════════════════════════════════════════════════════════════════════════════
🔍 ANALYSIS CONTEXT
═══════════════════════════════════════════════════════════════════════════════

**Analyzer reasoning:** {chain_of_thought}

**Entities identified:**
- Medications: {medications}
- Symptoms: {symptoms}
- Nutrients: {nutrients}

**Query type:** {retrieval_type}

═══════════════════════════════════════════════════════════════════════════════
💬 USER MESSAGE
═══════════════════════════════════════════════════════════════════════════════

{user_message}

═══════════════════════════════════════════════════════════════════════════════
📝 RESPONSE GUIDELINES
═══════════════════════════════════════════════════════════════════════════════

Keep response concise: 2-3 paragraphs max.
End with a guiding question when appropriate.
"""


NO_RETRIEVAL_PROMPT = """You are a helpful medical assistant focused on medication-nutrient interactions.

The user's message: "{user_message}"

Current conversation context:
- User's confirmed medications: {medications}
- User's reported symptoms: {symptoms}  
- User's response type: {response_type}

The analyzer determined NO database query was needed because: {reasoning}

Your task:
1. If user denied taking suggested medications → acknowledge and ask what they DO take
2. If user just acknowledged (thanks, ok) → ask if they have questions or want more info
3. If user gave vague info → ask for specifics
4. Keep response short (2-3 sentences)
5. Always end with a question to move conversation forward
6. Match the user's language

Generate a helpful, conversational response:"""


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def response_synthesizer_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Generează răspunsul final bazat pe analiză și rezultatele din graf.
    
    PRIORITY ORDER:
    1. Check for clarification_question → return it directly
    2. Check for NO_RETRIEVAL → generate conversational response
    3. Normal flow → synthesize from graph results
    """
    print("\n" + "="*60)
    print("💬 NODE 3: RESPONSE SYNTHESIZER")
    print("="*60)
    
    # Extract state values
    analysis = state.get("conversation_analysis")
    graph_results = state.get("graph_results", [])
    user_message = state.get("user_message", "")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 1: Handle missing analysis
    # ═══════════════════════════════════════════════════════════════════════════
    if not analysis:
        print("⚠️ No analysis found, returning default response")
        default_response = (
            "I'm sorry, I couldn't understand your question. "
            "I specialize in understanding how medications affect nutrient levels. "
            "Could you tell me what medications you're taking or what symptoms you're experiencing?"
        )
        return build_response_with_history(state, default_response)
    
    print(f"----> CONVERSATION ANALYSIS: {analysis}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 2: Check for clarification question FIRST!
    # ═══════════════════════════════════════════════════════════════════════════
    needs_clarification = getattr(analysis, 'needs_clarification', False)
    clarification_question = getattr(analysis, 'clarification_question', None)
    
    if needs_clarification:
        if clarification_question:
            print(f"🔄 CLARIFICATION NEEDED - Returning question: {clarification_question}")
            return build_response_with_history(state, clarification_question)
        else:
            # Fallback if needs_clarification=True but no question provided
            print("🔄 CLARIFICATION NEEDED - No question provided, using fallback")
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
    
    print(f"📊 Graph results count: {len(graph_results)}")
    print(f"🔎 Retrieval type: {retrieval_type_str}")
    
    if retrieval_type_str == "NO_RETRIEVAL" or retrieval_type == RetrievalType.NO_RETRIEVAL:
        print("⏭️ NO_RETRIEVAL - Generating conversational response")
        return handle_no_retrieval_response(state, analysis, user_message)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PRIORITY 4: Normal flow - synthesize from graph results
    # ═══════════════════════════════════════════════════════════════════════════
    return handle_graph_based_response(state, analysis, graph_results, user_message, retrieval_type_str)


def handle_no_retrieval_response(state: MedicalAgentState, analysis, user_message: str) -> Dict[str, Any]:
    """
    Handle NO_RETRIEVAL cases - generate conversational response without graph query.
    Used when:
    - User gives negative response ("no, I don't take those")
    - User acknowledges ("thanks", "ok")
    - Same retrieval was already done
    - No new information to look up
    """
    print("   Generating NO_RETRIEVAL response...")
    
    # Get context from analysis
    medications = getattr(analysis, 'accumulated_medications', []) or []
    symptoms = getattr(analysis, 'accumulated_symptoms', []) or []
    reasoning = getattr(analysis, 'step_by_step_reasoning', 'No reasoning available')
    
    # Try to detect response type from reasoning
    response_type = "unknown"
    reasoning_lower = reasoning.lower()
    if any(word in reasoning_lower for word in ['negative', 'denied', 'no ', "don't", "doesn't"]):
        response_type = "NEGATIVE"
    elif any(word in reasoning_lower for word in ['acknowledge', 'thanks', 'thank', 'ok', 'okay']):
        response_type = "ACKNOWLEDGMENT"
    
    print(f"   Detected response type: {response_type}")
    print(f"   Accumulated meds: {medications}")
    print(f"   Accumulated symptoms: {symptoms}")
    
    llm = get_llm()
    
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", NO_RETRIEVAL_PROMPT)
        ])
        
        formatted_prompt = prompt.format_messages(
            user_message=user_message,
            medications=", ".join(medications) if medications else "None confirmed yet",
            symptoms=", ".join(symptoms) if symptoms else "None reported yet",
            response_type=response_type,
            reasoning=reasoning[:500]  # Truncate to avoid token limits
        )
        
        response = llm.invoke(formatted_prompt)
        final_response = response.content
        
        print(f"✅ NO_RETRIEVAL response generated ({len(final_response)} chars)")
        return build_response_with_history(state, final_response)
        
    except Exception as e:
        print(f"❌ Error generating NO_RETRIEVAL response: {e}")
        
        # Smart fallback based on context
        if symptoms and not medications:
            fallback = f"I understand you're experiencing {', '.join(symptoms)}. To help identify if this might be related to nutrient deficiencies, could you tell me what medications you're currently taking?"
        elif medications and not symptoms:
            fallback = f"Thanks for letting me know about your medications. Are you experiencing any symptoms you'd like me to check for possible nutrient connections?"
        else:
            fallback = "I can help you understand how medications affect nutrient levels. What medications are you currently taking, or what symptoms are you experiencing?"
        
        return build_response_with_history(state, fallback)


def handle_graph_based_response(state: MedicalAgentState, analysis, graph_results: List[Dict], user_message: str, retrieval_type_str: str) -> Dict[str, Any]:
    """
    Handle normal flow - synthesize response from graph results.
    """
    print("   Generating response from graph results...")
    
    # Format graph results
    if graph_results and len(graph_results) > 0:
        results_text = "Results found:\n"
        for i, result in enumerate(graph_results, 1):
            results_text += f"\n--- Result {i} ---\n"
            for key, value in result.items():
                results_text += f"  {key}: {value}\n"
        print(f"📝 Results available: Yes ({len(graph_results)} records)")
    else:
        results_text = "NO RESULTS FOUND IN DATABASE - Do not invent any information. Say you don't have data about this."
        print("📝 Results available: No")
    
    # Get analysis attributes safely
    chain_of_thought = getattr(analysis, 'step_by_step_reasoning', 
                               getattr(analysis, 'chain_of_thought', 'No analysis available'))
    medications = getattr(analysis, 'accumulated_medications', []) or []
    symptoms = getattr(analysis, 'accumulated_symptoms', []) or []
    nutrients = getattr(analysis, 'accumulated_nutrients', []) or []
    
    # Format lists
    medications_str = ", ".join(medications) if medications else "None mentioned"
    symptoms_str = ", ".join(symptoms) if symptoms else "None mentioned"
    nutrients_str = ", ".join(nutrients) if nutrients else "None mentioned"
    
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
        
        print(f"✅ Response generated ({len(final_response)} chars)")
        return build_response_with_history(state, final_response)
        
    except Exception as e:
        print(f"❌ Error in response synthesis: {e}")
        import traceback
        traceback.print_exc()
        
        fallback = (
            "I apologize, but I encountered an error processing your request. "
            "Could you tell me what medications you're taking? "
            "I can help identify if they might be affecting your nutrient levels."
        )
        return build_response_with_history(state, fallback)


print("✅ Response Synthesizer node defined with CLARIFICATION HANDLING")