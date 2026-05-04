import logging

from src.repositories.product_repository import BaseProductRepository
from src.repositories import get_neo4j_product_repository
from src.services.service_results import ServiceResult, ResultStatus

logger = logging.getLogger(__name__)

class ProductService:
    def __init__(self, repo: BaseProductRepository):
        self.repo = repo


    def search_products(self, query: str) -> ServiceResult:
        results = self.repo.search_products(query)

        if results is None:
            logger.error(f"Database error while fetching products with query: {query}")
            return ServiceResult(
                status=ResultStatus.DB_ERROR,
                entity_searched=query,
            )
            
        if not results:
            logger.info(f"No products found for query: {query}")
            return ServiceResult(
                status=ResultStatus.NOT_FOUND,
                entity_searched=query,
            )

        logger.info(f"Found {len(results)} products for query: {query}")
        return ServiceResult(
            status=ResultStatus.SUCCESS,
            entity_searched=query,
            data=results
        )

    
    def get_product_info(self, product_name: str) -> ServiceResult:
        results = self.repo.get_product_details(product_name)

        if results is None:
            logger.error(f"Database error while fetching product info for: {product_name}")
            return ServiceResult(
                status=ResultStatus.DB_ERROR,
                entity_searched=product_name
            )
        
        if not results:
            logger.warning(f"No product info found for product: {product_name}")
            return ServiceResult(
                status=ResultStatus.EMPTY_DATA,
                entity_searched=product_name
            )
        
        logger.info(f"Found product info for product: {product_name}")
        return ServiceResult(
            status=ResultStatus.SUCCESS,
            entity_searched=product_name,
            data=results
        )
        


_prod_service_instance: ProductService | None = None

def get_product_service() -> ProductService:
    global _prod_service_instance
    if _prod_service_instance is None:
        repo = get_neo4j_product_repository()
        _prod_service_instance = ProductService(repo)
    return _prod_service_instance
