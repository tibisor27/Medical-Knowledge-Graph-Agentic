"""
ProductWorker — Deterministic Neo4j data retrieval for products.

Handles:
  - search: Search products by query/need
  - details: Get full details (prospect) for a specific product
  - catalog: Browse products by category
"""

import json
import logging

from src.multi_agent.state import MultiAgentState

# Import tools
from src.agent.tools.product_tool import (
    product_search_knowledge_graph,
    product_details_knowledge_graph,
    product_catalog_knowledge_graph
)

logger = logging.getLogger(__name__)


def run_product_worker(state: MultiAgentState) -> dict:
    task_type = state.get("worker_task_type", "")
    instructions = state.get("worker_instructions", {})

    logger.info(f"ProductWorker: task={task_type}, instructions={instructions}")

    try:
        if task_type == "search":
            query = instructions.get("query", "")
            raw_result = product_search_knowledge_graph.invoke({"query": query})
            worker_label = f"product_worker(search:{query})"

        elif task_type == "details":
            product_name = instructions.get("product_name", "")
            raw_result = product_details_knowledge_graph.invoke({"product_name": product_name})
            worker_label = f"product_worker(details:{product_name})"

        elif task_type == "catalog":
            category = instructions.get("category", "")
            raw_result = product_catalog_knowledge_graph.invoke({"category": category})
            worker_label = f"product_worker(catalog:{category})"

        else:
            logger.warning(f"ProductWorker: Unknown task_type '{task_type}'")
            raw_result = json.dumps({
                "error": True,
                "message": f"Unknown product task type: {task_type}",
            })
            worker_label = f"product_worker(unknown:{task_type})"

    except Exception as e:
        logger.error(f"ProductWorker failed: {e}", exc_info=True)
        raw_result = json.dumps({
            "error": True,
            "message": f"Product worker error: {str(e)}",
        })
        worker_label = "product_worker(error)"

    parsed = _safe_parse(raw_result)
    prods = _extract_product_names(state, parsed)

    logger.info(f"ProductWorker: Done. Result length={len(raw_result)} chars")

    return {
        "worker_results": [{
            "source": "product_worker",
            "task_type": task_type,
            "data": parsed,
        }],
        "persisted_products": prods,
        "execution_path": [worker_label],
    }


def _safe_parse(raw: str):
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def _extract_product_names(state: MultiAgentState, parsed) -> list:
    """Extract product names for context state."""
    prods = list(state.get("persisted_products", []))
    
    if not isinstance(parsed, (list, dict)):
        return prods

    items = parsed if isinstance(parsed, list) else [parsed]
    
    for item in items:
        if isinstance(item, dict):
            name = item.get("Name", "")
            if name and name not in prods:
                prods.append(name)
    
    return prods
