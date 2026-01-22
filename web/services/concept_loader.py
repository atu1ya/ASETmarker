"""
Concept loader utility for dynamic concept mapping based on year level.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Path to config directory
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

# Default year level
DEFAULT_YEAR_LEVEL = "year4_5"

# Cached concepts to avoid repeated file reads
_concept_cache: Dict[str, Dict[str, Any]] = {}


def get_available_year_levels() -> List[Dict[str, str]]:
    """
    Returns a list of available year levels with their display names.
    """
    return [
        {"value": "year4_5", "label": "Year 4/5 (Standard)"},
        {"value": "senior", "label": "Senior (Year 7+)"},
    ]


def load_concepts(year_level: Optional[str] = None) -> Dict[str, Any]:
    """
    Load concepts from the appropriate JSON config file based on year level.
    
    Args:
        year_level: The year level identifier (e.g., "year4_5", "senior").
                   If None, uses DEFAULT_YEAR_LEVEL.
    
    Returns:
        Dictionary containing all concept mappings and configurations.
    """
    if not year_level:
        year_level = DEFAULT_YEAR_LEVEL
    
    # Check cache first
    if year_level in _concept_cache:
        return _concept_cache[year_level]
    
    # Build config file path
    config_file = CONFIG_DIR / f"concepts_{year_level}.json"
    
    if not config_file.exists():
        # Fall back to default if specified year level doesn't exist
        config_file = CONFIG_DIR / f"concepts_{DEFAULT_YEAR_LEVEL}.json"
        if not config_file.exists():
            # Return empty defaults if no config exists
            return _get_fallback_concepts()
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            concepts = json.load(f)
        
        # Cache for future use
        _concept_cache[year_level] = concepts
        return concepts
    except (json.JSONDecodeError, IOError):
        return _get_fallback_concepts()


def get_reading_concepts(year_level: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Get Reading concept mappings for the specified year level.
    
    Returns:
        Dictionary mapping concept names to lists of question numbers.
    """
    concepts = load_concepts(year_level)
    return concepts.get("Reading", {})


def get_qr_concepts(year_level: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Get Quantitative Reasoning concept mappings for the specified year level.
    
    Returns:
        Dictionary mapping concept names to lists of question numbers.
    """
    concepts = load_concepts(year_level)
    return concepts.get("Quantitative Reasoning", {})


def get_reading_concepts_list(year_level: Optional[str] = None) -> List[str]:
    """
    Get Reading concept names as a list for the specified year level.
    
    Returns:
        List of concept names.
    """
    return list(get_reading_concepts(year_level).keys())


def get_qr_concepts_list(year_level: Optional[str] = None) -> List[str]:
    """
    Get Quantitative Reasoning concept names as a list for the specified year level.
    
    Returns:
        List of concept names.
    """
    return list(get_qr_concepts(year_level).keys())


def get_school_minimum_scores(year_level: Optional[str] = None) -> Dict[str, float]:
    """
    Get school minimum score cutoffs for the specified year level.
    
    Returns:
        Dictionary mapping school names to minimum scores.
    """
    concepts = load_concepts(year_level)
    return concepts.get("school_minimum_scores", {})


def get_journey_stages(year_level: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get journey stage definitions for the specified year level.
    
    Returns:
        List of stage dictionaries with label and score keys.
    """
    concepts = load_concepts(year_level)
    return concepts.get("journey_stages", [])


def get_score_config(year_level: Optional[str] = None) -> Dict[str, int]:
    """
    Get score configuration (totals) for the specified year level.
    
    Returns:
        Dictionary with reading_total, writing_total, qr_total, ar_total, total_max.
    """
    concepts = load_concepts(year_level)
    return concepts.get("score_config", {
        "reading_total": 35,
        "writing_total": 50,
        "qr_total": 35,
        "ar_total": 35,
        "total_max": 400
    })


def clear_cache():
    """Clear the concept cache to force reload from files."""
    global _concept_cache
    _concept_cache = {}


def _get_fallback_concepts() -> Dict[str, Any]:
    """
    Returns fallback concept mappings if no config file is available.
    """
    return {
        "Reading": {
            "Understanding main ideas": ["1", "2", "6", "21", "26", "35"],
            "Inference and deduction": ["3", "5", "16", "17", "18", "22", "28", "34"],
            "Identifying key details": ["4", "7", "8", "9", "10", "11", "12", "15", "19", "20", "23", "24", "27", "29"],
            "Vocabulary context clues": ["14", "25", "31"],
            "Author's purpose and tone": ["13", "26"],
            "Cause and effect relationships": ["21", "22", "24"],
            "Understanding tone and attitude": ["16", "18", "32", "34"],
            "Figurative / Literary devices": ["30", "33"]
        },
        "Quantitative Reasoning": {
            "Fractions / Decimals": ["7", "28", "30", "31", "34", "35"],
            "Time": ["28"],
            "Algebra": ["6", "18", "21", "22"],
            "Geometry": ["1", "2", "3", "4", "5", "33"],
            "Graph / Data Interpretation": ["8", "9", "10", "12", "13", "32"],
            "Multiplication / Division": ["14", "15", "16", "17", "29"],
            "Area / Perimeter": ["3", "5"],
            "Ratios / Unit Conversions": ["19", "20", "22"],
            "Probability": ["26"],
            "Patterns / Sequences": ["23", "24", "25", "35"],
            "Percentages": ["11", "27"]
        },
        "school_minimum_scores": {
            "Perth Modern School": 244.34,
            "Willetton SHS": 235.98,
            "Shenton SHS": 231.55,
            "Rossmoyne SHS": 227.00,
            "Harrisdale SHS": 226.57,
            "Kelmscott SHS": 209.5
        },
        "journey_stages": [],
        "score_config": {
            "reading_total": 35,
            "writing_total": 50,
            "qr_total": 35,
            "ar_total": 35,
            "total_max": 400
        }
    }
