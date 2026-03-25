from src.multi_agent.schemas import MedicalWorkerResult
from src.multi_agent.state.graph_state import MultiAgentState
from src.database.neo4j_client import get_neo4j_client
from src.database.cypher_queries import CypherQueries
from langchain_core.messages import AIMessage
import logging
 
logger = logging.getLogger(__name__)
driver = get_neo4j_client()
 
def run_medical_worker(state: MultiAgentState) -> dict:
 
    current_step = state["current_decision"]
    action = current_step.action
    medication = current_step.medication
    symptom = current_step.symptom
    reasoning = current_step.reasoning
    medical_query = current_step.medical_query.value
 
    logger.info(f"Task: {medical_query}, Medication: {medication}, Symptom: {symptom}, Reasoning: {reasoning}")
 
    try:
 
        if medical_query == "medication_lookup":
            result_data = handle_medical_lookup(medication)
       
        elif medical_query == "symptom_investigation":
            result_data = handle_symtom_lookup(symptom)
 
        elif medical_query == "validate_connection":
            result_data = handle_connection_validation(medication, symptom)
 
        else:
            # e posibil sa sa intample asta din moment ce e validat
            #inainte sa ajunga aici???? DE VERIFICAT
            logger.warning(f"Unknown medical_query task {medical_query}")
            result_data = {
                "summary": f"ERROR: Unknow task medical query '{medical_query}'",
                "label": f"medical_worker(unknown: {medical_query})"
            }
       
    except Exception as e:
        logger.error(f"MedicalWorker failed: {e}", exc_info=True)
        result_data = {
            "summary": f"ERROR: Medical worker failed — {str(e)}.",
            "label": "medical_worker(error)",
        }
 
    # Merge with existing persisted context (last-write-wins, so we read + append)
    existing_meds = state.get("persisted_medications", []) or []
    existing_nutrients = state.get("persisted_nutrients", []) or []
    existing_symptoms = state.get("persisted_symptoms", []) or []
 
    new_meds = list(dict.fromkeys(existing_meds + ([result_data.medication_name] if result_data.medication_name else [])))
    new_nutrients = list(dict.fromkeys(existing_nutrients + (result_data.nutrients_found if hasattr(result_data, 'nutrients_found') else [])))
    # Add symptom_name (explicitly queried symptom) and symptoms_found (from validation)
    symptoms_to_add = (getattr(result_data, 'symptoms_found', []) or []) + \
                      ([getattr(result_data, 'symptom_name', None)] if getattr(result_data, 'symptom_name', None) else [])
    new_symptoms = list(dict.fromkeys(existing_symptoms + symptoms_to_add))

    # Append Pydantic object to the accumulated list — type-safe, IDE-friendly
    return {
        "medical_worker_results": [result_data],
        "persisted_medications": new_meds,
        "persisted_nutrients": new_nutrients,
        "persisted_symptoms": new_symptoms,
        "execution_path": ["medical_worker"],
        "next_action": None,
        "current_decision": None,
    }
 
 
def _build_observation_message(result: MedicalWorkerResult) -> AIMessage:
    """Create an observation message from worker results — like ToolMessage in ReAct."""
    summary = result.summary if hasattr(result, 'summary') else str(result)
    med_name = result.medication_name if hasattr(result, 'medication_name') else "unknown"
   
    return AIMessage(
        content=f"[medical_worker observation] Medication: {med_name}\n{summary}",
        additional_kwargs={"worker_observation": True}
    )
 
 
def handle_medical_lookup(medication_name: str) -> MedicalWorkerResult:
    try:
        raw_results = driver.run_safe_query(
            CypherQueries.MEDICATION_LOOKUP,
            {"medications": [medication_name]}
        )
 
        logger.info(f"Raw lookup results: {raw_results}")
 
        if not raw_results:
            return MedicalWorkerResult(
                summary=f"No results found for medication '{medication_name}'",
                medication_name=medication_name
            )
 
 
        # logger.info(f"Raw lookup results for '{medication_name}': {raw_results[0]}")
        summaries, nutrients_found, symptoms_found = extract_summary_facts(raw_results[0].get("context", {}))
        # logger.info(f"Medication lookup for '{medication_name}' returned {summaries}")
        return MedicalWorkerResult(
            summary="\n".join(summaries),
            medication_name=medication_name,
            nutrients_found=nutrients_found,
            symptoms_found=[]  # DO NOT persist possible side-effects as actual user symptoms!
        )
 
    except Exception as e:
        logger.error(f"Error in handle_medical_lookup: {e}", exc_info=True)
        return MedicalWorkerResult(
            summary=f"Error looking up medication: {str(e)}",
            medication_name=medication_name
        )
 
   
 
