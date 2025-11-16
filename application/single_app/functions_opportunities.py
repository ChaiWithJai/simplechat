"""
Data access layer for opportunity management.

This module provides CRUD operations for opportunities and their sources,
interfacing with Cosmos DB.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from models_opportunities import Opportunity, OpportunitySource, OpportunityStatus, OpportunityType

logger = logging.getLogger(__name__)


class OpportunityDataAccess:
    """
    Data access layer for opportunities.
    Handles all CRUD operations with Cosmos DB.
    """

    def __init__(self, cosmos_container, cosmos_sources_container):
        """
        Initialize with Cosmos DB containers.

        Args:
            cosmos_container: Cosmos container for opportunities
            cosmos_sources_container: Cosmos container for opportunity sources
        """
        self.container = cosmos_container
        self.sources_container = cosmos_sources_container

    # ==================== OPPORTUNITY CRUD ====================

    def create_opportunity(self, opportunity: Opportunity) -> Opportunity:
        """
        Create a new opportunity in Cosmos DB.

        Args:
            opportunity: Opportunity object to create

        Returns:
            Created opportunity object

        Raises:
            Exception: If creation fails
        """
        try:
            opportunity_dict = opportunity.to_dict()
            result = self.container.create_item(body=opportunity_dict)
            logger.info(f"Created opportunity: {opportunity.id}")
            return Opportunity.from_dict(result)
        except Exception as e:
            logger.error(f"Error creating opportunity {opportunity.id}: {e}")
            raise

    def get_opportunity(self, opportunity_id: str, source_name: str = None) -> Optional[Opportunity]:
        """
        Retrieve an opportunity by ID.

        Args:
            opportunity_id: Opportunity ID
            source_name: Source name (partition key), if known for better performance

        Returns:
            Opportunity object or None if not found
        """
        try:
            if source_name:
                # Direct read with partition key (faster)
                item = self.container.read_item(item=opportunity_id, partition_key=source_name)
            else:
                # Cross-partition query
                query = "SELECT * FROM c WHERE c.id = @id"
                items = list(self.container.query_items(
                    query=query,
                    parameters=[{"name": "@id", "value": opportunity_id}],
                    enable_cross_partition_query=True
                ))
                if not items:
                    return None
                item = items[0]

            return Opportunity.from_dict(item)
        except CosmosResourceNotFoundError:
            logger.warning(f"Opportunity not found: {opportunity_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving opportunity {opportunity_id}: {e}")
            raise

    def update_opportunity(self, opportunity: Opportunity) -> Opportunity:
        """
        Update an existing opportunity.

        Args:
            opportunity: Opportunity object with updated data

        Returns:
            Updated opportunity object

        Raises:
            Exception: If update fails
        """
        try:
            opportunity.metadata['updated_at'] = datetime.now(timezone.utc).isoformat()
            opportunity_dict = opportunity.to_dict()
            result = self.container.upsert_item(body=opportunity_dict)
            logger.info(f"Updated opportunity: {opportunity.id}")
            return Opportunity.from_dict(result)
        except Exception as e:
            logger.error(f"Error updating opportunity {opportunity.id}: {e}")
            raise

    def delete_opportunity(self, opportunity_id: str, source_name: str) -> bool:
        """
        Delete an opportunity.

        Args:
            opportunity_id: Opportunity ID
            source_name: Source name (partition key)

        Returns:
            True if deleted successfully

        Raises:
            Exception: If deletion fails
        """
        try:
            self.container.delete_item(item=opportunity_id, partition_key=source_name)
            logger.info(f"Deleted opportunity: {opportunity_id}")
            return True
        except CosmosResourceNotFoundError:
            logger.warning(f"Opportunity not found for deletion: {opportunity_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting opportunity {opportunity_id}: {e}")
            raise

    # ==================== QUERY OPERATIONS ====================

    def list_opportunities(
        self,
        status: Optional[OpportunityStatus] = None,
        source_name: Optional[str] = None,
        opportunity_type: Optional[OpportunityType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Opportunity]:
        """
        List opportunities with optional filters.

        Args:
            status: Filter by status
            source_name: Filter by source
            opportunity_type: Filter by type
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            List of Opportunity objects
        """
        try:
            # Build query
            query = "SELECT * FROM c WHERE 1=1"
            parameters = []

            if status:
                query += " AND c.validation.status = @status"
                parameters.append({"name": "@status", "value": status.value})

            if source_name:
                query += " AND c.source.name = @source_name"
                parameters.append({"name": "@source_name", "value": source_name})

            if opportunity_type:
                query += " AND c.opportunity.type = @type"
                parameters.append({"name": "@type", "value": opportunity_type.value})

            # Add ordering
            query += " ORDER BY c.metadata.created_at DESC"

            # Add pagination
            query += f" OFFSET {offset} LIMIT {limit}"

            # Execute query
            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            opportunities = [Opportunity.from_dict(item) for item in items]
            logger.info(f"Retrieved {len(opportunities)} opportunities")
            return opportunities

        except Exception as e:
            logger.error(f"Error listing opportunities: {e}")
            raise

    def search_opportunities_by_keyword(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Opportunity]:
        """
        Search opportunities by keyword in title or description.

        Args:
            keyword: Search keyword
            limit: Maximum results to return

        Returns:
            List of matching Opportunity objects
        """
        try:
            query = """
                SELECT * FROM c
                WHERE CONTAINS(LOWER(c.opportunity.title), LOWER(@keyword))
                   OR CONTAINS(LOWER(c.opportunity.description), LOWER(@keyword))
                ORDER BY c.metadata.created_at DESC
                OFFSET 0 LIMIT @limit
            """
            parameters = [
                {"name": "@keyword", "value": keyword},
                {"name": "@limit", "value": limit}
            ]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            opportunities = [Opportunity.from_dict(item) for item in items]
            logger.info(f"Found {len(opportunities)} opportunities for keyword: {keyword}")
            return opportunities

        except Exception as e:
            logger.error(f"Error searching opportunities: {e}")
            raise

    def get_opportunities_by_deadline(
        self,
        before_date: Optional[str] = None,
        after_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Opportunity]:
        """
        Get opportunities by deadline date range.

        Args:
            before_date: Get opportunities with deadline before this date (ISO format)
            after_date: Get opportunities with deadline after this date (ISO format)
            limit: Maximum results

        Returns:
            List of Opportunity objects
        """
        try:
            query = "SELECT * FROM c WHERE c.opportunity.deadlines.application_close != null"
            parameters = []

            if before_date:
                query += " AND c.opportunity.deadlines.application_close < @before"
                parameters.append({"name": "@before", "value": before_date})

            if after_date:
                query += " AND c.opportunity.deadlines.application_close > @after"
                parameters.append({"name": "@after", "value": after_date})

            query += f" ORDER BY c.opportunity.deadlines.application_close ASC OFFSET 0 LIMIT {limit}"

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            return [Opportunity.from_dict(item) for item in items]

        except Exception as e:
            logger.error(f"Error getting opportunities by deadline: {e}")
            raise

    def get_opportunities_needing_validation(self, level: int = 1) -> List[Opportunity]:
        """
        Get opportunities that need validation at a specific level.

        Args:
            level: Validation level (1, 2, or 3)

        Returns:
            List of opportunities needing validation
        """
        try:
            level_field = f"level_{level}_schema" if level == 1 else (
                f"level_{level}_quality" if level == 2 else f"level_{level}_semantic"
            )

            query = f"""
                SELECT * FROM c
                WHERE c.validation.{level_field}.passed = null
                   OR c.validation.{level_field}.passed = false
                ORDER BY c.metadata.created_at ASC
            """

            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            return [Opportunity.from_dict(item) for item in items]

        except Exception as e:
            logger.error(f"Error getting opportunities needing validation: {e}")
            raise

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the opportunity pipeline.

        Returns:
            Dictionary with pipeline stats
        """
        try:
            # Total opportunities
            total_query = "SELECT VALUE COUNT(1) FROM c"
            total = list(self.container.query_items(
                query=total_query,
                enable_cross_partition_query=True
            ))[0]

            # By status
            status_query = """
                SELECT c.validation.status as status, COUNT(1) as count
                FROM c
                GROUP BY c.validation.status
            """
            status_counts = list(self.container.query_items(
                query=status_query,
                enable_cross_partition_query=True
            ))

            stats = {
                "total_opportunities": total,
                "by_status": {item['status']: item['count'] for item in status_counts}
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting pipeline stats: {e}")
            raise

    # ==================== SOURCE CRUD ====================

    def create_source(self, source: OpportunitySource) -> OpportunitySource:
        """Create a new opportunity source."""
        try:
            source_dict = source.to_dict()
            result = self.sources_container.create_item(body=source_dict)
            logger.info(f"Created source: {source.name}")
            return OpportunitySource.from_dict(result)
        except Exception as e:
            logger.error(f"Error creating source {source.name}: {e}")
            raise

    def get_source(self, source_id: str) -> Optional[OpportunitySource]:
        """Retrieve a source by ID."""
        try:
            item = self.sources_container.read_item(item=source_id, partition_key=source_id)
            return OpportunitySource.from_dict(item)
        except CosmosResourceNotFoundError:
            logger.warning(f"Source not found: {source_id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving source {source_id}: {e}")
            raise

    def update_source(self, source: OpportunitySource) -> OpportunitySource:
        """Update an existing source."""
        try:
            source.metadata['updated_at'] = datetime.now(timezone.utc).isoformat()
            source_dict = source.to_dict()
            result = self.sources_container.upsert_item(body=source_dict)
            logger.info(f"Updated source: {source.name}")
            return OpportunitySource.from_dict(result)
        except Exception as e:
            logger.error(f"Error updating source {source.name}: {e}")
            raise

    def list_sources(self, enabled_only: bool = False) -> List[OpportunitySource]:
        """List all opportunity sources."""
        try:
            query = "SELECT * FROM c"
            if enabled_only:
                query += " WHERE c.enabled = true"

            items = list(self.sources_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))

            return [OpportunitySource.from_dict(item) for item in items]

        except Exception as e:
            logger.error(f"Error listing sources: {e}")
            raise

    def update_source_run_metadata(
        self,
        source_id: str,
        success: bool,
        opportunities_count: int = 0
    ) -> None:
        """Update source metadata after a run."""
        try:
            source = self.get_source(source_id)
            if not source:
                logger.error(f"Source not found: {source_id}")
                return

            now = datetime.now(timezone.utc).isoformat()
            source.metadata['last_run'] = now

            if success:
                source.metadata['last_success'] = now
                source.metadata['opportunities_ingested'] += opportunities_count
            else:
                source.metadata['error_count'] += 1

            # Update success rate
            total_runs = source.metadata.get('opportunities_ingested', 0) + source.metadata.get('error_count', 0)
            if total_runs > 0:
                source.metadata['success_rate'] = source.metadata.get('opportunities_ingested', 0) / total_runs

            self.update_source(source)

        except Exception as e:
            logger.error(f"Error updating source run metadata: {e}")
            raise
