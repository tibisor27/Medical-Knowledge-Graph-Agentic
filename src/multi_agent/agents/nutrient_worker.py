"""
NutrientWorker — Deterministic Neo4j data retrieval for nutrient education.

Handles:
  - nutrient_edu: Return natural sources, benefits, and general info
"""

import json
import logging

from src.multi_agent.state import MultiAgentState

# Import tool
from src.agent.tools.nutrient_education_tool import nutrient_lookup

logger = logging.getLogger(__name__)


def run_nutrient_worker(state: MultiAgentState) -> dict:
    task_type = state.get("worker_task_type", "")
    instructions = state.get("worker_instructions", {})

    logger.info(f"NutrientWorker: task={task_type}, instructions={instructions}")

    try:
        if task_type == "nutrient_edu":
            nutrient = instructions.get("nutrient", "")
            raw_result = nutrient_lookup.invoke({"nutrient": nutrient})
            worker_label = f"nutrient_worker({nutrient})"
        else:
            logger.warning(f"NutrientWorker: Unknown task_type '{task_type}'")
            raw_result = json.dumps({
                "error": True,
                "message": f"Unknown nutrient task type: {task_type}",
            })
            worker_label = f"nutrient_worker(unknown:{task_type})"

    except Exception as e:
        logger.error(f"NutrientWorker failed: {e}", exc_info=True)
        raw_result = json.dumps({
            "error": True,
            "message": f"Nutrient worker error: {str(e)}",
        })
        worker_label = "nutrient_worker(error)"

    parsed = _safe_parse(raw_result)
    nuts = _extract_nutrients(state, parsed)

    logger.info(f"NutrientWorker: Done. Result length={len(raw_result)} chars")

    return {
        "worker_results": [{
            "source": "nutrient_worker",
            "task_type": task_type,
            "data": parsed,
        }],
        "persisted_nutrients": nuts,
        "execution_path": [worker_label],
    }


def _safe_parse(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _extract_nutrients(state: MultiAgentState, parsed) -> list:
    """Extract nutrient names for context state."""
    nuts = list(state.get("persisted_nutrients", []))
    
    if not isinstance(parsed, dict):
        return nuts

    nutrient_name = parsed.get("nutrient", "")
    if nutrient_name and nutrient_name not in nuts:
        nuts.append(nutrient_name)

    return nuts
