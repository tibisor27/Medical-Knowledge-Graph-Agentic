"""
Supervisor — The brain that routes user queries to deterministic workers.

═══════════════════════════════════════════════════════════════════════════════
DESIGN PHILOSOPHY
═══════════════════════════════════════════════════════════════════════════════

The Supervisor uses structured output (forced JSON) to make routing decisions.
It runs in a LOOP: after each worker returns data, the Supervisor re-evaluates
whether more data is needed or if it's time to send everything to Synthesis.

The Supervisor does NOT generate user-facing text. It ONLY decides:
  - Which worker to call next
  - What parameters to pass to that worker
  - When enough data has been gathered → route to Synthesis

CRITICAL: The Supervisor's prompt is ~60 lines (vs 300 in old ReAct).
          Workers add ZERO LLM cost. Total system = 2 LLM calls per query.

═══════════════════════════════════════════════════════════════════════════════
LOOP PATTERN
═══════════════════════════════════════════════════════════════════════════════

    Supervisor → decides "call_medical" → MedicalWorker → Supervisor
    Supervisor → decides "call_product" → ProductWorker → Supervisor
    Supervisor → decides "respond"      → SynthesisAgent → Guardrail → END

Max 3 iterations to prevent infinite loops.
"""

import json
import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from src.multi_agent.state import MultiAgentState
from src.utils.get_llm import get_llm_4_1_mini

logger = logging.getLogger(__name__)

MAX_SUPERVISOR_LOOPS = 3


# ═══════════════════════════════════════════════════════════════════════════════
# STRUCTURED OUTPUT SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

