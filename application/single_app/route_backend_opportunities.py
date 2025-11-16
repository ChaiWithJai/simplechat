"""
Backend API routes for Opportunity System.

Provides REST API endpoints for managing and querying funding opportunities.
"""

import logging
import json
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Any

from config import (
    cosmos_opportunities_container,
    cosmos_opportunity_sources_container
)
from functions_opportunities import OpportunityDataAccess
from models_opportunities import (
    Opportunity,
    OpportunitySource,
    OpportunityStatus,
    OpportunityType
)
from functions_authentication import login_required, admin_required
from swagger_wrapper import swagger_route

logger = logging.getLogger(__name__)

# Initialize data access layer
opportunity_db = OpportunityDataAccess(
    cosmos_opportunities_container,
    cosmos_opportunity_sources_container
)

# Create Blueprint
opportunity_bp = Blueprint('opportunities', __name__)


# ==================== OPPORTUNITY ENDPOINTS ====================

@opportunity_bp.route('/api/opportunities', methods=['GET'])
@login_required
@swagger_route(
    summary="List funding opportunities",
    description="Retrieve a list of funding opportunities with optional filters",
    tags=["Opportunities"],
    parameters=[
        {
            "name": "status",
            "in": "query",
            "description": "Filter by status (draft, validated, published, archived, rejected)",
            "required": False,
            "schema": {"type": "string"}
        },
        {
            "name": "type",
            "in": "query",
            "description": "Filter by opportunity type (Grant, Fellowship, Competition, etc.)",
            "required": False,
            "schema": {"type": "string"}
        },
        {
            "name": "source",
            "in": "query",
            "description": "Filter by source name",
            "required": False,
            "schema": {"type": "string"}
        },
        {
            "name": "search",
            "in": "query",
            "description": "Keyword search in title and description",
            "required": False,
            "schema": {"type": "string"}
        },
        {
            "name": "deadline_before",
            "in": "query",
            "description": "Filter by deadline before this date (ISO format)",
            "required": False,
            "schema": {"type": "string", "format": "date"}
        },
        {
            "name": "deadline_after",
            "in": "query",
            "description": "Filter by deadline after this date (ISO format)",
            "required": False,
            "schema": {"type": "string", "format": "date"}
        },
        {
            "name": "limit",
            "in": "query",
            "description": "Maximum results to return (default: 100)",
            "required": False,
            "schema": {"type": "integer", "default": 100}
        },
        {
            "name": "offset",
            "in": "query",
            "description": "Number of results to skip for pagination (default: 0)",
            "required": False,
            "schema": {"type": "integer", "default": 0}
        }
    ],
    responses={
        200: {
            "description": "List of opportunities",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "opportunities": {"type": "array"},
                            "total": {"type": "integer"},
                            "limit": {"type": "integer"},
                            "offset": {"type": "integer"}
                        }
                    }
                }
            }
        }
    }
)
def list_opportunities():
    """List opportunities with filters."""
    try:
        # Get query parameters
        status_str = request.args.get('status')
        type_str = request.args.get('type')
        source_name = request.args.get('source')
        search_keyword = request.args.get('search')
        deadline_before = request.args.get('deadline_before')
        deadline_after = request.args.get('deadline_after')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))

        # Convert status string to enum
        status = None
        if status_str:
            try:
                status = OpportunityStatus(status_str)
            except ValueError:
                return jsonify({"error": f"Invalid status: {status_str}"}), 400

        # Convert type string to enum
        opp_type = None
        if type_str:
            try:
                opp_type = OpportunityType(type_str)
            except ValueError:
                return jsonify({"error": f"Invalid type: {type_str}"}), 400

        # Handle search vs. filters
        if search_keyword:
            opportunities = opportunity_db.search_opportunities_by_keyword(
                keyword=search_keyword,
                limit=limit
            )
        elif deadline_before or deadline_after:
            opportunities = opportunity_db.get_opportunities_by_deadline(
                before_date=deadline_before,
                after_date=deadline_after,
                limit=limit
            )
        else:
            opportunities = opportunity_db.list_opportunities(
                status=status,
                source_name=source_name,
                opportunity_type=opp_type,
                limit=limit,
                offset=offset
            )

        # Convert to dictionaries
        opportunities_data = [opp.to_dict() for opp in opportunities]

        response = {
            "opportunities": opportunities_data,
            "total": len(opportunities_data),
            "limit": limit,
            "offset": offset
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error listing opportunities: {e}")
        return jsonify({"error": str(e)}), 500


@opportunity_bp.route('/api/opportunities/<opportunity_id>', methods=['GET'])
@login_required
@swagger_route(
    summary="Get opportunity details",
    description="Retrieve detailed information about a specific opportunity",
    tags=["Opportunities"],
    parameters=[
        {
            "name": "opportunity_id",
            "in": "path",
            "description": "Opportunity ID",
            "required": True,
            "schema": {"type": "string"}
        }
    ],
    responses={
        200: {"description": "Opportunity details"},
        404: {"description": "Opportunity not found"}
    }
)
def get_opportunity(opportunity_id):
    """Get opportunity by ID."""
    try:
        opportunity = opportunity_db.get_opportunity(opportunity_id)

        if not opportunity:
            return jsonify({"error": "Opportunity not found"}), 404

        return jsonify(opportunity.to_dict()), 200

    except Exception as e:
        logger.error(f"Error retrieving opportunity: {e}")
        return jsonify({"error": str(e)}), 500


@opportunity_bp.route('/api/opportunities/<opportunity_id>', methods=['PUT'])
@admin_required
@swagger_route(
    summary="Update opportunity",
    description="Update an existing opportunity (admin only)",
    tags=["Opportunities"],
    parameters=[
        {
            "name": "opportunity_id",
            "in": "path",
            "description": "Opportunity ID",
            "required": True,
            "schema": {"type": "string"}
        }
    ],
    responses={
        200: {"description": "Opportunity updated"},
        404: {"description": "Opportunity not found"}
    }
)
def update_opportunity(opportunity_id):
    """Update opportunity (admin only)."""
    try:
        opportunity = opportunity_db.get_opportunity(opportunity_id)

        if not opportunity:
            return jsonify({"error": "Opportunity not found"}), 404

        # Update fields from request
        data = request.json

        # TODO: Implement selective field updates
        # For POC, just update the whole object

        updated = opportunity_db.update_opportunity(opportunity)

        return jsonify(updated.to_dict()), 200

    except Exception as e:
        logger.error(f"Error updating opportunity: {e}")
        return jsonify({"error": str(e)}), 500


@opportunity_bp.route('/api/opportunities/<opportunity_id>', methods=['DELETE'])
@admin_required
@swagger_route(
    summary="Delete opportunity",
    description="Delete an opportunity (admin only)",
    tags=["Opportunities"],
    parameters=[
        {
            "name": "opportunity_id",
            "in": "path",
            "description": "Opportunity ID",
            "required": True,
            "schema": {"type": "string"}
        }
    ],
    responses={
        200: {"description": "Opportunity deleted"},
        404: {"description": "Opportunity not found"}
    }
)
def delete_opportunity(opportunity_id):
    """Delete opportunity (admin only)."""
    try:
        source_name = request.args.get('source')
        if not source_name:
            return jsonify({"error": "source query parameter required"}), 400

        success = opportunity_db.delete_opportunity(opportunity_id, source_name)

        if not success:
            return jsonify({"error": "Opportunity not found"}), 404

        return jsonify({"message": "Opportunity deleted successfully"}), 200

    except Exception as e:
        logger.error(f"Error deleting opportunity: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== PIPELINE/ADMIN ENDPOINTS ====================

@opportunity_bp.route('/api/admin/opportunities/pipeline', methods=['GET'])
@admin_required
@swagger_route(
    summary="Get pipeline status",
    description="Get status of opportunity ingestion pipeline (admin only)",
    tags=["Opportunities Admin"],
    responses={
        200: {"description": "Pipeline status and statistics"}
    }
)
def get_pipeline_status():
    """Get pipeline statistics (admin only)."""
    try:
        # Get overall stats
        stats = opportunity_db.get_pipeline_stats()

        # Get source statuses
        sources = opportunity_db.list_sources()
        source_statuses = []

        for source in sources:
            source_dict = source.to_dict()
            last_run = source_dict.get('metadata', {}).get('last_run')
            last_success = source_dict.get('metadata', {}).get('last_success')

            # Determine status
            if not source_dict.get('enabled'):
                status = "disabled"
            elif not last_run:
                status = "never_run"
            else:
                # Check if errored recently
                error_count = source_dict.get('metadata', {}).get('error_count', 0)
                success_rate = source_dict.get('metadata', {}).get('success_rate', 1.0)

                if success_rate < 0.5:
                    status = "error"
                elif last_success and last_success == last_run:
                    status = "idle"
                else:
                    status = "idle"

            source_statuses.append({
                "id": source_dict['id'],
                "name": source_dict['name'],
                "type": source_dict['type'],
                "status": status,
                "enabled": source_dict.get('enabled', True),
                "last_run": last_run,
                "last_success": last_success,
                "opportunities_ingested": source_dict.get('metadata', {}).get('opportunities_ingested', 0),
                "success_rate": source_dict.get('metadata', {}).get('success_rate', 1.0)
            })

        response = {
            "stats": stats,
            "sources": source_statuses
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return jsonify({"error": str(e)}), 500


@opportunity_bp.route('/api/admin/opportunities/ingest', methods=['POST'])
@admin_required
@swagger_route(
    summary="Trigger ingestion",
    description="Manually trigger opportunity ingestion from sources (admin only)",
    tags=["Opportunities Admin"],
    responses={
        200: {"description": "Ingestion triggered successfully"}
    }
)
def trigger_ingestion():
    """Manually trigger ingestion (admin only)."""
    try:
        data = request.json or {}
        source_id = data.get('source')

        # TODO: Implement actual ingestion trigger
        # For POC, return success message

        response = {
            "message": "Ingestion triggered",
            "source": source_id or "all",
            "note": "POC version - actual ingestion not yet implemented"
        }

        return jsonify(response), 200

    except Exception as e:
        logger.error(f"Error triggering ingestion: {e}")
        return jsonify({"error": str(e)}), 500


# ==================== SOURCE MANAGEMENT ENDPOINTS ====================

@opportunity_bp.route('/api/admin/opportunity-sources', methods=['GET'])
@admin_required
@swagger_route(
    summary="List opportunity sources",
    description="List all configured opportunity data sources (admin only)",
    tags=["Opportunities Admin"],
    responses={
        200: {"description": "List of sources"}
    }
)
def list_sources():
    """List all sources (admin only)."""
    try:
        sources = opportunity_db.list_sources()
        sources_data = [source.to_dict() for source in sources]

        return jsonify({"sources": sources_data, "total": len(sources_data)}), 200

    except Exception as e:
        logger.error(f"Error listing sources: {e}")
        return jsonify({"error": str(e)}), 500


@opportunity_bp.route('/api/admin/opportunity-sources', methods=['POST'])
@admin_required
@swagger_route(
    summary="Create opportunity source",
    description="Create a new opportunity data source (admin only)",
    tags=["Opportunities Admin"],
    responses={
        201: {"description": "Source created"}
    }
)
def create_source():
    """Create new source (admin only)."""
    try:
        data = request.json

        source = OpportunitySource(
            name=data.get('name'),
            type=data.get('type'),
            url=data.get('url'),
            schedule=data.get('schedule', 'daily'),
            enabled=data.get('enabled', True),
            config=data.get('config', {})
        )

        created = opportunity_db.create_source(source)

        return jsonify(created.to_dict()), 201

    except Exception as e:
        logger.error(f"Error creating source: {e}")
        return jsonify({"error": str(e)}), 500


def register_routes(app):
    """Register opportunity routes with Flask app."""
    app.register_blueprint(opportunity_bp)
    logger.info("Opportunity routes registered")
