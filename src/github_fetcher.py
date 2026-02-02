"""
GitHub Release fetcher for monitoring repository releases.

Tracks releases from specified GitHub repositories to surface
updates to AI coding tools.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
import requests

from sanitizer import sanitize_title, sanitize_release_notes


class GitHubFetcher:
    """Fetches releases from GitHub repositories."""
    
    DEFAULT_REPOS = [
        "getcursor/cursor",
    ]
    
    API_BASE = "https://api.github.com"
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitHub fetcher.
        
        Args:
            token: Optional GitHub token for higher rate limits.
                   Without token: 60 requests/hour
                   With token: 5000 requests/hour
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.session = requests.Session()
        
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "AI-News-Reporter/1.0"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        self.session.headers.update(headers)
    
    def get_repos(self) -> list[str]:
        """Get list of repos to monitor from env or defaults."""
        repos_str = os.getenv("GITHUB_REPOS")
        if repos_str:
            return [r.strip() for r in repos_str.split(",") if r.strip()]
        return self.DEFAULT_REPOS
    
    def fetch_releases(
        self,
        repo: str,
        days_back: int = 7,
        max_results: int = 10
    ) -> list[dict]:
        """
        Fetch recent releases for a repository.
        
        Args:
            repo: Repository in "owner/repo" format
            days_back: Number of days to look back
            max_results: Maximum releases to return
            
        Returns:
            List of release dictionaries
        """
        url = f"{self.API_BASE}/repos/{repo}/releases"
        
        try:
            response = self.session.get(url, params={"per_page": max_results}, timeout=10)
            
            if response.status_code == 404:
                print(f"GitHub repo not found: {repo}")
                return []
            
            if response.status_code != 200:
                print(f"GitHub API error for {repo}: {response.status_code}")
                return []
            
            releases_data = response.json()
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            releases = []
            for release in releases_data:
                # Parse publish date
                published_str = release.get("published_at", "")
                if not published_str:
                    continue
                    
                try:
                    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                except ValueError:
                    continue
                
                # Filter by date
                if published < cutoff_date:
                    continue
                
                # Extract release info
                tag = release.get("tag_name", "")
                name = release.get("name", "") or tag
                body = release.get("body", "")
                
                releases.append({
                    "repo": repo,
                    "tag": tag,
                    "name": sanitize_title(name, max_length=200),
                    "body": sanitize_release_notes(body, max_length=1000),
                    "url": release.get("html_url", ""),
                    "published_at": published_str,
                    "published": published,
                    "prerelease": release.get("prerelease", False),
                    "type": "release"
                })
            
            return releases
            
        except requests.RequestException as e:
            print(f"Error fetching releases for {repo}: {e}")
            return []
    
    def fetch_all_releases(
        self,
        repos: Optional[list[str]] = None,
        days_back: int = 7,
        top_n: int = 3
    ) -> list[dict]:
        """
        Fetch releases from all monitored repositories.
        
        Args:
            repos: List of repos to check (defaults to configured repos)
            days_back: Number of days to look back
            top_n: Maximum total releases to return
            
        Returns:
            List of releases sorted by date (newest first)
        """
        if repos is None:
            repos = self.get_repos()
        
        all_releases = []
        
        for repo in repos:
            releases = self.fetch_releases(repo, days_back=days_back)
            all_releases.extend(releases)
        
        # Sort by date (newest first)
        all_releases.sort(key=lambda r: r.get("published", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        
        # Calculate hours ago for display
        now = datetime.now(timezone.utc)
        for release in all_releases:
            published = release.get("published")
            if published:
                release["hours_ago"] = int((now - published).total_seconds() / 3600)
                release["days_ago"] = (now - published).days
            else:
                release["hours_ago"] = 0
                release["days_ago"] = 0
        
        return all_releases[:top_n]


def main():
    """Test the GitHub fetcher."""
    fetcher = GitHubFetcher()
    releases = fetcher.fetch_all_releases(top_n=5)
    
    print(f"\nFound {len(releases)} recent releases:\n")
    for i, release in enumerate(releases, 1):
        print(f"{i}. {release['repo']} - {release['name']}")
        print(f"   Tag: {release['tag']}")
        print(f"   Published: {release['hours_ago']} hours ago")
        print(f"   URL: {release['url']}")
        if release['body']:
            print(f"   Notes: {release['body'][:100]}...")
        print()


if __name__ == "__main__":
    main()
