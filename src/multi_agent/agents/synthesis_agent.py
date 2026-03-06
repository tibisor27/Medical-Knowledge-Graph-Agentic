"""
Synthesis Agent (Yoboo) — The personality and response formatting layer.

This is the ONLY agent that generates user-facing natural language.
It receives raw data from deterministic workers (via state["worker_results"])
and formats it in Yoboo's warm, empathetic, database-grounded tone.

NO tool calling. NO database access. ONLY text generation from provided data.
"""

import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage

from src.multi_agent.state import MultiAgentState
from src.utils.get_llm import get_llm_4_1_mini

logger = logging.getLogger(__name__)


SYNTHESIS_SYSTEM_PROMPT = """You are Yoboo, a friendly Wellbeing Energy Coach.

═══════ WHO YOU ARE ═══════

You are NOT a medical app, doctor, or diagnostic tool.
You ARE a knowledgeable companion that helps users explore medication-nutrient connections
using a verified database (Drug-Induced Nutrient Depletion Handbook).

Your role:
- Explain medication-nutrient depletion relationships from the database
- Help users understand how their medications might affect their nutrient levels
- Guide users to healthcare professionals for personalized advice

═══════ YOUR COMMUNICATION TONE ═══════

Be WARM, CURIOUS, EMPATHIC, and HONEST:
- Acknowledge how the user feels before presenting data
- Ask follow-up questions to keep the conversation going
- Be transparent: "According to my database..." or "My records show..."
- When there's no data: "I don't have information about that in my database"

═══════ CRITICAL RULES ═══════

1. ONLY use information from the DATA below. NEVER add general knowledge.
2. If the data is empty or contains errors, say you don't have that data.
3. Frame all information as coming from your database, not general medical knowledge.
4. NEVER diagnose, prescribe, or recommend specific dosages (unless from a product prospect).
5. ALWAYS add a gentle professional referral when discussing medications or symptoms.
6. Respond in the SAME LANGUAGE as the user's message.

═══════ RESPONSE STRUCTURE ═══════

1. Warm acknowledgment (1 sentence)
2. Database findings (what was discovered about medications/nutrients)
3. Product recommendations (if available and relevant)
4. Honest gaps (what you don't have data on)
5. Disclaimer (when discussing medications/symptoms)
6. Forward question (keep the conversation going)

═══════ DISCLAIMER RULES ═══════

Add stronger disclaimers when safety flags include:
- pregnancy/children → "Please discuss with your doctor before taking any supplements"
- dosage questions → "Dosages should be personalized by a healthcare professional"
- drug interactions → "A pharmacist can check for potential interactions"
- Multiple medications → "With multiple medications, a pharmacist review is especially important"

═══════ DATA FROM WORKERS ═══════

{worker_data}

═══════ SUPERVISOR REASONING ═══════

{supervisor_reasoning}

═══════ SAFETY FLAGS ═══════

{safety_flags}

═══════ CONVERSATION CONTEXT ═══════

{persisted_context}
"""


def run_synthesis_agent(state: MultiAgentState) -> dict:
    """
    LangGraph node: Formats gathered data into a warm, user-facing Yoboo response.

    Reads:  worker_results, supervisor_reasoning, safety_flags,
            persisted_*, messages, guardrail_feedback
    Writes: final_response, execution_path
    """
    logger.info("Synthesis Agent: Generating Yoboo response...")

    worker_results = state.get("worker_results", [])
    supervisor_reasoning = state.get("supervisor_reasoning", [])
    safety_flags = state.get("safety_flags", [])
    guardrail_feedback = state.get("guardrail_feedback", "")

    persisted_context = _build_context(state)

    # Format worker data for the prompt
    worker_data = _format_worker_results(worker_results)
    reasoning_str = "\n".join(supervisor_reasoning) if supervisor_reasoning else "No notes."

    system_prompt = SYNTHESIS_SYSTEM_PROMPT.format(
        worker_data=worker_data,
        supervisor_reasoning=reasoning_str,
        safety_flags=", ".join(safety_flags) if safety_flags else "None",
        persisted_context=persisted_context,
    )

    # Get the user's latest message
    messages = state.get("messages", [])
    user_msg = ""
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human":
            user_msg = msg.content
            break

    synthesis_input = user_msg
    if guardrail_feedback:
        synthesis_input = (
            f"{user_msg}\n\n"
            f"[GUARDRAIL CORRECTION: Your previous response had an issue. "
            f"Please fix: {guardrail_feedback}]"
        )

    llm = get_llm_4_1_mini()

    try:
        result = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=synthesis_input),
        ])

        response_text = result.content
        logger.info(f"Synthesis Agent: Generated response ({len(response_text)} chars)")

        return {
            "final_response": response_text,
            "execution_path": ["synthesis"],
        }

    except Exception as e:
        logger.error(f"Synthesis Agent failed: {e}", exc_info=True)
        return {
            "final_response": (
                "I'm sorry, I had trouble formatting my response. "
                "Could you please try asking again?"
            ),
            "execution_path": ["synthesis(error)"],
        }


def _format_worker_results(worker_results: list) -> str:
    """Format worker results into a structured string for the Synthesis prompt."""
    if not worker_results:
        return "No data was gathered from the database. Respond conversationally."

    sections = []
    for wr in worker_results:
        source = wr.get("source", "unknown")
        task_type = wr.get("task_type", "unknown")
        data = wr.get("data", {})

        header = f"── {source.upper()} ({task_type}) ──"
        if isinstance(data, (dict, list)):
            # Truncate to control prompt size
            data_str = json.dumps(data, indent=2, ensure_ascii=False)[:3000]
        else:
            data_str = str(data)[:3000]

        sections.append(f"{header}\n{data_str}")

    return "\n\n".join(sections)


def _build_context(state: MultiAgentState) -> str:
    parts = []
    meds = state.get("persisted_medications", [])
    if meds:
        parts.append(f"Medications: {', '.join(meds)}")
    syms = state.get("persisted_symptoms", [])
    if syms:
        parts.append(f"Symptoms: {', '.join(syms)}")
    nuts = state.get("persisted_nutrients", [])
    if nuts:
        parts.append(f"Nutrients identified: {', '.join(nuts)}")
    prods = state.get("persisted_products", [])
    if prods:
        parts.append(f"Products discussed: {', '.join(prods[-5:])}")
    lang = state.get("detected_language", "en")
    parts.append(f"Detected language: {lang}")
    return "\n".join(parts) if parts else "No prior context."
