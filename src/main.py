#!/usr/bin/env python3
"""
AI Trends Reporter - Main orchestration script.

Fetches trending YouTube videos and news articles about AI coding tools,
then sends a formatted report to Slack.

Usage:
    python main.py              # Run full report
    python main.py --test       # Send test message to Slack
    python main.py --dry-run    # Fetch data but don't send to Slack
    python main.py --videos     # Only fetch videos
    python main.py --articles   # Only fetch articles
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv


def load_environment():
    """Load environment variables from .env file."""
    # Try multiple locations for .env file
    env_paths = [
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent.parent / "config" / ".env",
        Path.cwd() / ".env",
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded environment from: {env_path}")
            return True
    
    # Load from environment anyway (for production)
    load_dotenv()
    return False


def get_search_terms() -> list[str]:
    """Get search terms from environment or use defaults."""
    terms_str = os.getenv("SEARCH_TERMS")
    if terms_str:
        return [term.strip() for term in terms_str.split(",")]
    return ["Cursor AI", "Claude Code", "Google Antigravity AI"]


def get_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "search_terms": get_search_terms(),
        "max_results_per_term": int(os.getenv("MAX_RESULTS_PER_TERM", "10")),
        "days_lookback": int(os.getenv("DAYS_LOOKBACK", "7")),
        "top_n": 3,
    }


def fetch_videos(config: dict) -> list[dict]:
    """Fetch trending YouTube videos."""
    from youtube_fetcher import YouTubeFetcher
    
    try:
        fetcher = YouTubeFetcher()
        videos = fetcher.fetch_trending_videos(
            search_terms=config["search_terms"],
            days_back=config["days_lookback"],
            max_results_per_term=config["max_results_per_term"],
            top_n=config["top_n"]
        )
        print(f"Found {len(videos)} trending videos")
        return videos
    except ValueError as e:
        print(f"YouTube API error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error fetching videos: {e}")
        return []


def fetch_articles(config: dict) -> list[dict]:
    """Fetch trending news articles."""
    from news_fetcher import NewsFetcher
    
    try:
        fetcher = NewsFetcher()
        articles = fetcher.fetch_trending_articles(
            search_terms=config["search_terms"],
            days_back=config["days_lookback"],
            max_results_per_term=config["max_results_per_term"],
            top_n=config["top_n"]
        )
        print(f"Found {len(articles)} trending articles")
        return articles
    except Exception as e:
        print(f"Error fetching articles: {e}")
        return []


def send_report(videos: list[dict], articles: list[dict]) -> bool:
    """Send report to Slack."""
    from slack_reporter import SlackReporter
    
    try:
        reporter = SlackReporter()
        return reporter.send_report(videos, articles)
    except ValueError as e:
        print(f"Slack configuration error: {e}")
        return False
    except Exception as e:
        print(f"Error sending report: {e}")
        return False


def send_test_message() -> bool:
    """Send a test message to Slack."""
    from slack_reporter import SlackReporter
    
    try:
        reporter = SlackReporter()
        return reporter.send_test_message()
    except ValueError as e:
        print(f"Slack configuration error: {e}")
        return False


def print_results(videos: list[dict], articles: list[dict]):
    """Print results to console."""
    print("\n" + "=" * 60)
    print("AI TRENDS REPORT")
    print("=" * 60)
    
    print("\nTRENDING YOUTUBE VIDEOS (Last 7 Days)")
    print("-" * 40)
    if videos:
        for i, video in enumerate(videos, 1):
            stats = video.get("stats", {})
            print(f"\n{i}. {video['title']}")
            print(f"   Channel: {video['channel']}")
            print(f"   Views: {stats.get('views', 0):,} | {video.get('days_ago', 0)} days ago")
            print(f"   URL: {video['url']}")
    else:
        print("No trending videos found.")
    
    print("\n\nTRENDING ARTICLES (Last 7 Days)")
    print("-" * 40)
    if articles:
        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Source: {article['source']}")
            print(f"   Published: {article.get('hours_ago', 0)} hours ago")
            print(f"   URL: {article['url']}")
    else:
        print("No trending articles found.")
    
    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI Trends Reporter - Fetch and report trending AI content to Slack"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Send a test message to Slack"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but don't send to Slack (print to console instead)"
    )
    parser.add_argument(
        "--videos",
        action="store_true",
        help="Only fetch videos"
    )
    parser.add_argument(
        "--articles",
        action="store_true",
        help="Only fetch articles"
    )
    
    args = parser.parse_args()
    
    # Load environment
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting AI Trends Reporter...")
    load_environment()
    
    # Test mode
    if args.test:
        print("\nSending test message to Slack...")
        success = send_test_message()
        sys.exit(0 if success else 1)
    
    # Get configuration
    config = get_config()
    print(f"Search terms: {', '.join(config['search_terms'])}")
    print(f"Looking back: {config['days_lookback']} days")
    
    # Determine what to fetch
    fetch_videos_flag = not args.articles or args.videos
    fetch_articles_flag = not args.videos or args.articles
    
    # Fetch data
    videos = []
    articles = []
    
    if fetch_videos_flag:
        print("\nFetching YouTube videos...")
        videos = fetch_videos(config)
    
    if fetch_articles_flag:
        print("\nFetching news articles...")
        articles = fetch_articles(config)
    
    # Output results
    if args.dry_run:
        print_results(videos, articles)
        print("\n[Dry run - report not sent to Slack]")
    else:
        print("\nSending report to Slack...")
        success = send_report(videos, articles)
        
        if success:
            print("\nReport sent successfully!")
        else:
            print("\nFailed to send report to Slack.")
            # Still print results to console as backup
            print_results(videos, articles)
            sys.exit(1)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done!")


if __name__ == "__main__":
    main()
