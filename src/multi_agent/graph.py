"""
Multi-Agent LangGraph — Supervisor + Deterministic Workers Architecture.

═══════════════════════════════════════════════════════════════════════════════
GRAPH STRUCTURE
═══════════════════════════════════════════════════════════════════════════════

    START
      │
      ▼
    InputGateway (deterministic: crisis detection, input validation)
      │
      ├─ crisis ──→ SafetyAgent (deterministic) ──→ END
      │
      ▼
    Supervisor (structured output LLM — routing decisions)
      │
      ├─ call_medical  ──→ MedicalWorker (deterministic) ──→ Supervisor
      ├─ call_product  ──→ ProductWorker (deterministic) ──→ Supervisor
      ├─ call_nutrient ──→ NutrientWorker (deterministic) ──→ Supervisor
      │
      └─ respond ──→ SynthesisAgent (LLM — user-facing text) ──→ Guardrail
                                                                    │
                                                              ├─ pass ──→ END
                                                              └─ fail ──→ SynthesisAgent

LLM calls: Supervisor (1 per loop, max 3) + Synthesis (1) = 2-4 total.
Workers: Zero LLM cost — deterministic Python + Neo4j queries.
"""

import logging
from langgraph.graph import StateGraph, END

from src.multi_agent.state import MultiAgentState
from src.multi_agent.agents.input_gateway import input_gateway
from src.multi_agent.agents.supervisor import run_supervisor
from src.multi_agent.agents.medical_worker import run_medical_worker
from src.multi_agent.agents.product_worker import run_product_worker
from src.multi_agent.agents.nutrient_worker import run_nutrient_worker
from src.multi_agent.agents.synthesis_agent import run_synthesis_agent
from src.multi_agent.agents.guardrail_agent import run_guardrail
from src.multi_agent.agents.safety_agent import run_safety_agent

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTING FUNCTIONS (deterministic, based on state values)
# ═══════════════════════════════════════════════════════════════════════════════

def _gateway_routing(state: MultiAgentState) -> str:
    """After InputGateway: route to safety or supervisor."""
    safety_flags = state.get("safety_flags", [])
    if "crisis_keyword_detected" in safety_flags:
        return "safety_agent"
    return "supervisor"


def _supervisor_routing(state: MultiAgentState) -> str:
    """After Supervisor: route to the appropriate worker or to synthesis."""
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
    """After Guardrail: pass to END or retry via Synthesis."""
    if state.get("guardrail_pass", True):
        return "end"
    return "retry_synthesis"


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH CONSTRUCTION
# ═══════════════════════════════════════════════════════════════════════════════

def build_multi_agent_graph():
    """
    Build and compile the Supervisor + Workers graph.

    Returns a compiled graph that can be invoked with:
        result = graph.invoke({"messages": [HumanMessage("Hello")]})
    """
    graph = StateGraph(MultiAgentState)

    # ── Register nodes ──
    graph.add_node("input_gateway", input_gateway)
    graph.add_node("supervisor", run_supervisor)
    graph.add_node("medical_worker", run_medical_worker)
    graph.add_node("product_worker", run_product_worker)
    graph.add_node("nutrient_worker", run_nutrient_worker)
    graph.add_node("synthesis", run_synthesis_agent)
    graph.add_node("guardrail", run_guardrail)
    graph.add_node("safety_agent", run_safety_agent)

    # ── Entry point ──
    graph.set_entry_point("input_gateway")

    # ── InputGateway → Supervisor or SafetyAgent ──
    graph.add_conditional_edges(
        "input_gateway",
        _gateway_routing,
        {"supervisor": "supervisor", "safety_agent": "safety_agent"},
    )

    # ── Supervisor → Workers or Synthesis ──
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

    # ── Workers → back to Supervisor (loop) ──
    graph.add_edge("medical_worker", "supervisor")
    graph.add_edge("product_worker", "supervisor")
    graph.add_edge("nutrient_worker", "supervisor")

    # ── Synthesis → Guardrail ──
    graph.add_edge("synthesis", "guardrail")

    # ── Guardrail → END or retry Synthesis ──
    graph.add_conditional_edges(
        "guardrail",
        _guardrail_routing,
        {"end": END, "retry_synthesis": "synthesis"},
    )

    # ── SafetyAgent → END ──
    graph.add_edge("safety_agent", END)

    compiled = graph.compile()
    logger.info("Multi-agent graph (Supervisor + Workers architecture) compiled successfully.")
    return compiled
