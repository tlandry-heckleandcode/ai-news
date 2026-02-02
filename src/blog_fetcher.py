"""
Official blog fetcher for AI tool companies.

Monitors RSS feeds from Cursor, Anthropic, OpenAI, and Google AI blogs.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import feedparser
import requests

from sanitizer import sanitize_title, sanitize_description


class BlogFetcher:
    """Fetches posts from official AI tool blogs via RSS."""
    
    # Official blog RSS feeds
    # Note: Cursor and Anthropic do not have public RSS feeds as of Feb 2026
    # These can be added via OFFICIAL_BLOGS env var if they become available
    OFFICIAL_BLOGS = {
        "OpenAI": "https://openai.com/news/rss.xml",
        "Google AI": "https://blog.google/technology/ai/rss/",
    }
    
    def __init__(self):
        """Initialize the blog fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AI-News-Reporter/1.0"
        })
    
    def get_blogs(self) -> dict[str, str]:
        """Get blog sources from env or defaults."""
        # Allow overriding via environment
        custom_blogs = os.getenv("OFFICIAL_BLOGS")
        if custom_blogs:
            # Format: "Name1=url1,Name2=url2"
            blogs = {}
            for item in custom_blogs.split(","):
                if "=" in item:
                    name, url = item.split("=", 1)
                    blogs[name.strip()] = url.strip()
            return blogs
        return self.OFFICIAL_BLOGS
    
    def fetch_blog_posts(
        self,
        blog_name: str,
        feed_url: str,
        days_back: int = 7,
        max_results: int = 5
    ) -> list[dict]:
        """
        Fetch recent posts from a blog RSS feed.
        
        Args:
            blog_name: Name of the blog source
            feed_url: RSS feed URL
            days_back: Number of days to look back
            max_results: Maximum posts to return
            
        Returns:
            List of post dictionaries
        """
        try:
            # Fetch and parse RSS feed
            response = self.session.get(feed_url, timeout=10)
            if response.status_code != 200:
                print(f"Failed to fetch {blog_name} blog: {response.status_code}")
                return []
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                print(f"Failed to parse {blog_name} RSS: {feed.bozo_exception}")
                return []
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            posts = []
            
            for entry in feed.entries[:max_results * 2]:  # Fetch extra to filter
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
                
                post = {
                    "title": title,
                    "summary": summary,
                    "url": entry.get("link", ""),
                    "source": blog_name,
                    "published": published,
                    "published_at": published.isoformat() if published else "",
                    "type": "blog"
                }
                
                posts.append(post)
                
                if len(posts) >= max_results:
                    break
            
            return posts
            
        except Exception as e:
            print(f"Error fetching {blog_name} blog: {e}")
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
    
    def fetch_all_blog_posts(
        self,
        days_back: int = 7,
        top_n: int = 3
    ) -> list[dict]:
        """
        Fetch posts from all official blogs.
        
        Args:
            days_back: Number of days to look back
            top_n: Maximum total posts to return
            
        Returns:
            List of posts sorted by date (newest first)
        """
        blogs = self.get_blogs()
        all_posts = []
        
        for blog_name, feed_url in blogs.items():
            posts = self.fetch_blog_posts(
                blog_name,
                feed_url,
                days_back=days_back,
                max_results=top_n  # Get top_n from each, then combine
            )
            all_posts.extend(posts)
        
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
    """Test the blog fetcher."""
    fetcher = BlogFetcher()
    posts = fetcher.fetch_all_blog_posts(days_back=30, top_n=5)
    
    print(f"\nFound {len(posts)} recent blog posts:\n")
    for i, post in enumerate(posts, 1):
        print(f"{i}. [{post['source']}] {post['title']}")
        print(f"   Published: {post.get('hours_ago', 0)} hours ago")
        print(f"   URL: {post['url']}")
        if post.get('summary'):
            print(f"   Summary: {post['summary'][:100]}...")
        print()


if __name__ == "__main__":
    main()
