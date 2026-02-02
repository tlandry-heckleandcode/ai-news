"""
Shared security utilities for sanitizing external input.

This module provides common functions for escaping, validating, and cleaning
data from external sources before displaying in Slack messages.
"""

import html
import re
from typing import Optional


def escape_mrkdwn(text: str, max_length: int = 0) -> str:
    """
    Escape Slack mrkdwn special characters to prevent injection.
    
    Args:
        text: Text to escape
        max_length: Maximum length (0 = no limit)
        
    Returns:
        Escaped and optionally truncated text
    """
    if not text:
        return ""
    
    # Truncate first if needed
    if max_length > 0 and len(text) > max_length:
        text = text[:max_length - 3] + "..."
    
    # Escape special mrkdwn characters: & < > * _ ~ `
    # Order matters: & must be first to avoid double-escaping
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    # These prevent formatting injection
    text = text.replace("*", "\\*")
    text = text.replace("_", "\\_")
    text = text.replace("~", "\\~")
    text = text.replace("`", "\\`")
    return text


def safe_url(url: str) -> str:
    """
    Return URL only if it appears safe, otherwise empty string.
    
    Args:
        url: URL to validate
        
    Returns:
        Original URL if safe, empty string otherwise
    """
    if url and url.startswith(("https://", "http://")):
        return url
    return ""


def clean_html(text: str) -> str:
    """
    Remove HTML tags and decode HTML entities from text.
    
    Args:
        text: Text potentially containing HTML
        
    Returns:
        Clean text without HTML
    """
    if not text:
        return ""
    
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    clean = html.unescape(clean)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def strip_urls(text: str) -> str:
    """
    Remove URLs from text.
    
    Args:
        text: Text potentially containing URLs
        
    Returns:
        Text with URLs removed
    """
    if not text:
        return ""
    
    # Remove http/https URLs
    text = re.sub(r'https?://\S+', '', text)
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def sanitize_title(text: str, max_length: int = 200) -> str:
    """
    Sanitize a title for display.
    
    Applies: HTML cleaning, URL stripping, length limit.
    Note: Does NOT apply mrkdwn escaping (do that at output time).
    
    Args:
        text: Raw title text
        max_length: Maximum length
        
    Returns:
        Sanitized title
    """
    text = clean_html(text)
    text = strip_urls(text)
    if max_length > 0 and len(text) > max_length:
        text = text[:max_length - 3] + "..."
    return text


def sanitize_description(text: str, max_length: int = 500) -> str:
    """
    Sanitize a description/summary for display.
    
    Applies: HTML cleaning, URL stripping, length limit.
    Note: Does NOT apply mrkdwn escaping (do that at output time).
    
    Args:
        text: Raw description text
        max_length: Maximum length
        
    Returns:
        Sanitized description
    """
    text = clean_html(text)
    text = strip_urls(text)
    if max_length > 0 and len(text) > max_length:
        text = text[:max_length - 3] + "..."
    return text


def sanitize_release_notes(text: str, max_length: int = 1000) -> str:
    """
    Sanitize release notes for display.
    
    Release notes often contain markdown which we strip for Slack display.
    
    Args:
        text: Raw release notes (may contain markdown)
        max_length: Maximum length
        
    Returns:
        Sanitized release notes
    """
    if not text:
        return ""
    
    # Remove markdown headers
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    # Remove markdown links but keep text: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove markdown bold/italic
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    # Remove code blocks
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove bullet points
    text = re.sub(r'^\s*[-*+]\s*', '', text, flags=re.MULTILINE)
    
    # Apply standard cleaning
    text = clean_html(text)
    text = strip_urls(text)
    
    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    if max_length > 0 and len(text) > max_length:
        text = text[:max_length - 3] + "..."
    
    return text
