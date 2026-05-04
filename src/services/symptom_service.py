import logging

from src.repositories.entity_repository import BaseRepository
from src.repositories import get_neo4j_symptom_repository
from src.services.service_results import ServiceResult, ResultStatus

logger = logging.getLogger(__name__)

class SymptomService:

    def __init__(self, repo: BaseRepository):
        self.repo = repo

    def get_symptoms_info(self, symptom_name: str) -> ServiceResult:
        canonical_name = self.repo.resolve(symptom_name)

        if canonical_name is None:
            logger.warning(f"Symptom '{symptom_name}' not found in the database.")
            return ServiceResult(
                status=ResultStatus.NOT_FOUND,
                entity_searched=symptom_name
            )
        
        logger.info(f"Symptom '{symptom_name}' resolved to '{canonical_name}'.")

        symptom_data = self.repo.fetch_entity_data(canonical_name)

        if symptom_data is None:
            logger.error(f"Database error while fetching symptom metadata for '{canonical_name}'.")
            return ServiceResult(
                status=ResultStatus.DB_ERROR,
                entity_searched=symptom_name,
                entity_found=canonical_name
            )
        
        if not symptom_data:
            logger.warning(f"Symptom '{canonical_name}' has no metadata in the database.")
            return ServiceResult(
                status=ResultStatus.EMPTY_DATA,
                entity_searched=symptom_name,
                entity_found=canonical_name
            )
        
        logger.info("Found symptom metadata for '{canonical_name}'")
        return ServiceResult(
            status=ResultStatus.SUCCESS,
            entity_searched=symptom_name,
            entity_found=canonical_name,
            data=symptom_data
        )


_symptom_service_instance: SymptomService | None = None

def get_symptom_service() -> SymptomService:
    global _symptom_service_instance
    if _symptom_service_instance is None:
        repo = get_neo4j_symptom_repository()
        _symptom_service_instance = SymptomService(repo)
    return _symptom_service_instance