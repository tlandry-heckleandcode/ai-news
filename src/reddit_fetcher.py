"""
Reddit fetcher for monitoring AI tool subreddits.

Uses Reddit's public JSON API (no authentication required).
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import requests

from sanitizer import sanitize_title, sanitize_description


class RedditFetcher:
    """Fetches trending posts from Reddit subreddits."""
    
    DEFAULT_SUBREDDITS = [
        "cursor",
        "ClaudeAI",
        "LocalLLaMA",
    ]
    
    DEFAULT_SEARCH_TERMS = [
        "Cursor AI",
        "Claude Code",
        "AI coding",
    ]
    
    def __init__(self):
        """Initialize the Reddit fetcher."""
        self.session = requests.Session()
        # Reddit requires a descriptive User-Agent
        self.session.headers.update({
            "User-Agent": "AI-News-Reporter/1.0 (Educational project for monitoring AI tools)"
        })
    
    def get_subreddits(self) -> list[str]:
        """Get subreddits to monitor from env or defaults."""
        subs_str = os.getenv("REDDIT_SUBREDDITS")
        if subs_str:
            return [s.strip() for s in subs_str.split(",") if s.strip()]
        return self.DEFAULT_SUBREDDITS
    
    def get_min_score(self) -> int:
        """Get minimum score threshold from env or default."""
        return int(os.getenv("REDDIT_MIN_SCORE", "5"))
    
    def fetch_subreddit_posts(
        self,
        subreddit: str,
        sort: str = "hot",
        days_back: int = 1,
        min_score: int = 5,
        max_results: int = 25
    ) -> list[dict]:
        """
        Fetch posts from a subreddit.
        
        Args:
            subreddit: Subreddit name (without r/)
            sort: Sort method (hot, new, top)
            days_back: Number of days to look back
            min_score: Minimum upvote threshold
            max_results: Maximum results to fetch
            
        Returns:
            List of post dictionaries
        """
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
        params = {
            "limit": max_results,
            "t": "day" if days_back <= 1 else "week"
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 403:
                print(f"Reddit access forbidden for r/{subreddit} (may be private)")
                return []
            
            if response.status_code == 404:
                print(f"Reddit subreddit not found: r/{subreddit}")
                return []
            
            if response.status_code != 200:
                print(f"Reddit API error for r/{subreddit}: {response.status_code}")
                return []
            
            data = response.json()
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            posts = []
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                
                # Parse creation time
                created_utc = post.get("created_utc", 0)
                if created_utc:
                    published = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                else:
                    continue
                
                # Filter by date
                if published < cutoff_date:
                    continue
                
                # Filter by score
                score = post.get("score", 0)
                if score < min_score:
                    continue
                
                # Skip stickied/pinned posts
                if post.get("stickied", False):
                    continue
                
                post_id = post.get("id", "")
                permalink = post.get("permalink", "")
                
                posts.append({
                    "id": post_id,
                    "title": sanitize_title(post.get("title", ""), max_length=200),
                    "url": f"https://www.reddit.com{permalink}" if permalink else "",
                    "external_url": post.get("url", ""),  # Link posts have external URL
                    "subreddit": subreddit,
                    "score": score,
                    "comments": post.get("num_comments", 0),
                    "author": post.get("author", ""),
                    "published": published,
                    "published_at": published.isoformat(),
                    "is_self": post.get("is_self", True),  # Text post vs link post
                    "source": f"r/{subreddit}",
                    "type": "discussion"
                })
            
            return posts
            
        except requests.RequestException as e:
            print(f"Error fetching r/{subreddit}: {e}")
            return []
    
    def fetch_trending_posts(
        self,
        subreddits: Optional[list[str]] = None,
        days_back: int = 1,
        min_score: Optional[int] = None,
        top_n: int = 3
    ) -> list[dict]:
        """
        Fetch trending posts from all monitored subreddits.
        
        Args:
            subreddits: List of subreddits (defaults to configured list)
            days_back: Number of days to look back
            min_score: Minimum score threshold
            top_n: Number of top posts to return
            
        Returns:
            List of top posts sorted by score
        """
        if subreddits is None:
            subreddits = self.get_subreddits()
        
        if min_score is None:
            min_score = self.get_min_score()
        
        all_posts = []
        seen_ids = set()
        
        for subreddit in subreddits:
            posts = self.fetch_subreddit_posts(
                subreddit, 
                days_back=days_back, 
                min_score=min_score
            )
            for post in posts:
                # Deduplicate by ID
                if post["id"] not in seen_ids:
                    seen_ids.add(post["id"])
                    all_posts.append(post)
        
        # Sort by score (most popular first)
        all_posts.sort(key=lambda p: p.get("score", 0), reverse=True)
        
        # Calculate hours ago for display
        now = datetime.now(timezone.utc)
        for post in all_posts:
            published = post.get("published")
            if published:
                post["hours_ago"] = int((now - published).total_seconds() / 3600)
                post["days_ago"] = (now - published).days
            else:
                post["hours_ago"] = 0
                post["days_ago"] = 0
        
        return all_posts[:top_n]


def main():
    """Test the Reddit fetcher."""
    fetcher = RedditFetcher()
    posts = fetcher.fetch_trending_posts(top_n=5)
    
    print(f"\nFound {len(posts)} trending Reddit posts:\n")
    for i, post in enumerate(posts, 1):
        print(f"{i}. [{post['source']}] {post['title']}")
        print(f"   Score: {post['score']} | Comments: {post['comments']}")
        print(f"   Posted: {post['hours_ago']} hours ago")
        print(f"   URL: {post['url']}")
        print()


if __name__ == "__main__":
    main()
