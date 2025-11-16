"""
Opportunity Pipeline Orchestrator

This script orchestrates the end-to-end pipeline:
1. Ingestion (RSS Feed)
2. Level 1 Validation (Schema)
3. Level 2 Validation (Quality)
4. Level 3 Validation (Semantic)
5. Publishing (Update status)

Usage:
    python opportunity_pipeline_orchestrator.py --source grants_gov --limit 10
"""

import logging
import json
import sys
import argparse
from typing import List, Dict, Any
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_ingestion(feed_url: str, source_name: str, max_items: int = 50) -> List[Dict]:
    """
    Run ingestion agent to fetch opportunities.

    Args:
        feed_url: RSS feed URL
        source_name: Source name
        max_items: Maximum items to fetch

    Returns:
        List of opportunity dictionaries
    """
    logger.info(f"Starting ingestion from {source_name}...")

    from semantic_kernel_plugins.rss_feed_ingestion_plugin import RSSFeedIngestionPlugin

    # Create plugin
    manifest = {
        "name": "grants_gov_rss",
        "feed_url": feed_url,
        "source_name": source_name
    }

    plugin = RSSFeedIngestionPlugin(manifest)

    # Fetch opportunities
    result_json = plugin.fetch_opportunities(feed_url=feed_url, max_items=max_items)
    result = json.loads(result_json)

    if "error" in result:
        logger.error(f"Ingestion failed: {result['error']}")
        return []

    opportunities = result.get('opportunities', [])
    logger.info(f"Ingested {len(opportunities)} opportunities")

    return opportunities


def run_validation_level_1(opportunity_dict: Dict) -> Dict:
    """
    Run Level 1 schema validation.

    Args:
        opportunity_dict: Opportunity dictionary

    Returns:
        Validation result
    """
    from semantic_kernel_plugins.opportunity_validation_plugin import OpportunityValidationPlugin

    plugin = OpportunityValidationPlugin()

    result_json = plugin.validate_level_1_schema(json.dumps(opportunity_dict))
    result = json.loads(result_json)

    return result


def run_validation_level_2(opportunity_dict: Dict) -> Dict:
    """
    Run Level 2 quality check.

    Args:
        opportunity_dict: Opportunity dictionary

    Returns:
        Validation result
    """
    from semantic_kernel_plugins.opportunity_validation_plugin import OpportunityValidationPlugin

    plugin = OpportunityValidationPlugin()

    result_json = plugin.validate_level_2_quality(json.dumps(opportunity_dict))
    result = json.loads(result_json)

    return result


def run_validation_level_3(opportunity_dict: Dict) -> Dict:
    """
    Run Level 3 semantic analysis.

    Args:
        opportunity_dict: Opportunity dictionary

    Returns:
        Validation result
    """
    from semantic_kernel_plugins.opportunity_validation_plugin import OpportunityValidationPlugin

    plugin = OpportunityValidationPlugin()

    result_json = plugin.validate_level_3_semantic(json.dumps(opportunity_dict))
    result = json.loads(result_json)

    return result


def save_opportunity(opportunity_dict: Dict, validation_results: Dict) -> bool:
    """
    Save opportunity to Cosmos DB with validation results.

    Args:
        opportunity_dict: Opportunity dictionary
        validation_results: Dictionary with level_1, level_2, level_3 results

    Returns:
        True if saved successfully
    """
    try:
        from config import cosmos_opportunities_container
        from functions_opportunities import OpportunityDataAccess
        from models_opportunities import Opportunity, OpportunityStatus
        from config import cosmos_opportunity_sources_container

        # Create data access layer
        opportunity_db = OpportunityDataAccess(
            cosmos_opportunities_container,
            cosmos_opportunity_sources_container
        )

        # Create opportunity object
        opportunity = Opportunity.from_dict(opportunity_dict)

        # Update validation results
        level_1 = validation_results.get('level_1', {})
        opportunity.update_validation_level_1(
            passed=level_1.get('passed', False),
            errors=level_1.get('errors', [])
        )

        level_2 = validation_results.get('level_2', {})
        opportunity.update_validation_level_2(
            passed=level_2.get('passed', False),
            score=level_2.get('score', 0.0),
            issues=level_2.get('issues', [])
        )

        level_3 = validation_results.get('level_3', {})
        opportunity.update_validation_level_3(
            passed=level_3.get('passed', False),
            analysis=level_3.get('analysis', {})
        )

        # Update status
        if all([
            validation_results['level_1'].get('passed'),
            validation_results['level_2'].get('passed'),
            validation_results['level_3'].get('passed')
        ]):
            opportunity.update_status(OpportunityStatus.VALIDATED)
        else:
            opportunity.update_status(OpportunityStatus.NEEDS_REVIEW)

        # Save to database
        opportunity_db.create_opportunity(opportunity)

        logger.info(f"Saved opportunity: {opportunity.id} (status: {opportunity.validation['status']})")
        return True

    except Exception as e:
        logger.error(f"Error saving opportunity: {e}")
        return False


