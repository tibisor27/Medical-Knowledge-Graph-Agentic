import logging
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.multi_agent.state import MultiAgentState
from src.multi_agent.nodes.supervisor import run_supervisor
from src.multi_agent.nodes.medical_worker import run_medical_worker
from src.multi_agent.nodes.product_worker import run_product_worker
from src.multi_agent.nodes.nutrient_worker import run_nutrient_worker
from src.multi_agent.nodes.synthesis_agent import run_synthesis_agent
from src.multi_agent.nodes.setup_turn import run_setup_turn
from src.multi_agent.schemas.enums import RoutingNextAction
 
logger = logging.getLogger(__name__)
 
 
def build_multi_agent_graph():
 
    graph = StateGraph(MultiAgentState)
 
    graph.add_node("setup_turn", run_setup_turn)
    graph.add_node("supervisor", run_supervisor)
    graph.add_node("medical_worker", run_medical_worker)
    graph.add_node("product_worker", run_product_worker)
    graph.add_node("nutrient_worker", run_nutrient_worker)
    graph.add_node("synthesis", run_synthesis_agent)
 
    graph.set_entry_point("setup_turn")
    graph.add_edge("setup_turn", "supervisor")
 
    graph.add_conditional_edges(
        "supervisor",
        supervisor_routing,
        {
            "medical_worker": "medical_worker",
            "product_worker": "product_worker",
            "nutrient_worker": "nutrient_worker",
            "synthesis": "synthesis",
        },
    )
 
    graph.add_edge("medical_worker", "supervisor")
    graph.add_edge("product_worker", "supervisor")
    graph.add_edge("nutrient_worker", "supervisor")
    graph.add_edge("synthesis", END)
 
 
    memory = MemorySaver()
    compiled = graph.compile(checkpointer=memory)
    logger.info("Multi-agent graph compiled successfully")
    return compiled
 
 
def supervisor_routing(state: MultiAgentState) -> str:
    current_supervisor_decision = state.get("current_decision")
    if not current_supervisor_decision:
        logger.error("Supervisor routing failed: 'current_decision' is missing in state.")
        return "synthesis"
 
    next_action = getattr(current_supervisor_decision, "action", None)
    if not next_action:
        logger.error("Supervisor routing failed: Decision object does not have 'action' attribute or it is None.")
        return "synthesis"
 
    if next_action == RoutingNextAction.MEDICAL_WORKER.value:
        return "medical_worker"
    elif next_action == RoutingNextAction.PRODUCT_WORKER.value:
        return "product_worker"
    elif next_action == RoutingNextAction.NUTRIENT_WORKER.value:
        return "nutrient_worker"
    else:
        return "synthesis"