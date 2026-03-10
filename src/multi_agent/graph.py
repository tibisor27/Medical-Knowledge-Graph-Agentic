import logging
from langgraph.graph import StateGraph, END

from src.multi_agent.state import MultiAgentState
from src.multi_agent.nodes.supervisor import run_supervisor
from src.multi_agent.nodes.medical_worker import run_medical_worker
from src.multi_agent.nodes.product_worker import run_product_worker
from src.multi_agent.nodes.nutrient_worker import run_nutrient_worker
from src.multi_agent.nodes.synthesis_agent import run_synthesis_agent
from src.multi_agent.nodes.guardrail_agent import run_guardrail

logger = logging.getLogger(__name__)

def _supervisor_routing(state: MultiAgentState) -> str:
    next_action = state.get("next_action", "respond")
    if next_action == "call_medical":
        return "medical_worker"
    elif next_action == "call_product":
        return "product_worker"
    elif next_action == "call_nutrient":
        return "nutrient_worker"
    else:
        return "synthesis"


def _guardrail_routing(state: MultiAgentState) -> str:
    if state.get("guardrail_pass", True):
        return "end"
    guardrail_retries = state.get("guardrail_retry_count", 0)
    if guardrail_retries < 2:
        return "retry_synthesis"
    return "end"

def build_multi_agent_graph():
    graph = StateGraph(MultiAgentState)

    graph.add_node("supervisor", run_supervisor)
    graph.add_node("medical_worker", run_medical_worker)
    graph.add_node("product_worker", run_product_worker)
    graph.add_node("nutrient_worker", run_nutrient_worker)
    graph.add_node("synthesis", run_synthesis_agent)
    graph.add_node("guardrail", run_guardrail)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        _supervisor_routing,
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
    graph.add_edge("synthesis", "guardrail")
    graph.add_conditional_edges(
        "guardrail",
        _guardrail_routing,
        {"end": END, "retry_synthesis": "synthesis"},
    )

    compiled = graph.compile()
    logger.info("Multi-agent graph compiled successfully (Supervisor + Workers, no gateway/safety).")
    return compiled
