"""
Cypher Generator Prompts - Optimized for Medical Knowledge Graph Agent.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# GRAPH SCHEMA
# ═══════════════════════════════════════════════════════════════════════════════

GRAPH_SCHEMA = """
NODE LABELS AND PROPERTIES:
1. Medicament - name, brand_names, synonyms, pharmacologic_class
2. Nutrient - name, overview, biological_function_effect, effects_of_depletion, dietary_sources, dosage_range, rda
3. DepletionEvent - mechanism, severity
4. Symptom - name, layman_variants
5. Study - study_title, source, content
6. PharmacologicClass - pharmacologic_class
7. FoodSource - dietary_source

RELATIONSHIPS:
(Medicament)-[:CAUSES]->(DepletionEvent)-[:DEPLETES]->(Nutrient)
(DepletionEvent)-[:Has_Symptom]->(Symptom)
(DepletionEvent)-[:HAS_EVIDENCE]->(Study)
(Nutrient)-[:Found_In]->(FoodSource)

FULL-TEXT INDEXES:
- "medicament_full_search" on Medicament(name, synonyms, brand_names)
- "nutrient_full_search" on Nutrient(name)
- "symptom_full_search" on Symptom(name, layman_variants)
"""

# ═══════════════════════════════════════════════════════════════════════════════
# CYPHER EXAMPLES BY INTENT
# ═══════════════════════════════════════════════════════════════════════════════

CYPHER_EXAMPLES = """
QUERY TEMPLATES BY INTENT (use the one matching the intent):

--- DRUG_DEPLETES_NUTRIENT ---
CALL db.index.fulltext.queryNodes("medicament_full_search", $med_name) YIELD node AS m, score
MATCH (m)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n:Nutrient)
RETURN m.name AS medication, n.name AS nutrient,n.biological_function_effect
AS biological_function_effect, n.overview AS nutrient_info
LIMIT 10
Params: {"med_name": "..."}

--- NUTRIENT_INFO ---
CALL db.index.fulltext.queryNodes("nutrient_full_search", $nutrient_name) YIELD node AS n, score
RETURN n.name AS nutrient, n.overview AS overview, n.biological_function_effect AS function, n.effects_of_depletion AS deficiency_effects, n.dietary_sources AS food_sources, n.dosage_range AS dosage
LIMIT 1
Params: {"nutrient_name": "..."}

--- NUTRIENT_DEPLETED_BY ---
CALL db.index.fulltext.queryNodes("nutrient_full_search", $nutrient_name) YIELD node AS n, score
MATCH (m:Medicament)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n)
RETURN n.name AS nutrient, collect(DISTINCT m.name) AS medications
LIMIT 10
Params: {"nutrient_name": "..."}

--- DEFICIENCY_SYMPTOMS ---
CALL db.index.fulltext.queryNodes("nutrient_full_search", $nutrient_name) YIELD node AS n, score
OPTIONAL MATCH (e:DepletionEvent)-[:DEPLETES]->(n)
OPTIONAL MATCH (e)-[:Has_Symptom]->(s:Symptom)
RETURN n.name AS nutrient, n.effects_of_depletion AS deficiency_description, collect(DISTINCT s.name) AS symptoms
LIMIT 1
Params: {"nutrient_name": "..."}

--- SYMPTOM_TO_DEFICIENCY ---
CALL db.index.fulltext.queryNodes("symptom_full_search", $symptom_name) YIELD node AS s, score
MATCH (e:DepletionEvent)-[:Has_Symptom]->(s)
MATCH (e)-[:DEPLETES]->(n:Nutrient)
OPTIONAL MATCH (m:Medicament)-[:CAUSES]->(e)
RETURN s.name AS symptom, n.name AS nutrient, collect(DISTINCT m.name) AS caused_by_medications
LIMIT 10
Params: {"symptom_name": "..."}

--- FOOD_SOURCES ---
CALL db.index.fulltext.queryNodes("nutrient_full_search", $nutrient_name) YIELD node AS n, score
OPTIONAL MATCH (n)-[:Found_In]->(f:FoodSource)
RETURN n.name AS nutrient, n.dietary_sources AS food_sources_text, collect(DISTINCT f.dietary_source) AS food_list
LIMIT 1
Params: {"nutrient_name": "..."}

--- DRUG_INFO ---
CALL db.index.fulltext.queryNodes("medicament_full_search", $med_name) YIELD node AS m, score
OPTIONAL MATCH (m)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n:Nutrient)
RETURN m.name AS medication, m.brand_names AS brands, m.pharmacologic_class AS drug_class, collect(DISTINCT n.name) AS depletes_nutrients
LIMIT 1
Params: {"med_name": "..."}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Cypher query generator for a Medical Knowledge Graph.

RULES:
1. Generate READ-ONLY queries (no CREATE, DELETE, MERGE)
2. ALWAYS include LIMIT clause
3. ALWAYS use parameters ($param_name) for entity values
4. Use the correct query template based on the INTENT
5. Return params dict with the query

SCHEMA:
{schema}

{examples}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# USER PROMPT TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

USER_PROMPT_TEMPLATE = """Generate a Cypher query.

INTENT: {intent}
RESOLVED ENTITIES: {resolved_entities}
USER QUESTION: {query}

Select the correct template for the INTENT and fill in the parameters.
IMPORTANT: 
- For NUTRIENT_INFO intent, use the nutrient_full_search index with $nutrient_name
- For DRUG_DEPLETES_NUTRIENT intent, use the medicament_full_search index with $med_name
- Always include LIMIT
"""
