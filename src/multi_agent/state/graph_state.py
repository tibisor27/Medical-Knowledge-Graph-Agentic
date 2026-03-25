from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from src.multi_agent.schemas import SupervisorDecision
from .reducers import clear_or_add
from src.multi_agent.schemas import MedicalWorkerResult, ProductWorkerResult, NutrientWorkerResult

class MultiAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    session_id: str

    #supervisor - workers
    current_decision: SupervisorDecision | None
    previous_decisions: Annotated[list[SupervisorDecision], clear_or_add]

    # Worker results are LISTS so multiple calls in the same turn accumulate
    # clear_or_add resets them between user turns via ["CLEAR"] in setup_turn
    medical_worker_results: Annotated[list[MedicalWorkerResult], clear_or_add]
    product_worker_results: Annotated[list[ProductWorkerResult], clear_or_add]
    nutrient_worker_results: Annotated[list[NutrientWorkerResult], clear_or_add]

    #persisted context across turns
    persisted_medications: list[str]
    persisted_symptoms: list[str]
    persisted_nutrients: list[str]
    persisted_products: list[str]

    #output
    final_response: str | None

    #observability
    step_count: int
    execution_path: Annotated[list[str], clear_or_add]