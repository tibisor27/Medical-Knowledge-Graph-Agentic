import logging
from src.multi_agent.state import MultiAgentState

logger = logging.getLogger(__name__)

def run_setup_turn(state: MultiAgentState) -> dict:
   
    return {
        "execution_path": ["CLEAR"],    
        "previous_decisions": ["CLEAR"],  
        "medical_worker_results": ["CLEAR"],
        "product_worker_results": ["CLEAR"],
        "nutrient_worker_results": ["CLEAR"],
        "step_count": 0,
        "current_decision": None,
        "next_action": None,
        "final_response": None
    }