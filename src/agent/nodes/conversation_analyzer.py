"""
Conversation Analyzer Node.

This node analyzes the full conversation context to:
1. Understand what the user wants to know (intent detection)
2. Accumulate information across multiple turns
3. Decide if we have enough information to query the graph
4. Generate clarification questions if needed

Uses Pydantic structured output for reliable parsing.
"""

from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from src.agent.state import (
    MedicalAgentState, 
    ConversationAnalysis, 
    VALID_INTENTS,
    add_to_execution_path
)
from src.config import (
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_API_KEY, 
    OPENAI_API_VERSION,
    validate_config
)
from src.agent.nodes.entity_extractor import entity_extractor_node


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT (describes the task and rules)
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are an intelligent conversation analyzer for a Medical Knowledge Graph system.

Your job is to analyze the FULL conversation (not just the last message) and determine:
1. **Analyze the CURRENT USER MESSAGE first.** This determines the Intent.
2. **Use HISTORY only for Context Resolution** (e.g., resolving "it", "that", "the drug", "the symptoms").
3. **Detect Context Switching:** If the user asks a completely new question unrelated to the previous topic, DROP the previous context and focus ONLY on the new message.

=== KNOWLEDGE GRAPH CAPABILITIES ===
Our graph contains:
- Medications (Medicament): name, brand_names, synonyms, pharmacologic_class
- Nutrients (Nutrient): vitamins, minerals, supplements with their functions and food sources
- DepletionEvents: Links showing which medications deplete which nutrients
- Symptoms: Symptoms of nutrient deficiencies
- Studies: Scientific evidence supporting the depletion relationships

=== VALID INTENT TYPES ===
- DRUG_DEPLETES_NUTRIENT: User asks what nutrients a medication depletes (e.g., "What does Acetaminophen deplete?")
- NUTRIENT_DEPLETED_BY: User asks what medications deplete a nutrient (e.g., "What depletes Vitamin B12?")
- SYMPTOM_TO_DEFICIENCY: User describes symptoms and wants to know possible deficiencies
- DRUG_INFO: User wants general info about a medication (e.g., "What is Tylenol?")
- NUTRIENT_INFO: User wants general info about a nutrient (e.g., "What is Glutathione?")
- DEFICIENCY_SYMPTOMS: User wants symptoms of a specific deficiency (e.g., "Symptoms of Zinc deficiency?")
- FOOD_SOURCES: User asks where to find a nutrient in food
- EVIDENCE_LOOKUP: User asks about studies/evidence
- GENERAL_MEDICAL: General medical question
- NEEDS_CLARIFICATION: Can't determine intent, need more info
- OFF_TOPIC: Not related to medications, nutrients, or health

=== INTENT DETECTION RULES ===

DRUG_DEPLETES_NUTRIENT:
- User asks what nutrients a medication depletes
- Keywords: "deplete", "affect", "reduce", "lower", "cause deficiency"
- Example: "What nutrients does Acetaminophen deplete?"

NUTRIENT_DEPLETED_BY:
- User asks what medications deplete a specific nutrient
- Example: "What medications deplete Vitamin B12?"

SYMPTOM_TO_DEFICIENCY:
- User describes symptoms and wants to know possible causes
- IMPORTANT: If symptoms are mentioned but NO medication context exists, set needs_clarification=true
- Example: "I feel tired and have headaches" → Ask about medications!

DRUG_INFO:
- User wants general information about a medication
- Example: "Tell me about Acetaminophen", "What is Tylenol?"

NUTRIENT_INFO:
- User wants general information about a nutrient
- Example: "What is Glutathione?", "Tell me about Vitamin B12"

DEFICIENCY_SYMPTOMS:
- User wants to know symptoms of a specific nutrient deficiency
- Example: "What are the symptoms of Zinc deficiency?"

=== CLARIFICATION RULES ===

SET needs_clarification=true WHEN:
1. User mentions symptoms but hasn't mentioned any medication they take
2. User uses vague terms ("the pill", "my medication") without specifying which one
3. User's question is ambiguous between multiple intents
4. Critical information is missing to form a useful database query

