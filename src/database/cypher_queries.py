class CypherQueries:
    """
    Predefined Cypher queries for different retrieval types.
    
    IMPORTANT (PRODUCTION):
    =======================
    Aceste query-uri primesc RESOLVED_NAME de la entity_extractor.
    Adică numele EXACT din Neo4j, nu ce a spus user-ul.
    
    Exemplu:
        entity_extractor: "Tylenol" → "Acetaminophen"
        query primește: $medications = ["Acetaminophen"]
        
    De aceea folosim DIRECT MATCH, nu full-text search (evităm redundanța).
    """
    
    MEDICATION_LOOKUP = """
    // ═══════════════════════════════════════════════════════════════════════════
    // MEDICATION_LOOKUP - Primește resolved_name (nume canonic din Neo4j)
    // ═══════════════════════════════════════════════════════════════════════════
    UNWIND $medications AS med_name
    
    // DIRECT MATCH - med_name e deja resolved_name de la entity_extractor
    MATCH (med:Medicament {name: med_name})

    // 2. Găsim relațiile: Medicament → DepletionEvent → Nutrient
    OPTIONAL MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
    
    // 3. Pentru fiecare nutrient, colectăm simptomele asociate
    OPTIONAL MATCH (de)-[:Has_Symptom]->(sym:Symptom)
    
    // 4. Grupăm simptomele per nutrient
    WITH med, nut, de, collect(DISTINCT sym.name) AS symptoms_for_nutrient
    
    // 5. Construim obiectul per nutrient cu simptomele sale
    WITH med,
        CASE WHEN nut IS NOT NULL THEN {
            nutrient: nut.name,
            symptoms: symptoms_for_nutrient[0..5]
        } ELSE null END AS nutrient_data
    
    // 6. Agregăm toți nutrienții într-o listă
    WITH med, collect(nutrient_data) AS all_nutrients
    
    // 7. Filtrăm null-urile
    WITH med,
        [n IN all_nutrients WHERE n IS NOT NULL] AS depletions,
        reduce(acc = [], n IN all_nutrients | 
            CASE WHEN n IS NOT NULL THEN acc + n.symptoms ELSE acc END
        ) AS all_symptoms_flat
    
    // 8. Returnăm structura finală
    RETURN {
        medication: {
            name: med.name,
            synonyms: med.synonyms
        },
        depletions: depletions,
        symptoms_to_ask: all_symptoms_flat[0..5]
    } AS context
    """
    
    SYMPTOM_INVESTIGATION = """
    // ═══════════════════════════════════════════════════════════════════════════
    // SYMPTOM_INVESTIGATION - Primește resolved_name (nume canonic din Neo4j)
    // ═══════════════════════════════════════════════════════════════════════════
    UNWIND $symptoms AS symptom_name
    
    // DIRECT MATCH - symptom_name e deja resolved de entity_extractor
    MATCH (sym:Symptom {name: symptom_name})

    // 2. Găsim relațiile complete
    MATCH (de:DepletionEvent)-[:Has_Symptom]->(sym)
    MATCH (de)-[:DEPLETES]->(nut:Nutrient)
    OPTIONAL MATCH (med:Medicament)-[:CAUSES]->(de)

    // 3. AGREGARE: Grupăm după MEDICAMENT
    WITH sym, med, collect(DISTINCT nut.name) AS nutrients_affected_by_this_drug

    // 4. Separăm logica: Medicamente vs. Doar Nutrienți
    WITH sym,
        CASE WHEN med IS NOT NULL THEN {
            drug_name: med.name,
            depletes_nutrients: nutrients_affected_by_this_drug 
        }
        ELSE null END AS drug_group,
        
        CASE WHEN med IS NULL THEN nutrients_affected_by_this_drug ELSE null END AS orphan_nutrients_list

    // 5. Construcția finală
    WITH sym, 
        collect(drug_group) AS all_drug_groups,
        collect(orphan_nutrients_list) AS all_orphan_lists

    WITH sym, 
        [x IN all_drug_groups WHERE x IS NOT NULL] AS clean_drug_groups,
        reduce(acc=[], list IN [y IN all_orphan_lists WHERE y IS NOT NULL] | acc + list) AS clean_orphan_nutrients

    RETURN {
        symptom: sym.name,
        top_suspects: clean_drug_groups[0..10],
        other_deficiencies: clean_orphan_nutrients[0..5],
        drugs_to_ask_about: [item IN clean_drug_groups | item.drug_name][0..5]
    } AS context
    """
    
    NUTRIENT_EDUCATION = """
    // ═══════════════════════════════════════════════════════════════════════════
    // NUTRIENT_EDUCATION - Primește resolved_name (nume canonic din Neo4j)
    // ═══════════════════════════════════════════════════════════════════════════
    UNWIND $nutrients AS nut_name
    
    // DIRECT MATCH - nut_name e deja resolved de entity_extractor
    MATCH (nut:Nutrient {name: nut_name})
            
    // 2. Colectăm sursele de hrană
    OPTIONAL MATCH (nut)-[:Found_In]->(food:FoodSource)
    WITH nut, collect(DISTINCT food.dietary_source) AS food_sources

    // 3. Colectăm Side Effects
    OPTIONAL MATCH (nut)-[:Has_Side_Effect]->(se:SideEffect)
    WITH nut, food_sources, collect(DISTINCT se.side_effect) AS side_effects_list
            
    // 4. Colectăm simptomele deficienței
    OPTIONAL MATCH (nut)<-[:DEPLETES]-(de:DepletionEvent)-[:Has_Symptom]->(sym:Symptom)
    WITH nut, food_sources, side_effects_list, collect(DISTINCT sym.name) AS symptoms_list
            
    // 5. Returnăm
    RETURN {
        education: {
            name: nut.name,
            overview: nut.overview,
            biological_function: nut.biological_function_effect,
            possible_side_effects: side_effects_list[0..5] 
        },
        what_user_needs: {
            forms: nut.forms,
            rda: nut.rda
        },
        deficiency_symptoms: symptoms_list[0..10],
        dietary_sources: food_sources[0..10]
    } AS context
    """
    
    CONNECTION_VALIDATION = """
    // ═══════════════════════════════════════════════════════════════════════════
    // CONNECTION_VALIDATION - Primește resolved_name pentru medication și symptom
    // ═══════════════════════════════════════════════════════════════════════════
    UNWIND $medications AS med_name
    
    // DIRECT MATCH pentru medicament (deja resolved)
    MATCH (med:Medicament {name: med_name})
    
    // 2. APOI verificăm FIECARE simptom din input
    UNWIND $symptoms AS sym_name
    
    // 3. Căutăm conexiunea - folosim DIRECT MATCH sau fuzzy pentru symptom
    // (symptom-urile pot fi mai fuzzy, deci păstrăm flexibilitate)
    MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
    MATCH (de)-[:Has_Symptom]->(real_symptom:Symptom)
    WHERE real_symptom.name = sym_name 
       OR toLower(real_symptom.name) CONTAINS toLower(sym_name) 
       OR toLower(sym_name) CONTAINS toLower(real_symptom.name)
    
    // 4. Colectăm toate match-urile pentru acest simptom
    WITH med, sym_name, 
        collect(DISTINCT {
            nutrient: nut.name,
            graph_symptom: real_symptom.name
        }) AS matches_for_symptom
    WHERE size(matches_for_symptom) > 0
    
    // 5. Agregăm rezultatele pentru TOATE simptomele
    WITH med, collect({
        user_symptom: sym_name,
        matched_nutrients: [m IN matches_for_symptom | m.nutrient],
        matched_graph_symptoms: [m IN matches_for_symptom | m.graph_symptom]
    }) AS all_symptom_matches
    
    // 6. Extragem lista unică de nutrienți
    WITH med, all_symptom_matches,
        reduce(acc = [], sm IN all_symptom_matches | 
            acc + [n IN sm.matched_nutrients WHERE NOT n IN acc]
        ) AS unique_nutrients
    
    RETURN {
        connection_found: true,
        medication: med.name,
        validated_symptoms: all_symptom_matches,
        nutrients_to_recommend: unique_nutrients
    } AS validation
    """

    # ═══════════════════════════════════════════════════════════════════════════════
    # PRODUCT RECOMMENDATION - Găsește produse BeLife care conțin nutrientul specificat
    # ═══════════════════════════════════════════════════════════════════════════════
    
    PRODUCT_RECOMMENDATION = """
    // 1. Primim lista de nutrienți necesari
    WITH $nutrients AS needed_nutrients
    
    // 2. Găsim produsele care conțin CEL PUȚIN UN nutrient din listă
    MATCH (product:BeLifeProduct)-[r:CONTAINS]->(nut:Nutrient)
    WHERE nut.name IN needed_nutrients
    
    // 3. Grupăm per produs - colectăm nutrienții matched cu toate detaliile
    WITH product, needed_nutrients,
         collect(DISTINCT {
             name: nut.name, 
             amount: r.amount, 
             unit: r.unit
         }) AS matched_nutrients
    
    // 4. Calculăm scorul de coverage
    WITH product, needed_nutrients, matched_nutrients,
         size(matched_nutrients) AS nutrients_covered,
         size(needed_nutrients) AS nutrients_needed
    
    // 5. Colectăm TOȚI nutrienții din produs (pentru context complet)
    OPTIONAL MATCH (product)-[all_r:CONTAINS]->(all_nut:Nutrient)
    WITH product, needed_nutrients, matched_nutrients, nutrients_covered, nutrients_needed,
         collect(DISTINCT {
             name: all_nut.name,
             amount: all_r.amount,
             unit: all_r.unit
         }) AS all_product_nutrients
    
    // 6. Ordonăm după câți nutrienți acoperă (cel mai bun primul)
    ORDER BY nutrients_covered DESC
    
    // 7. Returnăm rezultatul cu TOATE informațiile
    RETURN {
        recommended_product: {
            name: product.name,
            primary_category: product.primary_category,
            target_benefit: product.target_benefit,
            scientific_description: product.scientific_description,
            dosage_per_day: product.dosage_per_day,
            dosage_timing: product.dosage_timing,
            precautions: product.precautions
        },
        coverage: {
            nutrients_covered: nutrients_covered,
            nutrients_needed: nutrients_needed,
            coverage_percent: toInteger(toFloat(nutrients_covered) / nutrients_needed * 100)
        },
        matched_nutrients: matched_nutrients,
        other_nutrients_in_product: [n IN all_product_nutrients WHERE NOT n.name IN needed_nutrients][0..5]
    } AS recommendation
    
    LIMIT 1
    """

class CypherEntityValidationQueries:
    """Predefined Cypher queries for entity validation."""
    
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
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SYMPTOM EMBEDDINGS VECTOR SEARCH
    # ═══════════════════════════════════════════════════════════════════════════════
    # Uses Neo4j vector index to find semantically similar symptoms
    # Requires: Vector index created on Symptom.embedding
    # Index name: "symptom_embeddings_index" (create with: CREATE VECTOR INDEX ...)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    SYMPTOM_EMBEDDINGS_QUERY = """
    CALL db.index.vector.queryNodes(
        'symptom_embeddings_index',
        $top_k,
        $embedding_vector
    )
    YIELD node, score
    WHERE score > $similarity_threshold
    RETURN node.name AS name, 
           score AS similarity, 
           "Symptom" AS node_type
    ORDER BY score DESC
    LIMIT 1
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


