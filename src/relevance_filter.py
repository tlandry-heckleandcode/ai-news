"""
LLM-powered relevance filtering using OpenAI.

Filters content items by relevance to a senior developer
using AI coding tools.
"""

import os
from typing import Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# Context for relevance scoring
RELEVANCE_CONTEXT = """
You are filtering content for a senior software developer who:
- Uses AI coding tools like Cursor, Claude Code, and GitHub Copilot
- Wants to stay current on updates, new features, and releases
- Is interested in workflows, automations, and productivity tips
- Prefers technical content over marketing or beginner tutorials
- Cares about AI agent capabilities and local LLM developments
"""


def is_filtering_enabled() -> bool:
    """Check if LLM filtering is enabled."""
    return os.getenv("LLM_FILTER_ENABLED", "true").lower() == "true"


def filter_by_relevance(
    items: list[dict],
    content_type: str = "articles",
    min_score: int = 7,
    timeout: float = 10.0
) -> list[dict]:
    """
    Filter items by relevance using GPT-4o-mini.
    
    Args:
        items: List of content items (must have 'title' key)
        content_type: Description of content type for prompt
        min_score: Minimum relevance score (1-10) to include
        timeout: API timeout in seconds
        
    Returns:
        Filtered list of relevant items (or original list on error)
    """
    # Skip if disabled or no items
    if not is_filtering_enabled() or not items:
        return items
    
    # Skip if OpenAI not available
    if not HAS_OPENAI:
        print("OpenAI not installed, skipping relevance filtering")
        return items
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set, skipping relevance filtering")
        return items
    
    try:
        client = OpenAI(api_key=api_key, timeout=timeout)
        
        # Build numbered list of titles
        titles = [f"{i+1}. {item.get('title', 'Untitled')}" for i, item in enumerate(items)]
        titles_text = "\n".join(titles)
        
        # Create prompt
        prompt = f"""{RELEVANCE_CONTEXT}

Score each of these {content_type} from 1-10 for relevance to this developer:

{titles_text}

Return ONLY the numbers of items scoring {min_score} or higher, as a comma-separated list.
If none score high enough, return "NONE".
Example response: 1,3,5,8"""

        # Call API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=100,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        result = response.choices[0].message.content.strip()
        
        # Handle no relevant items
        if result.upper() == "NONE":
            print(f"LLM filter: No {content_type} scored {min_score}+")
            return []
        
        # Parse response - extract numbers
        relevant_indices = []
        for part in result.replace(" ", "").split(","):
            try:
                idx = int(part) - 1  # Convert to 0-based index
                if 0 <= idx < len(items):
                    relevant_indices.append(idx)
            except ValueError:
                continue
        
        if not relevant_indices:
            print(f"LLM filter: Could not parse response, returning all items")
            return items
        
        filtered = [items[i] for i in relevant_indices]
        print(f"LLM filter: {len(filtered)}/{len(items)} {content_type} passed relevance check")
        return filtered
        
    except Exception as e:
        print(f"LLM filter error: {e}, returning unfiltered items")
        return items


def main():
    """Test the relevance filter."""
    # Test data
    test_items = [
        {"title": "Cursor AI v0.45 Released - New Multi-file Editing"},
        {"title": "10 Beginner Python Tips for Complete Newbies"},
        {"title": "Claude Code Workflow: Automating Code Reviews"},
        {"title": "Celebrity News: What Stars Are Wearing"},
        {"title": "OpenAI Announces GPT-5 Developer Preview"},
        {"title": "How to Make Money with AI Side Hustles"},
        {"title": "Anthropic's New Agent Framework Deep Dive"},
    ]
    
    print("Testing relevance filter...\n")
    print("Input items:")
    for i, item in enumerate(test_items, 1):
        print(f"  {i}. {item['title']}")
    
    filtered = filter_by_relevance(test_items, "articles")
    
    print(f"\nFiltered items ({len(filtered)}):")
    for i, item in enumerate(filtered, 1):
        print(f"  {i}. {item['title']}")


if __name__ == "__main__":
    main()
