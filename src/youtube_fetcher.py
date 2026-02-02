"""
YouTube Data API integration for fetching trending AI videos.
"""

import html
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class YouTubeFetcher:
    """Fetches and ranks trending YouTube videos using the YouTube Data API."""
    
    DEFAULT_SEARCH_TERMS = [
        "Cursor AI",
        "Claude Code",
        "Google Antigravity AI"
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the YouTube fetcher.
        
        Args:
            api_key: YouTube Data API key. If not provided, reads from YOUTUBE_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YouTube API key is required. Set YOUTUBE_API_KEY environment variable.")
        
        self.youtube = build("youtube", "v3", developerKey=self.api_key)
    
    def _parse_duration(self, iso_duration: str) -> str:
        """
        Convert ISO 8601 duration (PT4M13S) to readable format (4:13).
        
        Args:
            iso_duration: Duration in ISO 8601 format (e.g., PT1H2M30S, PT4M13S, PT30S)
            
        Returns:
            Formatted duration string (e.g., "1:02:30", "4:13", "0:30")
        """
        if not iso_duration:
            return ""
        
        # Parse hours, minutes, seconds from PTxHxMxS format
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, iso_duration)
        
        if not match:
            return ""
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    def search_videos(
        self,
        query: str,
        days_back: int = 1,
        max_results: int = 10
    ) -> list[dict]:
        """
        Search for videos matching a query within the specified time range.
        
        Args:
            query: Search term
            days_back: Number of days to look back
            max_results: Maximum number of results to return
            
        Returns:
            List of video dictionaries with id, title, channel, published date
        """
        published_after = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        
        try:
            search_response = self.youtube.search().list(
                q=query,
                part="snippet",
                type="video",
                order="viewCount",
                publishedAfter=published_after,
                maxResults=max_results,
                relevanceLanguage="en"
            ).execute()
            
            videos = []
            for item in search_response.get("items", []):
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]
                
                # Get thumbnail URL (prefer medium, fallback to default)
                thumbnails = snippet.get("thumbnails", {})
                thumbnail_url = (
                    thumbnails.get("medium", {}).get("url") or
                    thumbnails.get("default", {}).get("url") or
                    ""
                )
                
                videos.append({
                    "id": video_id,
                    "title": html.unescape(snippet["title"]),
                    "channel": snippet["channelTitle"],
                    "published_at": snippet["publishedAt"],
                    "description": snippet.get("description", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail": thumbnail_url,
                    "search_term": query
                })
            
            return videos
            
        except HttpError as e:
            print(f"YouTube API error for query '{query}': {e}")
            return []
    
    def get_video_statistics(self, video_ids: list[str]) -> dict[str, dict]:
        """
        Fetch statistics (views, likes, comments) and duration for a list of video IDs.
        
        Args:
            video_ids: List of YouTube video IDs
            
        Returns:
            Dictionary mapping video ID to statistics and duration
        """
        if not video_ids:
            return {}
        
        try:
            # API allows up to 50 IDs per request
            stats = {}
            for i in range(0, len(video_ids), 50):
                batch = video_ids[i:i + 50]
                response = self.youtube.videos().list(
                    part="statistics,contentDetails",
                    id=",".join(batch)
                ).execute()
                
                for item in response.get("items", []):
                    video_id = item["id"]
                    statistics = item.get("statistics", {})
                    content_details = item.get("contentDetails", {})
                    
                    # Parse duration from ISO 8601 format
                    iso_duration = content_details.get("duration", "")
                    duration = self._parse_duration(iso_duration)
                    
                    stats[video_id] = {
                        "views": int(statistics.get("viewCount", 0)),
                        "likes": int(statistics.get("likeCount", 0)),
                        "comments": int(statistics.get("commentCount", 0)),
                        "duration": duration
                    }
            
            return stats
            
        except HttpError as e:
            print(f"YouTube API error fetching statistics: {e}")
            return {}
    
    def calculate_trending_score(
        self,
        video: dict,
        stats: dict,
        now: Optional[datetime] = None
    ) -> float:
        """
        Calculate a trending score for a video based on engagement and recency.
        
        Score formula: (views + likes*10 + comments*5) * recency_multiplier
        Recency multiplier: 1.0 for today, decreasing by 0.1 per day
        
        Args:
            video: Video dictionary with published_at
            stats: Statistics dictionary with views, likes, comments
            now: Current time (for testing)
            
        Returns:
            Trending score as a float
        """
        if now is None:
            now = datetime.now(timezone.utc)
        
        # Parse published date
        published_str = video.get("published_at", "")
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            published = now - timedelta(days=7)  # Default to oldest
        
        # Calculate days old
        days_old = (now - published).days
        
        # Recency multiplier (newer = higher score)
        recency_multiplier = max(0.3, 1.0 - (days_old * 0.1))
        
        # Engagement score
        views = stats.get("views", 0)
        likes = stats.get("likes", 0)
        comments = stats.get("comments", 0)
        
        engagement_score = views + (likes * 10) + (comments * 5)
        
        return engagement_score * recency_multiplier
    
    def fetch_trending_videos(
        self,
        search_terms: Optional[list[str]] = None,
        days_back: int = 1,
        max_results_per_term: int = 10,
        top_n: int = 3
    ) -> list[dict]:
        """
        Fetch and rank the top trending videos across all search terms.
        
        Args:
            search_terms: List of search terms (defaults to AI tools)
            days_back: Number of days to look back
            max_results_per_term: Max results to fetch per search term
            top_n: Number of top videos to return
            
        Returns:
            List of top N trending videos with full details and scores
        """
        if search_terms is None:
            search_terms = self.DEFAULT_SEARCH_TERMS
        
        # Collect all videos from all search terms
        all_videos = []
        seen_ids = set()
        
        for term in search_terms:
            videos = self.search_videos(term, days_back, max_results_per_term)
            for video in videos:
                # Deduplicate by video ID
                if video["id"] not in seen_ids:
                    seen_ids.add(video["id"])
                    all_videos.append(video)
        
        if not all_videos:
            return []
        
        # Fetch statistics for all videos
        video_ids = [v["id"] for v in all_videos]
        all_stats = self.get_video_statistics(video_ids)
        
        # Calculate trending scores and enrich videos
        now = datetime.now(timezone.utc)
        for video in all_videos:
            stats = all_stats.get(video["id"], {})
            video["stats"] = stats
            video["trending_score"] = self.calculate_trending_score(video, stats, now)
            
            # Calculate days ago for display
            try:
                published = datetime.fromisoformat(video["published_at"].replace("Z", "+00:00"))
                video["days_ago"] = (now - published).days
            except (ValueError, AttributeError):
                video["days_ago"] = 0
        
        # Sort by trending score and return top N
        all_videos.sort(key=lambda v: v["trending_score"], reverse=True)
        
        return all_videos[:top_n]


def main():
    """Test the YouTube fetcher."""
    from dotenv import load_dotenv
    load_dotenv()
    
    fetcher = YouTubeFetcher()
    videos = fetcher.fetch_trending_videos(top_n=3)
    
    print(f"\nFound {len(videos)} trending videos:\n")
    for i, video in enumerate(videos, 1):
        print(f"{i}. {video['title']}")
        print(f"   Channel: {video['channel']}")
        duration = video['stats'].get('duration', '')
        duration_str = f" | Duration: {duration}" if duration else ""
        print(f"   Views: {video['stats'].get('views', 0):,}{duration_str} | "
              f"Published: {video['days_ago']} days ago")
        print(f"   Score: {video['trending_score']:,.0f}")
        print(f"   URL: {video['url']}")
        print()


if __name__ == "__main__":
    main()
