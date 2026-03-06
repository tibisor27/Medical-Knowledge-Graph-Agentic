"""
MedicalWorker — Deterministic Neo4j data retrieval for medical queries.

NO LLM call. The Supervisor already decided WHAT to query; this worker
just executes the correct tool and returns raw data.

Handles:
  - med_lookup: What nutrients does a medication deplete?
  - symptom_inv: What deficiencies might cause a symptom?
  - connection: Does medication X cause symptom Y via depletion?
"""

import json
import logging

from src.multi_agent.state import MultiAgentState

# Import tools — these are @tool-decorated functions that return JSON strings
from src.agent.tools.medication_tool import medication_lookup
from src.agent.tools.symptom_investigation_tool import symptom_investigation
from src.agent.tools.connection_validation_tool import connection_validation

logger = logging.getLogger(__name__)


def run_medical_worker(state: MultiAgentState) -> dict:
    """
    LangGraph node: Deterministic medical data retrieval.

    Reads:  worker_task_type, worker_instructions
    Writes: worker_results, persisted_medications, persisted_symptoms,
            persisted_nutrients, execution_path
    """
    task_type = state.get("worker_task_type", "")
    instructions = state.get("worker_instructions", {})

    logger.info(f"MedicalWorker: task={task_type}, instructions={instructions}")

    try:
        if task_type == "med_lookup":
            medication = instructions.get("medication", "")
            raw_result = medication_lookup.invoke({"medication": medication})
            worker_label = f"medical_worker(med_lookup:{medication})"

        elif task_type == "symptom_inv":
            symptom = instructions.get("symptom", "")
            raw_result = symptom_investigation.invoke({"symptom": symptom})
            worker_label = f"medical_worker(symptom_inv:{symptom})"

        elif task_type == "connection":
            medication = instructions.get("medication", "")
            symptom = instructions.get("symptom", "")
            raw_result = connection_validation.invoke({
                "medication": medication,
                "symptom": symptom,
            })
            worker_label = f"medical_worker(connection:{medication}+{symptom})"

        else:
            logger.warning(f"MedicalWorker: Unknown task_type '{task_type}'")
            raw_result = json.dumps({
                "error": True,
                "message": f"Unknown medical task type: {task_type}",
            })
            worker_label = f"medical_worker(unknown:{task_type})"

    except Exception as e:
        logger.error(f"MedicalWorker failed: {e}", exc_info=True)
        raw_result = json.dumps({
            "error": True,
            "message": f"Medical worker error: {str(e)}",
        })
        worker_label = "medical_worker(error)"

    # Parse the result to extract entities for persistence
    parsed = _safe_parse(raw_result)
    meds, syms, nuts = _extract_entities(state, parsed, task_type)

    logger.info(f"MedicalWorker: Done. Result length={len(raw_result)} chars")

    return {
        "worker_results": [{
            "source": "medical_worker",
            "task_type": task_type,
            "data": parsed,
        }],
        "persisted_medications": meds,
        "persisted_symptoms": syms,
        "persisted_nutrients": nuts,
        "execution_path": [worker_label],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION (for session persistence)
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_parse(raw: str):
    """Parse JSON string from tool result, return original on failure."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _extract_entities(state: MultiAgentState, parsed, task_type: str) -> tuple:
    """Extract medication, symptom, nutrient names from tool results."""
    meds = list(state.get("persisted_medications", []))
    syms = list(state.get("persisted_symptoms", []))
    nuts = list(state.get("persisted_nutrients", []))

    if not isinstance(parsed, (list, dict)):
        return meds, syms, nuts

    items = parsed if isinstance(parsed, list) else [parsed]

    for item in items:
        if not isinstance(item, dict):
            continue

        context = item.get("context", item)
        if not isinstance(context, dict):
            continue

        # From medication lookup
        med_info = context.get("medication", {})
        if isinstance(med_info, dict):
            name = med_info.get("name", "")
            if name and name not in meds:
                meds.append(name)

        # From depletions
        for dep in context.get("depletions", []):
            if isinstance(dep, dict):
                nut = dep.get("nutrient", "")
                if nut and nut not in nuts:
                    nuts.append(nut)
                for sym in dep.get("symptoms", []):
                    if sym and sym not in syms:
                        syms.append(sym)

        # From symptom investigation
        symptom_name = context.get("symptom", "")
        if isinstance(symptom_name, str) and symptom_name and symptom_name not in syms:
            syms.append(symptom_name)

        # From connection validation
        if context.get("connection_found"):
            med_name = context.get("medication", "")
            if isinstance(med_name, str) and med_name and med_name not in meds:
                meds.append(med_name)
            for vs in context.get("validated_symptoms", []):
                if isinstance(vs, dict):
                    for n in vs.get("matched_nutrients", []):
                        if n and n not in nuts:
                            nuts.append(n)

    return meds, syms, nuts
