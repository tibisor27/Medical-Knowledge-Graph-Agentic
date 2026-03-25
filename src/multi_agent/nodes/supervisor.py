import logging
from src.multi_agent.state.graph_state import MultiAgentState
from src.multi_agent.schemas.supervisor_schema import SupervisorDecisionOutput, MedicalWorker, ProductWorker, NutrientWorker, RespondWorker
from src.multi_agent.prompts.supervisor_prompt import SUPERVISOR_CHAT_PROMPT
from src.utils.get_llm import get_llm_4_1_mini
from src.multi_agent.state import log_state_summary
 
logger = logging.getLogger(__name__)
 
MAX_SUPERVISOR_LOOPS = 5
TOOL_REGISTRY = {
    "MedicalWorker": MedicalWorker,
    "ProductWorker": ProductWorker,
    "NutrientWorker": NutrientWorker,
    "RespondWorker": RespondWorker
}
 
def run_supervisor(state: MultiAgentState) -> dict:
 
    loop_count = state.get("step_count", 0)
 
    if loop_count >= MAX_SUPERVISOR_LOOPS:
        logger.warning(f"Supervisor: Max loops ({MAX_SUPERVISOR_LOOPS}) reached.")
        return _force_respond(loop_count, "Max loop count reached.")
 
    prompt_values = build_prompt_values(state, loop_count)
 
    llm = get_llm_4_1_mini()
 
    # logger.info(f"Prompt values: {format_prompt_values_for_logging(prompt_values)}")
    # log_state_summary(state, title=f"Supervisor Loop {loop_count + 1} - State Summary Before Decision")
    # We use method="function_calling" instead of strict=False because LangChain 0.3+ defaults to JSON Schema
    # which forbids anyOf/oneOf (Pydantic Unions) even if strict=False.
    structured_llm = llm.with_structured_output(
        SupervisorDecisionOutput,
        method="function_calling"
    )
 
    # router_llm = llm.bind_tools(
    #     [TOOL_REGISTRY["MedicalWorker"], TOOL_REGISTRY["ProductWorker"], TOOL_REGISTRY["NutrientWorker"], TOOL_REGISTRY["RespondWorker"]],
    #     tool_choice = "any"
    # )
 
    chain = SUPERVISOR_CHAT_PROMPT | structured_llm
 
    try:
        response = chain.invoke(prompt_values)
        decision = response.decision
        logger.info(f"Supervisor decision at turn {loop_count + 1}: {decision.action.value} - {decision.reasoning}")

        return decision_to_state(decision, loop_count)
 
    except Exception as e:
        logger.error(f"Supervisor LLM failed: {e}", exc_info=True)
        return _force_respond(loop_count, f"LLM error: {str(e)}")
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# DECISION -> STATE CONVERSION
# ═══════════════════════════════════════════════════════════════════════════════
 
def decision_to_state(decision, loop_count: int) -> dict:
    """
    Add the new decision to previous_decisions immediately.

    setup_turn clears previous_decisions at the start of each user turn (CLEAR sentinel).
    Within a turn, the clear_or_add reducer accumulates:
      - Loop 1 prompt sees: previous_decisions=[]  (just cleared by setup_turn)
      - Loop 1 returns:     {previous_decisions: [Metformin]}
      - Loop 2 prompt sees: previous_decisions=[Metformin]   <- LLM sees what already ran
      - Loop 2 returns:     {previous_decisions: [Ibuprofen]}
      - Loop 3 prompt sees: previous_decisions=[Metformin, Ibuprofen]
    """
    return {
        "current_decision": decision,
        "previous_decisions": [decision],
        "step_count": loop_count + 1,
        "execution_path": [f"supervisor({decision.action.value})"],
    }
 
 
def _force_respond(loop_count: int, reason: str) -> dict:
    from src.multi_agent.schemas.supervisor_schema import RespondWorker
    from src.multi_agent.schemas.enums import RoutingNextAction

    forced_decision = RespondWorker(
        action=RoutingNextAction.RESPOND_WORKER,
        reasoning=reason,
        response_guidance="Respond warmly based on any data available. If no data was gathered, respond conversationally and ask what the user needs."
    )

    return {
        "next_action": "respond",
        "current_decision": forced_decision,
        "previous_decisions": [forced_decision],
        "step_count": loop_count,
        "execution_path": ["supervisor(forced_respond)"],
    }

 
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT VALUE BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════
 
def build_prompt_values(state: MultiAgentState, loop_count: int) -> dict:
    return {
        "persisted_context": build_persisted_context(state),
        "gathered_data_summary": format_worker_results_for_prompt(state),
        "previous_actions": format_previous_decisions(state),
        "loop_count": loop_count,
        "max_loops": MAX_SUPERVISOR_LOOPS,
        "messages": state.get("messages", [])[-10:],
    }
 
 
