from typing import Dict, Any
from src.agent.state import MedicalAgentState, add_to_execution_path
from src.utils.get_llm import get_llm_4_1_mini
from langchain_core.prompts import ChatPromptTemplate

# ═══════════════════════════════════════════════════════════════════════════════
# OFF-TOPIC RESPONSE NODE
# ═══════════════════════════════════════════════════════════════════════════════


general_chat_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful medical nutrition assistant specialized in drug-nutrient depletions.
    
    Your goal is to provide a natural, conversational response based on the users input and the recent context of what the agent has done.
    
    ### INPUTS:
    1. **Recent Context (Agent Reasoning):** {reasoning_context}
       (This tells you what happened just before: did we just list side effects? did we look for a vitamin?)
    2. **User's Last Message:** {last_user_input}
    
    ### INSTRUCTIONS:
    Analyze the User's Last Message in relation to the Context:
    
    - **CASE A: GRATITUDE / CONFIRMATION** (e.g., "Thanks", "Ok", "Great")
      - Respond warmly.
      - USE THE CONTEXT! If the context says you just found side effects for Metformin, say "You're welcome! Let me know if you need more details on those side effects."
      
    - **CASE B: GREETINGS** (e.g., "Hi", "Hello")
      - Welcome them and briefly mention your capability (drug-nutrient depletion checks).
      
    - **CASE C: OFF-TOPIC / UNKNOWN** (e.g., "Who won the match?", "Fix my car")
      - Politely decline. 
      - Pivot back to medical/nutrition topics.
      - Do NOT answer the off-topic question.
      
    - **CASE D: CONVERSATIONAL LINKING** (e.g., "That sounds bad", "Wow")
      - Acknowledge the emotion and offer a constructive next step based on the context.

    Keep the response concise (1-2 sentences) and helpful.
    """),
    
    # Nu mai punem MessagesPlaceholder aici, ci injectăm variabilele direct
])

def off_topic_response_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Generate a conversational response using only the reasoning summary and the last message.
    """
    print(f"\n********* NODE: OFF-TOPIC RESPONSE *********\n")
    
    # 1. Extragem ultimul mesaj al userului
    user_message = state.get("user_message", "")
    
    analysis = state.get("conversation_analysis", None)

    if analysis is not None:
        reasoning_context = analysis.step_by_step_reasoning
    else:
        reasoning_context = "No specific medical actions taken yet. Conversation just started."

    llm = get_llm_4_1_mini()
    chain = general_chat_prompt | llm
    
    response = chain.invoke({
        "reasoning_context": reasoning_context,
        "last_user_input": user_message
    })
    
    return {
        **state,
        "final_response": response.content,
        "execution_path": add_to_execution_path(state, "off_topic_response")
    }