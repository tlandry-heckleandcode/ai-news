"""
Legal and policy analysis fetcher.

Monitors RSS feeds from legal/policy expert sources like IAPP, Lawfare,
Tech Policy Press, and EFF for platform policy analysis.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import feedparser
import requests

from sanitizer import sanitize_title, sanitize_description


class LegalFetcher:
    """Fetches policy analysis from legal/policy expert sources via RSS."""
    
    # Legal and policy analysis RSS feeds
    LEGAL_FEEDS = {
        "IAPP Daily": "https://iapp.org/feeds/daily_dashboard",
        "Lawfare": "https://www.lawfaremedia.org/feeds/lawfare-news",
        "Tech Policy Press": "https://www.techpolicy.press/feed/",
        "EFF": "https://www.eff.org/rss/updates.xml",
    }
    
    # Keywords for filtering YouTube/platform-relevant content
    PLATFORM_KEYWORDS = [
        "youtube", "google", "platform", "content moderation", "creator",
        "monetization", "copyright", "dmca", "section 230", "dsa",
        "digital services", "ai act", "algorithm", "recommendation",
        "social media", "online safety", "child safety", "coppa",
        "privacy", "data protection", "terms of service", "community guidelines"
    ]
    
    def __init__(self):
        """Initialize the legal fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "YouTube-Policy-Monitor/1.0"
        })
    
    def _matches_platform_keywords(self, title: str, summary: str = "") -> bool:
        """Check if content is relevant to platform/YouTube policy."""
        text = (title + " " + summary).lower()
        return any(keyword in text for keyword in self.PLATFORM_KEYWORDS)
    
    def fetch_feed(
        self,
        source_name: str,
        feed_url: str,
        days_back: int = 1,
        max_results: int = 10,
        filter_keywords: bool = True
    ) -> list[dict]:
        """
        Fetch recent posts from a legal/policy RSS feed.
        
        Args:
            source_name: Name of the source
            feed_url: RSS feed URL
            days_back: Number of days to look back
            max_results: Maximum posts to return
            filter_keywords: Whether to filter by platform keywords
            
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
            
            for entry in feed.entries[:max_results * 5]:  # Fetch extra to filter
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
                
                # Filter by platform keywords if enabled
                if filter_keywords and not self._matches_platform_keywords(title, summary):
                    continue
                
                # Get author if available
                author = ""
                if entry.get("author"):
                    author = entry.get("author", "")
                elif entry.get("authors"):
                    authors = entry.get("authors", [])
                    if authors and isinstance(authors, list):
                        author = authors[0].get("name", "")
                
                post = {
                    "title": title,
                    "summary": summary,
                    "url": entry.get("link", ""),
                    "source": source_name,
                    "author": author,
                    "published": published,
                    "published_at": published.isoformat() if published else "",
                    "type": "legal",
                    "tier": 3
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
    
    def fetch_all_legal(
        self,
        days_back: int = 1,
        top_n: int = 3,
        filter_keywords: bool = True
    ) -> list[dict]:
        """
        Fetch posts from all legal/policy sources.
        
        Args:
            days_back: Number of days to look back
            top_n: Maximum total posts to return
            filter_keywords: Whether to filter by platform keywords
            
        Returns:
            List of posts sorted by date (newest first)
        """
        all_posts = []
        
        for source_name, feed_url in self.LEGAL_FEEDS.items():
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
    """Test the legal fetcher."""
    fetcher = LegalFetcher()
    
    # Test with longer lookback and no keyword filter for demo
    posts = fetcher.fetch_all_legal(days_back=30, top_n=10, filter_keywords=False)
    
    print(f"\nFound {len(posts)} recent legal/policy posts:\n")
    for i, post in enumerate(posts, 1):
        author_str = f" by {post['author']}" if post.get('author') else ""
        print(f"{i}. [{post['source']}] {post['title']}{author_str}")
        print(f"   Published: {post.get('hours_ago', 0)} hours ago")
        print(f"   URL: {post['url']}")
        if post.get('summary'):
            print(f"   Summary: {post['summary'][:100]}...")
        print()


if __name__ == "__main__":
    main()
