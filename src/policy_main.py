#!/usr/bin/env python3
"""
YouTube Policy Intelligence Monitor - Main orchestration script.

Fetches policy-related content from official YouTube sources,
community discussions, legal/policy analysis, and expert channels,
then sends a formatted 4-tier report to Slack.

Usage:
    python policy_main.py              # Run full report
    python policy_main.py --test       # Send test message to Slack
    python policy_main.py --dry-run    # Fetch data but don't send to Slack
    python policy_main.py --official   # Only fetch official sources
    python policy_main.py --community  # Only fetch community sources
    python policy_main.py --legal      # Only fetch legal sources
    python policy_main.py --experts    # Only fetch expert channels
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


def get_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "days_lookback": int(os.getenv("POLICY_DAYS_LOOKBACK", "1")),
        # Display limits per tier
        "top_official": int(os.getenv("POLICY_TOP_OFFICIAL", "5")),
        "top_community": int(os.getenv("POLICY_TOP_COMMUNITY", "5")),
        "top_legal": int(os.getenv("POLICY_TOP_LEGAL", "3")),
        "top_experts": int(os.getenv("POLICY_TOP_EXPERTS", "3")),
    }


def fetch_official(config: dict) -> list[dict]:
    """Fetch official YouTube policy updates."""
    from youtube_policy_fetcher import YouTubePolicyFetcher
    from policy_categorizer import categorize_policy_items
    
    try:
        fetcher = YouTubePolicyFetcher()
        posts = fetcher.fetch_all_official(
            days_back=config["days_lookback"],
            top_n=config["top_official"],
            filter_keywords=True
        )
        # Add categories
        posts = categorize_policy_items(posts)
        print(f"Found {len(posts)} official policy updates")
        return posts
    except Exception as e:
        print(f"Error fetching official sources: {e}")
        return []


def fetch_community(config: dict) -> list[dict]:
    """Fetch community discussions from Reddit."""
    from reddit_fetcher import RedditFetcher
    from policy_categorizer import categorize_policy_items
    
    try:
        fetcher = RedditFetcher()
        posts = fetcher.fetch_all_subreddits(
            days_back=config["days_lookback"],
            top_n=config["top_community"],
            filter_keywords=True
        )
        # Add categories
        posts = categorize_policy_items(posts)
        print(f"Found {len(posts)} community discussions")
        return posts
    except Exception as e:
        print(f"Error fetching community sources: {e}")
        return []


def fetch_legal(config: dict) -> list[dict]:
    """Fetch legal/policy analysis."""
    from legal_fetcher import LegalFetcher
    from policy_categorizer import categorize_policy_items
    
    try:
        fetcher = LegalFetcher()
        posts = fetcher.fetch_all_legal(
            days_back=config["days_lookback"],
            top_n=config["top_legal"],
            filter_keywords=True
        )
        # Add categories
        posts = categorize_policy_items(posts)
        print(f"Found {len(posts)} legal/policy analysis posts")
        return posts
    except Exception as e:
        print(f"Error fetching legal sources: {e}")
        return []


def fetch_experts(config: dict) -> list[dict]:
    """Fetch expert channel videos."""
    from expert_channel_fetcher import ExpertChannelFetcher
    from policy_categorizer import categorize_policy_items
    
    try:
        fetcher = ExpertChannelFetcher()
        videos = fetcher.fetch_all_channels(
            days_back=config["days_lookback"],
            top_n=config["top_experts"]
        )
        # Add categories
        videos = categorize_policy_items(videos)
        print(f"Found {len(videos)} expert videos")
        return videos
    except Exception as e:
        print(f"Error fetching expert channels: {e}")
        return []


def send_report(
    official: list[dict],
    community: list[dict],
    legal: list[dict],
    experts: list[dict]
) -> bool:
    """Send report to Slack."""
    from policy_slack_reporter import PolicySlackReporter
    
    try:
        reporter = PolicySlackReporter()
        return reporter.send_report(
            official=official,
            community=community,
            legal=legal,
            experts=experts
        )
    except ValueError as e:
        print(f"Slack configuration error: {e}")
        return False
    except Exception as e:
        print(f"Error sending report: {e}")
        return False


def send_test_message() -> bool:
    """Send a test message to Slack."""
    from policy_slack_reporter import PolicySlackReporter
    
    try:
        reporter = PolicySlackReporter()
        return reporter.send_test_message()
    except ValueError as e:
        print(f"Slack configuration error: {e}")
        return False


def print_results(
    official: list[dict],
    community: list[dict],
    legal: list[dict],
    experts: list[dict]
):
    """Print results to console."""
    from policy_categorizer import get_policy_category_emoji
    
    print("\n" + "=" * 60)
    print("YOUTUBE POLICY INTELLIGENCE REPORT")
    print("=" * 60)
    
    # Tier 1: Official
    print("\n🔴 TIER 1: OFFICIAL UPDATES")
    print("-" * 40)
    if official:
        for i, post in enumerate(official, 1):
            cat = post.get('category', '')
            cat_emoji = get_policy_category_emoji(cat) if cat else ""
            cat_str = f"{cat_emoji} [{cat}] " if cat else ""
            print(f"\n{i}. {cat_str}{post['title']}")
            print(f"   Source: {post['source']}")
            print(f"   Published: {post.get('hours_ago', 0)} hours ago")
            print(f"   URL: {post.get('url', '')}")
    else:
        print("No official updates found.")
    
    # Tier 2: Community
    print("\n\n🟠 TIER 2: COMMUNITY SIGNALS")
    print("-" * 40)
    if community:
        for i, post in enumerate(community, 1):
            cat = post.get('category', '')
            cat_emoji = get_policy_category_emoji(cat) if cat else ""
            cat_str = f"{cat_emoji} [{cat}] " if cat else ""
            print(f"\n{i}. {cat_str}{post['title']}")
            print(f"   Source: {post['source']} by u/{post.get('author', 'unknown')}")
            print(f"   Posted: {post.get('hours_ago', 0)} hours ago")
            print(f"   URL: {post.get('url', '')}")
    else:
        print("No community discussions found.")
    
    # Tier 3: Legal
    print("\n\n🔵 TIER 3: LEGAL ANALYSIS")
    print("-" * 40)
    if legal:
        for i, post in enumerate(legal, 1):
            cat = post.get('category', '')
            cat_emoji = get_policy_category_emoji(cat) if cat else ""
            cat_str = f"{cat_emoji} [{cat}] " if cat else ""
            print(f"\n{i}. {cat_str}{post['title']}")
            print(f"   Source: {post['source']}")
            print(f"   Published: {post.get('hours_ago', 0)} hours ago")
            print(f"   URL: {post.get('url', '')}")
    else:
        print("No legal analysis found.")
    
    # Tier 4: Experts
    print("\n\n🟣 TIER 4: EXPERT COMMENTARY")
    print("-" * 40)
    if experts:
        for i, video in enumerate(experts, 1):
            cat = video.get('category', '')
            cat_emoji = get_policy_category_emoji(cat) if cat else ""
            cat_str = f"{cat_emoji} [{cat}] " if cat else ""
            print(f"\n{i}. {cat_str}{video['title']}")
            print(f"   Channel: {video['source']}")
            print(f"   Published: {video.get('hours_ago', 0)} hours ago")
            print(f"   URL: {video.get('url', '')}")
    else:
        print("No expert videos found.")
    
    print("\n" + "=" * 60)
    print("REMINDER: Check manual sources for additional updates")
    print("  - https://www.youtube.com/policy/updates")
    print("  - https://support.google.com/youtube/answer/10008196")
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="YouTube Policy Intelligence - Monitor policy changes and send to Slack"
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
        "--official",
        action="store_true",
        help="Only fetch official sources (Tier 1)"
    )
    parser.add_argument(
        "--community",
        action="store_true",
        help="Only fetch community sources (Tier 2)"
    )
    parser.add_argument(
        "--legal",
        action="store_true",
        help="Only fetch legal sources (Tier 3)"
    )
    parser.add_argument(
        "--experts",
        action="store_true",
        help="Only fetch expert channels (Tier 4)"
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Skip keyword filtering (fetch all content)"
    )
    
    args = parser.parse_args()
    
    # Load environment
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting YouTube Policy Intelligence Monitor...")
    load_environment()
    
    # Test mode
    if args.test:
        print("\nSending test message to Slack...")
        success = send_test_message()
        sys.exit(0 if success else 1)
    
    # Get configuration
    config = get_config()
    print(f"Looking back: {config['days_lookback']} days")
    print(f"Display limits: {config['top_official']} official, {config['top_community']} community, "
          f"{config['top_legal']} legal, {config['top_experts']} experts")
    
    # Determine what to fetch
    fetch_all = not (args.official or args.community or args.legal or args.experts)
    
    # Fetch data
    official = []
    community = []
    legal = []
    experts = []
    
    # Tier 1: Official
    if fetch_all or args.official:
        print("\nFetching official YouTube sources (Tier 1)...")
        official = fetch_official(config)
    
    # Tier 2: Community
    if fetch_all or args.community:
        print("\nFetching community discussions (Tier 2)...")
        community = fetch_community(config)
    
    # Tier 3: Legal
    if fetch_all or args.legal:
        print("\nFetching legal/policy analysis (Tier 3)...")
        legal = fetch_legal(config)
    
    # Tier 4: Experts
    if fetch_all or args.experts:
        print("\nFetching expert channels (Tier 4)...")
        experts = fetch_experts(config)
    
    # Output results
    if args.dry_run:
        print_results(official, community, legal, experts)
        print("\n[Dry run - report not sent to Slack]")
    else:
        print("\nSending report to Slack...")
        success = send_report(official, community, legal, experts)
        
        if success:
            print("\nPolicy report sent successfully!")
        else:
            print("\nFailed to send policy report to Slack.")
            # Still print results to console as backup
            print_results(official, community, legal, experts)
            sys.exit(1)
    
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Done!")


if __name__ == "__main__":
    main()
