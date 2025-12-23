from typing import Dict, Any
from src.agent.state import MedicalAgentState

# ═══════════════════════════════════════════════════════════════════════════════
# ERROR RESPONSE NODE
# ═══════════════════════════════════════════════════════════════════════════════

def error_response_node(state: MedicalAgentState) -> Dict[str, Any]:
    """
    Generate a response when Cypher generation fails.
    """
    cypher_errors = state.get("cypher_errors", [])
    
    response = """I'm sorry, I couldn't process your question at this time.

You can try to:
- Rephrase your question more specifically
- Mention the exact medication or nutrient you're interested in

Example: "What nutrients does Acetaminophen deplete?" or "What is Vitamin B12?"
"""
    
    return {
        **state,
        "final_response": response,
        "cypher_errors": cypher_errors,
        "execution_path": state.get("execution_path", []) + ["error_response"]
    }
