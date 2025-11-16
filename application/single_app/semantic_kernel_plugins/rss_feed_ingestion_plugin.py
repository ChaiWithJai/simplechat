"""
RSS Feed Ingestion Plugin for Opportunity System.

This plugin ingests funding opportunities from RSS feeds (primarily Grants.gov).
"""

import logging
import feedparser
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from semantic_kernel.functions import kernel_function
from semantic_kernel_plugins.base_plugin import BasePlugin
from semantic_kernel_plugins.plugin_invocation_logger import plugin_function_logger
from models_opportunities import Opportunity, OpportunityType, OpportunityStatus, SourceType

logger = logging.getLogger(__name__)


class RSSFeedIngestionPlugin(BasePlugin):
    """
    Plugin for ingesting opportunities from RSS feeds.

    Example manifest:
    {
        "name": "grants_gov_rss",
        "feed_url": "https://www.grants.gov/rss/GG_NewOpps.xml",
        "source_name": "Grants.gov",
        "description": "Ingest new opportunities from Grants.gov RSS feed"
    }
    """

    def __init__(self, manifest: Dict[str, Any] = None):
        super().__init__(manifest)
        self.manifest = manifest or {}
        self.feed_url = self.manifest.get('feed_url', '')
        self.source_name = self.manifest.get('source_name', 'RSS Feed')

        if not self.feed_url:
            logger.warning("RSS Feed URL not configured in manifest")

    @property
    def display_name(self) -> str:
        return "RSS Feed Ingestion"

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.manifest.get("name", "rss_feed_ingestion"),
            "type": "ingestion",
            "description": "Plugin for ingesting funding opportunities from RSS feeds like Grants.gov",
            "methods": [
                {
                    "name": "fetch_opportunities",
                    "description": "Fetch new opportunities from the configured RSS feed",
                    "parameters": [
                        {
                            "name": "feed_url",
                            "type": "str",
                            "description": "RSS feed URL (optional, uses manifest URL if not provided)",
                            "required": False
                        },
                        {
                            "name": "max_items",
                            "type": "int",
                            "description": "Maximum number of items to fetch (default: 50)",
                            "required": False
                        }
                    ],
                    "returns": {
                        "type": "List[Dict]",
                        "description": "List of opportunity dictionaries"
                    }
                },
                {
                    "name": "parse_grants_gov_entry",
                    "description": "Parse a single Grants.gov RSS entry into an Opportunity object",
                    "parameters": [
                        {
                            "name": "entry",
                            "type": "Dict",
                            "description": "RSS feed entry",
                            "required": True
                        }
                    ],
                    "returns": {
                        "type": "Dict",
                        "description": "Parsed opportunity dictionary"
                    }
                }
            ]
        }

    @kernel_function(name="fetch_opportunities", description="Fetch new opportunities from RSS feed")
    @plugin_function_logger
    def fetch_opportunities(
        self,
        feed_url: str = None,
        max_items: int = 50
    ) -> str:
        """
        Fetch opportunities from RSS feed.

        Args:
            feed_url: RSS feed URL (optional)
            max_items: Maximum items to fetch

        Returns:
            JSON string with list of opportunities
        """
        try:
            url = feed_url or self.feed_url
            if not url:
                return '{"error": "No feed URL provided"}'

            logger.info(f"Fetching RSS feed from: {url}")

            # Fetch feed with timeout
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Parse feed
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.error(f"Feed parsing error: {feed.bozo_exception}")
                return f'{{"error": "Feed parsing failed: {str(feed.bozo_exception)}"}}'

            # Parse entries
            opportunities = []
            for entry in feed.entries[:max_items]:
                try:
                    opp_dict = self._parse_entry(entry)
                    opportunities.append(opp_dict)
                except Exception as e:
                    logger.error(f"Error parsing entry: {e}")
                    continue

            result = {
                "success": True,
                "source": self.source_name,
                "feed_url": url,
                "count": len(opportunities),
                "opportunities": opportunities
            }

            import json
            return json.dumps(result, indent=2)

        except requests.RequestException as e:
            logger.error(f"HTTP error fetching feed: {e}")
            return f'{{"error": "Failed to fetch feed: {str(e)}"}}'
        except Exception as e:
            logger.error(f"Unexpected error in fetch_opportunities: {e}")
            return f'{{"error": "Unexpected error: {str(e)}"}}'

    def _parse_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse RSS entry into opportunity dictionary.

        Args:
            entry: RSS feed entry

        Returns:
            Opportunity dictionary
        """
        # Extract basic fields
        title = entry.get('title', '').strip()
        description = entry.get('description', '') or entry.get('summary', '')
        link = entry.get('link', '')
        pub_date = entry.get('published', '') or entry.get('updated', '')

        # Parse publication date
        ingestion_date = datetime.now(timezone.utc).isoformat()
        if pub_date:
            try:
                from dateutil import parser
                parsed_date = parser.parse(pub_date)
                ingestion_date = parsed_date.isoformat()
            except:
                pass

        # Extract Grants.gov specific fields if available
        # Grants.gov RSS often has custom fields
        amount_min = None
        amount_max = None
        deadline_close = None

        # Try to extract amount from description
        import re
        amount_pattern = r'\$?([\d,]+)\s*-\s*\$?([\d,]+)'
        amount_match = re.search(amount_pattern, description)
        if amount_match:
            try:
                amount_min = int(amount_match.group(1).replace(',', ''))
                amount_max = int(amount_match.group(2).replace(',', ''))
            except:
                pass

        # Try to extract deadline
        deadline_patterns = [
            r'(?:deadline|due|close)(?:\s+date)?:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(?:deadline|due|close)(?:\s+date)?:?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
        ]
        for pattern in deadline_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                try:
                    from dateutil import parser
                    deadline_close = parser.parse(match.group(1)).isoformat()
                    break
                except:
                    pass

        # Create opportunity object
        opportunity = Opportunity(
            source_name=self.source_name,
            source_url=link,
            source_type=SourceType.RSS.value,
            ingestion_date=ingestion_date,
            title=title,
            description=description,
            type=OpportunityType.GRANT.value,  # Default for Grants.gov
            amount_min=amount_min,
            amount_max=amount_max,
            deadline_close=deadline_close,
            status=OpportunityStatus.DRAFT.value
        )

        return opportunity.to_dict()

    @kernel_function(
        name="parse_grants_gov_entry",
        description="Parse a single Grants.gov RSS entry"
    )
    @plugin_function_logger
    def parse_grants_gov_entry(self, entry_json: str) -> str:
        """
        Parse a single entry (for testing/debugging).

        Args:
            entry_json: JSON string of entry

        Returns:
            Parsed opportunity JSON
        """
        try:
            import json
            entry = json.loads(entry_json)
            opportunity = self._parse_entry(entry)
            return json.dumps(opportunity, indent=2)
        except Exception as e:
            logger.error(f"Error parsing entry: {e}")
            return f'{{"error": "{str(e)}"}}'

    def get_functions(self) -> List[str]:
        """Return list of exposed functions."""
        return ["fetch_opportunities", "parse_grants_gov_entry"]
