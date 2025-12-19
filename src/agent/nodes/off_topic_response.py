from typing import Dict, Any
from src.agent.state import MedicalAgentState

# ═══════════════════════════════════════════════════════════════════════════════
# OFF-TOPIC RESPONSE NODE
# ═══════════════════════════════════════════════════════════════════════════════

def off_topic_response_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Generate a response for off-topic queries.
    """
    response = """I'm sorry, but I can only answer questions related to:

🏥 **What I can help with:**
- Information about medications and the nutrients they deplete
- Information about vitamins, minerals, and supplements
- Symptoms of nutrient deficiencies
- Food sources for nutrients

Do you have a medical question I can help with?"""
    
    return {
        **state,
        "final_response": response,
        "execution_path": state.get("execution_path", []) + ["off_topic_response"]
    }
