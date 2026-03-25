import json
import logging
 
from src.multi_agent.state.graph_state import MultiAgentState
from src.multi_agent.schemas.worker_results import ProductWorkerResult
 
from src.agent.tools.find_belife_products_tool import find_belife_products
from src.agent.tools.product_details_tool import product_details
from src.agent.tools.product_catalog_tool import product_catalog
 
logger = logging.getLogger(__name__)
 
 
def run_product_worker(state: MultiAgentState) -> dict:
    step = state.get("current_decision")
    task_type = step.product_query.value if hasattr(step.product_query, 'value') else step.product_query
   
    # Extract instruction fields from step
    query = step.query or ""
    product_name = step.product_name or ""
    category = step.category or ""
    instructions = {}
    if query:
        instructions["query"] = query
    if product_name:
        instructions["product_name"] = product_name
    if category:
        instructions["category"] = category
 
    logger.info(f"ProductWorker: task={task_type}, instructions={instructions}")
 
    try:
        if task_type == "search":
            result_data = _handle_search(instructions, state)
 
        elif task_type == "details":
            result_data = _handle_details(instructions)
 
        elif task_type == "catalog":
            result_data = _handle_catalog(instructions)
 
        else:
            logger.warning(f"ProductWorker: Unknown task_type '{task_type}'")
            result_data = {
                "parsed": {"error": True, "message": f"Unknown product task type: {task_type}"},
                "summary": f"ERROR: Unknown task type '{task_type}'.",
                "label": f"product_worker(unknown:{task_type})",
            }
 
    except Exception as e:
        logger.error(f"ProductWorker failed: {e}", exc_info=True)
        result_data = {
            "parsed": {"error": True, "message": str(e)},
            "summary": f"ERROR: Product worker failed — {str(e)}.",
            "label": "product_worker(error)",
        }
 
    parsed = result_data["parsed"]
    prods = _extract_product_names(state, parsed)
 
    logger.info(f"ProductWorker: Done. Summary: {result_data['summary'][:120]}")
 
    pydantic_result = ProductWorkerResult(
        summary=result_data["summary"],
        products=parsed if isinstance(parsed, list) else [],
    )

    return {
        "product_worker_results": [pydantic_result],
        "persisted_products": prods,
        "execution_path": [result_data["label"]],
    }
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# TASK HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
 
def _handle_search(instructions: dict, state: MultiAgentState) -> dict:
    query = instructions.get("query", "")
 
    # Auto-enrich: include nutrients identified by medical worker
    persisted_nutrients = state.get("persisted_nutrients", [])
    enriched_query = _enrich_search_query(query, persisted_nutrients)
 
    raw = find_belife_products.invoke({"query": enriched_query})
    parsed = _safe_parse(raw)
    summary = _build_search_summary(parsed, enriched_query, persisted_nutrients)
 
    return {
        "parsed": parsed,
        "summary": summary,
        "label": f"product_worker(search:{enriched_query[:50]})",
    }
 
 
def _handle_details(instructions: dict) -> dict:
    product_name = instructions.get("product_name", "")
    raw = product_details.invoke({"product_name": product_name})
    parsed = _safe_parse(raw)
    summary = _build_details_summary(parsed, product_name)
 
    return {
        "parsed": parsed,
        "summary": summary,
        "label": f"product_worker(details:{product_name})",
    }
 
 
def _handle_catalog(instructions: dict) -> dict:
    category = instructions.get("category", "")
    raw = product_catalog.invoke({"category": category})
    parsed = _safe_parse(raw)
    summary = _build_catalog_summary(parsed, category)
 
    return {
        "parsed": parsed,
        "summary": summary,
        "label": f"product_worker(catalog:{category or 'all'})",
    }
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH QUERY ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════════
 
def _enrich_search_query(query: str, persisted_nutrients: list[str]) -> str:
    """Append known depleted nutrients to make search more precise."""
    if not persisted_nutrients:
        return query
 
    nutrient_terms = " ".join(persisted_nutrients[:4])
    if query:
        return f"{query} {nutrient_terms}".strip()
    return nutrient_terms
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# DETERMINISTIC SUMMARIES
# ═══════════════════════════════════════════════════════════════════════════════
 
