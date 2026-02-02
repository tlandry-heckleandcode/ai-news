#!/usr/bin/env python3
"""
AI Trends Reporter - Main orchestration script.

Fetches trending YouTube videos, news articles, GitHub releases,
and community posts (Hacker News, Reddit) about AI coding tools,
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
        "days_lookback": int(os.getenv("DAYS_LOOKBACK", "1")),
        # Result limits per source
        "top_videos": int(os.getenv("TOP_VIDEOS", "5")),
        "top_articles": int(os.getenv("TOP_ARTICLES", "5")),
        "top_releases": int(os.getenv("TOP_RELEASES", "3")),
        "top_hn": int(os.getenv("TOP_HN", "3")),
        "top_reddit": int(os.getenv("TOP_REDDIT", "3")),
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
            top_n=config["top_videos"]
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
    from categorizer import categorize_items
    
    try:
        fetcher = NewsFetcher()
        articles = fetcher.fetch_trending_articles(
            search_terms=config["search_terms"],
            days_back=config["days_lookback"],
            max_results_per_term=config["max_results_per_term"],
            top_n=config["top_articles"]
        )
        # Add categories
        articles = categorize_items(articles)
        print(f"Found {len(articles)} trending articles")
        return articles
    except Exception as e:
        print(f"Error fetching articles: {e}")
        return []


def fetch_releases(config: dict) -> list[dict]:
    """Fetch GitHub releases."""
    from github_fetcher import GitHubFetcher
    
    try:
        fetcher = GitHubFetcher()
        releases = fetcher.fetch_all_releases(
            days_back=config["days_lookback"] + 6,  # Look back a week for releases
            top_n=config["top_releases"]
        )
        print(f"Found {len(releases)} recent releases")
        return releases
    except Exception as e:
        print(f"Error fetching releases: {e}")
        return []


def fetch_hackernews(config: dict) -> list[dict]:
    """Fetch Hacker News posts."""
    from hackernews_fetcher import HackerNewsFetcher
    from categorizer import categorize_items
    
    try:
        fetcher = HackerNewsFetcher()
        stories = fetcher.fetch_trending_stories(
            days_back=config["days_lookback"],
            top_n=config["top_hn"]
        )
        # Add categories
        stories = categorize_items(stories)
        print(f"Found {len(stories)} trending HN stories")
        return stories
    except Exception as e:
        print(f"Error fetching HN stories: {e}")
        return []


def fetch_reddit(config: dict) -> list[dict]:
    """Fetch Reddit posts."""
    from reddit_fetcher import RedditFetcher
    from categorizer import categorize_items
    
    try:
        fetcher = RedditFetcher()
        posts = fetcher.fetch_trending_posts(
            days_back=config["days_lookback"],
            top_n=config["top_reddit"]
        )
        # Add categories
        posts = categorize_items(posts)
        print(f"Found {len(posts)} trending Reddit posts")
        return posts
    except Exception as e:
        print(f"Error fetching Reddit posts: {e}")
        return []


def combine_community_posts(hn_stories: list[dict], reddit_posts: list[dict], top_n: int = 6) -> list[dict]:
    """Combine and deduplicate community posts from HN and Reddit."""
    from deduplicator import deduplicate_items
    
    # Combine all posts
    all_posts = hn_stories + reddit_posts
    
    # Normalize score key
    for post in all_posts:
        post["score"] = post.get("points", 0) or post.get("score", 0)
    
    # Deduplicate
    deduped = deduplicate_items(all_posts, threshold=0.8, score_key="score")
    
    # Sort by score and limit
    deduped.sort(key=lambda x: x.get("score", 0), reverse=True)
    return deduped[:top_n]


def send_report(
    videos: list[dict],
    articles: list[dict],
    releases: list[dict],
    community: list[dict]
) -> bool:
    """Send report to Slack."""
    from slack_reporter import SlackReporter
    
    try:
        reporter = SlackReporter()
        return reporter.send_report(
            videos=videos,
            articles=articles,
            releases=releases,
            community=community
        )
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


def print_results(
    videos: list[dict],
    articles: list[dict],
    releases: list[dict],
    community: list[dict]
):
    """Print results to console."""
    print("\n" + "=" * 60)
    print("AI TRENDS REPORT")
    print("=" * 60)
    
    # Releases
    if releases:
        print("\n:rocket: RELEASES")
        print("-" * 40)
        for i, release in enumerate(releases, 1):
            print(f"\n{i}. {release['repo']} - {release['name']}")
            print(f"   Tag: {release['tag']} | {release.get('hours_ago', 0)} hours ago")
            print(f"   URL: {release['url']}")
    
    # Videos
    print("\n:tv: TRENDING YOUTUBE VIDEOS (Last 24 Hours)")
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
    
    # Articles
    print("\n\n:newspaper: TRENDING ARTICLES (Last 24 Hours)")
    print("-" * 40)
    if articles:
        for i, article in enumerate(articles, 1):
            category = article.get('category', '')
            cat_str = f"[{category}] " if category else ""
            print(f"\n{i}. {cat_str}{article['title']}")
            print(f"   Source: {article['source']}")
            print(f"   Published: {article.get('hours_ago', 0)} hours ago")
            print(f"   URL: {article['url']}")
    else:
        print("No trending articles found.")
    
    # Community
    if community:
        print("\n\n:speech_balloon: COMMUNITY (Hacker News + Reddit)")
        print("-" * 40)
        for i, post in enumerate(community, 1):
            category = post.get('category', 'DISCUSSION')
            score = post.get('points', 0) or post.get('score', 0)
            print(f"\n{i}. [{category}] {post['title']}")
            print(f"   {post.get('source', '')} | {score} pts | {post.get('comments', 0)} comments")
            print(f"   URL: {post.get('url', '')}")
    
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
    parser.add_argument(
        "--no-releases",
        action="store_true",
        help="Skip fetching GitHub releases"
    )
    parser.add_argument(
        "--no-community",
        action="store_true",
        help="Skip fetching community posts (HN/Reddit)"
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
    print(f"Limits: {config['top_videos']} videos, {config['top_articles']} articles, "
          f"{config['top_releases']} releases, {config['top_hn']} HN, {config['top_reddit']} Reddit")
    
    # Determine what to fetch
    fetch_only_videos = args.videos and not args.articles
    fetch_only_articles = args.articles and not args.videos
    
    # Fetch data
    videos = []
    articles = []
    releases = []
    community = []
    
    # GitHub Releases
    if not args.no_releases and not fetch_only_videos and not fetch_only_articles:
        print("\nFetching GitHub releases...")
        releases = fetch_releases(config)
    
    # YouTube Videos
    if not fetch_only_articles:
        print("\nFetching YouTube videos...")
        videos = fetch_videos(config)
    
    # News Articles
    if not fetch_only_videos:
        print("\nFetching news articles...")
        articles = fetch_articles(config)
    
    # Community (HN + Reddit)
    if not args.no_community and not fetch_only_videos and not fetch_only_articles:
        print("\nFetching Hacker News stories...")
        hn_stories = fetch_hackernews(config)
        
        print("\nFetching Reddit posts...")
        reddit_posts = fetch_reddit(config)
        
        # Combine and deduplicate community posts
        total_community = config["top_hn"] + config["top_reddit"]
        community = combine_community_posts(hn_stories, reddit_posts, top_n=total_community)
        print(f"Combined {len(community)} unique community posts")
    
    # Output results
    if args.dry_run:
        print_results(videos, articles, releases, community)
        print("\n[Dry run - report not sent to Slack]")
    else:
        print("\nSending report to Slack...")
        success = send_report(videos, articles, releases, community)
        
        if success:
            print("\nReport sent successfully!")
        else:
            print("\nFailed to send report to Slack.")
            # Still print results to console as backup
            print_results(videos, articles, releases, community)
            sys.exit(1)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done!")


if __name__ == "__main__":
    main()
