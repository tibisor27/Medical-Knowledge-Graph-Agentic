from typing import List

from src.agent.state import ResolvedEntity

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def format_resolved_entities(entities: List[ResolvedEntity]) -> str:
    """Format resolved entities for the prompt."""
    if not entities:
        return "No entities were resolved from the graph."
    
    lines = []
    for entity in entities:
        lines.append(
            f"- Name: '{entity.resolved_name}' (Type: {entity.node_type})")
    return "\n".join(lines)