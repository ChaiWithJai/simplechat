"""
Data models for the Multi-Level AI Agent System for Opportunity Grounding.

This module defines the schema for funding opportunities (grants, fellowships, competitions)
and their validation/enrichment metadata.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from enum import Enum


class OpportunityType(str, Enum):
    """Types of funding opportunities."""
    GRANT = "Grant"
    FELLOWSHIP = "Fellowship"
    COMPETITION = "Competition"
    AWARD = "Award"
    LOAN = "Loan"
    PRIZE = "Prize"
    ACCELERATOR = "Accelerator"


class OpportunityStatus(str, Enum):
    """Lifecycle status of an opportunity."""
    DRAFT = "draft"  # Initial ingestion, not validated
    VALIDATED = "validated"  # Passed all validation levels
    PUBLISHED = "published"  # Published to AI Search and available to users
    ARCHIVED = "archived"  # Deadline passed or no longer available
    REJECTED = "rejected"  # Failed validation
    NEEDS_REVIEW = "needs_review"  # Manual review required


class SourceType(str, Enum):
    """Type of data source."""
    API = "API"
    WEB = "Web"
    RSS = "RSS"
    MANUAL = "Manual"
    EMAIL = "Email"


class Opportunity:
    """
    Complete opportunity data model.

    This represents a funding opportunity with all metadata from source,
    through validation and enrichment, to publishing.
    """

    def __init__(self, **kwargs):
        # Core identification
        self.id: str = kwargs.get('id', f"opp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")

        # Source information
        self.source = {
            "name": kwargs.get('source_name', ''),
            "url": kwargs.get('source_url', ''),
            "type": kwargs.get('source_type', SourceType.MANUAL.value),
            "ingestion_date": kwargs.get('ingestion_date', datetime.now(timezone.utc).isoformat())
        }

        # Opportunity details
        self.opportunity = {
            "title": kwargs.get('title', ''),
            "description": kwargs.get('description', ''),
            "type": kwargs.get('type', OpportunityType.GRANT.value),
            "amount": {
                "min": kwargs.get('amount_min'),
                "max": kwargs.get('amount_max'),
                "currency": kwargs.get('currency', 'USD')
            },
            "deadlines": {
                "application_open": kwargs.get('deadline_open'),
                "application_close": kwargs.get('deadline_close'),
                "notification_date": kwargs.get('notification_date')
            },
            "eligibility": {
                "geography": kwargs.get('geography', []),
                "entity_types": kwargs.get('entity_types', []),
                "industries": kwargs.get('industries', []),
                "stage": kwargs.get('stage', []),
                "demographics": kwargs.get('demographics', [])
            },
            "requirements": {
                "minimum_employees": kwargs.get('min_employees'),
                "minimum_revenue": kwargs.get('min_revenue'),
                "years_in_business": kwargs.get('years_in_business', 0),
                "other": kwargs.get('other_requirements', [])
            }
        }

        # Validation status
        self.validation = {
            "status": kwargs.get('status', OpportunityStatus.DRAFT.value),
            "level_1_schema": {
                "passed": None,
                "timestamp": None,
                "errors": []
            },
            "level_2_quality": {
                "passed": None,
                "score": None,
                "timestamp": None,
                "issues": [],
                "duplicate_check": {
                    "is_duplicate": False,
                    "similar_opportunities": []
                }
            },
            "level_3_semantic": {
                "passed": None,
                "timestamp": None,
                "analysis": {
                    "categories": [],
                    "keywords": [],
                    "entities": {
                        "organizations": [],
                        "locations": [],
                        "dates": []
                    },
                    "relevance_score": None,
                    "summary": ""
                }
            }
        }

        # Enrichment data
        self.enrichment = {
            "embedding": kwargs.get('embedding', []),
            "tags": kwargs.get('tags', []),
            "ai_summary": kwargs.get('ai_summary', ''),
            "matching_keywords": kwargs.get('matching_keywords', [])
        }

        # Metadata
        self.metadata = {
            "created_at": kwargs.get('created_at', datetime.now(timezone.utc).isoformat()),
            "updated_at": kwargs.get('updated_at', datetime.now(timezone.utc).isoformat()),
            "published_at": kwargs.get('published_at'),
            "version": kwargs.get('version', 1),
            "processing_time_ms": kwargs.get('processing_time_ms'),
            "last_verified": kwargs.get('last_verified', datetime.now(timezone.utc).isoformat())
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert opportunity to dictionary for storage."""
        return {
            "id": self.id,
            "source": self.source,
            "opportunity": self.opportunity,
            "validation": self.validation,
            "enrichment": self.enrichment,
            "metadata": self.metadata
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Opportunity':
        """Create opportunity from dictionary."""
        opp = Opportunity()
        opp.id = data.get('id', opp.id)
        opp.source = data.get('source', opp.source)
        opp.opportunity = data.get('opportunity', opp.opportunity)
        opp.validation = data.get('validation', opp.validation)
        opp.enrichment = data.get('enrichment', opp.enrichment)
        opp.metadata = data.get('metadata', opp.metadata)
        return opp

    def update_validation_level_1(self, passed: bool, errors: List[str] = None):
        """Update Level 1 validation results."""
        self.validation['level_1_schema'] = {
            "passed": passed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "errors": errors or []
        }
        self.metadata['updated_at'] = datetime.now(timezone.utc).isoformat()

    def update_validation_level_2(self, passed: bool, score: float, issues: List[str] = None,
                                   is_duplicate: bool = False, similar_opps: List[str] = None):
        """Update Level 2 validation results."""
        self.validation['level_2_quality'] = {
            "passed": passed,
            "score": score,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "issues": issues or [],
            "duplicate_check": {
                "is_duplicate": is_duplicate,
                "similar_opportunities": similar_opps or []
            }
        }
        self.metadata['updated_at'] = datetime.now(timezone.utc).isoformat()

    def update_validation_level_3(self, passed: bool, analysis: Dict[str, Any]):
        """Update Level 3 semantic validation results."""
        self.validation['level_3_semantic'] = {
            "passed": passed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis": analysis
        }
        self.metadata['updated_at'] = datetime.now(timezone.utc).isoformat()

    def update_status(self, status: OpportunityStatus):
        """Update opportunity status."""
        self.validation['status'] = status.value
        self.metadata['updated_at'] = datetime.now(timezone.utc).isoformat()

        if status == OpportunityStatus.PUBLISHED:
            self.metadata['published_at'] = datetime.now(timezone.utc).isoformat()


class OpportunitySource:
    """
    Configuration for an opportunity data source.
    """

    def __init__(self, **kwargs):
        self.id: str = kwargs.get('id', f"src_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
        self.name: str = kwargs.get('name', '')
        self.type: str = kwargs.get('type', SourceType.WEB.value)
        self.url: str = kwargs.get('url', '')
        self.schedule: str = kwargs.get('schedule', 'daily')  # daily, weekly, hourly
        self.enabled: bool = kwargs.get('enabled', True)

        # Configuration specific to source type
        self.config: Dict[str, Any] = kwargs.get('config', {})
        # For Web: {"selectors": {...}, "pagination": {...}}
        # For API: {"auth": {...}, "endpoints": [...]}
        # For RSS: {"feed_url": "..."}

        # Metadata
        self.metadata: Dict[str, Any] = {
            "created_at": kwargs.get('created_at', datetime.now(timezone.utc).isoformat()),
            "updated_at": kwargs.get('updated_at', datetime.now(timezone.utc).isoformat()),
            "last_run": kwargs.get('last_run'),
            "last_success": kwargs.get('last_success'),
            "opportunities_ingested": kwargs.get('opportunities_ingested', 0),
            "error_count": kwargs.get('error_count', 0),
            "success_rate": kwargs.get('success_rate', 1.0)
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert source to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "schedule": self.schedule,
            "enabled": self.enabled,
            "config": self.config,
            "metadata": self.metadata
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'OpportunitySource':
        """Create source from dictionary."""
        return OpportunitySource(**data)


class ValidationResult:
    """
    Result of a validation stage.
    """

    def __init__(self, level: int, passed: bool, **kwargs):
        self.level: int = level  # 1, 2, or 3
        self.passed: bool = passed
        self.timestamp: str = datetime.now(timezone.utc).isoformat()
        self.errors: List[str] = kwargs.get('errors', [])
        self.issues: List[str] = kwargs.get('issues', [])
        self.score: Optional[float] = kwargs.get('score')
        self.analysis: Optional[Dict[str, Any]] = kwargs.get('analysis')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level,
            "passed": self.passed,
            "timestamp": self.timestamp,
            "errors": self.errors,
            "issues": self.issues,
            "score": self.score,
            "analysis": self.analysis
        }
