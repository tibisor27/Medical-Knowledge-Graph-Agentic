"""
Medical Agent Tools — ReAct Agent Tool Registry.

All tools are registered here and exposed via get_tools().
"""

from src.agent.tools.medication_tool import medication_lookup
from src.agent.tools.symptom_investigation_tool import symptom_investigation
from src.agent.tools.connection_validation_tool import connection_validation
from src.agent.tools.nutrient_tool import nutrient_lookup
from src.agent.tools.find_belife_products_tool import find_belife_products
from src.agent.tools.product_details_tool import product_details
from src.agent.tools.product_catalog_tool import product_catalog


def get_tools():
    """Return all tools for the ReAct agent."""
    return [
        # Medical Knowledge (graph relationships)
        medication_lookup,
        symptom_investigation,
        connection_validation,
        nutrient_lookup,
        # BeLife Products (embeddings + keyword search)
        find_belife_products,
        product_details,
        product_catalog,
    ]

__all__ = [
    "get_tools",
    "medication_lookup",
    "symptom_investigation",
    "connection_validation",
    "nutrient_lookup",
    "find_belife_products",
    "product_details",
    "product_catalog",
]
