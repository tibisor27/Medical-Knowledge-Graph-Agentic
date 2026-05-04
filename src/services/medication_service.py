import logging

from src.repositories.entity_repository import BaseRepository
from src.repositories import get_neo4j_medication_repository
from src.services.service_results import ServiceResult, ResultStatus

logger = logging.getLogger(__name__)

class MedicationService:

    def __init__(self, repo: BaseRepository):
        self.repo = repo

    def get_medication_info(self, medication_name: str) -> ServiceResult:
        canonical_name = self.repo.resolve(medication_name)

        if not canonical_name:
            logger.warning(f"Medication '{medication_name}' not found in the knowledge graph")
            return ServiceResult(
                status=ResultStatus.NOT_FOUND,
                entity_searched=medication_name
            )
        
        logger.info(f"Medication '{medication_name}' resolved to '{canonical_name}'")

        medication_data = self.repo.fetch_entity_data(canonical_name)

        if medication_data is None:
            logger.error(f"Database error while fetching depletions for '{canonical_name}'")
            return ServiceResult(
                status=ResultStatus.DB_ERROR,
                entity_searched=medication_name,
                entity_found=canonical_name
            )        

        if not medication_data:
            logger.warning(f"No depletions found for '{canonical_name}'")
            return ServiceResult(
                status=ResultStatus.EMPTY_DATA,
                entity_searched=medication_name,
                entity_found=canonical_name
            )

        logger.info(f"Found depletions for '{canonical_name}'")
        return ServiceResult(
            status=ResultStatus.SUCCESS,
            data=medication_data,
            entity_searched=medication_name,
            entity_found=canonical_name
        )

_med_service_instance: MedicationService | None = None

def get_medication_service() -> MedicationService:
    global _med_service_instance
    if _med_service_instance is None:
        repo = get_neo4j_medication_repository()
        _med_service_instance = MedicationService(repo)
    return _med_service_instance
