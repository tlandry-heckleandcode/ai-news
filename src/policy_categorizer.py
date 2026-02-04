"""
Policy content categorizer for YouTube policy intelligence.

Categorizes content based on title keywords to identify
the type of policy change or discussion.
"""

import re
from typing import Optional


# Policy-specific category definitions with keywords
POLICY_CATEGORIES = {
    "MONETIZATION": {
        "keywords": [
            r"\bdemonetiz", r"\badsense\b", r"\brevenue\b", r"\bcpm\b",
            r"\bypp\b", r"\bpartner\s*program", r"\bmonetiz", r"\bads?\s+policy",
            r"\bad\s+suitab", r"\badvertiser", r"\bearnings?\b", r"\bpayment"
        ],
        "priority": 1,
        "emoji": ":moneybag:"
    },
    "CONTENT_GUIDELINES": {
        "keywords": [
            r"\bcommunity\s+guidelines?\b", r"\bstrike\b", r"\bremoved?\b",
            r"\bviolat", r"\brestrict", r"\bage[\s-]restrict", r"\bsuspend",
            r"\bterminat", r"\bban(ned)?\b", r"\bappeal\b", r"\bwarning\b"
        ],
        "priority": 2,
        "emoji": ":shield:"
    },
    "COPYRIGHT": {
        "keywords": [
            r"\bcopyright\b", r"\bdmca\b", r"\bcontent\s*id\b", r"\bclaim\b",
            r"\btakedown\b", r"\bfair\s+use\b", r"\blicens", r"\bmusic\s+policy"
        ],
        "priority": 3,
        "emoji": ":copyright:"
    },
    "ALGORITHM": {
        "keywords": [
            r"\balgorithm\b", r"\bshadowban", r"\bimpressions?\b", r"\breach\b",
            r"\brecommend", r"\bdiscover", r"\bvisibility\b", r"\bsuppressed?\b",
            r"\bviews?\s+drop", r"\btrending\b"
        ],
        "priority": 4,
        "emoji": ":bar_chart:"
    },
    "TERMS_OF_SERVICE": {
        "keywords": [
            r"\btos\b", r"\bterms\s+of\s+service\b", r"\bpolicy\s+update",
            r"\bpolicy\s+change", r"\bnew\s+policy", r"\brules?\s+change",
            r"\bguidelines?\s+update"
        ],
        "priority": 5,
        "emoji": ":scroll:"
    },
    "API_CHANGES": {
        "keywords": [
            r"\bapi\b", r"\bdeveloper\b", r"\bquota\b", r"\bendpoint",
            r"\bdeprecated?\b", r"\brate\s+limit", r"\boauth\b", r"\bsdk\b"
        ],
        "priority": 6,
        "emoji": ":wrench:"
    },
    "AI_POLICY": {
        "keywords": [
            r"\bai[\s-]generat", r"\bsynthetic\b", r"\bdeepfake\b",
            r"\bartificial\s+intelligen", r"\bmachine\s+learn", r"\bgenerat.*\s+content",
            r"\bdream\s*track", r"\bai\s+disclos", r"\bai\s+label"
        ],
        "priority": 7,
        "emoji": ":robot_face:"
    },
    "GENERAL": {
        "keywords": [],  # Default fallback
        "priority": 99,
        "emoji": ":mega:"
    }
}


def categorize_policy(title: str, content: Optional[str] = None) -> str:
    """
    Categorize policy content based on title and optional content.
    
    Args:
        title: Content title to analyze
        content: Optional full content/description for deeper analysis
        
    Returns:
        Category string (e.g., "MONETIZATION", "COPYRIGHT", "GENERAL")
    """
    if not title:
        return "GENERAL"
    
    # Combine title and content for analysis
    text_to_analyze = title.lower()
    if content:
        text_to_analyze += " " + content.lower()[:500]  # Limit content length
    
    # Check each category's keywords
    matches = []
    for category, config in POLICY_CATEGORIES.items():
        for pattern in config["keywords"]:
            if re.search(pattern, text_to_analyze, re.IGNORECASE):
                matches.append((category, config["priority"]))
                break
    
    # Return highest priority match
    if matches:
        matches.sort(key=lambda x: x[1])
        return matches[0][0]
    
    return "GENERAL"


def categorize_policy_item(item: dict) -> dict:
    """
    Add policy category to an item dictionary.
    
    Args:
        item: Dictionary with 'title' and optionally 'summary' or 'description' keys
        
    Returns:
        Same dictionary with 'category' key added
    """
    title = item.get("title", "")
    content = item.get("summary") or item.get("description", "")
    
    item["category"] = categorize_policy(title, content)
    return item


def categorize_policy_items(items: list[dict]) -> list[dict]:
    """
    Add policy categories to a list of items.
    
    Args:
        items: List of item dictionaries
        
    Returns:
        Same list with 'category' key added to each item
    """
    return [categorize_policy_item(item) for item in items]


def get_policy_category_emoji(category: str) -> str:
    """
    Get an emoji for a policy category (for Slack display).
    
    Args:
        category: Category string
        
    Returns:
        Emoji string
    """
    config = POLICY_CATEGORIES.get(category, POLICY_CATEGORIES["GENERAL"])
    return config.get("emoji", ":mega:")


def main():
    """Test the policy categorizer."""
    test_titles = [
        "YouTube updates monetization policies for AI-generated content",
        "New community guidelines strike system announced",
        "Content ID now detects AI-generated music",
        "Algorithm changes causing view drops for creators",
        "Terms of Service update effective January 2026",
        "YouTube Data API v3 quota changes",
        "Deepfake policy expanded to cover synthetic voices",
        "Channel demonetized without warning - what happened?",
        "Copyright claim on fair use content",
        "Shadowbanned? How to check your reach",
    ]
    
    print("Policy Categorization Results:\n")
    for title in test_titles:
        category = categorize_policy(title)
        emoji = get_policy_category_emoji(category)
        print(f"{emoji} [{category}] {title}")


if __name__ == "__main__":
    main()
