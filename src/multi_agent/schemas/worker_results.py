from pydantic import BaseModel
from typing import Optional
 
class MedicalWorkerResult(BaseModel):
    summary: str
    medication_name: Optional[str] = None
    symptom_name: Optional[str] = None
    nutrients_found: list[str] = []
    symptoms_found: list[str] = []
 
class ProductWorkerResult(BaseModel):
    summary: str
    products: list[dict] = []
 
class NutrientWorkerResult(BaseModel):
    summary: str
    nutrient_name: Optional[str] = None