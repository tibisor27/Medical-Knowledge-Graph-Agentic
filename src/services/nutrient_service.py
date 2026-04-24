import logging

from src.repositories import get_neo4j_nutrient_repository
from src.services.service_results import ServiceResult, ResultStatus

logger = logging.getLogger(__name__)

class NutrientService:
    def __init__(self):
        self.repo = get_neo4j_nutrient_repository()

    def get_nutrient_info(self, nutrient_name: str) -> ServiceResult:
        canonical_name = self.repo.resolve(nutrient_name)

        if not canonical_name:
            logger.warning(f"Nutrient '{nutrient_name}' not found in the database.")
            return ServiceResult(
                status=ResultStatus.NOT_FOUND,
                entity_searched=nutrient_name
            )
        
        logger.info(f"Nutrient '{nutrient_name}' resolved to '{canonical_name}'.")
            
        nutrient_data = self.repo.find_nutrient_metadata(canonical_name)

        if nutrient_data is None:
            logger.error(f"Database error while fetching nutrient metadata for '{canonical_name}'.")
            return ServiceResult(
                status=ResultStatus.ERROR,
                entity_searched=nutrient_name,
                entity_found=canonical_name
            )
            
        if not nutrient_data:
            logger.warning(f"Nutrient '{canonical_name}' has no metadata in the database.")
            return ServiceResult(
                status=ResultStatus.EMPTY_DATA,
                entity_searched=nutrient_name,
                entity_found=canonical_name
            )
        
        logger.info("Found nutrient metadata for '{canonical_name}'")
        return ServiceResult(
            status=ResultStatus.SUCCESS,
            entity_searched=nutrient_name,
            entity_found=canonical_name,
            data=nutrient_data
        )


_nutrient_service_instance: NutrientService | None = None

def get_nutrient_service() -> NutrientService:
    global _nutrient_service_instance
    if _nutrient_service_instance is None:
        _nutrient_service_instance = NutrientService()
    return _nutrient_service_instance

