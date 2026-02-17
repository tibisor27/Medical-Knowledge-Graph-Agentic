from pydantic import BaseModel, Field
 
# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY TYPES
# ═══════════════════════════════════════════════════════════════════════════════
 
class ResolvedEntity(BaseModel):
    """An entity that has been matched to a node in the knowledge graph."""
    original_text: str           # Original text from query ("Tylenol")
    resolved_name: str           # Canonical name in graph ("Acetaminophen")
    node_type: str               # Neo4j label: Medicament, Nutrient, Symptom
    match_score: float           # Full-text search score
    match_method: str            # How it was matched: "exact", "fulltext", "synonym", "brand_name"