def _build_search_summary(parsed, query: str, persisted_nutrients: list[str]) -> str:
    if isinstance(parsed, dict):
        if parsed.get("error"):
            return f"ERROR: {parsed.get('message', 'unknown')}"
        if parsed.get("message"):
            return f"No products found for '{query}': {parsed['message']}"
 
    if not isinstance(parsed, list) or not parsed:
        return f"No products found for '{query}'."
 
    nutrient_note = ""
    if persisted_nutrients:
        nutrient_note = f" (enriched with depleted nutrients: {', '.join(persisted_nutrients[:3])})"
 
    parts = [f"{len(parsed)} product(s) found for '{query}'{nutrient_note}:"]
    for item in parsed[:5]:
        if not isinstance(item, dict):
            continue
        prod = item.get("recommendation", item.get("recommended_product", item.get("product", item)))
        if isinstance(prod, dict):
            prod_inner = prod.get("recommended_product", prod)
            name = prod_inner.get("name", "unknown")
            cat = prod_inner.get("primary_category", "")
            benefit = prod_inner.get("target_benefit", "")
            parts.append(f"  - {name} [{cat}] — {benefit[:60]}")
        else:
            name = item.get("Name", item.get("name", "unknown"))
            parts.append(f"  - {name}")
 
    return "\n".join(parts)
 
 
def _build_details_summary(parsed, product_name: str) -> str:
    if isinstance(parsed, dict):
        if parsed.get("error"):
            return f"ERROR: {parsed.get('message', 'unknown')}"
        if parsed.get("message"):
            return f"Product '{product_name}' not found: {parsed['message']}"
 
    if not isinstance(parsed, list) or not parsed:
        return f"No details found for '{product_name}'."
 
    item = parsed[0]
    if not isinstance(item, dict):
        return f"Details received for '{product_name}' but could not parse."
 
    details = item.get("product_details", item)
    if not isinstance(details, dict):
        return f"Details received for '{product_name}' but unexpected structure."
 
    name = details.get("name", product_name)
    dosage = details.get("dosage_per_day", "N/A")
    timing = details.get("dosage_timing", "")
    precautions = details.get("precautions", "")
    ingredients = details.get("ingredients_summary", details.get("ingredient_names", ""))
 
    parts = [f"PRODUCT DETAILS: '{name}'"]
    parts.append(f"  Dosage: {dosage}")
    if timing:
        parts.append(f"  Timing: {timing[:80]}")
    if ingredients:
        ing_str = ingredients if isinstance(ingredients, str) else ", ".join(ingredients[:6])
        parts.append(f"  Ingredients: {ing_str[:100]}")
    if precautions:
        parts.append(f"  Precautions: {precautions[:100]}")
 
    return "\n".join(parts)
 
 
def _build_catalog_summary(parsed, category: str) -> str:
    if isinstance(parsed, dict) and parsed.get("error"):
        return f"ERROR: {parsed.get('message', 'unknown')}"
 
    if not isinstance(parsed, list) or not parsed:
        cat_str = f" in category '{category}'" if category else ""
        return f"No products found{cat_str}."
 
    cat_str = f" in '{category}'" if category else ""
    names = []
    for item in parsed[:10]:
        if isinstance(item, dict):
            prod = item.get("catalog_entry", item.get("product", item))
            if isinstance(prod, dict):
                names.append(prod.get("name", "unknown"))
            else:
                names.append(item.get("Name", item.get("name", "unknown")))
 
    return f"CATALOG{cat_str}: {len(parsed)} product(s) — {', '.join(names[:6])}."
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
 
def _safe_parse(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
 
 
def _extract_product_names(state: MultiAgentState, parsed) -> list:
    prods = list(state.get("persisted_products", []))
 
    if not isinstance(parsed, (list, dict)):
        return prods
 
    items = parsed if isinstance(parsed, list) else [parsed]
 
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in ["recommended_product", "product", "product_details", "catalog_entry"]:
            prod = item.get(key, {})
            if isinstance(prod, dict):
                name = prod.get("name", "")
                if name and name not in prods:
                    prods.append(name)
        name = item.get("Name", item.get("name", ""))
        if name and name not in prods:
            prods.append(name)
 
    return prods