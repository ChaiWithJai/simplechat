"""
Opportunity Validation Plugin - Multi-Level Validation System.

This plugin provides 3 levels of validation:
1. Schema Validation - Required fields and data types
2. Quality Check - Completeness score and duplicate detection
3. Semantic Analysis - AI-powered categorization and enrichment
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from semantic_kernel.functions import kernel_function
from semantic_kernel_plugins.base_plugin import BasePlugin
from semantic_kernel_plugins.plugin_invocation_logger import plugin_function_logger
from models_opportunities import Opportunity, OpportunityStatus, ValidationResult

logger = logging.getLogger(__name__)


class OpportunityValidationPlugin(BasePlugin):
    """
    Multi-level validation plugin for funding opportunities.

    Provides 3 validation levels with increasing sophistication.
    """

    def __init__(self, manifest: Dict[str, Any] = None):
        super().__init__(manifest)
        self.manifest = manifest or {}

        # Validation thresholds (configurable via manifest)
        self.min_quality_score = self.manifest.get('min_quality_score', 0.70)
        self.duplicate_threshold = self.manifest.get('duplicate_threshold', 0.95)
        self.min_description_length = self.manifest.get('min_description_length', 50)

    @property
    def display_name(self) -> str:
        return "Opportunity Validation"

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.manifest.get("name", "opportunity_validation"),
            "type": "validation",
            "description": "Multi-level validation system for funding opportunities",
            "methods": [
                {
                    "name": "validate_level_1_schema",
                    "description": "Level 1: Validate required fields and data types",
                    "parameters": [
                        {
                            "name": "opportunity_json",
                            "type": "str",
                            "description": "Opportunity as JSON string",
                            "required": True
                        }
                    ],
                    "returns": {
                        "type": "Dict",
                        "description": "Validation result with passed flag and errors"
                    }
                },
                {
                    "name": "validate_level_2_quality",
                    "description": "Level 2: Check data quality and completeness",
                    "parameters": [
                        {
                            "name": "opportunity_json",
                            "type": "str",
                            "description": "Opportunity as JSON string",
                            "required": True
                        }
                    ],
                    "returns": {
                        "type": "Dict",
                        "description": "Validation result with quality score and issues"
                    }
                },
                {
                    "name": "validate_level_3_semantic",
                    "description": "Level 3: AI-powered semantic analysis (requires GPT integration)",
                    "parameters": [
                        {
                            "name": "opportunity_json",
                            "type": "str",
                            "description": "Opportunity as JSON string",
                            "required": True
                        }
                    ],
                    "returns": {
                        "type": "Dict",
                        "description": "Semantic analysis with categories, keywords, and summary"
                    }
                }
            ]
        }

    # ==================== LEVEL 1: SCHEMA VALIDATION ====================

    @kernel_function(
        name="validate_level_1_schema",
        description="Level 1 validation: Check required fields and data types"
    )
    @plugin_function_logger
    def validate_level_1_schema(self, opportunity_json: str) -> str:
        """
        Validate opportunity schema - required fields and data types.

        Args:
            opportunity_json: Opportunity as JSON string

        Returns:
            JSON validation result
        """
        try:
            opportunity_dict = json.loads(opportunity_json)
            errors = []

            # Check required fields
            required_fields = [
                ('opportunity.title', 'Title'),
                ('opportunity.description', 'Description'),
                ('source.url', 'Source URL')
            ]

            for field_path, field_name in required_fields:
                value = self._get_nested_value(opportunity_dict, field_path)
                if not value or (isinstance(value, str) and not value.strip()):
                    errors.append(f"Missing required field: {field_name}")

            # Validate title length
            title = self._get_nested_value(opportunity_dict, 'opportunity.title')
            if title and len(title) < 5:
                errors.append("Title must be at least 5 characters")

            # Validate description length
            description = self._get_nested_value(opportunity_dict, 'opportunity.description')
            if description and len(description) < 20:
                errors.append("Description must be at least 20 characters")

            # Validate amount if provided
            amount_min = self._get_nested_value(opportunity_dict, 'opportunity.amount.min')
            amount_max = self._get_nested_value(opportunity_dict, 'opportunity.amount.max')

            if amount_min is not None:
                if not isinstance(amount_min, (int, float)) or amount_min < 0:
                    errors.append("Minimum amount must be a positive number")

            if amount_max is not None:
                if not isinstance(amount_max, (int, float)) or amount_max < 0:
                    errors.append("Maximum amount must be a positive number")

            if amount_min and amount_max and amount_min > amount_max:
                errors.append("Minimum amount cannot be greater than maximum amount")

            # Validate dates
            deadline_close = self._get_nested_value(opportunity_dict, 'opportunity.deadlines.application_close')
            if deadline_close:
                if not self._is_valid_iso_date(deadline_close):
                    errors.append("Application close deadline must be valid ISO date")
                else:
                    # Check if deadline is in the future
                    try:
                        from dateutil import parser
                        deadline_dt = parser.parse(deadline_close)
                        if deadline_dt < datetime.now(timezone.utc):
                            errors.append("Application deadline has already passed")
                    except:
                        errors.append("Invalid deadline date format")

            # Validate URL format
            source_url = self._get_nested_value(opportunity_dict, 'source.url')
            if source_url and not self._is_valid_url(source_url):
                errors.append("Invalid source URL format")

            # Result
            passed = len(errors) == 0
            result = {
                "level": 1,
                "name": "Schema Validation",
                "passed": passed,
                "errors": errors,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Level 1 validation: {'PASSED' if passed else 'FAILED'} ({len(errors)} errors)")
            return json.dumps(result, indent=2)

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return json.dumps({
                "level": 1,
                "passed": False,
                "errors": [f"Invalid JSON: {str(e)}"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.error(f"Level 1 validation error: {e}")
            return json.dumps({
                "level": 1,
                "passed": False,
                "errors": [f"Validation error: {str(e)}"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    # ==================== LEVEL 2: QUALITY CHECK ====================

    @kernel_function(
        name="validate_level_2_quality",
        description="Level 2 validation: Check data quality and completeness"
    )
    @plugin_function_logger
    def validate_level_2_quality(self, opportunity_json: str) -> str:
        """
        Check data quality - completeness score and reasonableness.

        Args:
            opportunity_json: Opportunity as JSON string

        Returns:
            JSON validation result with quality score
        """
        try:
            opportunity_dict = json.loads(opportunity_json)
            issues = []
            score_components = []

            # 1. Completeness check (40% of score)
            completeness_score = self._calculate_completeness(opportunity_dict)
            score_components.append(('completeness', completeness_score, 0.4))

            if completeness_score < 0.7:
                issues.append(f"Low completeness: {completeness_score:.0%} of fields filled")

            # 2. Description quality (30% of score)
            description = self._get_nested_value(opportunity_dict, 'opportunity.description') or ''
            description_score = min(len(description) / 200, 1.0)  # Target 200+ chars
            score_components.append(('description_quality', description_score, 0.3))

            if len(description) < self.min_description_length:
                issues.append(f"Description too short: {len(description)} characters (min: {self.min_description_length})")

            # 3. Amount reasonableness (15% of score)
            amount_min = self._get_nested_value(opportunity_dict, 'opportunity.amount.min')
            amount_max = self._get_nested_value(opportunity_dict, 'opportunity.amount.max')
            amount_score = 1.0

            if amount_min is not None and amount_max is not None:
                # Check if amounts are in reasonable range ($1K - $10M)
                if amount_min < 1000:
                    issues.append("Minimum amount suspiciously low (< $1,000)")
                    amount_score *= 0.7
                if amount_max > 10000000:
                    issues.append("Maximum amount suspiciously high (> $10M)")
                    amount_score *= 0.8
            else:
                issues.append("Amount range not specified")
                amount_score = 0.5

            score_components.append(('amount_reasonableness', amount_score, 0.15))

            # 4. Deadline validity (15% of score)
            deadline_score = 1.0
            deadline_close = self._get_nested_value(opportunity_dict, 'opportunity.deadlines.application_close')

            if not deadline_close:
                issues.append("No application deadline specified")
                deadline_score = 0.3
            else:
                try:
                    from dateutil import parser
                    deadline_dt = parser.parse(deadline_close)
                    days_until = (deadline_dt - datetime.now(timezone.utc)).days

                    if days_until < 0:
                        issues.append("Deadline has passed")
                        deadline_score = 0.0
                    elif days_until < 7:
                        issues.append("Deadline very soon (< 7 days)")
                        deadline_score = 0.6
                    elif days_until > 365:
                        issues.append("Deadline very far in future (> 1 year)")
                        deadline_score = 0.8
                except:
                    issues.append("Invalid deadline format")
                    deadline_score = 0.5

            score_components.append(('deadline_validity', deadline_score, 0.15))

            # Calculate overall quality score (weighted average)
            quality_score = sum(score * weight for _, score, weight in score_components)

            # Determine if passed
            passed = quality_score >= self.min_quality_score

            result = {
                "level": 2,
                "name": "Quality Check",
                "passed": passed,
                "score": round(quality_score, 3),
                "min_threshold": self.min_quality_score,
                "score_breakdown": {
                    name: {"score": round(score, 3), "weight": weight}
                    for name, score, weight in score_components
                },
                "issues": issues,
                "duplicate_check": {
                    "is_duplicate": False,
                    "similar_opportunities": [],
                    "note": "Duplicate detection requires AI Search integration"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Level 2 validation: {'PASSED' if passed else 'FAILED'} (score: {quality_score:.2f})")
            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Level 2 validation error: {e}")
            return json.dumps({
                "level": 2,
                "passed": False,
                "score": 0.0,
                "issues": [f"Validation error: {str(e)}"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    # ==================== LEVEL 3: SEMANTIC ANALYSIS ====================

    @kernel_function(
        name="validate_level_3_semantic",
        description="Level 3 validation: AI-powered semantic analysis"
    )
    @plugin_function_logger
    def validate_level_3_semantic(self, opportunity_json: str) -> str:
        """
        Semantic analysis using GPT-4 for categorization and enrichment.

        NOTE: This is a placeholder that returns mock data for POC.
        In production, this would call GPT-4 via Azure OpenAI.

        Args:
            opportunity_json: Opportunity as JSON string

        Returns:
            JSON semantic analysis result
        """
        try:
            opportunity_dict = json.loads(opportunity_json)

            title = self._get_nested_value(opportunity_dict, 'opportunity.title') or ''
            description = self._get_nested_value(opportunity_dict, 'opportunity.description') or ''

            # POC: Simple keyword-based categorization
            # TODO: Replace with GPT-4 call in production
            categories = self._extract_categories_simple(title, description)
            keywords = self._extract_keywords_simple(title, description)

            # Calculate relevance score (simple heuristic for POC)
            relevance_score = self._calculate_relevance_simple(title, description)

            # Generate simple summary (first 150 chars of description)
            summary = description[:150].strip() + "..." if len(description) > 150 else description

            # Result
            result = {
                "level": 3,
                "name": "Semantic Analysis",
                "passed": True,  # For POC, always pass (add logic later)
                "analysis": {
                    "categories": categories,
                    "keywords": keywords,
                    "entities": {
                        "organizations": [],  # TODO: NER extraction
                        "locations": [],
                        "dates": []
                    },
                    "relevance_score": round(relevance_score, 3),
                    "summary": summary
                },
                "note": "POC version - uses simple keyword matching. Production will use GPT-4.",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            logger.info(f"Level 3 validation: PASSED (relevance: {relevance_score:.2f})")
            return json.dumps(result, indent=2)

        except Exception as e:
            logger.error(f"Level 3 validation error: {e}")
            return json.dumps({
                "level": 3,
                "passed": False,
                "analysis": {},
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

    # ==================== HELPER METHODS ====================

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL format is valid."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None

    def _is_valid_iso_date(self, date_str: str) -> bool:
        """Check if string is valid ISO date."""
        try:
            from dateutil import parser
            parser.parse(date_str)
            return True
        except:
            return False

    def _calculate_completeness(self, opportunity_dict: Dict) -> float:
        """Calculate what percentage of fields are filled."""
        fields = [
            'opportunity.title',
            'opportunity.description',
            'opportunity.type',
            'opportunity.amount.min',
            'opportunity.amount.max',
            'opportunity.deadlines.application_close',
            'opportunity.eligibility.geography',
            'opportunity.eligibility.entity_types',
            'source.url',
            'source.name'
        ]

        filled_count = 0
        for field in fields:
            value = self._get_nested_value(opportunity_dict, field)
            if value is not None and value != "" and value != []:
                filled_count += 1

        return filled_count / len(fields)

    def _extract_categories_simple(self, title: str, description: str) -> List[str]:
        """Simple keyword-based category extraction (POC version)."""
        text = (title + " " + description).lower()
        categories = []

        category_keywords = {
            "Innovation": ["innovation", "innovative", "r&d", "research", "development"],
            "Technology": ["technology", "tech", "software", "hardware", "ai", "machine learning"],
            "Healthcare": ["health", "medical", "healthcare", "clinical", "biomedical"],
            "Education": ["education", "educational", "training", "learning", "academic"],
            "Social Impact": ["social", "community", "nonprofit", "impact", "sustainability"],
            "Small Business": ["small business", "sme", "startup", "entrepreneur"],
            "Federal Grant": ["federal", "government", "usda", "nsf", "nih", "doe", "nasa"],
            "Fellowship": ["fellowship", "scholar", "postdoc", "graduate"],
            "Competition": ["competition", "prize", "challenge", "award"]
        }

        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)

        return categories[:5]  # Max 5 categories

    def _extract_keywords_simple(self, title: str, description: str) -> List[str]:
        """Simple keyword extraction (POC version)."""
        text = (title + " " + description).lower()

        # Common funding keywords
        common_keywords = [
            "grant", "funding", "research", "innovation", "development", "technology",
            "small business", "startup", "entrepreneur", "sbir", "sttr", "fellowship",
            "competition", "prize", "award", "nonprofit", "community", "education"
        ]

        found_keywords = [kw for kw in common_keywords if kw in text]
        return found_keywords[:15]  # Max 15 keywords

    def _calculate_relevance_simple(self, title: str, description: str) -> float:
        """Simple relevance score for small business entrepreneurs."""
        text = (title + " " + description).lower()

        # Keywords indicating high relevance for entrepreneurs
        high_relevance_keywords = [
            "small business", "startup", "entrepreneur", "sbir", "sttr",
            "innovation", "commercialization", "funding", "grant"
        ]

        score = 0.5  # Base score
        matches = sum(1 for kw in high_relevance_keywords if kw in text)
        score += min(matches * 0.1, 0.4)  # Up to +0.4 for keyword matches

        # Bonus for amount range being reasonable for small business
        score += 0.1  # Default bonus

        return min(score, 1.0)

    def get_functions(self) -> List[str]:
        """Return list of exposed functions."""
        return [
            "validate_level_1_schema",
            "validate_level_2_quality",
            "validate_level_3_semantic"
        ]
