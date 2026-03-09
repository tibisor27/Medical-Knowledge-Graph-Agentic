from typing import Annotated, TypedDict, Any
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from src.multi_agent.schemas import RoutingNextAction
from src.multi_agent.schemas import SupervisorDecision


class MultiAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_query: str
    session_id: str

    #supervisor - workers
    next_action: str
    current_decision: SupervisorDecision | None
    previous_decisions: Annotated[list[SupervisorDecision], operator.add]
    medical_worker_result: Any | None
    product_worker_result: Any | None
    nutrient_worker_result: Any | None

    #persisted context across turns
    persisted_medications: list[str]
    persisted_symptoms: list[str]
    persisted_nutrients: list[str]
    persisted_products: list[str]

    #output
    final_repsonse: str | None 

    #observability
    step_count: int
    execution_path: Annotated[list[str], operator.add]

