
import logging

from src.repositories.entity_repository import BaseRepository
from src.repositories.neo4j_query_repository import Neo4jQueryRepository
from src.repositories import get_neo4j_query_repository, get_neo4j_medication_repository, get_neo4j_symptom_repository
from src.services.service_results import ServiceResult, ResultStatus

logger = logging.getLogger(__name__)

class CrossEntityService:
    def __init__(self, query_repo: Neo4jQueryRepository, med_repo: BaseRepository, sym_repo: BaseRepository):
        self.query_repo = query_repo
        self.med_repo = med_repo
        self.sym_repo = sym_repo
        
    def validate_med_symptom_connection(self, med_name: str, sym_name: str) -> ServiceResult:
        med_canonical_name = self.med_repo.resolve(med_name)

        if not med_canonical_name:
            logger.warning(f"Medication '{med_name}' not found in the knowledge graph")
            return ServiceResult(
                status=ResultStatus.NOT_FOUND,
                entity_searched=med_name
            )
        
        logger.info(f"Medication '{med_name}' resolved to '{med_canonical_name}'")

        sym_canonical_name = self.sym_repo.resolve(sym_name)

        if not sym_canonical_name:
            logger.warning(f"Symptom '{sym_name}' not found in the knowledge graph")
            return ServiceResult(
                status=ResultStatus.NOT_FOUND,
                entity_searched=sym_name
            )
        
        logger.info(f"Symptom '{sym_name}' resolved to '{sym_canonical_name}'")

        connection_data = self.query_repo.find_med_symptom_connection(med_canonical_name, sym_canonical_name)

        if connection_data is None:
            logger.error(f"Data not found for the connection between '{med_canonical_name}' and '{sym_canonical_name}'")
            return ServiceResult(
                status=ResultStatus.DB_ERROR,
                entity_searched=f"{med_canonical_name} - {sym_canonical_name}"
            )

        if not connection_data:
            logger.warning(f"No connection found for '{med_canonical_name}' and '{sym_canonical_name}'")
            return ServiceResult(
                status=ResultStatus.EMPTY_DATA,
                entity_searched=f"{med_canonical_name} - {sym_canonical_name}",
                entity_found=f"{med_canonical_name} - {sym_canonical_name}"
            )

        
        logger.info(f"Connection found for '{med_canonical_name}' and '{sym_canonical_name}'")
        return ServiceResult(
            status=ResultStatus.SUCCESS,
            entity_searched=f"{med_canonical_name} - {sym_canonical_name}",
            entity_found=f"{med_canonical_name} - {sym_canonical_name}",
            data=connection_data
        )


_cross_entity_service: CrossEntityService | None = None

def get_cross_entity_service() -> CrossEntityService:
    global _cross_entity_service
    if _cross_entity_service is None:
        query_repo = get_neo4j_query_repository()
        med_repo = get_neo4j_medication_repository()
        sym_repo = get_neo4j_symptom_repository()
        _cross_entity_service = CrossEntityService(query_repo, med_repo, sym_repo)
    return _cross_entity_service