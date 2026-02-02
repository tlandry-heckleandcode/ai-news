"""
Content categorizer for auto-tagging articles and posts.

Categorizes content based on title keywords to help users
quickly identify content type.
"""

import re
from typing import Optional


# Category definitions with keywords
CATEGORIES = {
    "RELEASE": {
        "keywords": [
            r"\brelease\b", r"\bv\d+\.", r"\bversion\s*\d", r"\bchangelog\b",
            r"\bupdate\b", r"\blaunched?\b", r"\bannounce", r"\bnew\s+feature",
            r"\bwhat'?s\s+new\b", r"\bintroduc"
        ],
        "priority": 1
    },
    "TUTORIAL": {
        "keywords": [
            r"\bhow\s+to\b", r"\bguide\b", r"\btutorial\b", r"\bgetting\s+started\b",
            r"\bwalkthrough\b", r"\bstep[\s-]by[\s-]step\b", r"\blearn\b",
            r"\bbeginners?\b", r"\bintro(duction)?\s+to\b"
        ],
        "priority": 2
    },
    "WORKFLOW": {
        "keywords": [
            r"\bworkflow\b", r"\bautomation?\b", r"\bproductivity\b", r"\btips?\b",
            r"\bsetup\b", r"\bconfigur", r"\bintegrat", r"\bpipeline\b",
            r"\bbest\s+practices?\b", r"\boptimiz"
        ],
        "priority": 3
    },
    "COMPARISON": {
        "keywords": [
            r"\bvs\.?\b", r"\bversus\b", r"\bcompare", r"\balternative",
            r"\bbetter\s+than\b", r"\bor\b.*\bwhich\b"
        ],
        "priority": 4
    },
    "DISCUSSION": {
        "keywords": [
            r"\bthoughts?\b", r"\bopinion\b", r"\bdiscuss", r"\bexperience\b",
            r"\breview\b", r"\bimpression", r"\bama\b", r"\bask\s"
        ],
        "priority": 5
    },
    "NEWS": {
        "keywords": [],  # Default fallback
        "priority": 99
    }
}


def categorize(title: str, content_type: Optional[str] = None) -> str:
    """
    Categorize content based on title and optional type hint.
    
    Args:
        title: Content title to analyze
        content_type: Optional hint ("release", "discussion", "article", etc.)
        
    Returns:
        Category string (e.g., "RELEASE", "TUTORIAL", "NEWS")
    """
    if not title:
        return "NEWS"
    
    title_lower = title.lower()
    
    # Check each category's keywords
    matches = []
    for category, config in CATEGORIES.items():
        for pattern in config["keywords"]:
            if re.search(pattern, title_lower, re.IGNORECASE):
                matches.append((category, config["priority"]))
                break
    
    # Return highest priority match
    if matches:
        matches.sort(key=lambda x: x[1])
        return matches[0][0]
    
    # Use type hint for defaults
    if content_type:
        content_type_lower = content_type.lower()
        if content_type_lower in ("release",):
            return "RELEASE"
        if content_type_lower in ("discussion", "post"):
            return "DISCUSSION"
    
    return "NEWS"


def categorize_item(item: dict) -> dict:
    """
    Add category to an item dictionary.
    
    Args:
        item: Dictionary with 'title' and optionally 'type' keys
        
    Returns:
        Same dictionary with 'category' key added
    """
    title = item.get("title", "")
    content_type = item.get("type")
    
    item["category"] = categorize(title, content_type)
    return item


def categorize_items(items: list[dict]) -> list[dict]:
    """
    Add categories to a list of items.
    
    Args:
        items: List of item dictionaries
        
    Returns:
        Same list with 'category' key added to each item
    """
    return [categorize_item(item) for item in items]


def get_category_emoji(category: str) -> str:
    """
    Get an emoji for a category (for Slack display).
    
    Args:
        category: Category string
        
    Returns:
        Emoji string
    """
    emojis = {
        "RELEASE": ":rocket:",
        "TUTORIAL": ":books:",
        "WORKFLOW": ":gear:",
        "COMPARISON": ":scales:",
        "DISCUSSION": ":speech_balloon:",
        "NEWS": ":newspaper:"
    }
    return emojis.get(category, ":newspaper:")


def main():
    """Test the categorizer."""
    test_titles = [
        "Cursor v0.45.0 Released - New Multi-file Editing",
        "How to Use Claude Code for Large Refactors",
        "My Cursor AI Workflow for Maximum Productivity",
        "Cursor vs GitHub Copilot - Which is Better?",
        "Thoughts on the new Claude Code update?",
        "Anthropic announces Claude 3.5 Sonnet",
        "Tips for setting up your AI coding environment",
        "Getting Started with Local LLMs",
    ]
    
    print("Categorization Results:\n")
    for title in test_titles:
        category = categorize(title)
        emoji = get_category_emoji(category)
        print(f"{emoji} [{category}] {title}")


if __name__ == "__main__":
    main()
