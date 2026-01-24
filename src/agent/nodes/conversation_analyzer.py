from typing import Dict, Any
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.agent.state import MedicalAgentState, ConversationAnalysis, RetrievalType, add_to_execution_path
from src.config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, OPENAI_API_VERSION, validate_config
from src.agent.nodes.entity_extractor import entity_extractor_node
from src.agent.nodes.graph_executor import graph_executor_node
from src.prompts import CONV_ANALYZER_SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from src.agent.nodes.response_synthesizer import response_synthesizer_node
from src.utils.get_llm import get_llm_4_1_mini as get_llm

import logging
logger = logging.getLogger(__name__)

def conversation_analyzer_node(state: MedicalAgentState) -> Dict[str, Any]:

    conversation_history = state.get("conversation_history", [])
    current_message = state.get("user_message", "")
    logger.info(f"Conversation history: {conversation_history}")
    
    # Use persisted entities from state, not conversation_analysis!
    # These are passed by MedicalChatSession from previous turn
    persisted_medications = state.get("persisted_medications", [])
    persisted_symptoms = state.get("persisted_symptoms", [])
    persisted_nutrients = state.get("persisted_nutrients", [])
    
    logger.info(f"Persisted context from previous turns:")
    logger.info(f"      - Medications: {persisted_medications}")
    logger.info(f"      - Symptoms: {persisted_symptoms}")
    logger.info(f"      - Nutrients: {persisted_nutrients}")

    try:
        llm = get_llm()
        # Build the prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", CONV_ANALYZER_SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="conversation_history"),
            ("human", USER_PROMPT_TEMPLATE)
        ])
        
        chain = prompt | llm.with_structured_output(ConversationAnalysis)
        
        # Transmite entitățile persistente ca punct de plecare pentru LLM
        response = chain.invoke({
            "conversation_history": conversation_history, 
            "query": current_message, 
            "current_meds": persisted_medications, 
            "current_symps": persisted_symptoms, 
            "current_nuts": persisted_nutrients
        })
        
        logger.info(f"Analysis complete:")
        logger.info(f"      - Retrieval type: {response.retrieval_type}")
        logger.info(f"      - Updated medications: {response.accumulated_medications}")
        logger.info(f"      - Updated symptoms: {response.accumulated_symptoms}")
        logger.info(f"      - Updated nutrients: {response.accumulated_nutrients}")
        logger.info(f"      - Chain of thought: {response.step_by_step_reasoning}")
        logger.info(f"      - Query medications: {response.query_medications}")
        logger.info(f"      - Query symptoms: {response.query_symptoms}")
        logger.info(f"      - Query nutrients: {response.query_nutrients}")
        
        return {
            **state,
            "user_message": current_message,
            "conversation_analysis": response,
            "execution_path": add_to_execution_path(state, "conversation_analyzer")
        }
        
    except Exception as e:
        # Handle any errors - return a safe default
        logger.error(f"Error: {str(e)}")
        
        # Create a fallback analysis - Keep existing entities!
        fallback_analysis = ConversationAnalysis(
            step_by_step_reasoning=f"Error occurred: {str(e)}. Keeping existing entities.",
            has_sufficient_info=False,
            retrieval_type=RetrievalType.NO_RETRIEVAL, 
            needs_clarification=True,
            clarification_question="I couldn't understand your question. Could you please rephrase it?",
            accumulated_medications=persisted_medications,
            accumulated_symptoms=persisted_symptoms,
            accumulated_nutrients=persisted_nutrients,
            query_medications=persisted_medications,
            query_symptoms=persisted_symptoms,
            query_nutrients=persisted_nutrients
        )
        return {
            **state,
            "user_message": current_message,
            "conversation_analysis": fallback_analysis,
            "execution_path": add_to_execution_path(state, "conversation_analyzer"),
            "errors": state.get("errors", []) + [f"Error in conversation_analyzer: {str(e)}"]
        }