def run_pipeline(feed_url: str, source_name: str, max_items: int = 10, save_to_db: bool = False):
    """
    Run the complete opportunity pipeline.

    Args:
        feed_url: RSS feed URL
        source_name: Source name
        max_items: Maximum opportunities to process
        save_to_db: Whether to save to Cosmos DB
    """
    logger.info("=" * 60)
    logger.info("OPPORTUNITY GROUNDING PIPELINE - POC DEMO")
    logger.info("=" * 60)

    # Step 1: Ingestion
    opportunities = run_ingestion(feed_url, source_name, max_items)

    if not opportunities:
        logger.error("No opportunities fetched. Exiting.")
        return

    # Pipeline statistics
    stats = {
        "total": len(opportunities),
        "level_1_pass": 0,
        "level_2_pass": 0,
        "level_3_pass": 0,
        "validated": 0,
        "needs_review": 0
    }

    # Process each opportunity
    for idx, opportunity_dict in enumerate(opportunities, 1):
        logger.info("-" * 60)
        logger.info(f"Processing opportunity {idx}/{len(opportunities)}")
        logger.info(f"Title: {opportunity_dict.get('opportunity', {}).get('title', 'N/A')}")

        # Step 2: Level 1 Validation
        logger.info("Running Level 1 validation (Schema)...")
        level_1_result = run_validation_level_1(opportunity_dict)
        level_1_passed = level_1_result.get('passed', False)
        stats['level_1_pass'] += 1 if level_1_passed else 0

        logger.info(f"  - Level 1: {'✓ PASS' if level_1_passed else '✗ FAIL'}")
        if not level_1_passed:
            logger.warning(f"  - Errors: {level_1_result.get('errors', [])}")

        # Step 3: Level 2 Validation
        logger.info("Running Level 2 validation (Quality)...")
        level_2_result = run_validation_level_2(opportunity_dict)
        level_2_passed = level_2_result.get('passed', False)
        level_2_score = level_2_result.get('score', 0.0)
        stats['level_2_pass'] += 1 if level_2_passed else 0

        logger.info(f"  - Level 2: {'✓ PASS' if level_2_passed else '✗ FAIL'} (score: {level_2_score:.2f})")
        if not level_2_passed:
            logger.warning(f"  - Issues: {level_2_result.get('issues', [])}")

        # Step 4: Level 3 Validation
        logger.info("Running Level 3 validation (Semantic)...")
        level_3_result = run_validation_level_3(opportunity_dict)
        level_3_passed = level_3_result.get('passed', False)
        level_3_analysis = level_3_result.get('analysis', {})
        stats['level_3_pass'] += 1 if level_3_passed else 0

        logger.info(f"  - Level 3: {'✓ PASS' if level_3_passed else '✗ FAIL'}")
        logger.info(f"  - Categories: {level_3_analysis.get('categories', [])}")
        logger.info(f"  - Relevance: {level_3_analysis.get('relevance_score', 0.0):.2f}")

        # Determine overall status
        all_passed = level_1_passed and level_2_passed and level_3_passed
        if all_passed:
            stats['validated'] += 1
            logger.info("  - Overall: ✓ VALIDATED")
        else:
            stats['needs_review'] += 1
            logger.info("  - Overall: ⚠ NEEDS REVIEW")

        # Save to database if requested
        if save_to_db:
            validation_results = {
                'level_1': level_1_result,
                'level_2': level_2_result,
                'level_3': level_3_result
            }
            save_opportunity(opportunity_dict, validation_results)

    # Print summary
    logger.info("=" * 60)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total opportunities processed: {stats['total']}")
    logger.info(f"Level 1 (Schema) pass rate: {stats['level_1_pass']}/{stats['total']} ({stats['level_1_pass']/stats['total']*100:.1f}%)")
    logger.info(f"Level 2 (Quality) pass rate: {stats['level_2_pass']}/{stats['total']} ({stats['level_2_pass']/stats['total']*100:.1f}%)")
    logger.info(f"Level 3 (Semantic) pass rate: {stats['level_3_pass']}/{stats['total']} ({stats['level_3_pass']/stats['total']*100:.1f}%)")
    logger.info(f"Validated opportunities: {stats['validated']}")
    logger.info(f"Needs review: {stats['needs_review']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run opportunity pipeline")
    parser.add_argument(
        '--source',
        default='grants_gov',
        help='Source name (default: grants_gov)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum opportunities to process (default: 10)'
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='Save opportunities to Cosmos DB'
    )

    args = parser.parse_args()

    # Grants.gov RSS feed
    GRANTS_GOV_RSS = "https://www.grants.gov/rss/GG_NewOpps.xml"

    try:
        run_pipeline(
            feed_url=GRANTS_GOV_RSS,
            source_name=args.source,
            max_items=args.limit,
            save_to_db=args.save
        )
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)
