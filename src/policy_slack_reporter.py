"""
Slack webhook integration for YouTube Policy Intelligence reports.

Sends formatted 4-tier policy reports to Slack via incoming webhooks.
"""

import os
from datetime import datetime
from typing import Optional
import requests

from policy_categorizer import get_policy_category_emoji
from manual_source_placeholder import ManualSourcePlaceholder


class PolicySlackReporter:
    """Sends formatted policy intelligence reports to Slack via webhooks."""
    
    # Tier configuration with colors and emojis
    TIERS = {
        1: {"name": "Official Updates", "emoji": ":red_circle:", "color": "#dc3545"},
        2: {"name": "Community Signals", "emoji": ":large_orange_circle:", "color": "#fd7e14"},
        3: {"name": "Legal Analysis", "emoji": ":large_blue_circle:", "color": "#0d6efd"},
        4: {"name": "Expert Commentary", "emoji": ":large_purple_circle:", "color": "#6f42c1"},
    }
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize the Policy Slack reporter.
        
        Args:
            webhook_url: Slack webhook URL. If not provided, reads from
                        SLACK_WEBHOOK_URL_POLICY env var.
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL_POLICY")
        
        if not self.webhook_url:
            raise ValueError(
                "Slack webhook URL is required. Set SLACK_WEBHOOK_URL_POLICY environment variable."
            )
    
    def _escape_mrkdwn(self, text: str, max_length: int = 0) -> str:
        """
        Escape Slack mrkdwn special characters to prevent injection.
        
        Args:
            text: Text to escape
            max_length: Maximum length (0 = no limit)
            
        Returns:
            Escaped and optionally truncated text
        """
        if not text:
            return ""
        
        # Truncate first if needed
        if max_length > 0 and len(text) > max_length:
            text = text[:max_length - 3] + "..."
        
        # Escape special mrkdwn characters
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace("*", "\\*")
        text = text.replace("_", "\\_")
        text = text.replace("~", "\\~")
        text = text.replace("`", "\\`")
        return text
    
    def _safe_url(self, url: str) -> str:
        """Return URL only if it appears safe."""
        if url and url.startswith(("https://", "http://")):
            return url
        return ""
    
    def _format_time_ago(self, hours_ago: int) -> str:
        """Format hours into human-readable time string."""
        if hours_ago < 1:
            return "Just now"
        elif hours_ago < 24:
            return f"{hours_ago}h ago"
        elif hours_ago < 48:
            return "1 day ago"
        else:
            days = hours_ago // 24
            return f"{days} days ago"
    
    def _build_item_blocks(self, item: dict, index: int, tier: int) -> list[dict]:
        """Build Slack blocks for a single item."""
        # Sanitize inputs
        title = self._escape_mrkdwn(item.get('title', ''), max_length=200)
        source = self._escape_mrkdwn(item.get('source', ''), max_length=100)
        summary = self._escape_mrkdwn(item.get('summary', ''), max_length=300)
        url = self._safe_url(item.get('url', ''))
        thumbnail = self._safe_url(item.get('thumbnail', ''))
        
        hours_ago = item.get("hours_ago", 0)
        category = item.get("category", "")
        
        blocks = []
        
        # Category emoji
        cat_emoji = get_policy_category_emoji(category) if category else ""
        cat_tag = f"{cat_emoji} [{category}] " if category else ""
        
        # Build text
        title_text = f"*{index}. {cat_tag}{title}*"
        if summary:
            title_text += f"\n_{summary}_"
        if url:
            title_text += f"\n<{url}|:link: View>"
        
        section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": title_text
            }
        }
        
        # Add thumbnail for expert videos
        if thumbnail and tier == 4:
            section["accessory"] = {
                "type": "image",
                "image_url": thumbnail,
                "alt_text": item.get("title", "Video thumbnail")[:75]
            }
        
        blocks.append(section)
        
        # Context line
        time_str = self._format_time_ago(hours_ago)
        context_elements = [
            {"type": "mrkdwn", "text": f":globe_with_meridians: {source}"},
            {"type": "mrkdwn", "text": f":clock1: {time_str}"}
        ]
        
        # Add author for reddit posts
        if item.get("author") and tier == 2:
            author = self._escape_mrkdwn(item.get("author", ""), max_length=50)
            context_elements.insert(1, {"type": "mrkdwn", "text": f":bust_in_silhouette: u/{author}"})
        
        blocks.append({
            "type": "context",
            "elements": context_elements
        })
        
        return blocks
    
    def _build_tier_section(
        self,
        items: list[dict],
        tier: int,
        header_text: str
    ) -> list[dict]:
        """Build blocks for a tier section."""
        tier_config = self.TIERS.get(tier, self.TIERS[1])
        emoji = tier_config["emoji"]
        
        blocks = []
        
        # Tier header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {header_text}",
                "emoji": True
            }
        })
        
        if items:
            for i, item in enumerate(items, 1):
                blocks.extend(self._build_item_blocks(item, i, tier))
        else:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "_No updates in this category._"}
                ]
            })
        
        blocks.append({"type": "divider"})
        
        return blocks
    
    def build_report(
        self,
        official: list[dict] = None,
        community: list[dict] = None,
        legal: list[dict] = None,
        experts: list[dict] = None,
        report_time: Optional[datetime] = None
    ) -> dict:
        """
        Build a formatted Slack message payload.
        
        Args:
            official: Tier 1 - Official YouTube updates
            community: Tier 2 - Community discussions (Reddit)
            legal: Tier 3 - Legal/policy analysis
            experts: Tier 4 - Expert commentary
            report_time: Report generation time
            
        Returns:
            Slack message payload dictionary
        """
        official = official or []
        community = community or []
        legal = legal or []
        experts = experts or []
        
        if report_time is None:
            report_time = datetime.now()
        
        date_str = report_time.strftime("%A, %B %d, %Y")
        time_str = report_time.strftime("%I:%M %p")
        
        # Check if we have any content
        total_items = len(official) + len(community) + len(legal) + len(experts)
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":shield: YouTube Policy Intelligence - {date_str}",
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Daily monitoring of YouTube policy changes, community signals, and expert analysis."
                    }
                ]
            },
            {"type": "divider"}
        ]
        
        if total_items == 0:
            # No content - send a brief message
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":white_check_mark: *No policy updates detected in the last 24 hours.*\n\nAll quiet on the policy front. Manual sources may still have updates."
                }
            })
            blocks.append({"type": "divider"})
        else:
            # Tier 1: Official Updates
            if official:
                blocks.extend(self._build_tier_section(
                    official, 1, "Tier 1: Official Updates"
                ))
            
            # Tier 2: Community Signals
            if community:
                blocks.extend(self._build_tier_section(
                    community, 2, "Tier 2: Community Signals"
                ))
            
            # Tier 3: Legal Analysis
            if legal:
                blocks.extend(self._build_tier_section(
                    legal, 3, "Tier 3: Legal Analysis"
                ))
            
            # Tier 4: Expert Commentary
            if experts:
                blocks.extend(self._build_tier_section(
                    experts, 4, "Tier 4: Expert Commentary"
                ))
        
        # Footer with manual source reminder
        manual_reminder = ManualSourcePlaceholder.get_reminder_text()
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Report generated at {time_str} | {manual_reminder}"
                }
            ]
        })
        
        return {"blocks": blocks}
    
    def send_report(
        self,
        official: list[dict] = None,
        community: list[dict] = None,
        legal: list[dict] = None,
        experts: list[dict] = None,
        report_time: Optional[datetime] = None
    ) -> bool:
        """
        Build and send a policy report to Slack.
        
        Args:
            official: Tier 1 - Official YouTube updates
            community: Tier 2 - Community discussions
            legal: Tier 3 - Legal/policy analysis
            experts: Tier 4 - Expert commentary
            report_time: Report generation time
            
        Returns:
            True if successful, False otherwise
        """
        payload = self.build_report(official, community, legal, experts, report_time)
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                print("Policy report sent successfully to Slack!")
                return True
            else:
                print(f"Failed to send policy report. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"Error sending policy report: {e}")
            return False
    
    def send_test_message(self) -> bool:
        """Send a test message to verify webhook configuration."""
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":white_check_mark: *YouTube Policy Intelligence - Test Message*\n\nYour Slack integration is working correctly!"
                    }
                }
            ]
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                print("Test message sent successfully!")
                return True
            else:
                print(f"Failed to send test message. Status: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            print(f"Error sending test message: {e}")
            return False


def main():
    """Test the policy reporter with sample data."""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Sample data
    sample_official = [
        {
            "title": "Updates to YouTube Partner Program monetization policies",
            "source": "YouTube Blog",
            "url": "https://blog.youtube/example",
            "summary": "New guidelines for AI-generated content monetization.",
            "hours_ago": 12,
            "category": "MONETIZATION"
        }
    ]
    
    sample_community = [
        {
            "title": "Channel demonetized without warning - anyone else?",
            "source": "r/PartneredYouTube",
            "url": "https://reddit.com/r/PartneredYouTube/example",
            "author": "creator123",
            "hours_ago": 6,
            "category": "MONETIZATION"
        }
    ]
    
    sample_legal = [
        {
            "title": "EU Digital Services Act: Implications for Content Creators",
            "source": "Tech Policy Press",
            "url": "https://techpolicy.press/example",
            "summary": "How the DSA affects YouTube content moderation.",
            "hours_ago": 24,
            "category": "TERMS_OF_SERVICE"
        }
    ]
    
    sample_experts = [
        {
            "title": "YouTube's New Policy Explained | What Creators Need to Know",
            "source": "Creator Insider",
            "url": "https://youtube.com/watch?v=example",
            "thumbnail": "https://i.ytimg.com/vi/example/mqdefault.jpg",
            "hours_ago": 8,
            "category": "CONTENT_GUIDELINES"
        }
    ]
    
    try:
        reporter = PolicySlackReporter()
        
        print("Sending sample policy report...")
        reporter.send_report(
            official=sample_official,
            community=sample_community,
            legal=sample_legal,
            experts=sample_experts
        )
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nTo test, set SLACK_WEBHOOK_URL_POLICY in your .env file")


if __name__ == "__main__":
    main()
