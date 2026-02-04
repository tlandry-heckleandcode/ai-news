"""
Reddit RSS fetcher for YouTube policy community discussions.

Monitors subreddits for policy-related discussions using public RSS feeds.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import feedparser
import requests

from sanitizer import sanitize_title, sanitize_description


class RedditFetcher:
    """Fetches policy discussions from Reddit via RSS feeds."""
    
    # Default subreddits to monitor
    DEFAULT_SUBREDDITS = {
        "r/PartneredYouTube": "https://www.reddit.com/r/PartneredYouTube/new.rss",
        "r/NewTubers": "https://www.reddit.com/r/NewTubers/new.rss",
        "r/youtubers": "https://www.reddit.com/r/youtubers/new.rss",
    }
    
    # Default keywords for filtering
    DEFAULT_KEYWORDS = [
        "policy", "demonetized", "demonetization", "shadowban", "shadowbanned",
        "guidelines", "strike", "removed", "banned", "terminated",
        "suspended", "appeal", "monetization", "adsense", "copyright",
        "claim", "content id", "community guidelines", "tos", "terms"
    ]
    
    def __init__(self):
        """Initialize the Reddit fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "YouTube-Policy-Monitor/1.0 (RSS Reader)"
        })
    
    def get_subreddits(self) -> dict[str, str]:
        """Get subreddits from env or defaults."""
        subreddits_str = os.getenv("POLICY_SUBREDDITS")
        if subreddits_str:
            # Format: "SubredditName1,SubredditName2"
            subreddits = {}
            for name in subreddits_str.split(","):
                name = name.strip()
                if name:
                    subreddits[f"r/{name}"] = f"https://www.reddit.com/r/{name}/new.rss"
            return subreddits
        return self.DEFAULT_SUBREDDITS
    
    def get_keywords(self) -> list[str]:
        """Get keywords from env or defaults."""
        keywords_str = os.getenv("POLICY_KEYWORDS")
        if keywords_str:
            return [k.strip().lower() for k in keywords_str.split(",")]
        return self.DEFAULT_KEYWORDS
    
    def _matches_keywords(self, title: str, content: str = "") -> bool:
        """Check if content matches policy-related keywords."""
        keywords = self.get_keywords()
        text = (title + " " + content).lower()
        return any(keyword in text for keyword in keywords)
    
    def _extract_score(self, entry: dict) -> int:
        """Extract upvote score from Reddit RSS entry."""
        # Reddit RSS includes score in various ways
        # Try to extract from content or title
        try:
            # Check for score in entry attributes
            if hasattr(entry, 'score'):
                return int(entry.score)
            
            # Reddit RSS sometimes includes points in the content
            content = entry.get("content", [{}])
            if isinstance(content, list) and content:
                content_text = content[0].get("value", "")
                # Look for "X points" pattern
                import re
                match = re.search(r'(\d+)\s+points?', content_text)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        
        return 0
    
    def fetch_subreddit(
        self,
        subreddit_name: str,
        feed_url: str,
        days_back: int = 1,
        max_results: int = 10,
        filter_keywords: bool = True
    ) -> list[dict]:
        """
        Fetch recent posts from a subreddit RSS feed.
        
        Args:
            subreddit_name: Name of the subreddit (e.g., "r/PartneredYouTube")
            feed_url: RSS feed URL
            days_back: Number of days to look back
            max_results: Maximum posts to return
            filter_keywords: Whether to filter by policy keywords
            
        Returns:
            List of post dictionaries
        """
        try:
            # Fetch and parse RSS feed
            response = self.session.get(feed_url, timeout=15)
            if response.status_code != 200:
                print(f"Failed to fetch {subreddit_name}: {response.status_code}")
                return []
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                print(f"Failed to parse {subreddit_name} RSS: {feed.bozo_exception}")
                return []
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            posts = []
            
            for entry in feed.entries[:max_results * 3]:  # Fetch extra to filter
                # Parse publication date
                published = self._parse_date(entry)
                
                if published and published < cutoff_date:
                    continue
                
                # Extract post info
                title = sanitize_title(entry.get("title", ""), max_length=200)
                
                # Get content/summary
                summary = ""
                content_list = entry.get("content", [])
                if content_list and isinstance(content_list, list):
                    summary = sanitize_description(content_list[0].get("value", ""), max_length=300)
                elif entry.get("summary"):
                    summary = sanitize_description(entry.get("summary", ""), max_length=300)
                
                # Filter by keywords if enabled
                if filter_keywords and not self._matches_keywords(title, summary):
                    continue
                
                # Extract score
                score = self._extract_score(entry)
                
                # Get author
                author = entry.get("author", "")
                if author.startswith("/u/"):
                    author = author[3:]
                
                post = {
                    "title": title,
                    "summary": summary,
                    "url": entry.get("link", ""),
                    "source": subreddit_name,
                    "author": author,
                    "score": score,
                    "published": published,
                    "published_at": published.isoformat() if published else "",
                    "type": "reddit",
                    "tier": 2
                }
                
                posts.append(post)
                
                if len(posts) >= max_results:
                    break
            
            return posts
            
        except Exception as e:
            print(f"Error fetching {subreddit_name}: {e}")
            return []
    
    def _parse_date(self, entry: dict) -> Optional[datetime]:
        """Parse publication date from feed entry."""
        # Try structured time first
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        
        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        
        # Try string parsing
        date_str = entry.get("published") or entry.get("updated") or ""
        if not date_str:
            return None
        
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        return None
    
    def fetch_all_subreddits(
        self,
        days_back: int = 1,
        top_n: int = 5,
        filter_keywords: bool = True
    ) -> list[dict]:
        """
        Fetch posts from all configured subreddits.
        
        Args:
            days_back: Number of days to look back
            top_n: Maximum total posts to return
            filter_keywords: Whether to filter by policy keywords
            
        Returns:
            List of posts sorted by recency and score
        """
        subreddits = self.get_subreddits()
        all_posts = []
        
        for subreddit_name, feed_url in subreddits.items():
            posts = self.fetch_subreddit(
                subreddit_name,
                feed_url,
                days_back=days_back,
                max_results=top_n,
                filter_keywords=filter_keywords
            )
            all_posts.extend(posts)
            print(f"Fetched {len(posts)} posts from {subreddit_name}")
        
        # Sort by date (newest first), then by score
        all_posts.sort(
            key=lambda p: (
                p.get("published") or datetime.min.replace(tzinfo=timezone.utc),
                p.get("score", 0)
            ),
            reverse=True
        )
        
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
    
    # Test with longer lookback and no keyword filter for demo
    posts = fetcher.fetch_all_subreddits(days_back=7, top_n=10, filter_keywords=False)
    
    print(f"\nFound {len(posts)} recent Reddit posts:\n")
    for i, post in enumerate(posts, 1):
        score_str = f"[{post.get('score', 0)} pts]" if post.get('score') else ""
        print(f"{i}. {score_str} [{post['source']}] {post['title']}")
        print(f"   Posted: {post.get('hours_ago', 0)} hours ago by u/{post.get('author', 'unknown')}")
        print(f"   URL: {post['url']}")
        if post.get('summary'):
            print(f"   Preview: {post['summary'][:100]}...")
        print()


if __name__ == "__main__":
    main()
