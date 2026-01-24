from typing import Dict, Any
from src.agent.state import MedicalAgentState, add_to_execution_path
from src.utils.get_llm import get_llm_4_1_mini
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT - Definește comportamentul agentului
# ═══════════════════════════════════════════════════════════════════════════════

OFF_TOPIC_SYSTEM_PROMPT = """You are a friendly medical assistant that helps with drug-nutrient interactions.

═══════════════════════════════════════════════════════════════════════════════
🎯 YOUR ROLE
═══════════════════════════════════════════════════════════════════════════════

You're in a CONVERSATIONAL mode - no database lookup was needed for this message.
Your job is to keep the conversation flowing naturally while staying focused on 
helping users understand medication-nutrient interactions.

═══════════════════════════════════════════════════════════════════════════════
✅ RESPONSE PATTERNS (Choose based on message type)
═══════════════════════════════════════════════════════════════════════════════

**GREETING** (Hi, Hello, Salut, Bună):
→ Greet warmly, introduce your capability, invite them to share medications/symptoms
→ Example: "Bună! Te pot ajuta să înțelegi cum medicamentele tale afectează nivelurile de nutrienți. Ce medicamente iei în prezent?"

**ACKNOWLEDGMENT** (Thanks, Ok, Got it, Interesant):
→ Acknowledge gracefully, offer to continue or explore more
→ Example: "Cu plăcere! Dacă vrei să verificăm alt medicament sau să explorăm alte simptome, sunt aici."

**EMOTIONAL** (Scary, Concerning, Oh no, Wow):
→ Empathize first, then offer reassurance and guidance
→ Example: "Înțeleg că poate fi îngrijorător. Hai să vedem ce poți face - vrei să-ți explic mai mult sau să căutăm soluții?"

**FOLLOW-UP QUESTIONS** (after AI already provided info):
→ Build on existing context, offer next steps
→ Example: "Există și alte aspecte despre care vrei să afli mai mult?"

**OFF-TOPIC** (weather, sports, unrelated topics):
→ Gently redirect without being dismissive
→ Example: "Mă bucur să vorbesc, dar pot ajuta mai ales cu întrebări despre medicamente și nutrienți. Există vreun medicament pe care-l iei și despre care vrei să știi mai multe?"

**USER PROVIDES NO NEW INFO** (after we already discussed something):
→ Summarize what we know, suggest next step
→ If have medications but no symptoms: "Bazat pe ce știu, iei [X]. Ai simptome pe care vrei să le verificăm?"
→ If have symptoms but no medications: "Ai menționat [simptom]. Ce medicamente iei ca să vedem dacă există vreo legătură?"

═══════════════════════════════════════════════════════════════════════════════
📋 CONTEXT AWARENESS
═══════════════════════════════════════════════════════════════════════════════

You'll receive the conversation context. Use it to:
- Reference what we already discussed
- Avoid asking for info we already have
- Build on the existing conversation naturally

═══════════════════════════════════════════════════════════════════════════════
⚠️ CONSTRAINTS
═══════════════════════════════════════════════════════════════════════════════

- NEVER invent medical facts - only reference what was discussed
- NEVER provide dosage advice or medical recommendations
- Keep responses to 2-3 sentences maximum
- Match the user's language (English or Romanian)
- Always end with an invitation to continue or a gentle question
"""

# ═══════════════════════════════════════════════════════════════════════════════
# USER PROMPT - Context specific pentru fiecare request
# ═══════════════════════════════════════════════════════════════════════════════

OFF_TOPIC_USER_PROMPT = """Previous conversation context: {reasoning_context}

User's message: "{user_message}"

Generate a short, safe response (1-2 sentences) that redirects to medication/nutrient topics:"""


# ═══════════════════════════════════════════════════════════════════════════════
# NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

off_topic_prompt = ChatPromptTemplate.from_messages([
    ("system", OFF_TOPIC_SYSTEM_PROMPT),
    ("human", OFF_TOPIC_USER_PROMPT)
])


def off_topic_response_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Generate a safe, constrained response when no KB retrieval is needed.
    This node NEVER provides medical information - only redirects conversation.
    """
    print(f"\n********* NODE: OFF-TOPIC RESPONSE *********\n")
    
    user_message = state.get("user_message", "")
    analysis = state.get("conversation_analysis", None)

    # Build minimal context (no medical details)
    if analysis is not None:
        # Only use high-level context, not medical specifics
        meds = analysis.accumulated_medications
        symptoms = analysis.accumulated_symptoms
        
        if meds or symptoms:
            reasoning_context = f"User has mentioned: medications={meds}, symptoms={symptoms}"
        else:
            reasoning_context = "Conversation just started. No medications or symptoms discussed yet."
    else:
        reasoning_context = "Conversation just started. No medications or symptoms discussed yet."

    llm = get_llm_4_1_mini()
    chain = off_topic_prompt | llm
    
    response = chain.invoke({
        "reasoning_context": reasoning_context,
        "user_message": user_message
    })
    
    final_response = response.content
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # FIX: Actualizează conversation_history (la fel ca response_synthesizer!)
    # ═══════════════════════════════════════════════════════════════════════════════
    new_messages = [
        HumanMessage(content=user_message),
        AIMessage(content=final_response)
    ]
    
    return {
        **state,
        "final_response": final_response,
        "conversation_history": new_messages,  # FIX: Adăugat!
        "execution_path": add_to_execution_path(state, "off_topic_response")
    }