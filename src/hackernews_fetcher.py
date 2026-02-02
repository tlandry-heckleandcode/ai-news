"""
Hacker News fetcher for trending AI tool discussions.

Uses the Algolia HN Search API to find relevant posts.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import requests

from sanitizer import sanitize_title, sanitize_description


class HackerNewsFetcher:
    """Fetches trending posts from Hacker News."""
    
    DEFAULT_SEARCH_TERMS = [
        "Cursor AI",
        "Claude Code",
        "Claude AI",
        "Anthropic",
        "AI coding",
        "vibe coding",
    ]
    
    # Algolia HN Search API
    API_BASE = "https://hn.algolia.com/api/v1"
    
    def __init__(self):
        """Initialize the Hacker News fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "AI-News-Reporter/1.0"
        })
    
    def get_search_terms(self) -> list[str]:
        """Get search terms from env or defaults."""
        terms_str = os.getenv("HN_SEARCH_TERMS")
        if terms_str:
            return [t.strip() for t in terms_str.split(",") if t.strip()]
        return self.DEFAULT_SEARCH_TERMS
    
    def get_min_score(self) -> int:
        """Get minimum score threshold from env or default."""
        return int(os.getenv("HN_MIN_SCORE", "10"))
    
    def search_stories(
        self,
        query: str,
        days_back: int = 1,
        min_score: int = 10,
        max_results: int = 20
    ) -> list[dict]:
        """
        Search for HN stories matching a query.
        
        Args:
            query: Search term
            days_back: Number of days to look back
            min_score: Minimum points threshold
            max_results: Maximum results to fetch
            
        Returns:
            List of story dictionaries
        """
        # Calculate timestamp for date filter
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_timestamp = int(cutoff.timestamp())
        
        url = f"{self.API_BASE}/search"
        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{cutoff_timestamp},points>{min_score}",
            "hitsPerPage": max_results
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"HN API error for query '{query}': {response.status_code}")
                return []
            
            data = response.json()
            stories = []
            
            for hit in data.get("hits", []):
                # Parse creation date
                created_at = hit.get("created_at_i", 0)
                if created_at:
                    published = datetime.fromtimestamp(created_at, tz=timezone.utc)
                else:
                    published = None
                
                story_id = hit.get("objectID", "")
                
                stories.append({
                    "id": story_id,
                    "title": sanitize_title(hit.get("title", ""), max_length=200),
                    "url": hit.get("url", "") or f"https://news.ycombinator.com/item?id={story_id}",
                    "hn_url": f"https://news.ycombinator.com/item?id={story_id}",
                    "points": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                    "author": hit.get("author", ""),
                    "published": published,
                    "published_at": published.isoformat() if published else "",
                    "search_term": query,
                    "source": "Hacker News",
                    "type": "discussion"
                })
            
            return stories
            
        except requests.RequestException as e:
            print(f"Error fetching HN stories for '{query}': {e}")
            return []
    
    def fetch_trending_stories(
        self,
        search_terms: Optional[list[str]] = None,
        days_back: int = 1,
        min_score: Optional[int] = None,
        top_n: int = 3
    ) -> list[dict]:
        """
        Fetch trending HN stories across all search terms.
        
        Args:
            search_terms: List of search terms (defaults to configured terms)
            days_back: Number of days to look back
            min_score: Minimum points threshold
            top_n: Number of top stories to return
            
        Returns:
            List of top stories sorted by points
        """
        if search_terms is None:
            search_terms = self.get_search_terms()
        
        if min_score is None:
            min_score = self.get_min_score()
        
        all_stories = []
        seen_ids = set()
        
        for term in search_terms:
            stories = self.search_stories(term, days_back=days_back, min_score=min_score)
            for story in stories:
                # Deduplicate by ID
                if story["id"] not in seen_ids:
                    seen_ids.add(story["id"])
                    all_stories.append(story)
        
        # Sort by points (most popular first)
        all_stories.sort(key=lambda s: s.get("points", 0), reverse=True)
        
        # Calculate hours ago for display
        now = datetime.now(timezone.utc)
        for story in all_stories:
            published = story.get("published")
            if published:
                story["hours_ago"] = int((now - published).total_seconds() / 3600)
                story["days_ago"] = (now - published).days
            else:
                story["hours_ago"] = 0
                story["days_ago"] = 0
        
        return all_stories[:top_n]


def main():
    """Test the Hacker News fetcher."""
    fetcher = HackerNewsFetcher()
    stories = fetcher.fetch_trending_stories(top_n=5)
    
    print(f"\nFound {len(stories)} trending HN stories:\n")
    for i, story in enumerate(stories, 1):
        print(f"{i}. {story['title']}")
        print(f"   Points: {story['points']} | Comments: {story['comments']}")
        print(f"   Posted: {story['hours_ago']} hours ago")
        print(f"   URL: {story['url']}")
        print()


if __name__ == "__main__":
    main()
