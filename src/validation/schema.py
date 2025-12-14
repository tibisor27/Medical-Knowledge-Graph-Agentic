
def get_schema_for_prompt() -> str:
    """
    Returns the schema formatted for inclusion in LLM prompts.
    """
    schema_text = """
=== GRAPH SCHEMA ===

NODES:
------
1. Medicament
   Properties: name, us_brand_names[], canadian_brand_names[], synonyms[], pharmacologic_class[]
   Examples: "Acetaminophen", "Acebutolol", "Amiloride"

2. Nutrient  
   Properties: name, synonyms[], overview, biological_function_and_effect, dietary_sources, dosage_range, effects_of_depletion, side_effects_and_toxicity
   Examples: "Vitamin B12", "Zinc", "Coenzyme Q10", "Glutathione"

3. DepletionEvent
   Properties: depletion_event_id
   Note: This is a hyperedge connecting Medicament → Nutrient

4. Symptom
   Properties: name, layman_variants[], embedding (vector)
   Examples: "Fatigue", "Muscle weakness", "Depression"
   Vector Index: symptom_index

5. Study
   Properties: study_no, study_title, content, source

RELATIONSHIPS:
--------------
(Medicament)-[:CAUSES]->(DepletionEvent)
(DepletionEvent)-[:DEPLETES]->(Nutrient)
(DepletionEvent)-[:Has_Symptom]->(Symptom)
(DepletionEvent)-[:HAS_EVIDENCE]->(Study)

TRAVERSAL PATTERNS:
-------------------
• Medication → Nutrients:
  (m:Medicament)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n:Nutrient)

• Medication → Symptoms:
  (m:Medicament)-[:CAUSES]->(e:DepletionEvent)-[:Has_Symptom]->(s:Symptom)

• Symptom → Cause (reverse lookup):
  (s:Symptom)<-[:Has_Symptom]-(e:DepletionEvent)<-[:CAUSES]-(m:Medicament)
  Plus: (e)-[:DEPLETES]->(n:Nutrient)

• Full chain with evidence:
  (m:Medicament)-[:CAUSES]->(e:DepletionEvent)-[:DEPLETES]->(n:Nutrient)
  (e)-[:HAS_EVIDENCE]->(st:Study)
"""
    return schema_text.strip()
