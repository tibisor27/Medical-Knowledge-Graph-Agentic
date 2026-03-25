from pydantic import BaseModel, Field
from .enums import RoutingNextAction, MedicalQueryType, ProductQueryType
from typing import Literal, Union, Annotated
 
 
#Literal[RoutingNextAction.MEDICAL_AGENT] - transform the instance object('MEDICAL_AGENT')
#of RoutingNextAction into fake Type. ':' requires a type not an object or class instance
class MedicalWorker(BaseModel):
    """
    Route to medical knowledge graph
    """
    action: Literal[RoutingNextAction.MEDICAL_WORKER]
    medical_query: MedicalQueryType
    medication: str | None = Field(default = None, description = "The name of the medication (e.g, 'Metformin')")              #same as medication: Optionarl[str] = None
    symptom: str | None = Field(default = None, description = "The symptom the user is experiencing (e.g., 'fatigue')")
    reasoning: str = Field(description="Brief explanation of why you chose to call the medical worker right now.")
 
 
class ProductWorker(BaseModel):
    """
    Route to product catalog
    """
    action: Literal[RoutingNextAction.PRODUCT_WORKER]
    product_query: ProductQueryType
    query: str | None = Field(default=None, description="Search terms for finding products (r.g 'energy supplemets').")
    product_name: str | None = Field(default=None, description="The exact name of the product e.g. 'Be-Energy'")
    category: str | None = Field(default=None, description="The product category e.g. 'vitamins'")
    reasoning: str = Field(description = "Brief explanation of why you chose to call the product worker right now")
 
 
class NutrientWorker(BaseModel):
    """
    Route ot nutreint education
    """
    action: Literal[RoutingNextAction.NUTRIENT_WORKER]
    nutrient: str = Field(description="The name of the nutrient (e.g., 'Vitamin B12').")
    reasoning: str = Field(description = "Brief explanation of why you chose to call the nutrient worker right now")
 
   
class RespondWorker(BaseModel):
    """
   Enough data gathered - route to synthesis
    """
    action: Literal[RoutingNextAction.RESPOND_WORKER]
    reasoning: str = Field(description="Why I have enough data to respond now, or why I am responding instead of calling a worker.")
    response_guidance: str = Field(
        default="Respond naturally and warmly based on the evidence and user needs",
        description=(
            "Clear instructions for how the Synthesis Agent should frame the response based on the current user needs and the evidence gathered."
            "Examples: 'Explain the medical information you found, ask if they want to learn more.' "
            "or 'Just greet warmly and ask what medications they take.' "
            "or 'Present the product naturally after explaining the nutrient gap.' "
            "NEVER instruct to mention products unless product_worker was called in this turn."
        )
    )
 
 
#discriminator tells the LLM to look for the 'action' field because it has multiple options,
#and it will return the object that matches the action field
 
SupervisorDecision = Annotated[
    Union[MedicalWorker, ProductWorker, NutrientWorker, RespondWorker],
    Field(discriminator="action")
]
 
class SupervisorDecisionOutput(BaseModel):
    """
    Wrapper around the discriminated union so LangChain can process it via with_structured_output.
    """
    decision: SupervisorDecision