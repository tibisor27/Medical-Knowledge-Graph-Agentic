from enum import Enum

class RoutingNextAction(str, Enum):
    MEDICAL_WORKER = "call_medical"
    PRODUCT_WORKER = "call_product"
    NUTRIENT_WORKER = "call_nutrient"
    RESPOND_WORKER = "respond"


class MedicalQueryType(str, Enum):                           #str as argument - each enum member inherits from 'str' -> its literally a string
    MED_LOOKUP = "medication_lookup"
    SYMPTOM_INVESTIGATION = "symptom_investigation"
    VALIDATE_CONNECTION = "validate_connection"


class ProductQueryType(str, Enum):
    PRODUCTS_SEARCH = "products_search"
    PRODUCT_DETAILS = "product_details"
    PRODUCTS_CATALOG = "products_catalog"

