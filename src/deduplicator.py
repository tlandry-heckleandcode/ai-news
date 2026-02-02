"""
Duplicate detection for content items.

Uses fuzzy string matching to identify when the same story
appears from multiple sources.
"""

import re
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urlparse


def normalize_title(title: str) -> str:
    """
    Normalize a title for comparison.
    
    - Lowercase
    - Remove punctuation
    - Remove common filler words
    - Normalize whitespace
    
    Args:
        title: Original title
        
    Returns:
        Normalized title for comparison
    """
    if not title:
        return ""
    
    # Lowercase
    normalized = title.lower()
    
    # Remove punctuation
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    
    # Remove common filler words that don't add meaning
    filler_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'to', 'of', 'and', 'or', 'for', 'in', 'on', 'at', 'by',
        'with', 'about', 'how', 'what', 'why', 'when', 'where',
        'this', 'that', 'these', 'those', 'it', 'its',
        'new', 'just', 'now', 'here', 'heres'
    }
    words = normalized.split()
    words = [w for w in words if w not in filler_words]
    
    # Rejoin and normalize whitespace
    normalized = ' '.join(words)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized


def get_domain(url: str) -> str:
    """Extract domain from URL for source identification."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def similarity_score(title1: str, title2: str) -> float:
    """
    Calculate similarity between two titles.
    
    Args:
        title1: First title
        title2: Second title
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    if not norm1 or not norm2:
        return 0.0
    
    return SequenceMatcher(None, norm1, norm2).ratio()


def is_duplicate(title1: str, title2: str, threshold: float = 0.8) -> bool:
    """
    Check if two titles are duplicates.
    
    Args:
        title1: First title
        title2: Second title
        threshold: Similarity threshold (default 0.8 = 80%)
        
    Returns:
        True if titles are considered duplicates
    """
    return similarity_score(title1, title2) >= threshold


def deduplicate_items(
    items: list[dict],
    threshold: float = 0.8,
    score_key: str = "score"
) -> list[dict]:
    """
    Remove duplicate items, keeping the one with highest score.
    
    For items with the same content from different sources,
    keeps the version with the highest engagement score.
    
    Args:
        items: List of item dictionaries (must have 'title' key)
        threshold: Similarity threshold for duplicates
        score_key: Key to use for scoring (e.g., 'score', 'points', 'trending_score')
        
    Returns:
        Deduplicated list of items
    """
    if not items:
        return []
    
    # Group items by similarity
    groups = []
    used = set()
    
    for i, item1 in enumerate(items):
        if i in used:
            continue
        
        group = [item1]
        used.add(i)
        
        for j, item2 in enumerate(items):
            if j in used:
                continue
            
            title1 = item1.get("title", "")
            title2 = item2.get("title", "")
            
            if is_duplicate(title1, title2, threshold):
                group.append(item2)
                used.add(j)
        
        groups.append(group)
    
    # From each group, keep the item with highest score
    result = []
    for group in groups:
        if len(group) == 1:
            best = group[0]
        else:
            # Sort by score descending, take first
            group.sort(key=lambda x: x.get(score_key, 0), reverse=True)
            best = group[0]
            
            # Track that this was deduplicated
            sources = [g.get("source", "") for g in group if g.get("source")]
            if len(sources) > 1:
                best["also_on"] = [s for s in sources if s != best.get("source")]
        
        result.append(best)
    
    return result


def deduplicate_across_sources(
    *source_lists: list[dict],
    threshold: float = 0.8
) -> list[dict]:
    """
    Deduplicate items across multiple source lists.
    
    Combines all items and removes duplicates, prioritizing
    by engagement score.
    
    Args:
        *source_lists: Multiple lists of items
        threshold: Similarity threshold
        
    Returns:
        Combined, deduplicated list
    """
    # Combine all items
    all_items = []
    for items in source_lists:
        all_items.extend(items)
    
    # Normalize score keys
    for item in all_items:
        # Map various score keys to a common one
        if "score" not in item:
            item["score"] = (
                item.get("points", 0) or 
                item.get("trending_score", 0) or
                0
            )
    
    return deduplicate_items(all_items, threshold=threshold, score_key="score")


def main():
    """Test the deduplicator."""
    test_items = [
        {"title": "Cursor AI raises $100M in Series B funding", "source": "TechCrunch", "score": 150},
        {"title": "Cursor raises $100 million in Series B", "source": "The Verge", "score": 120},
        {"title": "AI coding startup Cursor raises $100M", "source": "VentureBeat", "score": 80},
        {"title": "How to use Claude Code for large refactors", "source": "Dev.to", "score": 50},
        {"title": "Claude Code tips for refactoring", "source": "Reddit", "score": 30},
        {"title": "Google announces new AI features", "source": "Google Blog", "score": 200},
    ]
    
    print("Original items:")
    for item in test_items:
        print(f"  [{item['source']}] {item['title']} (score: {item['score']})")
    
    deduped = deduplicate_items(test_items)
    
    print(f"\nAfter deduplication ({len(test_items)} -> {len(deduped)}):")
    for item in deduped:
        also = item.get("also_on", [])
        also_str = f" (also on: {', '.join(also)})" if also else ""
        print(f"  [{item['source']}] {item['title']} (score: {item['score']}){also_str}")


if __name__ == "__main__":
    main()
