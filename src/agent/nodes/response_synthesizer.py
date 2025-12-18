"""
Response Synthesizer Node - Optimized for Concise, Contextual Responses.

This node generates natural language responses that:
1. Are CONCISE (50-150 words) for optimal conversation history
2. Explicitly mention key entities for future reference
3. Offer relevant follow-up suggestions
4. Adapt to detected language
"""

import json
from typing import Dict, Any, List, Tuple
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

from src.agent.state import MedicalAgentState, add_to_execution_path
from src.config import (
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_API_KEY, 
    OPENAI_API_VERSION,
    validate_config
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MAX_ENTITIES_DETAILED = 5  # Show detailed info for top N entities
MAX_RESPONSE_WORDS = 150   # Target max words for response


def build_response_with_history(state: MedicalAgentState, final_response: str, extra_updates: Dict = None) -> Dict[str, Any]:
    """
    Build the return dict and ADD messages to conversation_history.
    This ensures follow-up questions appear in history for next turn.
    """
    user_message = state.get("user_message", "")
    
    # Build the messages to add to history
    new_messages = [
        HumanMessage(content=user_message),
        AIMessage(content=final_response)
    ]
    
    result = {
        **state,
        "final_response": final_response,
        "conversation_history": new_messages,  # LangGraph's add_messages will append these
        "execution_path": add_to_execution_path(state, "response_synthesizer")
    }
    
    if extra_updates:
        result.update(extra_updates)
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE SYNTHESIS PROMPTS (Softened for Azure Content Filter)
# ═══════════════════════════════════════════════════════════════════════════════

RESPONSE_SYSTEM_PROMPT = """You are a DATA REPORTER. Your ONLY job is to convert structured database results into natural language.

CRITICAL RULES:
1. You are NOT a medical expert. You are a data translator.
2. ONLY use information from the DATABASE_RESULTS section.
3. If a field is NULL, empty, or missing - DO NOT mention it at all.
4. DO NOT add explanations, definitions, or medical advice from your training.
5. DO NOT add follow-up questions or suggestions.
6. Respond in the SAME LANGUAGE as the user's question.

YOUR TASK:
- Take the raw data from DATABASE_RESULTS
- Convert it into a clear, readable sentence or list
- Nothing more, nothing less

RESPONSE FORMAT BY INTENT:

DRUG_DEPLETES_NUTRIENT:
"[Medication] can deplete:
• [Nutrient 1]
• [Nutrient 2]"

NUTRIENT_DEPLETED_BY:
"[Nutrient] can be depleted by:
• [Medication 1]
• [Medication 2]"

DEFICIENCY_SYMPTOMS:
"[Nutrient] deficiency symptoms:
• [Symptom 1]
• [Symptom 2]"

FOOD_SOURCES:
"[Nutrient] food sources:
• [Food 1]
• [Food 2]"

NUTRIENT_INFO:
"[Nutrient]: [overview from data]
Function: [function from data]
Food sources: [sources from data]"

DRUG_INFO:
"[Medication]: [info from data]
Drug class: [class from data]
Depletes: [nutrients from data]"

SYMPTOM_TO_DEFICIENCY:
"[Symptom] may indicate deficiency of:
• [Nutrient 1] (caused by: [medications])
• [Nutrient 2] (caused by: [medications])"

IF NO DATA:
"No information found for [topic] in the database."

REMEMBER: You are a reporter, not an expert. Report ONLY what is in the data."""


RESPONSE_USER_PROMPT = """Convert this database query result into a natural language response.

USER QUESTION: {query}
INTENT: {intent}
SUBJECT: {main_entity}

DATABASE_RESULTS:
{results}

Instructions:
1. Use ONLY the data above
2. Format according to the INTENT template
3. If a field is missing/null, skip it
4. Match the user's language
5. No explanations, no follow-ups, just the data as text"""


NO_RESULTS_PROMPT = """I couldn't find specific information for your query in my database.

User Question: {query}

Please explain that I can help with:
- Medications and nutrient depletions
- Symptoms of vitamin deficiencies
- General info on vitamins and minerals

Suggest that the user might rephrase their question. Respond in the same language as the user."""


CLARIFICATION_PROMPT = """Generate a brief clarification question.

USER SAID: {query}
REASON FOR CLARIFICATION: {reason}

Requirements:
1. Acknowledge what user said
2. Ask for the specific missing info
3. Give 1-2 examples if helpful
4. Same language as user
5. Maximum 2 sentences"""


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


def extract_discovered_entities(results: List[Dict], intent: str) -> List[str]:
    """
    Extract the key entities discovered from graph results.
    These will be explicitly mentioned in the response for future reference.
    """
    entities = set()
    
    # Field mappings based on common query result structures
    entity_fields = [
        'nutrient_name', 'nutrient', 'name',
        'medication_name', 'medication',
        'symptom', 'symptom_searched',
        'possible_deficiency',
        'food_sources_list'
    ]
    
    for result in results:
        for field in entity_fields:
            value = result.get(field)
            if value:
                if isinstance(value, list):
                    entities.update(value[:MAX_ENTITIES_DETAILED])
                elif isinstance(value, str) and value.strip():
                    entities.add(value)
    
    return list(entities)[:MAX_ENTITIES_DETAILED * 2]  # Cap at reasonable number


def extract_main_entity(state: MedicalAgentState) -> str:
    """Extract the main entity the user asked about."""
    resolved = state.get("resolved_entities", [])
    if resolved:
        # Get first resolved entity
        first = resolved[0]
        if hasattr(first, 'resolved_name'):
            return first.resolved_name
        elif isinstance(first, dict):
            return first.get('resolved_name', 'Unknown')
    
    # Fallback to accumulated from analysis
    analysis = state.get("conversation_analysis")
    if analysis:
        if analysis.accumulated_medications:
            return analysis.accumulated_medications[0]
        if analysis.accumulated_nutrients:
            return analysis.accumulated_nutrients[0]
        if analysis.accumulated_symptoms:
            return analysis.accumulated_symptoms[0]
    
    return "the requested topic"


def format_results_for_prompt(results: List[Dict], max_results: int = 5) -> str:
    """Format graph results for the prompt, limiting size."""
    if not results:
        return "No results found."
    
    # Limit results to avoid huge prompts
    limited_results = results[:max_results]
    
    # Clean up results - remove very long text fields
    cleaned = []
    for r in limited_results:
        cleaned_result = {}
        for key, value in r.items():
            if isinstance(value, str) and len(value) > 300:
                cleaned_result[key] = value[:300] + "..."
            else:
                cleaned_result[key] = value
        cleaned.append(cleaned_result)
    
    return json.dumps(cleaned, indent=2, ensure_ascii=False)


def summarize_large_results(results: List[Dict], intent: str) -> Tuple[str, List[str]]:
    """
    For large result sets, create a summary instead of showing all.
    Returns (summary_text, list_of_key_entities)
    """
    entities = extract_discovered_entities(results, intent)
    count = len(results)
    
    summary = f"Found {count} results. Key entities: {', '.join(entities[:5])}"
    if count > 5:
        summary += f" and {count - 5} more."
    
    return summary, entities


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def response_synthesizer_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Generate a concise, contextual response from graph results.
    
    Key behaviors:
    1. Generates responses under 150 words
    2. Explicitly lists discovered entities (for future reference)
    3. Adapts format to detected intent
    4. Handles no-results and clarification cases
    """
    print(f"\n********* NODE 5: RESPONSE SYNTHESIZER *********\n")
    
    # Get analysis from state
    analysis = state.get("conversation_analysis")
    user_message = state.get("user_message", "")
    graph_results = state.get("graph_results", [])
    has_results = state.get("has_results", False)
    
    # Extract context
    intent = analysis.detected_intent if analysis else "GENERAL_MEDICAL"
    main_entity = extract_main_entity(state)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CASE 1: Needs Clarification
    # ═══════════════════════════════════════════════════════════════════════════
    
    if analysis and analysis.needs_clarification:
        clarification = analysis.clarification_question
        if clarification:
            print(f"----> Returning clarification: {clarification}")
            return build_response_with_history(state, clarification)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CASE 2: No Results
    # ═══════════════════════════════════════════════════════════════════════════
    
    if not has_results or not graph_results:
        print(f"----> No results, generating helpful response")
        try:
            llm = get_llm()
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a helpful medical assistant. Be brief and helpful."),
                ("human", NO_RESULTS_PROMPT)
            ])
            
            chain = prompt | llm
            response = chain.invoke({
                "query": user_message,
                "intent": intent,
                "main_entity": main_entity
            })
            
            return build_response_with_history(state, response.content)
        except Exception as e:
            fallback = f"Nu am găsit informații despre {main_entity}. Poți reformula întrebarea?"
            return build_response_with_history(state, fallback, {"errors": state.get("errors", []) + [str(e)]})
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CASE 3: Has Results - Generate Response
    # ═══════════════════════════════════════════════════════════════════════════
    
    try:
        llm = get_llm()
        
        # Extract discovered entities for explicit mention
        discovered_entities = extract_discovered_entities(graph_results, intent)
        
        # Format results (limit size for prompt)
        formatted_results = format_results_for_prompt(graph_results, max_results=5)
        
        print(f"----> Intent: {intent}")
        print(f"----> Main entity: {main_entity}")
        print(f"----> Discovered entities: {discovered_entities}")
        print(f"----> Results count: {len(graph_results)}")
        
        # Build prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", RESPONSE_SYSTEM_PROMPT),
            ("human", RESPONSE_USER_PROMPT)
        ])
        
        chain = prompt | llm
        
        response = chain.invoke({
            "query": user_message,
            "intent": intent,
            "main_entity": main_entity,
            "results": formatted_results
        })
        
        final_response = response.content
        print(f"----> Generated response ({len(final_response.split())} words)")
        print(f"----> Final response: {final_response}")
        
        return build_response_with_history(state, final_response)
        
    except Exception as e:
        print(f"----> ERROR: {str(e)}")
        
        # Fallback: Generate simple response from data
        fallback_response = generate_fallback_response(
            intent, main_entity, graph_results
        )
        
        return build_response_with_history(
            state, 
            fallback_response, 
            {"errors": state.get("errors", []) + [f"Response synthesis error: {str(e)}"]}
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK RESPONSE GENERATOR (No LLM needed)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_fallback_response(intent: str, main_entity: str, results: List[Dict]) -> str:
    """
    Generate a simple response without LLM as fallback.
    Uses templates and extracts data directly from results.
    """
    if not results:
        return f"Nu am găsit informații despre {main_entity}."
    
    # Extract common fields
    entities = extract_discovered_entities(results, intent)
    entities_str = ", ".join(entities[:5]) if entities else "N/A"
    
    # Simple template responses
    templates = {
        "DRUG_DEPLETES_NUTRIENT": f"**{main_entity}** poate depleta: {entities_str}.\n\nVrei detalii despre vreunul?",
        
        "NUTRIENT_DEPLETED_BY": f"**{main_entity}** poate fi depletat de: {entities_str}.\n\nVrei să afli simptomele deficienței?",
        
        "NUTRIENT_INFO": f"**{main_entity}**: Am găsit informații despre acest nutrient.\n\nVrei detalii specifice?",
        
        "DEFICIENCY_SYMPTOMS": f"Deficiența de **{main_entity}** poate cauza diverse simptome.\n\nVrei să afli surse alimentare?",
        
        "SYMPTOM_TO_DEFICIENCY": f"Simptomul **{main_entity}** poate fi asociat cu deficiențe de: {entities_str}.\n\nVrei detalii?",
        
        "FOOD_SOURCES": f"**{main_entity}** se găsește în diverse alimente.\n\nVrei recomandări specifice?",
        
        "DRUG_INFO": f"**{main_entity}**: Am găsit informații despre acest medicament.\n\nVrei să afli ce nutrienți depletează?",
    }
    
    return templates.get(intent, f"Am găsit informații despre {main_entity}. Ce vrei să afli mai exact?")


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY: Response Quality Check
# ═══════════════════════════════════════════════════════════════════════════════

def check_response_quality(response: str) -> Dict[str, Any]:
    """
    Check if response meets quality standards.
    Returns quality metrics.
    """
    words = response.split()
    word_count = len(words)
    
    # Check for entity mentions (bold text)
    has_entities = "**" in response
    
    # Check for follow-up suggestion
    follow_up_markers = ["vrei", "dorești", "want", "would you like", "?"]
    has_follow_up = any(marker in response.lower() for marker in follow_up_markers)
    
    # Check for bullet points
    has_structure = "•" in response or "- " in response or "* " in response
    
    return {
        "word_count": word_count,
        "is_concise": word_count <= MAX_RESPONSE_WORDS,
        "has_explicit_entities": has_entities,
        "has_follow_up": has_follow_up,
        "has_structure": has_structure,
        "quality_score": sum([
            word_count <= MAX_RESPONSE_WORDS,
            has_entities,
            has_follow_up,
            has_structure
        ]) / 4
    }
