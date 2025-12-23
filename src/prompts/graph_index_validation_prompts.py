
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




MEDICATION_QUERY = """
// 1. Găsim medicamentul
CALL db.index.fulltext.queryNodes('medicament_full_search', "lamivudine") 
YIELD node AS drug, score
WHERE score > 0.3
WITH drug, score
ORDER BY score DESC
LIMIT 1

// 2. Găsim medicamente similare (Agregare separată)
OPTIONAL MATCH (drug)-[:Belongs_To]->(pc:PharmacologicClass)
OPTIONAL MATCH (pc)<-[:Belongs_To]-(similar:Medicament)
WHERE similar <> drug
WITH drug, score, collect(DISTINCT similar.name)[0..10] as similar_drugs

// 3. Extindem către nutrienți
OPTIONAL MATCH (drug)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)

// 4. Construim obiectul nutrientului (folosind Pattern Comprehension pentru a evita duplicarea rândurilor)
WITH drug, score, similar_drugs, nut, de,
    CASE WHEN nut IS NOT NULL THEN {
        nutrient_name: nut.name,
        effects_of_depletion: nut.effects_of_depletion,
        
        // Listele interne (nu creează rânduri noi, ci liste în interiorul rândului)
        symptoms: [(de)-[:Has_Symptom]->(s:Symptom) | s.name],
        studies: [(de)-[:HAS_EVIDENCE]->(st:Study) | {title: st.study_title, source: st.source}],
        food_sources: [(nut)-[:Found_In]->(f:FoodSource) | f.dietary_source],
        side_effects: [(nut)-[:Has_Side_Effect]->(se:SideEffect) | se.side_effect]
    } ELSE null END as nutrient_data_raw

// 5. AGREGAREA FINALĂ (Aici rezolvăm eroarea ta 42I18)
// Colectăm nutrienții într-o listă, grupând implicit după drug, score și similar_drugs
WITH drug, score, similar_drugs, collect(nutrient_data_raw) as all_nutrients_list

// Filtrăm null-urile (cazul în care medicamentul nu are depleții cunoscute)
WITH drug, score, similar_drugs, [x IN all_nutrients_list WHERE x IS NOT NULL] as depleted_nutrients

// 6. Returnăm obiectul final curat
RETURN {
    entity_type: 'DRUG',
    match_score: score,
    drug: {
        name: drug.name,
        brand_names: drug.brand_names,
        synonyms: drug.synonyms,
        pharmacologic_class: drug.pharmacologic_class
    },
    similar_drugs: similar_drugs,
    depleted_nutrients: depleted_nutrients
} AS context
"""


