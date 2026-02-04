"""
YouTube policy fetcher for official YouTube sources.

Monitors RSS feeds from YouTube Blog and API changelog.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import feedparser
import requests

from sanitizer import sanitize_title, sanitize_description


class YouTubePolicyFetcher:
    """Fetches policy-related content from official YouTube sources via RSS."""
    
    # Official YouTube RSS feeds
    OFFICIAL_FEEDS = {
        "YouTube Blog": "https://www.blog.youtube/rss/",
    }
    
    # Default keywords for policy-relevant content filtering
    DEFAULT_KEYWORDS = [
        "policy", "guidelines", "monetization", "terms", "community",
        "copyright", "strike", "update", "change", "new", "rules",
        "enforcement", "restriction", "age", "partner", "creator"
    ]
    
    def __init__(self):
        """Initialize the YouTube policy fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "YouTube-Policy-Monitor/1.0"
        })
    
    def get_keywords(self) -> list[str]:
        """Get keywords from env or defaults."""
        keywords_str = os.getenv("POLICY_KEYWORDS")
        if keywords_str:
            return [k.strip().lower() for k in keywords_str.split(",")]
        return self.DEFAULT_KEYWORDS
    
    def _matches_keywords(self, title: str, summary: str = "") -> bool:
        """Check if content matches policy-related keywords."""
        keywords = self.get_keywords()
        text = (title + " " + summary).lower()
        return any(keyword in text for keyword in keywords)
    
    def fetch_feed(
        self,
        source_name: str,
        feed_url: str,
        days_back: int = 1,
        max_results: int = 10,
        filter_keywords: bool = True
    ) -> list[dict]:
        """
        Fetch recent posts from an RSS feed.
        
        Args:
            source_name: Name of the source
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
                print(f"Failed to fetch {source_name}: {response.status_code}")
                return []
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                print(f"Failed to parse {source_name} RSS: {feed.bozo_exception}")
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
                
                # Get description/summary
                summary = ""
                if entry.get("summary"):
                    summary = sanitize_description(entry.get("summary", ""), max_length=500)
                elif entry.get("description"):
                    summary = sanitize_description(entry.get("description", ""), max_length=500)
                
                # Filter by keywords if enabled
                if filter_keywords and not self._matches_keywords(title, summary):
                    continue
                
                post = {
                    "title": title,
                    "summary": summary,
                    "url": entry.get("link", ""),
                    "source": source_name,
                    "published": published,
                    "published_at": published.isoformat() if published else "",
                    "type": "official",
                    "tier": 1
                }
                
                posts.append(post)
                
                if len(posts) >= max_results:
                    break
            
            return posts
            
        except Exception as e:
            print(f"Error fetching {source_name}: {e}")
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
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
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
    
    def fetch_all_official(
        self,
        days_back: int = 1,
        top_n: int = 5,
        filter_keywords: bool = True
    ) -> list[dict]:
        """
        Fetch posts from all official YouTube sources.
        
        Args:
            days_back: Number of days to look back
            top_n: Maximum total posts to return
            filter_keywords: Whether to filter by policy keywords
            
        Returns:
            List of posts sorted by date (newest first)
        """
        all_posts = []
        
        for source_name, feed_url in self.OFFICIAL_FEEDS.items():
            posts = self.fetch_feed(
                source_name,
                feed_url,
                days_back=days_back,
                max_results=top_n,
                filter_keywords=filter_keywords
            )
            all_posts.extend(posts)
            print(f"Fetched {len(posts)} posts from {source_name}")
        
        # Sort by date (newest first)
        all_posts.sort(
            key=lambda p: p.get("published") or datetime.min.replace(tzinfo=timezone.utc),
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
    """Test the YouTube policy fetcher."""
    fetcher = YouTubePolicyFetcher()
    
    # Test with longer lookback and no keyword filter for demo
    posts = fetcher.fetch_all_official(days_back=30, top_n=10, filter_keywords=False)
    
    print(f"\nFound {len(posts)} recent YouTube blog posts:\n")
    for i, post in enumerate(posts, 1):
        print(f"{i}. [{post['source']}] {post['title']}")
        print(f"   Published: {post.get('hours_ago', 0)} hours ago")
        print(f"   URL: {post['url']}")
        if post.get('summary'):
            print(f"   Summary: {post['summary'][:100]}...")
        print()


if __name__ == "__main__":
    main()
