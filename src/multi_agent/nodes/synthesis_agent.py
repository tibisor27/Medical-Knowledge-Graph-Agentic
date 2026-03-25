import logging

from langchain_core.messages import SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

from src.multi_agent.state.graph_state import MultiAgentState
from src.utils.get_llm import get_llm_4_1_mini

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

SYNTHESIS_SYSTEM_PROMPT = """\
You are Yoboo, a friendly Wellbeing Energy Coach.

═══ WHO YOU ARE ═══

You are NOT a medical app, doctor, or diagnostic tool.
You ARE a knowledgeable companion that helps users understand how their medications
can affect their nutrient levels, based on the "Drug-Induced Nutrient Depletion Handbook".

Your role:
- Explain medication-nutrient depletion relationships from your verified database
- Help users understand how this may relate to symptoms they experience
- Guide them toward a healthcare professional for personalized advice

═══ COMMUNICATION STYLE ═══

• Warm, curious, empathic, and honest.
• Acknowledge how the user feels before presenting data.
• Speak naturally — not like a report. Avoid bullet dumps unless truly useful.
• Ask one follow-up question at the end to keep the conversation going.
• Be transparent: "According to my database..." or "My records show..."
• When no data: "I don't have that in my database, but here is what I know..."

═══ CRITICAL RULES ═══

1. ONLY use information from the EVIDENCE section below. Do NOT add external knowledge.
2. If evidence is empty or contains errors, say so honestly and respond conversationally.
3. NEVER diagnose, prescribe, or recommend dosages (unless from a product's own label).
4. ALWAYS add a gentle professional referral when discussing medications or symptoms.
5. Respond in the same language the user is writing in.
6. Keep responses focused — not everything needs to be said at once.

═══ DISCLAIMER RULES ═══

Add stronger disclaimers when safety flags include:
- pregnancy/children → "Please discuss with your doctor before taking any supplements"
- dosage questions → "Dosages should be personalized by a healthcare professional"
- drug interactions → "A pharmacist can check for potential interactions"
- Multiple medications → "With multiple medications, a pharmacist review is especially important"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SUPERVISOR BRIEFING (read this first)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Guidance: {response_guidance}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 EVIDENCE FROM DATABASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{gathered_evidence}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 USER CONTEXT (across entire conversation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{persisted_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SAFETY FLAGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{safety_flags}
"""

SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYNTHESIS_SYSTEM_PROMPT),
    ("placeholder", "{messages}"),
])


# ═══════════════════════════════════════════════════════════════════════════════
# NODE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def run_synthesis_agent(state: MultiAgentState) -> dict:

    # ── 1. Extract supervisor briefing ──────────────────────────────────────
    current_decision = state.get("current_decision")
    response_guidance = getattr(current_decision, "response_guidance", "Respond naturally based on the evidence available.")
    logger.info(f"Synthesis: guidance='{response_guidance}'")

    # ── 2. Build worker evidence ─────────────────────────────────────────────
    gathered_evidence = _build_evidence(state)
    logger.info(f"Synthesis: evidence length={len(gathered_evidence)}")

    # ── 3. Build persisted context ───────────────────────────────────────────
    persisted_context = _build_persisted_context(state)

    # ── 4. Safety flags ──────────────────────────────────────────────────────
    safety_flags_raw = state.get("safety_flags", [])
    safety_flags = ", ".join(safety_flags_raw) if safety_flags_raw else "None detected."

    # ── 5. Build prompt values ───────────────────────────────────────────────
    prompt_values = {
        "response_guidance": response_guidance,
        "gathered_evidence": gathered_evidence,
        "persisted_context": persisted_context,
        "safety_flags": safety_flags,
        "messages": state.get("messages", [])[-10:],
    }

    # ── 6. Invoke LLM ────────────────────────────────────────────────────────
    llm = get_llm_4_1_mini()
    chain = SYNTHESIS_PROMPT | llm

    try:
        result = chain.invoke(prompt_values)
        response_text = result.content
        logger.info(f"Synthesis: Generated response ({len(response_text)} chars)")

        return {
            "final_response": response_text,
            "messages": [AIMessage(content=response_text)],
            "execution_path": ["synthesis"],
        }

    except Exception as e:
        logger.error(f"Synthesis Agent failed: {e}", exc_info=True)
        return {
            "final_response": (
                "I'm sorry, I had a little trouble putting my thoughts together. "
                "Could you ask again? I'm here to help!"
            ),
            "execution_path": ["synthesis(error)"],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EVIDENCE BUILDER — Reads all worker results from shared state
# ═══════════════════════════════════════════════════════════════════════════════

def _build_evidence(state: MultiAgentState) -> str:
    """
    Assembles the 'EVIDENCE FROM DATABASE' section for the synthesis prompt.
    Reads from plural Pydantic list fields — all results accumulated across
    multiple worker calls in the same turn are combined into evidence.
    """
    blocks = []

    # ── Medical results ───────────────────────────────────────────────────────
    med_results = [r for r in (state.get("medical_worker_results") or []) if r and r != "CLEAR"]
    for i, med in enumerate(med_results, 1):
        if med.summary:
            label = f"[MEDICAL DATA #{i}]" if len(med_results) > 1 else "[MEDICAL DATA]"
            blocks.append(f"{label}\n{med.summary}")

    # ── Product results ───────────────────────────────────────────────────────
    prod_results = [r for r in (state.get("product_worker_results") or []) if r and r != "CLEAR"]
    for i, prod in enumerate(prod_results, 1):
        if prod.summary:
            label = f"[PRODUCT RECOMMENDATIONS #{i}]" if len(prod_results) > 1 else "[PRODUCT RECOMMENDATIONS]"
            blocks.append(f"{label}\n{prod.summary}")

    # ── Nutrient results ──────────────────────────────────────────────────────
    nut_results = [r for r in (state.get("nutrient_worker_results") or []) if r and r != "CLEAR"]
    for i, nut in enumerate(nut_results, 1):
        if nut.summary:
            label = f"[NUTRIENT EDUCATION #{i}]" if len(nut_results) > 1 else "[NUTRIENT EDUCATION]"
            blocks.append(f"{label}\n{nut.summary}")

    if not blocks:
        return "No data was retrieved from the database in this turn. Respond conversationally using only what is in the User Context above."

    return "\n\n".join(blocks)




# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT BUILDER — Cross-turn persisted entities
# ═══════════════════════════════════════════════════════════════════════════════

def _build_persisted_context(state: MultiAgentState) -> str:
    """
    Builds a readable summary of what is already known about the user
    from all previous conversation turns.
    """
    parts = []

    meds = state.get("persisted_medications", [])
    if meds:
        parts.append(f"Medications user takes: {', '.join(meds)}")

    symptoms = state.get("persisted_symptoms", [])
    if symptoms:
        parts.append(f"Symptoms reported: {', '.join(symptoms)}")

    nutrients = state.get("persisted_nutrients", [])
    if nutrients:
        parts.append(f"Nutrients already identified: {', '.join(nutrients)}")

    products = state.get("persisted_products", [])
    if products:
        parts.append(f"Products already discussed: {', '.join(products[-5:])}")

    return "\n".join(parts) if parts else "No prior context — this appears to be the start of the conversation."