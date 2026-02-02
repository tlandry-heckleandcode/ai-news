"""
Slack webhook integration for sending formatted reports.
"""

import os
from datetime import datetime
from typing import Optional
import requests


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
    
    def format_video(self, video: dict, index: int) -> str:
        """Format a single video for display."""
        stats = video.get("stats", {})
        views = stats.get("views", 0)
        days_ago = video.get("days_ago", 0)
        
        # Format views with commas
        views_str = f"{views:,}"
        
        # Time description
        if days_ago == 0:
            time_str = "Today"
        elif days_ago == 1:
            time_str = "1 day ago"
        else:
            time_str = f"{days_ago} days ago"
        
        return (
            f"*{index}. {video['title']}*\n"
            f"   Channel: {video['channel']}\n"
            f"   Views: {views_str} | Published: {time_str}\n"
            f"   <{video['url']}|Watch on YouTube>"
        )
    
    def format_article(self, article: dict, index: int) -> str:
        """Format a single article for display."""
        hours_ago = article.get("hours_ago", 0)
        
        # Time description
        if hours_ago < 1:
            time_str = "Just now"
        elif hours_ago < 24:
            time_str = f"{hours_ago} hours ago"
        elif hours_ago < 48:
            time_str = "1 day ago"
        else:
            days = hours_ago // 24
            time_str = f"{days} days ago"
        
        return (
            f"*{index}. {article['title']}*\n"
            f"   Source: {article['source']}\n"
            f"   Published: {time_str}\n"
            f"   <{article['url']}|Read Article>"
        )
    
    def build_report(
        self,
        videos: list[dict],
        articles: list[dict],
        report_time: Optional[datetime] = None
    ) -> dict:
        """
        Build a formatted Slack message payload.
        
        Args:
            videos: List of trending videos
            articles: List of trending articles
            report_time: Report generation time
            
        Returns:
            Slack message payload dictionary
        """
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
        
        # YouTube Videos Section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:tv: TRENDING YOUTUBE VIDEOS (Last 7 Days)*"
            }
        })
        
        if videos:
            for i, video in enumerate(videos, 1):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.format_video(video, i)
                    }
                })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No new trending videos found in the last 7 days._"
                }
            })
        
        blocks.append({"type": "divider"})
        
        # Articles Section
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*:newspaper: TRENDING ARTICLES (Last 7 Days)*"
            }
        })
        
        if articles:
            for i, article in enumerate(articles, 1):
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": self.format_article(article, i)
                    }
                })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No new trending articles found in the last 7 days._"
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
        videos: list[dict],
        articles: list[dict],
        report_time: Optional[datetime] = None
    ) -> bool:
        """
        Build and send a report to Slack.
        
        Args:
            videos: List of trending videos
            articles: List of trending articles
            report_time: Report generation time
            
        Returns:
            True if successful, False otherwise
        """
        payload = self.build_report(videos, articles, report_time)
        
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
            "days_ago": 2
        },
        {
            "title": "Claude Code vs GitHub Copilot",
            "channel": "Developer Weekly",
            "url": "https://youtube.com/watch?v=example2",
            "stats": {"views": 35000, "likes": 1800, "comments": 200},
            "days_ago": 3
        }
    ]
    
    sample_articles = [
        {
            "title": "Cursor AI Raises $100M in Series B",
            "source": "TechCrunch",
            "url": "https://techcrunch.com/example",
            "hours_ago": 12
        },
        {
            "title": "Google Announces New AI Coding Assistant",
            "source": "The Verge",
            "url": "https://theverge.com/example",
            "hours_ago": 36
        }
    ]
    
    reporter = SlackReporter()
    
    # Send test message first
    print("Sending test message...")
    reporter.send_test_message()
    
    # Then send sample report
    print("\nSending sample report...")
    reporter.send_report(sample_videos, sample_articles)


if __name__ == "__main__":
    main()
