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
    
    def __init__(self, webhook_urls: Optional[list[str]] = None):
        """
        Initialize the Slack reporter.
        
        Args:
            webhook_urls: List of Slack webhook URLs. If not provided, reads from
                         SLACK_WEBHOOK_URL and SLACK_WEBHOOK_URL_2 env vars.
        """
        if webhook_urls:
            self.webhook_urls = webhook_urls
        else:
            # Collect all webhook URLs from environment
            urls = []
            if os.getenv("SLACK_WEBHOOK_URL"):
                urls.append(os.getenv("SLACK_WEBHOOK_URL"))
            if os.getenv("SLACK_WEBHOOK_URL_2"):
                urls.append(os.getenv("SLACK_WEBHOOK_URL_2"))
            self.webhook_urls = urls
        
        if not self.webhook_urls:
            raise ValueError("At least one Slack webhook URL is required. Set SLACK_WEBHOOK_URL environment variable.")
    
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
            return f"{hours_ago}h ago"
        elif hours_ago < 48:
            return "1 day ago"
        else:
            days = hours_ago // 24
            return f"{days} days ago"
    
    def _format_days_ago(self, days_ago: int) -> str:
        """Format days into human-readable time string."""
        if days_ago == 0:
            return "Today"
        elif days_ago == 1:
            return "Yesterday"
        else:
            return f"{days_ago} days ago"
    
    def _build_video_blocks(self, video: dict, index: int) -> list[dict]:
        """Build Slack blocks for a single video."""
        stats = video.get("stats", {})
        views = stats.get("views", 0)
        duration = stats.get("duration", "")
        days_ago = video.get("days_ago", 0)
        
        # Sanitize external input
        title = self._escape_mrkdwn(video.get('title', ''), max_length=200)
        channel = self._escape_mrkdwn(video.get('channel', ''), max_length=100)
        url = self._safe_url(video.get('url', ''))
        thumbnail = self._safe_url(video.get("thumbnail", ""))
        
        blocks = []
        
        # Build metadata line
        time_str = self._format_days_ago(days_ago)
        meta_parts = [f"{channel}", f"{views:,} views"]
        if duration:
            meta_parts.append(duration)
        meta_parts.append(time_str)
        meta_line = "  •  ".join(meta_parts)
        
        # Title section with thumbnail - include all info in one block
        title_text = f"*{index}. {title}*\n{meta_line}"
        if url:
            title_text += f"\n<{url}|:arrow_forward: Watch on YouTube>"
        
        section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": title_text
            }
        }
        
        if thumbnail:
            section["accessory"] = {
                "type": "image",
                "image_url": thumbnail,
                "alt_text": video.get("title", "Video thumbnail")[:75]
            }
        
        blocks.append(section)
        
        return blocks
    
    def _build_article_blocks(self, article: dict, index: int) -> list[dict]:
        """Build Slack blocks for a single article."""
        hours_ago = article.get("hours_ago", 0)
        category = article.get("category", "")
        
        # Sanitize external input
        title = self._escape_mrkdwn(article.get('title', ''), max_length=200)
        source = self._escape_mrkdwn(article.get('source', ''), max_length=100)
        summary = self._escape_mrkdwn(article.get('summary', ''), max_length=400)
        url = self._safe_url(article.get('url', ''))
        thumbnail = self._safe_url(article.get("thumbnail", ""))
        
        blocks = []
        
        # Category tag
        cat_tag = f"[{category}] " if category else ""
        
        # Title section with thumbnail
        title_text = f"*{index}. {cat_tag}{title}*"
        if summary:
            title_text += f"\n_{summary}_"
        if url:
            title_text += f"\n<{url}|:link: Read Article>"
        
        section = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": title_text
            }
        }
        
        if thumbnail:
            section["accessory"] = {
                "type": "image",
                "image_url": thumbnail,
                "alt_text": article.get("title", "Article thumbnail")[:75]
            }
        
        blocks.append(section)
        
        # Metadata context block
        time_str = self._format_time_ago(hours_ago)
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":newspaper: {source}"},
                {"type": "mrkdwn", "text": f":calendar: {time_str}"}
            ]
        })
        
        return blocks
    
    def _build_release_blocks(self, release: dict, index: int) -> list[dict]:
        """Build Slack blocks for a single GitHub release."""
        hours_ago = release.get("hours_ago", 0)
        
        # Sanitize external input
        repo = self._escape_mrkdwn(release.get('repo', ''), max_length=100)
        name = self._escape_mrkdwn(release.get('name', ''), max_length=200)
        tag = self._escape_mrkdwn(release.get('tag', ''), max_length=50)
        body = self._escape_mrkdwn(release.get('body', ''), max_length=250)
        url = self._safe_url(release.get('url', ''))
        
        blocks = []
        
        prerelease = " _(pre-release)_" if release.get("prerelease") else ""
        
        # Title section
        title_text = f"*{index}. {repo}*{prerelease}\n`{tag}` - {name}"
        if body:
            title_text += f"\n_{body}_"
        if url:
            title_text += f"\n<{url}|:link: View Release>"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": title_text
            }
        })
        
        # Metadata context block
        time_str = self._format_time_ago(hours_ago)
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":calendar: Released {time_str}"}
            ]
        })
        
        return blocks
    
    def _build_blog_blocks(self, post: dict, index: int) -> list[dict]:
        """Build Slack blocks for a single blog post."""
        hours_ago = post.get("hours_ago", 0)
        category = post.get("category", "")
        
        # Sanitize external input
        title = self._escape_mrkdwn(post.get('title', ''), max_length=200)
        source = self._escape_mrkdwn(post.get('source', ''), max_length=100)
        summary = self._escape_mrkdwn(post.get('summary', ''), max_length=300)
        url = self._safe_url(post.get('url', ''))
        
        blocks = []
        
        # Category tag
        cat_tag = f"[{category}] " if category else ""
        
        # Title section
        title_text = f"*{index}. {cat_tag}{title}*"
        if summary:
            title_text += f"\n_{summary}_"
        if url:
            title_text += f"\n<{url}|:link: Read Post>"
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": title_text
            }
        })
        
        # Metadata context block
        time_str = self._format_time_ago(hours_ago)
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f":office: {source}"},
                {"type": "mrkdwn", "text": f":calendar: {time_str}"}
            ]
        })
        
        return blocks
    
    def build_report(
        self,
        videos: list[dict] = None,
        articles: list[dict] = None,
        releases: list[dict] = None,
        blogs: list[dict] = None,
        report_time: Optional[datetime] = None
    ) -> dict:
        """
        Build a formatted Slack message payload.
        
        Args:
            videos: List of trending videos
            articles: List of trending articles
            releases: List of GitHub releases
            blogs: List of official blog posts
            report_time: Report generation time
            
        Returns:
            Slack message payload dictionary
        """
        videos = videos or []
        articles = articles or []
        releases = releases or []
        blogs = blogs or []
        
        if report_time is None:
            report_time = datetime.now()
        
        date_str = report_time.strftime("%A, %B %d, %Y")
        time_str = report_time.strftime("%I:%M %p")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":robot_face: AI Trends Report - {date_str}",
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Good morning! Here's your daily roundup of trending AI content."
                    }
                ]
            },
            {"type": "divider"}
        ]
        
        # GitHub Releases Section (if any)
        if releases:
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":rocket: Releases",
                    "emoji": True
                }
            })
            
            for i, release in enumerate(releases, 1):
                blocks.extend(self._build_release_blocks(release, i))
            
            blocks.append({"type": "divider"})
        
        # YouTube Videos Section
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":tv: YouTube Videos",
                "emoji": True
            }
        })
        
        if videos:
            for i, video in enumerate(videos, 1):
                blocks.extend(self._build_video_blocks(video, i))
        else:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "_No new trending videos found._"}
                ]
            })
        
        blocks.append({"type": "divider"})
        
        # Articles Section
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":newspaper: News Articles",
                "emoji": True
            }
        })
        
        if articles:
            for i, article in enumerate(articles, 1):
                blocks.extend(self._build_article_blocks(article, i))
        else:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "_No new trending articles found._"}
                ]
            })
        
        blocks.append({"type": "divider"})
        
        # Official Blogs Section (if any)
        if blogs:
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":memo: Official Blogs",
                    "emoji": True
                }
            })
            
            for i, post in enumerate(blogs, 1):
                blocks.extend(self._build_blog_blocks(post, i))
            
            blocks.append({"type": "divider"})
        
        # Footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Report generated at {time_str} | Sources: YouTube, Google News, Official Blogs"
                }
            ]
        })
        
        return {"blocks": blocks}
    
    def _send_to_webhook(self, webhook_url: str, payload: dict) -> bool:
        """
        Send a payload to a single webhook URL.
        
        Args:
            webhook_url: Slack webhook URL
            payload: Message payload
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                return True
            else:
                print(f"Failed to send to webhook. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.RequestException as e:
            print(f"Error sending to webhook: {e}")
            return False
    
    def send_report(
        self,
        videos: list[dict] = None,
        articles: list[dict] = None,
        releases: list[dict] = None,
        blogs: list[dict] = None,
        report_time: Optional[datetime] = None
    ) -> bool:
        """
        Build and send a report to all configured Slack webhooks.
        
        Args:
            videos: List of trending videos
            articles: List of trending articles
            releases: List of GitHub releases
            blogs: List of official blog posts
            report_time: Report generation time
            
        Returns:
            True if all sends successful, False if any failed
        """
        payload = self.build_report(videos, articles, releases, blogs, report_time)
        
        success_count = 0
        for i, webhook_url in enumerate(self.webhook_urls, 1):
            if self._send_to_webhook(webhook_url, payload):
                success_count += 1
                print(f"Report sent successfully to Slack webhook {i}!")
            else:
                print(f"Failed to send report to Slack webhook {i}")
        
        return success_count == len(self.webhook_urls)
    
    def send_test_message(self) -> bool:
        """Send a test message to all configured webhooks."""
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
        
        success_count = 0
        for i, webhook_url in enumerate(self.webhook_urls, 1):
            if self._send_to_webhook(webhook_url, payload):
                success_count += 1
                print(f"Test message sent successfully to webhook {i}!")
            else:
                print(f"Failed to send test message to webhook {i}")
        
        return success_count == len(self.webhook_urls)


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
            "stats": {"views": 50000, "likes": 2500, "comments": 300, "duration": "12:34"},
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
    
    sample_blogs = [
        {
            "title": "Introducing Claude 3.5 Sonnet",
            "source": "Anthropic",
            "url": "https://anthropic.com/news/example",
            "summary": "Our most capable model yet, with improved reasoning and coding abilities.",
            "hours_ago": 24,
            "category": "RELEASE"
        }
    ]
    
    reporter = SlackReporter()
    
    # Send sample report
    print("Sending sample report...")
    reporter.send_report(sample_videos, sample_articles, sample_releases, sample_blogs)


if __name__ == "__main__":
    main()
