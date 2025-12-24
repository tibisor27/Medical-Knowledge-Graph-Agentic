from typing import Dict, Any, List
from src.agent.state import MedicalAgentState, add_to_execution_path, format_conversation_history_for_analysis
from src.database.neo4j_client import get_neo4j_client
from src.agent.state import RetrievalType
# ═══════════════════════════════════════════════════════════════════════════════
# MAIN NODE FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def graph_executor_node(state: MedicalAgentState) -> Dict[str, Any]:

    print(f"\n********* NODE 5: GRAPH EXECUTOR *********\n")
    conv_history = format_conversation_history_for_analysis(state.get("conversation_history"))
    print(f"----> CONVERSATION HISTORY:\n{conv_history}")
    r_type = state.get("conversation_analysis").retrieval_type
    print(f"----> RETRIEVAL TYPE: {r_type}")
    # cypher = state.get("generated_cypher", "")
    # is_valid = state.get("cypher_is_valid", False)
    # params = state.get("cypher_params", {})
    accumulated_medications = [entity.resolved_name for entity in state.get("resolved_entities") if entity.node_type == "Medicament"]
    accumulated_symptoms = [entity.resolved_name for entity in state.get("resolved_entities") if entity.node_type == "Symptom"]
    accumulated_nutrients = [entity.resolved_name for entity in state.get("resolved_entities") if entity.node_type == "Nutrient"]
    
    # Don't execute if Cypher is invalid or empty
    # if not cypher or not is_valid:
    #     return {
    #         **state,
    #         "graph_results": [],
    #         "has_results": False,
    #         "execution_error": "No valid Cypher query to execute",
    #         "execution_path": add_to_execution_path(state, "graph_executor")
    #     }
    query = ""
    params = {}
    
    # --- BLOC FIXAT PENTRU NEO4J AGGREGATION ---
    if r_type == RetrievalType.MEDICATION_LOOKUP:
        query = """
        UNWIND $medications AS med_name
        // 1. Găsim medicamentul
        CALL db.index.fulltext.queryNodes("medicament_full_search", med_name) 
        YIELD node AS med, score
        WHERE score > 0.5
        WITH med, score ORDER BY score DESC LIMIT 1

        // 2. Găsim relațiile (MODIFICARE AICI: OPTIONAL MATCH)
        // Daca nu gaseste relatii, 'nut', 'de' si 'sym' vor fi NULL, dar 'med' ramane!
        OPTIONAL MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
        OPTIONAL MATCH (de)-[:Has_Symptom]->(sym:Symptom)

        // 3. Pregătim datele (Gestionam NULL-urile)
        WITH med, 
            nut,
            sym,
            // Verificam daca am gasit ceva, altfel returnam null in obiect
            CASE WHEN nut IS NOT NULL THEN {
                nutrient: nut.name
            } ELSE null END AS dep_data

        // 4. Agregăm
        WITH med, 
            // collect ignora automat null-urile, deci daca nu are depletii, lista va fi goala []
            collect(DISTINCT dep_data) AS depletions_list,
            collect(DISTINCT sym.name) AS symptoms_list

        // 5. Returnăm
        RETURN {
            medication: {
                name: med.name,
                class: med.pharmacologic_class
            },
            depletions: depletions_list,
            symptoms_to_ask: symptoms_list[0..5]
        } AS context
        """
        params = {"medications": accumulated_medications}
        
    elif r_type == RetrievalType.SYMPTOM_INVESTIGATION:
        query = """
        UNWIND $symptoms AS symptom_name
        
        // 1. Căutare Simptom
        CALL db.index.fulltext.queryNodes('symptom_full_search', symptom_name) 
        YIELD node AS sym, score
        WHERE score > 0.2
        WITH sym ORDER BY score DESC LIMIT 1

        // 2. Găsim relațiile complete
        MATCH (de:DepletionEvent)-[:Has_Symptom]->(sym)
        MATCH (de)-[:DEPLETES]->(nut:Nutrient)
        OPTIONAL MATCH (med:Medicament)-[:CAUSES]->(de)

        // 3. AGREGARE CHEIE: Grupăm după MEDICAMENT
        // Aici se întâmplă magia: pentru fiecare medicament unic, colectăm toți nutrienții pe care îi afectează
        // legat de acest simptom.
        WITH sym, med, collect(DISTINCT nut.name) AS nutrients_affected_by_this_drug

        // 4. Separăm logica: Medicamente vs. Doar Nutrienți (fără medicament cunoscut)
        WITH sym,
            // Cazul A: Avem un medicament identificat
            CASE WHEN med IS NOT NULL THEN
            {
                drug_name: med.name,
                // Aici vei vedea lista completă de nutrienți per medicament
                depletes_nutrients: nutrients_affected_by_this_drug 
            }
            ELSE null END AS drug_group,
            
            // Cazul B: Nu avem medicament, dar știm că lipsa nutrientului cauzează simptomul
            CASE WHEN med IS NULL THEN nutrients_affected_by_this_drug ELSE null END AS orphan_nutrients_list

        // 5. Construcția finală a obiectului
        WITH sym, 
            collect(drug_group) AS all_drug_groups,
            collect(orphan_nutrients_list) AS all_orphan_lists

        // Curățăm valorile null din liste (filtrare standard Cypher)
        WITH sym, 
            [x IN all_drug_groups WHERE x IS NOT NULL] AS clean_drug_groups,
            reduce(acc=[], list IN [y IN all_orphan_lists WHERE y IS NOT NULL] | acc + list) AS clean_orphan_nutrients

        RETURN {
            symptom: sym.name,
            
            // LISTA PRINCIPALĂ: Medicament + Lista Nutrienților săi (fără duplicate de medicamente)
            top_suspects: clean_drug_groups[0..10],
            
            // LISTA SECUNDARĂ: Nutrienți care dau simptomul, dar nu știm ce medicament îi fură
            other_deficiencies: clean_orphan_nutrients[0..5],
            
            // LISTA SIMPLĂ: Doar numele medicamentelor pentru ca AI-ul să întrebe rapid
            drugs_to_ask_about: [item IN clean_drug_groups | item.drug_name][0..5]
        } AS context
        """
        params = {"symptoms": accumulated_symptoms}
    elif r_type == RetrievalType.NUTRIENT_EDUCATION:
        query = """
        UNWIND $nutrients AS nut_name
        CALL db.index.fulltext.queryNodes("nutrient_full_search", nut_name) 
        YIELD node AS nut, score
        WHERE score > 0.5
        WITH nut ORDER BY score DESC LIMIT 1
                
        // 2. Colectăm sursele de hrană
        OPTIONAL MATCH (nut)-[:Found_In]->(food:FoodSource)
        // IMPORTANT: Colectăm lista și o denumim
        WITH nut, collect(DISTINCT food.dietary_source) AS food_sources

        // 3. Colectăm Side Effects (Efecte Adverse)
        OPTIONAL MATCH (nut)-[:Has_Side_Effect]->(se:SideEffect)
        // IMPORTANT: Trebuie să păstrăm 'nut' ȘI 'food_sources' în acest WITH
        WITH nut, food_sources, collect(DISTINCT se.side_effect) AS side_effects_list
                
        // 4. Colectăm simptomele deficienței
        // Relația: Nutrient este epuizat de un Event, care are Simptome
        OPTIONAL MATCH (nut)<-[:DEPLETES]-(de:DepletionEvent)-[:Has_Symptom]->(sym:Symptom)
        // Din nou, cărăm toate variabilele anterioare după noi
        WITH nut, food_sources, side_effects_list, collect(DISTINCT sym.name) AS symptoms_list
                
        // 5. Agregare Finală
        RETURN {
            education: {
                name: nut.name,
                overview: nut.overview,
                biological_function: nut.biological_function_effect,
                // Adăugăm lista colectată la pasul 3
                possible_side_effects: side_effects_list[0..5] 
            },
            
            what_user_needs: {
                forms: nut.forms,
                rda: nut.rda
            },
            
            // Adăugăm lista colectată la pasul 4
            deficiency_symptoms: symptoms_list[0..10],
            
            dietary_sources: food_sources[0..10]
                        
        } AS context
        """
        params = {"nutrients": accumulated_nutrients}
    elif r_type == RetrievalType.CONNECTION_VALIDATION:
        # Extragem listele din dicționarul targets
        med_list = accumulated_medications
        sym_list = accumulated_symptoms
        
        query = """
        UNWIND $medications AS med_input
        UNWIND $symptoms AS sym_input
        
        /// 1. Căutăm Medicamentul folosind INDEXUL
        CALL db.index.fulltext.queryNodes('medicament_full_search', med_input) 
        YIELD node AS med, score AS med_score
        WHERE med_score > 0.2
        WITH med, sym_input, med_score ORDER BY med_score DESC LIMIT 1
        
        // 2. Căutăm Simptomul folosind INDEXUL
        CALL db.index.fulltext.queryNodes('symptom_full_search', sym_input) 
        YIELD node AS target_sym, score AS sym_score
        WHERE sym_score > 0.2
        WITH med, target_sym, sym_score ORDER BY sym_score DESC LIMIT 1
        
        // 3. Verificăm dacă există conexiunea între ele în graf
        MATCH (med)-[:CAUSES]->(de:DepletionEvent)-[:DEPLETES]->(nut:Nutrient)
        MATCH (de)-[:Has_Symptom]->(target_sym)
        
        // 4. Extragem alte simptome pentru context (Pattern Comprehension)
        WITH med, nut, target_sym, de,
                [ (de)-[:Has_Symptom]->(other:Symptom) WHERE other <> target_sym | other.name ] AS other_symptoms_list
        
        RETURN {
            connection_found: true,
            
            validated_path: {
                medication: med.name,
                nutrient: nut.name,
                symptom: target_sym.name
               
            },
            
            
            explanation: "Tratamentul cu " + med.name + " poate depleta " + nut.name + 
                        ", iar " + target_sym.name + " este un simptom direct al acestei deficiențe.",
            
            other_symptoms_to_check: other_symptoms_list[0..3],
            
            nutrient_to_recommand: nut.name
            
        } AS validation
        LIMIT 1
        """
        
        params = {
            "medications": med_list,
            "symptoms": sym_list
        }
    
    try:
        # Get Neo4j client and execute query
        neo4j_client = get_neo4j_client()
        results = neo4j_client.run_safe_query(query, params)
        
        # Handle different result types
        if isinstance(results, str):
            # Error message returned as string
            if "ERROR" in results or "SECURITY_BLOCK" in results:
                return {
                    **state,
                    "graph_results": [],
                    "has_results": False,
                    "execution_error": results,
                    "execution_path": add_to_execution_path(state, "graph_executor")
                }
            else:
                # Some other string result
                return {
                    **state,
                    "graph_results": [{"result": results}],
                    "has_results": True,
                    "execution_error": None,
                    "execution_path": add_to_execution_path(state, "graph_executor")
                }
        
        elif isinstance(results, list):
            # Normal list of results
            has_results = len(results) > 0
            
            # Clean up results (remove None values, empty strings)
            cleaned_results = []
            for record in results:
                if isinstance(record, dict):
                    cleaned_record = {
                        k: v for k, v in record.items() 
                        if v is not None and v != "" and v != []
                    }
                    if cleaned_record:
                        cleaned_results.append(cleaned_record)
                else:
                    cleaned_results.append(record)
            
            return {
                **state,
                "graph_results": cleaned_results,
                "has_results": len(cleaned_results) > 0,
                "execution_error": None,
                "execution_path": add_to_execution_path(state, "graph_executor")
            }
        
        else:
            # Unexpected result type
            return {
                **state,
                "graph_results": [],
                "has_results": False,
                "execution_error": f"Unexpected result type: {type(results)}",
                "execution_path": add_to_execution_path(state, "graph_executor")
            }
            
    except Exception as e:
        return {
            **state,
            "graph_results": [],
            "has_results": False,
            "execution_error": f"Query execution failed: {str(e)}",
            "execution_path": add_to_execution_path(state, "graph_executor"),
            "errors": state.get("errors", []) + [f"Error in graph_executor: {str(e)}"]
        }

