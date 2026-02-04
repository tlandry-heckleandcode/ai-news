"""
Expert YouTube channel fetcher.

Monitors YouTube channels from policy experts like Creator Insider and Hoeg Law
using YouTube's RSS feed feature (no API key required).
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import feedparser
import requests

from sanitizer import sanitize_title, sanitize_description


class ExpertChannelFetcher:
    """Fetches videos from expert YouTube channels via RSS."""
    
    # Expert YouTube channels
    # Channel ID can be found in the channel URL or via YouTube
    DEFAULT_CHANNELS = {
        "Creator Insider": "UCGg-UqjRgzhYDPJMr-9HXCg",  # Official-ish, YouTube employees
        "Hoeg Law": "UCi5RTzzeCFurWTPLm8usDkQ",        # Lawyer commentary on platform terms
    }
    
    # YouTube channel RSS URL format
    RSS_URL_FORMAT = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    
    def __init__(self):
        """Initialize the expert channel fetcher."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "YouTube-Policy-Monitor/1.0"
        })
    
    def get_channels(self) -> dict[str, str]:
        """Get channels from env or defaults."""
        channels_str = os.getenv("POLICY_EXPERT_CHANNELS")
        if channels_str:
            # Format: "channel_id1,channel_id2" or "Name1=channel_id1,Name2=channel_id2"
            channels = {}
            for item in channels_str.split(","):
                item = item.strip()
                if "=" in item:
                    name, channel_id = item.split("=", 1)
                    channels[name.strip()] = channel_id.strip()
                elif item:
                    # Just channel ID, use as both name and ID
                    channels[item] = item
            return channels
        return self.DEFAULT_CHANNELS
    
    def fetch_channel(
        self,
        channel_name: str,
        channel_id: str,
        days_back: int = 1,
        max_results: int = 5
    ) -> list[dict]:
        """
        Fetch recent videos from a YouTube channel via RSS.
        
        Args:
            channel_name: Display name for the channel
            channel_id: YouTube channel ID
            days_back: Number of days to look back
            max_results: Maximum videos to return
            
        Returns:
            List of video dictionaries
        """
        feed_url = self.RSS_URL_FORMAT.format(channel_id=channel_id)
        
        try:
            # Fetch and parse RSS feed
            response = self.session.get(feed_url, timeout=15)
            if response.status_code != 200:
                print(f"Failed to fetch {channel_name}: {response.status_code}")
                return []
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                print(f"Failed to parse {channel_name} RSS: {feed.bozo_exception}")
                return []
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            videos = []
            
            for entry in feed.entries[:max_results * 2]:
                # Parse publication date
                published = self._parse_date(entry)
                
                if published and published < cutoff_date:
                    continue
                
                # Extract video info
                title = sanitize_title(entry.get("title", ""), max_length=200)
                
                # Get description from media:group or summary
                summary = ""
                if entry.get("summary"):
                    summary = sanitize_description(entry.get("summary", ""), max_length=300)
                
                # Get video ID from link
                video_id = ""
                link = entry.get("link", "")
                if "watch?v=" in link:
                    video_id = link.split("watch?v=")[-1].split("&")[0]
                
                # Get thumbnail
                thumbnail = ""
                if video_id:
                    thumbnail = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                
                # Get author (channel name from feed)
                author = entry.get("author", channel_name)
                
                video = {
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "video_id": video_id,
                    "thumbnail": thumbnail,
                    "source": channel_name,
                    "channel": author,
                    "published": published,
                    "published_at": published.isoformat() if published else "",
                    "type": "expert_video",
                    "tier": 4
                }
                
                videos.append(video)
                
                if len(videos) >= max_results:
                    break
            
            return videos
            
        except Exception as e:
            print(f"Error fetching {channel_name}: {e}")
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
            "%Y-%m-%dT%H:%M:%S+00:00",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
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
    
    def fetch_all_channels(
        self,
        days_back: int = 1,
        top_n: int = 3
    ) -> list[dict]:
        """
        Fetch videos from all expert channels.
        
        Args:
            days_back: Number of days to look back
            top_n: Maximum total videos to return
            
        Returns:
            List of videos sorted by date (newest first)
        """
        channels = self.get_channels()
        all_videos = []
        
        for channel_name, channel_id in channels.items():
            videos = self.fetch_channel(
                channel_name,
                channel_id,
                days_back=days_back,
                max_results=top_n
            )
            all_videos.extend(videos)
            print(f"Fetched {len(videos)} videos from {channel_name}")
        
        # Sort by date (newest first)
        all_videos.sort(
            key=lambda v: v.get("published") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        # Calculate hours ago for display
        now = datetime.now(timezone.utc)
        for video in all_videos:
            published = video.get("published")
            if published:
                video["hours_ago"] = int((now - published).total_seconds() / 3600)
                video["days_ago"] = (now - published).days
            else:
                video["hours_ago"] = 0
                video["days_ago"] = 0
        
        return all_videos[:top_n]


def main():
    """Test the expert channel fetcher."""
    fetcher = ExpertChannelFetcher()
    
    # Test with longer lookback
    videos = fetcher.fetch_all_channels(days_back=30, top_n=10)
    
    print(f"\nFound {len(videos)} recent expert videos:\n")
    for i, video in enumerate(videos, 1):
        print(f"{i}. [{video['source']}] {video['title']}")
        print(f"   Published: {video.get('hours_ago', 0)} hours ago")
        print(f"   URL: {video['url']}")
        if video.get('summary'):
            print(f"   Description: {video['summary'][:100]}...")
        print()


if __name__ == "__main__":
    main()
