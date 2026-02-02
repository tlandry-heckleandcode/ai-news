"""
Google News RSS fetcher for trending AI articles.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus
import feedparser
import requests


class NewsFetcher:
    """Fetches and ranks trending news articles from Google News RSS."""
    
    DEFAULT_SEARCH_TERMS = [
        "Cursor AI",
        "Claude Code",
        "Google Antigravity AI"
    ]
    
    # Higher authority sources get a boost
    HIGH_AUTHORITY_SOURCES = {
        "techcrunch": 1.5,
        "the verge": 1.4,
        "wired": 1.4,
        "ars technica": 1.4,
        "engadget": 1.3,
        "venturebeat": 1.3,
        "zdnet": 1.2,
        "cnet": 1.2,
        "forbes": 1.2,
        "bloomberg": 1.3,
        "reuters": 1.3,
        "bbc": 1.2,
        "new york times": 1.3,
        "washington post": 1.3,
        "hacker news": 1.2,
        "dev.to": 1.1,
        "medium": 1.0,
    }
    
    GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    def __init__(self):
        """Initialize the news fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
    
    def search_news(
        self,
        query: str,
        days_back: int = 1,
        max_results: int = 10
    ) -> list[dict]:
        """
        Search for news articles matching a query.
        
        Args:
            query: Search term
            days_back: Number of days to look back
            max_results: Maximum number of results to return
            
        Returns:
            List of article dictionaries
        """
        url = self.GOOGLE_NEWS_RSS_URL.format(query=quote_plus(query))
        
        try:
            feed = feedparser.parse(url)
            
            if feed.bozo and not feed.entries:
                print(f"Failed to parse feed for query '{query}': {feed.bozo_exception}")
                return []
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            articles = []
            
            for entry in feed.entries[:max_results * 2]:  # Fetch extra to filter
                # Parse publication date
                published = self._parse_date(entry.get("published", ""))
                
                if published and published < cutoff_date:
                    continue
                
                # Extract source from title (Google News format: "Title - Source")
                title, source = self._extract_source(entry.get("title", ""))
                
                article = {
                    "title": title,
                    "source": source,
                    "url": entry.get("link", ""),
                    "published_at": published.isoformat() if published else "",
                    "published": published,
                    "summary": self._clean_html(entry.get("summary", "")),
                    "search_term": query
                }
                
                articles.append(article)
                
                if len(articles) >= max_results:
                    break
            
            return articles
            
        except Exception as e:
            print(f"Error fetching news for query '{query}': {e}")
            return []
    
    def _parse_date(self, date_string: str) -> Optional[datetime]:
        """Parse various date formats from RSS feeds."""
        if not date_string:
            return None
        
        # Common RSS date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_string, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        # Try feedparser's parsed time
        try:
            import time
            struct = feedparser._parse_date(date_string)
            if struct:
                return datetime(*struct[:6], tzinfo=timezone.utc)
        except Exception:
            pass
        
        return None
    
    def _extract_source(self, title: str) -> tuple[str, str]:
        """
        Extract the article title and source from Google News format.
        Google News titles are typically: "Article Title - Source Name"
        """
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            return parts[0].strip(), parts[1].strip()
        return title.strip(), "Unknown"
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()
    
    def _resolve_redirect_url(self, url: str) -> str:
        """
        Follow redirects to get the final article URL.
        Google News RSS returns redirect URLs that need to be resolved.
        
        Args:
            url: Original URL (possibly a redirect)
            
        Returns:
            Final URL after following redirects
        """
        try:
            # Use HEAD request to follow redirects without downloading content
            response = self.session.head(url, timeout=5, allow_redirects=True)
            if response.url and response.url != url:
                return response.url
            
            # Some sites block HEAD, try GET with stream to get redirect URL
            response = self.session.get(url, timeout=5, allow_redirects=True, stream=True)
            response.close()  # Don't download the body
            return response.url
            
        except Exception:
            return url  # Fallback to original URL
    
    def _fetch_article_image(self, url: str) -> Optional[str]:
        """
        Fetch the og:image meta tag from an article page.
        
        Args:
            url: Article URL (may be a Google News redirect URL)
            
        Returns:
            Image URL or None if not found
        """
        try:
            # Skip Google News URLs - they use JavaScript redirects that we can't follow,
            # and fetching them returns Google's og:image instead of the article's image
            if 'news.google.com' in url:
                return None
            
            # Resolve any redirect URLs to get actual article URL
            resolved_url = self._resolve_redirect_url(url)
            
            # Skip if still a Google News URL after resolution
            if 'news.google.com' in resolved_url:
                return None
            
            response = self.session.get(resolved_url, timeout=5, allow_redirects=True)
            if response.status_code != 200:
                return None
            
            # Look for og:image meta tag
            # Pattern: <meta property="og:image" content="...">
            og_pattern = r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']'
            og_match = re.search(og_pattern, response.text, re.IGNORECASE)
            if og_match:
                return og_match.group(1)
            
            # Try alternate format: content before property
            og_pattern_alt = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'
            og_match_alt = re.search(og_pattern_alt, response.text, re.IGNORECASE)
            if og_match_alt:
                return og_match_alt.group(1)
            
            return None
            
        except Exception:
            # Silently fail - thumbnails are optional
            return None
    
    def calculate_trending_score(
        self,
        article: dict,
        now: Optional[datetime] = None
    ) -> float:
        """
        Calculate a trending score for an article based on recency and source authority.
        
        Score formula: recency_score * source_authority_multiplier
        
        Args:
            article: Article dictionary
            now: Current time (for testing)
            
        Returns:
            Trending score as a float
        """
        if now is None:
            now = datetime.now(timezone.utc)
        
        published = article.get("published")
        if not published:
            return 0.0
        
        # Recency score: higher for more recent articles
        hours_old = (now - published).total_seconds() / 3600
        recency_score = max(0, 168 - hours_old)  # 168 hours = 7 days
        
        # Source authority multiplier
        source_lower = article.get("source", "").lower()
        authority_multiplier = 1.0
        
        for source_name, multiplier in self.HIGH_AUTHORITY_SOURCES.items():
            if source_name in source_lower:
                authority_multiplier = multiplier
                break
        
        return recency_score * authority_multiplier
    
    def fetch_trending_articles(
        self,
        search_terms: Optional[list[str]] = None,
        days_back: int = 1,
        max_results_per_term: int = 10,
        top_n: int = 3
    ) -> list[dict]:
        """
        Fetch and rank the top trending articles across all search terms.
        
        Args:
            search_terms: List of search terms (defaults to AI tools)
            days_back: Number of days to look back
            max_results_per_term: Max results to fetch per search term
            top_n: Number of top articles to return
            
        Returns:
            List of top N trending articles with scores
        """
        if search_terms is None:
            search_terms = self.DEFAULT_SEARCH_TERMS
        
        # Collect all articles from all search terms
        all_articles = []
        seen_urls = set()
        
        for term in search_terms:
            articles = self.search_news(term, days_back, max_results_per_term)
            for article in articles:
                # Deduplicate by URL
                url = article.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(article)
        
        if not all_articles:
            return []
        
        # Calculate trending scores
        now = datetime.now(timezone.utc)
        for article in all_articles:
            article["trending_score"] = self.calculate_trending_score(article, now)
            
            # Calculate days ago for display
            published = article.get("published")
            if published:
                article["days_ago"] = (now - published).days
                article["hours_ago"] = int((now - published).total_seconds() / 3600)
            else:
                article["days_ago"] = 0
                article["hours_ago"] = 0
        
        # Sort by trending score and return top N
        all_articles.sort(key=lambda a: a["trending_score"], reverse=True)
        top_articles = all_articles[:top_n]
        
        # Fetch thumbnails for top articles only (to minimize HTTP requests)
        for article in top_articles:
            article["thumbnail"] = self._fetch_article_image(article.get("url", ""))
        
        return top_articles


def main():
    """Test the news fetcher."""
    fetcher = NewsFetcher()
    articles = fetcher.fetch_trending_articles(top_n=3)
    
    print(f"\nFound {len(articles)} trending articles:\n")
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   Published: {article['hours_ago']} hours ago")
        print(f"   Score: {article['trending_score']:.1f}")
        print(f"   URL: {article['url']}")
        print()


if __name__ == "__main__":
    main()
