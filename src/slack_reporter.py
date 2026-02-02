"""
Slack webhook integration for sending formatted reports.
"""

import os
from datetime import datetime
from typing import Optional
import requests

from categorizer import get_category_emoji


class SlackReporter:
    """Sends formatted reports to Slack via incoming webhooks."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize the Slack reporter.
        
        Args:
            webhook_url: Slack webhook URL. If not provided, reads from SLACK_WEBHOOK_URL env var.
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            raise ValueError("Slack webhook URL is required. Set SLACK_WEBHOOK_URL environment variable.")
    
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
        
        # Escape special mrkdwn characters: & < > * _ ~ `
        # Order matters: & must be first to avoid double-escaping
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        # These prevent formatting injection
        text = text.replace("*", "\\*")
        text = text.replace("_", "\\_")
        text = text.replace("~", "\\~")
        text = text.replace("`", "\\`")
        return text
    
    def _safe_url(self, url: str) -> str:
        """
        Return URL only if it appears safe, otherwise empty string.
        
        Args:
            url: URL to validate
            
        Returns:
            Original URL if safe, empty string otherwise
        """
        if url and url.startswith(("https://", "http://")):
            return url
        return ""
    
    def _format_time_ago(self, hours_ago: int) -> str:
        """Format hours into human-readable time string."""
        if hours_ago < 1:
            return "Just now"
        elif hours_ago < 24:
            return f"{hours_ago} hours ago"
        elif hours_ago < 48:
            return "1 day ago"
        else:
            days = hours_ago // 24
            return f"{days} days ago"
    
    def format_video(self, video: dict, index: int) -> str:
        """Format a single video for display."""
        stats = video.get("stats", {})
        views = stats.get("views", 0)
        days_ago = video.get("days_ago", 0)
        
        # Sanitize external input
        title = self._escape_mrkdwn(video.get('title', ''), max_length=200)
        channel = self._escape_mrkdwn(video.get('channel', ''), max_length=100)
        url = self._safe_url(video.get('url', ''))
        
        # Format views with commas
        views_str = f"{views:,}"
        
        # Time description
        if days_ago == 0:
            time_str = "Today"
        elif days_ago == 1:
            time_str = "1 day ago"
        else:
            time_str = f"{days_ago} days ago"
        
        # Build output with safe values
        lines = [
            f"*{index}. {title}*",
            f"   Channel: {channel}",
            f"   Views: {views_str} | Published: {time_str}",
        ]
        if url:
            lines.append(f"   <{url}|Watch on YouTube>")
        
        return "\n".join(lines)
    
    def format_article(self, article: dict, index: int) -> str:
        """Format a single article for display."""
        hours_ago = article.get("hours_ago", 0)
        category = article.get("category", "")
        
        # Sanitize external input
        title = self._escape_mrkdwn(article.get('title', ''), max_length=200)
        source = self._escape_mrkdwn(article.get('source', ''), max_length=100)
        summary = self._escape_mrkdwn(article.get('summary', ''), max_length=500)
        url = self._safe_url(article.get('url', ''))
        
        time_str = self._format_time_ago(hours_ago)
        
        # Category tag
        cat_tag = f"[{category}] " if category else ""
        
        # Build output with safe values
        lines = [f"*{index}. {cat_tag}{title}*"]
        if summary:
            lines.append(f"   _{summary}_")
        lines.append(f"   Source: {source}")
        lines.append(f"   Published: {time_str}")
        if url:
            lines.append(f"   <{url}|Read Article>")
        
        return "\n".join(lines)
    
    def format_release(self, release: dict, index: int) -> str:
        """Format a single GitHub release for display."""
        hours_ago = release.get("hours_ago", 0)
        
        # Sanitize external input
        repo = self._escape_mrkdwn(release.get('repo', ''), max_length=100)
        name = self._escape_mrkdwn(release.get('name', ''), max_length=200)
        tag = self._escape_mrkdwn(release.get('tag', ''), max_length=50)
        body = self._escape_mrkdwn(release.get('body', ''), max_length=300)
        url = self._safe_url(release.get('url', ''))
        
        time_str = self._format_time_ago(hours_ago)
        prerelease = " (pre-release)" if release.get("prerelease") else ""
        
        # Build output
        lines = [f"*{index}. {repo} - {name}*{prerelease}"]
        lines.append(f"   Tag: `{tag}` | Released: {time_str}")
        if body:
            # Show first 200 chars of release notes
            lines.append(f"   _{body[:200]}{'...' if len(body) > 200 else ''}_")
        if url:
            lines.append(f"   <{url}|View Release>")
        
        return "\n".join(lines)
    
    def format_community_post(self, post: dict, index: int) -> str:
        """Format a single community post (HN/Reddit) for display."""
        hours_ago = post.get("hours_ago", 0)
        category = post.get("category", "DISCUSSION")
        
        # Sanitize external input
        title = self._escape_mrkdwn(post.get('title', ''), max_length=200)
        source = self._escape_mrkdwn(post.get('source', ''), max_length=50)
        url = self._safe_url(post.get('url', '') or post.get('hn_url', ''))
        
        time_str = self._format_time_ago(hours_ago)
        
        # Score display (points for HN, score for Reddit)
        score = post.get("points", 0) or post.get("score", 0)
        comments = post.get("comments", 0)
        
        # Category emoji
        cat_emoji = get_category_emoji(category)
        
        # Build output
        lines = [f"*{index}. {cat_emoji} [{category}] {title}*"]
        lines.append(f"   {source} | {score} pts | {comments} comments | {time_str}")
        if url:
            lines.append(f"   <{url}|View Discussion>")
        
        return "\n".join(lines)
    
    def build_report(
        self,
        videos: list[dict] = None,
        articles: list[dict] = None,
        releases: list[dict] = None,
        community: list[dict] = None,
        report_time: Optional[datetime] = None
    ) -> dict:
        """
        Build a formatted Slack message payload.
        
        Args:
            videos: List of trending videos
            articles: List of trending articles
            releases: List of GitHub releases
            community: List of community posts (HN/Reddit)
            report_time: Report generation time
            
        Returns:
            Slack message payload dictionary
        """
        videos = videos or []
        articles = articles or []
        releases = releases or []
        community = community or []
        
        if report_time is None:
            report_time = datetime.now()
        
        date_str = report_time.strftime("%A, %B %d, %Y")
        time_str = report_time.strftime("%I:%M %p")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"AI Trends Report - {date_str}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Good morning! Here's your daily roundup of trending AI content."
                }
            },
            {"type": "divider"}
        ]
        
        # GitHub Releases Section (if any)
        if releases:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*:rocket: RELEASES*"
                }
            })
            
            for i, release in enumerate(releases, 1):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.format_release(release, i)
                    }
                })
            
            blocks.append({"type": "divider"})
        
        # YouTube Videos Section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:tv: TRENDING YOUTUBE VIDEOS (Last 24 Hours)*"
            }
        })
        
        if videos:
            for i, video in enumerate(videos, 1):
                section = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.format_video(video, i)
                    }
                }
                # Add thumbnail if available (validate URL)
                thumbnail = self._safe_url(video.get("thumbnail", ""))
                if thumbnail:
                    alt_text = video.get("title", "Video thumbnail")[:75]
                    section["accessory"] = {
                        "type": "image",
                        "image_url": thumbnail,
                        "alt_text": alt_text
                    }
                blocks.append(section)
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No new trending videos found in the last 24 hours._"
                }
            })
        
        blocks.append({"type": "divider"})
        
        # Articles Section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:newspaper: TRENDING ARTICLES (Last 24 Hours)*"
            }
        })
        
        if articles:
            for i, article in enumerate(articles, 1):
                section = {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.format_article(article, i)
                    }
                }
                # Add thumbnail if available (validate URL)
                thumbnail = self._safe_url(article.get("thumbnail", ""))
                if thumbnail:
                    alt_text = article.get("title", "Article thumbnail")[:75]
                    section["accessory"] = {
                        "type": "image",
                        "image_url": thumbnail,
                        "alt_text": alt_text
                    }
                blocks.append(section)
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No new trending articles found in the last 24 hours._"
                }
            })
        
        blocks.append({"type": "divider"})
        
        # Community Section (HN + Reddit)
        if community:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*:speech_balloon: COMMUNITY (Hacker News + Reddit)*"
                }
            })
            
            for i, post in enumerate(community, 1):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.format_community_post(post, i)
                    }
                })
            
            blocks.append({"type": "divider"})
        
        # Footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Report generated at {time_str} | Search terms: Cursor AI, Claude Code, Google Antigravity AI"
                }
            ]
        })
        
        return {"blocks": blocks}
    
    def send_report(
        self,
        videos: list[dict] = None,
        articles: list[dict] = None,
        releases: list[dict] = None,
        community: list[dict] = None,
        report_time: Optional[datetime] = None
    ) -> bool:
        """
        Build and send a report to Slack.
        
        Args:
            videos: List of trending videos
            articles: List of trending articles
            releases: List of GitHub releases
            community: List of community posts (HN/Reddit)
            report_time: Report generation time
            
        Returns:
            True if successful, False otherwise
        """
        payload = self.build_report(videos, articles, releases, community, report_time)
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                print("Report sent successfully to Slack!")
                return True
            else:
                print(f"Failed to send report. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"Error sending report to Slack: {e}")
            return False
    
    def send_test_message(self) -> bool:
        """Send a test message to verify webhook configuration."""
        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":white_check_mark: *AI Trends Reporter - Test Message*\n\nYour Slack integration is working correctly!"
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
    """Test the Slack reporter with sample data."""
    from dotenv import load_dotenv
    load_dotenv()
    
    # Sample data for testing
    sample_videos = [
        {
            "title": "Cursor AI: The Future of Coding",
            "channel": "Tech Channel",
            "url": "https://youtube.com/watch?v=example1",
            "stats": {"views": 50000, "likes": 2500, "comments": 300},
            "days_ago": 0
        },
    ]
    
    sample_articles = [
        {
            "title": "Cursor AI Raises $100M in Series B",
            "source": "TechCrunch",
            "url": "https://techcrunch.com/example",
            "hours_ago": 12,
            "category": "NEWS"
        },
    ]
    
    sample_releases = [
        {
            "repo": "getcursor/cursor",
            "name": "Cursor v0.45.0",
            "tag": "v0.45.0",
            "body": "New multi-file editing support and improved performance.",
            "url": "https://github.com/getcursor/cursor/releases/tag/v0.45.0",
            "hours_ago": 6
        }
    ]
    
    sample_community = [
        {
            "title": "How I use Claude Code for large refactors",
            "source": "Hacker News",
            "url": "https://news.ycombinator.com/item?id=12345",
            "points": 142,
            "comments": 45,
            "hours_ago": 8,
            "category": "WORKFLOW"
        }
    ]
    
    reporter = SlackReporter()
    
    # Send sample report
    print("Sending sample report...")
    reporter.send_report(sample_videos, sample_articles, sample_releases, sample_community)


if __name__ == "__main__":
    main()
