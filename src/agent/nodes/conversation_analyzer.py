"""
This node analyzes the full conversation context to:
1. Understand what the user wants to know (intent detection)
2. Accumulate information across multiple turns
3. Decide if we have enough information to query the graph
4. Generate clarification questions if needed
"""

from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.agent.state import MedicalAgentState, ConversationAnalysis, VALID_INTENTS, add_to_execution_path, print_state_debug, print_analysis_debug
from src.config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, OPENAI_API_VERSION, validate_config
from src.agent.nodes.entity_extractor import entity_extractor_node
from src.agent.nodes.cypher_generator import cypher_generator_node
from src.agent.nodes.graph_executor import graph_executor_node
from src.prompts import CONV_ANALYZER_SYSTEM_PROMPT as SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.agent.nodes.response_synthesizer import response_synthesizer_node


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
    print(f"\n********* NODE 1: CONVERSATION ANALYZER *********\n")
    # Format conversation history
    conversation_history = state.get("conversation_history", [])
    current_message = state.get("user_message", "")
    current_analysis = state.get("conversation_analysis", None)
    print(f"Conversation history: {conversation_history}")

    if current_analysis is not None:
        accumulated_medications = current_analysis.accumulated_medications
        accumulated_symptoms = current_analysis.accumulated_symptoms
        accumulated_nutrients = current_analysis.accumulated_nutrients
    else:
        accumulated_medications = []
        accumulated_symptoms = []
        accumulated_nutrients = []

    try:
        llm = get_llm()
        # Build the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="conversation_history"),
            ("human", USER_PROMPT_TEMPLATE)
        ])
        
        chain = prompt | llm.with_structured_output(ConversationAnalysis)
        
        response = chain.invoke({"conversation_history": conversation_history, "query": current_message, "current_meds": accumulated_medications, "current_symps": accumulated_symptoms, "current_nuts": accumulated_nutrients})
        return {
            **state,
            "user_message": current_message,
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
            "user_message": current_message,
            "conversation_analysis": fallback_analysis,
            "execution_path": add_to_execution_path(state, "conversation_analyzer"),
            "errors": state.get("errors", []) + [f"Error in conversation_analyzer: {str(e)}"]
        }


def test_conversation_analyzer():
    """Test the conversation analyzer node."""
    state = MedicalAgentState(
        user_message="Are there any side effects of taking these drugs?",
        conversation_history=[HumanMessage(content="What nutrients does Acetaminophen deplete?"),
        AIMessage(content="Acetaminophen depletes Glutathione")]
    )
    state = conversation_analyzer_node(state)
    print_state_debug(state)

    # state = entity_extractor_node(state)
    # print_state_debug(state)

    # state = cypher_generator_node(state)
    # print_state_debug(state)

    # state = graph_executor_node(state)
    # print_state_debug(state)
    
    # state = response_synthesizer_node(state)
    # print_state_debug(state)

if __name__ == "__main__":
    test_conversation_analyzer()