SET needs_clarification=false WHEN:
1. User clearly asks about a specific medication or nutrient BY NAME
2. User asks a general information question
3. You can determine intent from conversation history
4. Intent is OFF_TOPIC (just respond that it's off-topic)

=== ACCUMULATION RULES ===
- accumulated_medications: Include ALL medication names from the ENTIRE conversation, not just the last message
- accumulated_symptoms: Include ALL symptoms mentioned throughout the conversation
- accumulated_nutrients: Include ALL nutrients mentioned throughout the conversation
- Look for brand names too (Tylenol = Acetaminophen)
1. **Explicit Extraction:** Extract entities mentioned directly in the current message.

2. **Reference Resolution (CRITICAL):** - IF the user uses pronouns or references like "it", "that nutrient", "the supplement", "the drug":
   - YOU MUST LOOK at the Conversation History (specifically the Assistant's last message).
   - IDENTIFY the specific entity being referred to.
   - ADD that specific entity name to the `accumulated_nutrients` or `accumulated_medications` list.

   *Example:*
   - History: Assistant says "It depletes CoQ10."
   - User says: "What are the symptoms of *that*?"
   - Action: Add "Coenzyme Q10" to `accumulated_nutrients`.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# USER PROMPT TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

USER_PROMPT_TEMPLATE = """=== CONVERSATION HISTORY ===
{conversation_history}

=== CURRENT USER MESSAGE ===
{current_message}

Analyze this conversation and provide your structured analysis."""


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def format_conversation_for_analysis(messages: list) -> str:
    """Format conversation history for the analyzer prompt."""
    if not messages:
        return "No previous conversation."
    
    formatted = []
    # Exclude the last message (it's the current one we're analyzing)
    history_messages = messages
    
    for msg in history_messages[-10:]:  # Last 10 messages from history
        if isinstance(msg, HumanMessage):
            formatted.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            # Truncate long assistant responses
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            formatted.append(f"Assistant: {content}")
        elif isinstance(msg, dict):
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")[:500] 
            formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted) if formatted else "No previous conversation."


def get_llm():
    """Get the Azure OpenAI LLM instance."""
    validate_config()
    return AzureChatOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=OPENAI_API_VERSION,
        azure_deployment='gpt-4.1-mini',
        temperature=0.0,  # Deterministic for classification
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def conversation_analyzer_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    This node:
    1. Looks at the full conversation history
    2. Detects the user's intent
    3. Accumulates entities mentioned across turns
    4. Decides if clarification is needed
    """
    
    # Format conversation history
    conversation_history = format_conversation_for_analysis(
        state.get("conversation_history", [])
    )
    current_message = state.get("user_message", "")
    
    # Debug logging
    print(f"[ConversationAnalyzer] History: {conversation_history[:200]}...")
    print(f"[ConversationAnalyzer] Current message: {current_message}")
    
    try:
        # Get LLM with structured output
        llm = get_llm()
        
        # Create the structured LLM that outputs ConversationAnalysis directly
        
        # Build the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", USER_PROMPT_TEMPLATE)
        ])
        
        # Create the chain
        chain = prompt | llm.with_structured_output(ConversationAnalysis)
        
        response = chain.invoke({"conversation_history": conversation_history, "current_message": current_message})
        
        print(f"----> Response: {response}\n")
        print(f"----> Response type: {type(response)}")
        
        # Debug logging
        print(f"[ConversationAnalyzer] Intent: {response.detected_intent}")
        print(f"[ConversationAnalyzer] Has sufficient info: {response.has_sufficient_info}")
        print(f"[ConversationAnalyzer] Needs clarification: {response.needs_clarification}")
        print(f"[ConversationAnalyzer] Accumulated meds: {response.accumulated_medications}")
        
        return {
            **state,
            "conversation_analysis": response,
            "execution_path": add_to_execution_path(state, "conversation_analyzer")
        }
        
    except Exception as e:
        # Handle any errors - return a safe default
        print(f"[ConversationAnalyzer] Error: {str(e)}")
        
        # Create a fallback analysis
        fallback_analysis = ConversationAnalysis(
            has_sufficient_info=False,
            detected_intent="NEEDS_CLARIFICATION",
            needs_clarification=True,
            clarification_question="I couldn't understand your question. Could you please rephrase it?",
            accumulated_medications=[],
            accumulated_symptoms=[],
            accumulated_nutrients=[]
        )
        
        return {
            **state,
            "conversation_analysis": fallback_analysis,
            "execution_path": add_to_execution_path(state, "conversation_analyzer"),
            "errors": state.get("errors", []) + [f"Error in conversation_analyzer: {str(e)}"]
        }


def test_conversation_analyzer():
    """Test the conversation analyzer node."""
    state = MedicalAgentState(
        user_message="What If I take that Paracetamol? it will affect my anemia because of any nutrient depletion?",
        conversation_history=[HumanMessage(content="What nutrients does Acetaminophen deplete?"),
        AIMessage(content="Acetaminophen deplete Glutathione.")],
        conversation_analysis=None,
        extracted_entities=[],
        resolved_entities=[],
        unresolved_entities=[],
        generated_cypher="",
    )
    state = conversation_analyzer_node(state)
    print(f"----> State: {state}")
    print(f"----> Conversation analysis: {state['conversation_analysis']}")

    state = entity_extractor_node(state)
    print(f"----> State: {state}")
    print(f"----> Extracted entities: {state['extracted_entities']}")
    print(f"----> Resolved entities: {state['resolved_entities']}")
    print(f"----> Unresolved entities: {state['unresolved_entities']}")

if __name__ == "__main__":
    test_conversation_analyzer()