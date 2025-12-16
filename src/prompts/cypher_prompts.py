GRAPH_SCHEMA = """
=== KNOWLEDGE GRAPH SCHEMA ===

NODE LABELS AND PROPERTIES:

1. Medicament (Medication)
   - name: String (unique, e.g., "Acetaminophen")
   - brand_names: List<String> (e.g., ["Tylenol", "Panadol"])
   - synonyms: List<String> (e.g., ["Paracetamol", "APAP"])
   - pharmacologic_class: List<String> (e.g., ["Analgesic"])

2. Nutrient
   - name: String (unique, e.g., "Glutathione")
   - overview: String (general description)
   - biological_function_effect: String (what it does in the body)
   - effects_of_depletion: String (symptoms when deficient)
   - dosage_range: String (recommended dosage)
   - dietary_sources: String (food sources)
   - forms: String (supplement forms)
   - rda: String (recommended daily allowance)

3. DepletionEvent
   - depletion_event_id: String (e.g., "DE_Acetaminophen_Glutathione")

4. Symptom
   - name: String (canonical medical term, e.g., "Fatigue")
   - layman_variants: List<String> (e.g., ["oboseală", "tired", "exhausted"])
   - embedding: List<Float> (vector for semantic search)

5. Study
   - study_no: String (study number)
   - study_title: String (title of the study)
   - content: String (study summary)
   - source: String (citation)

6. PharmacologicClass
   - pharmacologic_class: String

7. FoodSource
   - dietary_source: String

8. SideEffect
   - side_effect: String

RELATIONSHIPS:

(Medicament)-[:CAUSES]->(DepletionEvent)
(DepletionEvent)-[:DEPLETES]->(Nutrient)
(DepletionEvent)-[:Has_Symptom]->(Symptom)
(DepletionEvent)-[:HAS_EVIDENCE]->(Study)
(Medicament)-[:Belongs_To]->(PharmacologicClass)
(Nutrient)-[:Found_In]->(FoodSource)
(Nutrient)-[:Has_Side_Effect]->(SideEffect)

INDEXES:
- Full-text index "medicament_full_search" on Medicament(name, synonyms, brand_names)
- Full-text index "nutrient_full_search" on Nutrient(name, synonyms)
- Full-text index "symptom_full_search" on Symptom(name, layman_variants)
"""


# ═══════════════════════════════════════════════════════════════════════════════
# CYPHER GENERATOR PROMPT
# ═══════════════════════════════════════════════════════════════════════════════
CYPHER_EXAMPLES = """
=== QUERY PATTERNS BY INTENT ===

DRUG_DEPLETES_NUTRIENT (What nutrients does medication X deplete?):

CALL db.index.fulltext.queryNodes("medicament_full_search", $med_name) YIELD node AS m, score
MATCH (m)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n:Nutrient)
OPTIONAL MATCH (e)-[:Has_Symptom]->(s:Symptom)
OPTIONAL MATCH (e)-[:HAS_EVIDENCE]->(st:Study)
RETURN m.name AS medication,
       n.name AS nutrient,
       n.overview AS nutrient_overview,
       n.effects_of_depletion AS deficiency_effects,
       n.dietary_sources AS food_sources,
       collect(DISTINCT s.name)[0..5] AS deficiency_symptoms,
       collect(DISTINCT st.study_title)[0..3] AS supporting_studies
LIMIT 10


NUTRIENT_DEPLETED_BY (What medications deplete nutrient X?):

CALL db.index.fulltext.queryNodes("nutrient_full_search", $nutrient_name) YIELD node AS n, score
MATCH (m:Medicament)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n)
OPTIONAL MATCH (e)-[:HAS_EVIDENCE]->(st:Study)
RETURN n.name AS nutrient,
       collect(DISTINCT m.name) AS medications_that_deplete,
       n.effects_of_depletion AS why_it_matters,
       collect(DISTINCT st.study_title)[0..5] AS studies
LIMIT 1


NUTRIENT_INFO (General info about a nutrient):

CALL db.index.fulltext.queryNodes("nutrient_full_search", $nutrient_name) YIELD node AS n, score
OPTIONAL MATCH (n)-[:Found_In]->(fs:FoodSource)
RETURN n.name AS name,
       n.overview AS overview,
       n.biological_function_effect AS functions,
       n.effects_of_depletion AS deficiency_symptoms,
       n.dietary_sources AS food_sources,
       n.dosage_range AS dosage,
       n.rda AS rda
LIMIT 1


DRUG_INFO (General info about a medication):

CALL db.index.fulltext.queryNodes("medicament_full_search", $med_name) YIELD node AS m, score
OPTIONAL MATCH (m)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n:Nutrient)
RETURN m.name AS name,
       m.brand_names AS brand_names,
       m.synonyms AS synonyms,
       m.pharmacologic_class AS drug_class,
       collect(DISTINCT n.name) AS nutrients_depleted
LIMIT 1


DEFICIENCY_SYMPTOMS (Symptoms of nutrient X deficiency):

CALL db.index.fulltext.queryNodes("nutrient_full_search", $nutrient_name) YIELD node AS n, score
OPTIONAL MATCH (e:DepletionEvent)-[:DEPLETES]->(n)
OPTIONAL MATCH (e)-[:Has_Symptom]->(s:Symptom)
RETURN n.name AS nutrient,
       n.effects_of_depletion AS deficiency_description,
       collect(DISTINCT {{name: s.name, variants: s.layman_variants}}) AS symptoms
LIMIT 1


SYMPTOM_TO_DEFICIENCY (What deficiency causes symptom X?):

CALL db.index.fulltext.queryNodes("symptom_full_search", $symptom_name) YIELD node AS s, score
MATCH (e:DepletionEvent)-[:Has_Symptom]->(s)
MATCH (e)-[:DEPLETES]->(n:Nutrient)
OPTIONAL MATCH (m:Medicament)-[:CAUSES]->(e)
RETURN s.name AS symptom,
       n.name AS possible_deficiency,
       n.dietary_sources AS food_solution,
       collect(DISTINCT m.name)[0..5] AS possible_drug_causes
LIMIT 10
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
SYSTEM_INSTRUCTIONS = """
You are an expert Neo4j Cypher developer assisting with a Medical Knowledge Graph.

Your goal is to translate user questions into precise, read-only Cypher queries based on the provided schema.

### SCHEMA CONTEXT
{schema}

### GUIDELINES
1. **Index Usage:** ALWAYS prioritize `CALL db.index.fulltext.queryNodes` for searching names (Medicament, Nutrient, Symptom).
2. **Schema Traversal:** Correctly navigate the Hypernode structure: (Medicament)-[:CAUSES]->(DepletionEvent)-[:DEPLETES]->(Nutrient).
3. **Safety:** Generate READ-ONLY queries only. No CREATE/MERGE/DELETE.
4. **Formatting:** Return raw Cypher code without markdown blocks.
5. **Robustness:** Always use `toLower()` for string comparisons if not using indexes. Use `OPTIONAL MATCH` for auxiliary info (studies, food sources) to avoid data loss.

### EXPECTED BEHAVIOR
- Analyze the user's intent.
- Map entities (drugs, symptoms) to the correct Node Labels.
- Construct a query that answers the specific question efficiently.

{examples}
"""