def extract_summary_facts(context: dict) -> list:
 
    medication_info = context.get("medication", {})
    logger.info(f"medication: {medication_info}")
    medication_name = medication_info.get("name", "unknown")
    medication_synonyms = medication_info.get("synonyms", [])
 
    depletions = context.get("depletions", [])
 
    symptoms = []
    summary = []
 
    if not depletions:
        summary.append(f"{medication_name}: no depletion data found in database")
        return summary, [], []
   
    nutrient_names = [deplt["nutrient"] for deplt in depletions if deplt.get("nutrient")]
    all_symptoms = []
 
    summary.append(f"{medication_name}(also known as {', '.join(medication_synonyms)}) depletes: {', '.join(nutrient_names)}")
 
    for deplt in depletions:
        nutrient = deplt.get("nutrient")
        symptoms = deplt.get("symptoms", [])
 
        if symptoms:
            all_symptoms.extend(symptoms)
            summary.append(f"  └ {nutrient} deficiency → {', '.join(symptoms)}")
 
    return summary, nutrient_names, all_symptoms
 
 
def handle_symtom_lookup(symptom: str) -> MedicalWorkerResult:
   
    try:
        raw_results = driver.run_safe_query(
            CypherQueries.SYMPTOM_INVESTIGATION,
            {"symptom": symptom}
        )
 
        logger.info(f"Raw symptom investigation results: {raw_results}")
 
        if not raw_results:
            return MedicalWorkerResult(
                summary=f"No results found for symptom '{symptom}'",
                symptom_name=symptom
            )
 
        summaries = _extract_symptom_investigation_facts(raw_results[0].get("context", {}), symptom)
        return MedicalWorkerResult(
            summary="\n".join(summaries),
            symptom_name=symptom,
            nutrients_found=[],
            symptoms_found=[]
        )
 
    except Exception as e:
        logger.error(f"Error in handle_symtom_lookup: {e}", exc_info=True)
        return MedicalWorkerResult(
            summary=f"Error looking up symptom: {str(e)}",
            symptom_name=symptom
        )
 
 
def handle_connection_validation(medication: str, symptom: str) -> MedicalWorkerResult:
    """Check if there's a connection between a medication and symptom via nutrient depletion."""
    try:
        raw_results = driver.run_safe_query(
            CypherQueries.CONNECTION_VALIDATION,
            {"medications": [medication], "symptoms": [symptom]}
        )
   
        logger.info(f"Raw connection validation results: {raw_results}")
 
        if not raw_results:
            return MedicalWorkerResult(
                summary=f"No documented connection found between '{medication}' and '{symptom}'",
                medication_name=medication,
                symptom_name=symptom
            )
 
        summaries = _extract_connection_facts(raw_results[0].get("context", {}), medication, symptom)
        nutrients_involved = _extract_nutrients_from_connection(raw_results[0].get("context", {}))
       
        return MedicalWorkerResult(
            summary="\n".join(summaries),
            medication_name=medication,
            symptom_name=symptom,
            nutrients_found=nutrients_involved,
            symptoms_found=[symptom]
        )
 
    except Exception as e:
        logger.error(f"Error in handle_connection_validation: {e}", exc_info=True)
        return MedicalWorkerResult(
            summary=f"Error validating connection: {str(e)}",
            medication_name=medication,
            symptom_name=symptom
        )
 
 
def _extract_symptom_investigation_facts(context: dict, symptom: str) -> list:
    """Extract facts from symptom investigation query results."""
    summary = []
   
    depletions = context.get("depletions", [])
    medications = context.get("medications", [])
   
    if not depletions and not medications:
        summary.append(f"{symptom}: no associated causes found in database")
        return summary
   
    summary.append(f"Symptom '{symptom}' may be connected to:")
   
    if depletions:
        nutrient_names = [d.get("nutrient") for d in depletions if d.get("nutrient")]
        if nutrient_names:
            summary.append(f"  • Nutrient deficiencies: {', '.join(nutrient_names)}")
   
    if medications:
        med_names = [m.get("name") for m in medications if m.get("name")]
        if med_names:
            summary.append(f"  • Medications: {', '.join(med_names)}")
   
    return summary
 
 
def _extract_connection_facts(context: dict, medication: str, symptom: str) -> list:
    """Extract facts from connection validation results."""
    summary = []
   
    depletions = context.get("depletions", [])
   
    if not depletions:
        summary.append(f"No connection found between '{medication}' and '{symptom}' in database")
        return summary
   
    summary.append(f"Connection found: {medication} → nutrient depletion → {symptom}")
   
    for depletion in depletions:
        nutrient = depletion.get("nutrient", "unknown")
        symptoms = depletion.get("symptoms", [])
        if symptom.lower() in [s.lower() for s in symptoms]:
            summary.append(f"  └ {medication} depletes {nutrient}")
            summary.append(f"  └ {nutrient} deficiency can cause: {', '.join(symptoms)}")
   
    return summary
 
 
def _extract_nutrients_from_connection(context: dict) -> list:
    """Extract nutrient names from connection validation context."""
    nutrients = []
    depletions = context.get("depletions", [])
   
    for depletion in depletions:
        nutrient = depletion.get("nutrient")
        if nutrient and nutrient not in nutrients:
            nutrients.append(nutrient)
   
    return nutrients