from pydantic import BaseModel, Field
from .enums import RoutingNextAction, MedicalQueryType, ProductQueryType
from typing import Literal, Union


#Literal[RoutingNextAction.MEDICAL_AGENT] - transform the instance object('MEDICAL_AGENT')
#of RoutingNextAction into fake Type. ':' requires a type not an object or class instance
class MedicalWorker(BaseModel):
    """
    Choose this action to query the medical knowledge graph.
    Use this for medication lookups, finding side effects symptoms, or checking 
    depletion connections between medications and symptoms.
    """
    action: Literal[RoutingNextAction.MEDICAL_WORKER]
    medical_query: MedicalQueryType = Field(description = "The specific medical query to run")
    medication: str | None = Field(default = None, description = "The name of the medication (e.g, 'Metformin'), if mentioned")              #same as medication: Optionarl[str] = None
    symptom: str | None = Field(default = None, description = "The symptom the user is experiencing (e.g., 'fatigue'), if mentioned.")
    reasoning: str = Field(description="Brief explanation of why you chose to call the medical worker.")


class ProductWorker(BaseModel):
    """
    Choose this action to search the product catalog or get specific product details.
    Use this when the user asks for supplement recommendations or details about a supplement.
    """
    action: Literal[RoutingNextAction.PRODUCT_WORKER]
    product_query: ProductQueryType = Field(description = "The specific product query to run")
    query: str | None = Field(default=None, description="Search terms for finding products (used for 'search' task).")
    product_name: str | None = Field(default=None, description="The exact name of the product (used for 'details' task)")
    category: str | None = Field(default=None, description="The product category (used for 'catalog' task).")
    reasoning: str = Field(description = "Brief explanation of why you chose to call the product worker.")


class NutrientWorker(BaseModel):
    """
    Choose this action for general education about a nutrient.
    Use this to find out what a nutrient does in the body or its natural food sources.
    """
    action: Literal[RoutingNextAction.NUTRIENT_WORKER]
    nutrient: str = Field(description="The name of the nutrient (e.g., 'Vitamin B12').")
    reasoning: str = Field(description = "Brief explanation of why you chose to call the nutrient worker.")


class RespondWorker(BaseModel):
    """
    Choose this action when you have gathered enough information to answer the user,
    or if the user is just chatting normally and no database lookup is required.
    """
    action: Literal[RoutingNextAction.RESPOND_WORKER]
    reasoning: str


SupervisorDecision = Union[MedicalWorker, ProductWorker, NutrientWorker, RespondWorker]

