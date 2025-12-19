
# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH VALIDATION QUERIES
# ═══════════════════════════════════════════════════════════════════════════════

MEDICATION_FULLTEXT_QUERY = """
CALL db.index.fulltext.queryNodes("medicament_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN node.name AS name, score, "Medicament" AS node_type
ORDER BY score DESC
LIMIT 3
"""

NUTRIENT_FULLTEXT_QUERY = """
CALL db.index.fulltext.queryNodes("nutrient_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN node.name AS name, score, "Nutrient" AS node_type
ORDER BY score DESC
LIMIT 3
"""

PHARMACOLOGIC_CLASS_FULLTEXT_QUERY = """
CALL db.index.fulltext.queryNodes("pharmacologic_class_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN p.pharmacologic_class AS name, score, "PharmacologicClass" AS node_type
ORDER BY score DESC
LIMIT 3
"""

PHARMACOLOGIC_CLASS_DIRECT_QUERY = """
MATCH (p:PharmacologicClass)
WHERE toLower(p.pharmacologic_class) CONTAINS toLower($search_term)
RETURN p.pharmacologic_class AS name, 1.0 AS score, "PharmacologicClass" AS node_type
LIMIT 3
"""

# Fallback: Direct match queries (if fulltext index doesn't exist)
MEDICATION_DIRECT_QUERY = """
MATCH (m:Medicament)
WHERE toLower(m.name) CONTAINS toLower($search_term)
   OR ANY(brand IN m.brand_names WHERE toLower(brand) CONTAINS toLower($search_term))
   OR ANY(syn IN m.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
RETURN m.name AS name, 1.0 AS score, "Medicament" AS node_type
LIMIT 3
"""

NUTRIENT_DIRECT_QUERY = """
MATCH (n:Nutrient)
WHERE toLower(n.name) CONTAINS toLower($search_term)
   OR ANY(syn IN n.synonyms WHERE toLower(syn) CONTAINS toLower($search_term))
RETURN n.name AS name, 1.0 AS score, "Nutrient" AS node_type
LIMIT 3
"""

SYMPTOM_QUERY = """
CALL db.index.fulltext.queryNodes("symptom_full_search", $search_term)
YIELD node, score
WHERE score > 0.5
RETURN node.name AS name, score, "Symptom" AS node_type
ORDER BY score DESC
LIMIT 3
"""