class SupervisorDecision(BaseModel):
    """The Supervisor's routing decis""ion. Forced JSON — cannot hallucinate."""

    next_action: Literal["call_medical", "call_product", "call_nutrient", "respond"] = Field(
        description=(
            "What to do next. "
            "'call_medical' = query the medical knowledge graph for medication/symptom/connection data. "
            "'call_product' = search for BeLife supplement products. "
            "'call_nutrient' = get educational info about a specific nutrient. "
            "'respond' = enough data gathered, send to Synthesis for user-facing response."
        )
    )

    worker_task_type: Optional[str] = Field(
        default=None,
        description=(
            "Specific task for the worker. "
            "For call_medical: 'med_lookup' | 'symptom_inv' | 'connection'. "
            "For call_product: 'search' | 'details' | 'catalog'. "
            "For call_nutrient: 'nutrient_edu'. "
            "Not needed when next_action='respond'."
        )
    )

    worker_instructions: Optional[dict] = Field(
        default=None,
        description=(
            "Parameters for the worker. Examples: "
            "{'medication': 'Metformin'}, "
            "{'symptom': 'fatigue'}, "
            "{'medication': 'Aspirin', 'symptom': 'headache'}, "
            "{'nutrient': 'Vitamin B12'}, "
            "{'query': 'energy supplements'}, "
            "{'product_name': 'Be-Energy'}, "
            "{'category': 'vitamins'}. "
            "Not needed when next_action='respond'."
        )
    )

    reasoning: str = Field(
        description="Brief explanation of why this action was chosen. For observability."
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

SUPERVISOR_SYSTEM_PROMPT = """You are the Supervisor for a medical knowledge chatbot called Yoboo.

Your ONLY job is to decide what data to gather from the database. You do NOT generate user-facing text.

═══════ AVAILABLE WORKERS ═══════

1. MEDICAL WORKER (call_medical):
   - med_lookup: Look up what nutrients a medication depletes → needs {{"medication": "name"}}
   - symptom_inv: Find what deficiencies/medications cause a symptom → needs {{"symptom": "name"}}
   - connection: Check if medication X causes symptom Y via depletion → needs {{"medication": "name", "symptom": "name"}}

2. PRODUCT WORKER (call_product):
   - search: Find BeLife products matching a need → needs {{"query": "search text"}}
   - details: Get full prospect for a product → needs {{"product_name": "name"}}
   - catalog: Browse product catalog by category → needs {{"category": "optional"}}

3. NUTRIENT WORKER (call_nutrient):
   - nutrient_edu: Educational info about a nutrient → needs {{"nutrient": "name"}}

4. RESPOND: When you have enough data (or no data is needed), choose 'respond' 
   to send everything to the Synthesis Agent for formatting.

═══════ DECISION RULES ═══════

1. If user mentions a medication → call_medical with med_lookup FIRST.
2. If user mentions a symptom (no specific medication) → call_medical with symptom_inv.
3. If user mentions BOTH medication AND symptom → call_medical with connection.
4. If user asks specifically about a nutrient → call_nutrient with nutrient_edu.
5. If user EXPLICITLY asks for products/supplements → call_product with search.
   DO NOT search products unless user explicitly asks.
6. For greetings, thanks, off-topic → respond immediately (no workers needed).
7. If worker_results already contain the needed data → respond.
8. You can call workers SEQUENTIALLY (one per loop iteration, max 3 total).

═══════ CONTEXT ═══════

Persisted context: {persisted_context}
Safety flags: {safety_flags}
Data already gathered: {gathered_data_summary}
Loop iteration: {loop_count} / {max_loops}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def run_supervisor(state: MultiAgentState) -> dict:
    """
    LangGraph node: Routes user queries to the appropriate worker.

    Uses structured output — the LLM returns a SupervisorDecision JSON object.
    Cannot hallucinate or return free text.

    Reads:  messages, persisted_*, worker_results, supervisor_loop_count
    Writes: next_action, worker_task_type, worker_instructions,
            supervisor_reasoning, supervisor_loop_count, execution_path
    """
    loop_count = state.get("supervisor_loop_count", 0)

    # Safety: prevent infinite loops
    if loop_count >= MAX_SUPERVISOR_LOOPS:
        logger.warning(f"Supervisor: Max loops ({MAX_SUPERVISOR_LOOPS}) reached, forcing respond.")
        return {
            "next_action": "respond",
            "supervisor_reasoning": [f"Max loop count ({MAX_SUPERVISOR_LOOPS}) reached, proceeding to synthesis."],
            "execution_path": ["supervisor(max_loops)"],
        }

    # Build context
    persisted_context = _build_persisted_context(state)
    safety_flags = state.get("safety_flags", [])
    worker_results = state.get("worker_results", [])
    gathered_summary = _summarize_gathered_data(worker_results)

    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        persisted_context=persisted_context,
        safety_flags=", ".join(safety_flags) if safety_flags else "None",
        gathered_data_summary=gathered_summary,
        loop_count=loop_count,
        max_loops=MAX_SUPERVISOR_LOOPS,
    )

    # Build messages: system prompt + conversation history
    messages = [SystemMessage(content=system_prompt)]
    conversation_history = state.get("messages", [])
    recent_history = conversation_history[-10:]
    messages.extend(recent_history)

    # Call LLM with structured output
    llm = get_llm_4_1_mini()
    structured_llm = llm.with_structured_output(SupervisorDecision)

    try:
        decision: SupervisorDecision = structured_llm.invoke(messages)
        logger.info(
            f"Supervisor: action={decision.next_action}, "
            f"task={decision.worker_task_type}, "
            f"instructions={decision.worker_instructions}, "
            f"reasoning={decision.reasoning}"
        )
    except Exception as e:
        logger.error(f"Supervisor LLM call failed: {e}. Falling back to respond.", exc_info=True)
        return {
            "next_action": "respond",
            "supervisor_reasoning": [f"Supervisor LLM error: {str(e)}. Falling back to respond."],
            "supervisor_loop_count": loop_count,
            "execution_path": ["supervisor(error)"],
        }

    return {
        "next_action": decision.next_action,
        "worker_task_type": decision.worker_task_type or "",
        "worker_instructions": decision.worker_instructions or {},
        "supervisor_reasoning": [decision.reasoning],
        "supervisor_loop_count": loop_count + 1,
        "execution_path": [f"supervisor({decision.next_action})"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_persisted_context(state: MultiAgentState) -> str:
    parts = []
    meds = state.get("persisted_medications", [])
    if meds:
        parts.append(f"Medications discussed: {', '.join(meds)}")
    symptoms = state.get("persisted_symptoms", [])
    if symptoms:
        parts.append(f"Symptoms mentioned: {', '.join(symptoms)}")
    nutrients = state.get("persisted_nutrients", [])
    if nutrients:
        parts.append(f"Nutrients identified: {', '.join(nutrients)}")
    products = state.get("persisted_products", [])
    if products:
        parts.append(f"Products discussed: {', '.join(products[-5:])}")
    lang = state.get("detected_language", "en")
    parts.append(f"Detected language: {lang}")
    return "\n".join(parts) if parts else "No prior context — start of conversation."


def _summarize_gathered_data(worker_results: list) -> str:
    if not worker_results:
        return "No data gathered yet."

    summaries = []
    for wr in worker_results:
        source = wr.get("source", "unknown")
        task_type = wr.get("task_type", "unknown")
        data = wr.get("data", {})

        # Create a brief summary of what data was returned
        if isinstance(data, dict):
            if data.get("error"):
                summaries.append(f"[{source}/{task_type}] Error: {data.get('message', 'unknown')}")
            else:
                # Truncate for prompt size control
                data_str = json.dumps(data, ensure_ascii=False)[:200]
                summaries.append(f"[{source}/{task_type}] Data received ({len(data_str)} chars): {data_str}...")
        elif isinstance(data, list):
            summaries.append(f"[{source}/{task_type}] {len(data)} results received.")
        else:
            summaries.append(f"[{source}/{task_type}] Data received.")

    return "\n".join(summaries)