def format_prompt_values_for_logging(prompt_values: dict) -> dict:
    """Format prompt values for clean logging, showing only message content."""
    formatted = prompt_values.copy()
   
    if "messages" in formatted:
        messages = formatted["messages"]
        formatted["messages"] = [
            {"role": msg.type, "content": msg.content}
            for msg in messages
        ]
   
    return formatted
 
 
def build_persisted_context(state: MultiAgentState) -> str:
    parts = []
 
    if state.get("persisted_medications"):
        parts.append(f"Medications user takes: {', '.join(state['persisted_medications'])}")
    else:
        parts.append("Medications: None confirmed yet")
 
    if state.get("persisted_symptoms"):
        parts.append(f"Symptoms user reported: {', '.join(state['persisted_symptoms'])}")
    else:
        parts.append("Symptoms: None reported yet")
 
    if state.get("persisted_nutrients"):
        parts.append(f"Nutrients already identified: {', '.join(state['persisted_nutrients'])}")
    else:
        parts.append("Nutrients: None identified yet")
 
    if state.get("persisted_products"):
        parts.append(f"Products already discussed/ recommended: {', '.join(state['persisted_products'])}")
    else:
        parts.append("Products: None discussed yet")
 
    return "\n".join(parts) if parts else "No prior context."
 
 
def format_previous_decisions(state: MultiAgentState) -> str:
    prev = state.get("previous_decisions", [])
    if not prev:
        return "No previous actions taken yet."
   
    lines = []
    for i, d in enumerate(prev, 1):
        action = d.action.value if hasattr(d.action, 'value') else d.action
        params = _format_decision_params(d)
        lines.append(f"  {i}. {action} {params} — {d.reasoning}")
    logger.info(f"Formatted previous decisions for prompt: {lines}")
    return "\n".join(lines)
 
 
def _format_decision_params(decision) -> str:
    """Extract key params from a decision for display in previous_actions."""
    parts = []
    if hasattr(decision, 'medication') and decision.medication:
        parts.append(f"medication='{decision.medication}'")
    if hasattr(decision, 'symptom') and decision.symptom:
        parts.append(f"symptom='{decision.symptom}'")
    if hasattr(decision, 'medical_query') and decision.medical_query:
        qv = decision.medical_query.value if hasattr(decision.medical_query, 'value') else decision.medical_query
        parts.append(f"query_type='{qv}'")
    if hasattr(decision, 'nutrient') and decision.nutrient:
        parts.append(f"nutrient='{decision.nutrient}'")
    if hasattr(decision, 'product_name') and decision.product_name:
        parts.append(f"product='{decision.product_name}'")
    if hasattr(decision, 'query') and decision.query:
        parts.append(f"search='{decision.query}'")
    if hasattr(decision, 'product_query') and decision.product_query:
        pv = decision.product_query.value if hasattr(decision.product_query, 'value') else decision.product_query
        parts.append(f"query_type='{pv}'")
    return f" ({', '.join(parts)})" if parts else ""
 
 
def format_worker_results_for_prompt(state: MultiAgentState) -> str:
    """
    Builds the WORKER RESULTS section of the supervisor prompt.
    Reads from plural Pydantic list fields — all results accumulated
    across multiple worker calls in the same turn are shown.
    """
    blocks = []

    # ── Medical results (one MedicalWorkerResult per medication called) ───────
    med_results = [r for r in (state.get("medical_worker_results") or []) if r and r != "CLEAR"]
    for i, med in enumerate(med_results, 1):
        label = f"[medical_worker #{i}]" if len(med_results) > 1 else "[medical_worker]"
        med_label = f" (Medication: {med.medication_name})" if med.medication_name else ""
        blocks.append(f"{label}{med_label}:\n{med.summary}")

    # ── Product results ───────────────────────────────────────────────────────
    prod_results = [r for r in (state.get("product_worker_results") or []) if r and r != "CLEAR"]
    for i, prod in enumerate(prod_results, 1):
        label = f"[product_worker #{i}]" if len(prod_results) > 1 else "[product_worker]"
        blocks.append(f"{label}:\n{prod.summary}")

    # ── Nutrient results ──────────────────────────────────────────────────────
    nut_results = [r for r in (state.get("nutrient_worker_results") or []) if r and r != "CLEAR"]
    for i, nut in enumerate(nut_results, 1):
        label = f"[nutrient_worker #{i}]" if len(nut_results) > 1 else "[nutrient_worker]"
        blocks.append(f"{label}:\n{nut.summary}")

    return "\n\n".join(blocks) if blocks else "No worker results yet."