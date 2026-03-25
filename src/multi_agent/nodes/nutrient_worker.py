import json
import logging
 
from src.multi_agent.state.graph_state import MultiAgentState
from src.multi_agent.schemas.worker_results import NutrientWorkerResult
from src.agent.tools.nutrient_tool import nutrient_lookup
 
logger = logging.getLogger(__name__)
 
 
def run_nutrient_worker(state: MultiAgentState) -> dict:
    step = state.get("current_decision")
    nutrient = step.nutrient if step else ""
    task_type = "nutrient_edu"
    instructions = {"nutrient": nutrient}
 
    logger.info(f"NutrientWorker: task={task_type}, instructions={instructions}")
 
    try:
        if task_type == "nutrient_edu":
            nutrient = instructions.get("nutrient", "")
            raw = nutrient_lookup.invoke({"nutrient": nutrient})
            parsed = _safe_parse(raw)
            summary = _build_summary(parsed, nutrient, state)
            worker_label = f"nutrient_worker({nutrient})"
        else:
            logger.warning(f"NutrientWorker: Unknown task_type '{task_type}'")
            parsed = {"error": True, "message": f"Unknown nutrient task type: {task_type}"}
            summary = f"ERROR: Unknown task type '{task_type}'."
            worker_label = f"nutrient_worker(unknown:{task_type})"
 
    except Exception as e:
        logger.error(f"NutrientWorker failed: {e}", exc_info=True)
        parsed = {"error": True, "message": str(e)}
        summary = f"ERROR: Nutrient worker failed — {str(e)}."
        worker_label = "nutrient_worker(error)"
 
    nuts = _extract_nutrients(state, parsed)
 
    logger.info(f"NutrientWorker: Done. Summary: {summary[:120]}")
 
    pydantic_result = NutrientWorkerResult(
        summary=summary,
        nutrient_name=nutrient if isinstance(parsed, dict) else None,
    )

    return {
        "nutrient_worker_results": [pydantic_result],
        "persisted_nutrients": nuts,
        "execution_path": [worker_label],
    }
 
 
def _build_summary(parsed, nutrient: str, state: MultiAgentState) -> str:
    if isinstance(parsed, dict):
        if parsed.get("error"):
            return f"ERROR: {parsed.get('message', 'unknown')}"
        if parsed.get("message") and not parsed.get("nutrient_info"):
            return f"No data found for nutrient '{nutrient}': {parsed['message']}"
 
    items = parsed if isinstance(parsed, list) else [parsed]
    for item in items:
        if not isinstance(item, dict):
            continue
        ctx = item.get("context", item)
        if not isinstance(ctx, dict):
            continue
 
        info = ctx.get("nutrient_info", {})
        supp = ctx.get("supplementation", {})
        sources = ctx.get("dietary_sources", [])
 
        name = info.get("name", nutrient)
        overview = info.get("overview", "")
        rda = supp.get("daily_allowance", "N/A")
        forms = supp.get("recommended_forms", "")
        side_effects = supp.get("side_effects_if_overdosed", [])
 
        # Cross-reference: is this nutrient depleted by a known medication?
        meds = state.get("persisted_medications", [])
        link = ""
        if meds:
            link = f" (context: depleted by {', '.join(meds[:2])})"
 
        parts = [f"NUTRIENT: {name}{link}"]
        if overview:
            parts.append(f"  Overview: {overview[:120]}")
        parts.append(f"  RDA: {rda}")
        if forms:
            parts.append(f"  Recommended forms: {forms[:80]}")
        if sources:
            parts.append(f"  Food sources: {', '.join(sources[:5])}")
        if side_effects:
            parts.append(f"  Overdose risks: {', '.join(side_effects[:3])}")
 
        return "\n".join(parts)
 
    return f"Data received for '{nutrient}' but could not parse structure."
 
 
def _safe_parse(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
 
 
def _extract_nutrients(state: MultiAgentState, parsed) -> list:
    nuts = list(state.get("persisted_nutrients", []))
 
    if not isinstance(parsed, dict):
        return nuts
 
    items = parsed if isinstance(parsed, list) else [parsed]
    for item in items:
        if not isinstance(item, dict):
            continue
        ctx = item.get("context", item)
        if isinstance(ctx, dict):
            info = ctx.get("nutrient_info", {})
            if isinstance(info, dict):
                name = info.get("name", "")
                if name and name not in nuts:
                    nuts.append(name)
 
    return nuts