#!/usr/bin/env python3
"""
AI Trends Reporter - Main orchestration script.

Fetches trending YouTube videos, news articles, GitHub releases,
and official blog posts about AI coding tools,
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
        # Result limits per source (display limits)
        "top_videos": int(os.getenv("TOP_VIDEOS", "5")),
        "top_articles": int(os.getenv("TOP_ARTICLES", "3")),
        "top_releases": int(os.getenv("TOP_RELEASES", "3")),
        "top_blogs": int(os.getenv("TOP_BLOGS", "3")),
        # Fetch pool size (fetch more, then filter down to display limits)
        "fetch_pool_size": int(os.getenv("FETCH_POOL_SIZE", "10")),
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


def fetch_articles(config: dict, use_pool_size: bool = True) -> list[dict]:
    """Fetch trending news articles.
    
    Args:
        config: Configuration dictionary
        use_pool_size: If True, fetch pool_size items for filtering. If False, fetch top_articles.
    """
    from news_fetcher import NewsFetcher
    from categorizer import categorize_items
    
    # Fetch more items if we'll be filtering them down
    fetch_limit = config["fetch_pool_size"] if use_pool_size else config["top_articles"]
    
    try:
        fetcher = NewsFetcher()
        articles = fetcher.fetch_trending_articles(
            search_terms=config["search_terms"],
            days_back=config["days_lookback"],
            max_results_per_term=config["max_results_per_term"],
            top_n=fetch_limit
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
            days_back=config["days_lookback"],
            top_n=config["top_releases"]
        )
        print(f"Found {len(releases)} recent releases")
        return releases
    except Exception as e:
        print(f"Error fetching releases: {e}")
        return []


def fetch_blogs(config: dict, use_pool_size: bool = True) -> list[dict]:
    """Fetch official blog posts.
    
    Args:
        config: Configuration dictionary
        use_pool_size: If True, fetch pool_size items for filtering. If False, fetch top_blogs.
    """
    from blog_fetcher import BlogFetcher
    from categorizer import categorize_items
    
    # Fetch more items if we'll be filtering them down
    fetch_limit = config["fetch_pool_size"] if use_pool_size else config["top_blogs"]
    
    try:
        fetcher = BlogFetcher()
        posts = fetcher.fetch_all_blog_posts(
            days_back=config["days_lookback"],
            top_n=fetch_limit
        )
        # Add categories
        posts = categorize_items(posts)
        print(f"Found {len(posts)} official blog posts")
        return posts
    except Exception as e:
        print(f"Error fetching blog posts: {e}")
        return []


def apply_relevance_filter(
    articles: list[dict],
    blogs: list[dict],
    top_articles: int = 3,
    top_blogs: int = 3
) -> tuple[list[dict], list[dict]]:
    """Apply LLM relevance filtering to articles and blogs, then truncate to display limits."""
    from relevance_filter import filter_by_relevance, is_filtering_enabled
    
    if not is_filtering_enabled():
        print("LLM filtering disabled")
        # Still truncate to display limits
        return articles[:top_articles], blogs[:top_blogs]
    
    print("\nApplying LLM relevance filtering...")
    
    filtered_articles = filter_by_relevance(articles, "news articles")
    filtered_blogs = filter_by_relevance(blogs, "blog posts")
    
    # Truncate to display limits
    filtered_articles = filtered_articles[:top_articles]
    filtered_blogs = filtered_blogs[:top_blogs]
    
    return filtered_articles, filtered_blogs


def send_report(
    videos: list[dict],
    articles: list[dict],
    releases: list[dict],
    blogs: list[dict]
) -> bool:
    """Send report to Slack."""
    from slack_reporter import SlackReporter
    
    try:
        reporter = SlackReporter()
        return reporter.send_report(
            videos=videos,
            articles=articles,
            releases=releases,
            blogs=blogs
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
    blogs: list[dict]
):
    """Print results to console."""
    print("\n" + "=" * 60)
    print("AI TRENDS REPORT")
    print("=" * 60)
    
    # Releases
    if releases:
        print("\nRELEASES")
        print("-" * 40)
        for i, release in enumerate(releases, 1):
            print(f"\n{i}. {release['repo']} - {release['name']}")
            print(f"   Tag: {release['tag']} | {release.get('hours_ago', 0)} hours ago")
            print(f"   URL: {release['url']}")
    
    # Videos
    print("\nTRENDING YOUTUBE VIDEOS")
    print("-" * 40)
    if videos:
        for i, video in enumerate(videos, 1):
            stats = video.get("stats", {})
            duration = stats.get("duration", "")
            duration_str = f" | Duration: {duration}" if duration else ""
            print(f"\n{i}. {video['title']}")
            print(f"   Channel: {video['channel']}")
            print(f"   Views: {stats.get('views', 0):,}{duration_str} | {video.get('days_ago', 0)} days ago")
            print(f"   URL: {video['url']}")
    else:
        print("No trending videos found.")
    
    # Articles
    print("\n\nTRENDING ARTICLES")
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
    
    # Official Blogs
    if blogs:
        print("\n\nOFFICIAL BLOGS")
        print("-" * 40)
        for i, post in enumerate(blogs, 1):
            category = post.get('category', '')
            cat_str = f"[{category}] " if category else ""
            print(f"\n{i}. {cat_str}{post['title']}")
            print(f"   Source: {post.get('source', '')}")
            print(f"   Published: {post.get('hours_ago', 0)} hours ago")
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
        "--no-blogs",
        action="store_true",
        help="Skip fetching official blog posts"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Skip LLM relevance filtering"
    )
    
    args = parser.parse_args()
    
    # Load environment
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting AI Trends Reporter...")
    load_environment()
    
    # Override LLM filter if --no-filter flag
    if args.no_filter:
        os.environ["LLM_FILTER_ENABLED"] = "false"
    
    # Test mode
    if args.test:
        print("\nSending test message to Slack...")
        success = send_test_message()
        sys.exit(0 if success else 1)
    
    # Get configuration
    config = get_config()
    print(f"Search terms: {', '.join(config['search_terms'])}")
    print(f"Looking back: {config['days_lookback']} days")
    print(f"Display limits: {config['top_videos']} videos, {config['top_articles']} articles, "
          f"{config['top_releases']} releases, {config['top_blogs']} blogs")
    
    # Determine if we should use pool size (fetch more for filtering)
    from relevance_filter import is_filtering_enabled
    use_pool_size = is_filtering_enabled() and not args.no_filter
    if use_pool_size:
        print(f"Fetch pool size: {config['fetch_pool_size']} (for LLM filtering)")
    
    # Determine what to fetch
    fetch_only_videos = args.videos and not args.articles
    fetch_only_articles = args.articles and not args.videos
    
    # Fetch data
    videos = []
    articles = []
    releases = []
    blogs = []
    
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
        articles = fetch_articles(config, use_pool_size=use_pool_size)
    
    # Official Blogs
    if not args.no_blogs and not fetch_only_videos and not fetch_only_articles:
        print("\nFetching official blog posts...")
        blogs = fetch_blogs(config, use_pool_size=use_pool_size)
    
    # Apply LLM relevance filtering and truncate to display limits
    if articles or blogs:
        articles, blogs = apply_relevance_filter(
            articles,
            blogs,
            top_articles=config["top_articles"],
            top_blogs=config["top_blogs"]
        )
    
    # Output results
    if args.dry_run:
        print_results(videos, articles, releases, blogs)
        print("\n[Dry run - report not sent to Slack]")
    else:
        print("\nSending report to Slack...")
        success = send_report(videos, articles, releases, blogs)
        
        if success:
            print("\nReport sent successfully!")
        else:
            print("\nFailed to send report to Slack.")
            # Still print results to console as backup
            print_results(videos, articles, releases, blogs)
            sys.exit(1)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done!")


if __name__ == "__main__":
    main()
