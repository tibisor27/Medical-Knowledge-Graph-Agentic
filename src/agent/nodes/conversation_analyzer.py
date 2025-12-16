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
    add_to_execution_path,
    print_state_debug
)
from src.config import (
    AZURE_OPENAI_ENDPOINT, 
    AZURE_OPENAI_API_KEY, 
    OPENAI_API_VERSION,
    validate_config
)
from src.agent.nodes.entity_extractor import entity_extractor_node
from src.agent.nodes.cypher_generator import cypher_generator_node
from src.prompts import SYSTEM_PROMPT

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
        azure_deployment='gpt-4.1-mini'
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
        user_message="What nutrients would help me with my anemia?",
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
    print(f"\n----> FINAL STATE: {state}\n")
    print(f"\n----> EXECUTION PATH: {state['execution_path']}\n")

    state = cypher_generator_node(state)

if __name__ == "__main__":
    test_conversation_analyzer()