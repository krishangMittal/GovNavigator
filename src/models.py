"""
models.py - Data models for our municipal code system

=== WHAT ARE DATA MODELS? ===
Data models define the STRUCTURE of our data. Think of them like blueprints:
- A "User" model might have: name, email, password
- Our "Ordinance" model has: section_number, title, content, etc.

=== WHY USE PYDANTIC? ===
Pydantic is a library that:
1. Validates data automatically (catches errors early)
2. Converts types (string "123" → integer 123)
3. Generates documentation
4. Works great with modern Python type hints

Example without Pydantic:
    data = {"name": "John", "age": "not a number"}  # Bug! age should be int
    # This would crash later when you do: age + 1

Example with Pydantic:
    user = User(name="John", age="not a number")
    # Pydantic catches this IMMEDIATELY and tells you the error
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Ordinance(BaseModel):
    """
    Represents a single municipal ordinance/code section.

    === CLASS INHERITANCE ===
    `class Ordinance(BaseModel)` means:
    - Ordinance "inherits from" BaseModel
    - It gets all of Pydantic's validation superpowers
    - Like a child inheriting traits from a parent
    """

    # === FIELD DEFINITIONS ===
    # Each line defines a piece of data this model holds

    section_number: str = Field(
        ...,  # ... means "required" - you MUST provide this
        description="The official section number, e.g., '28.04(1)(a)'",
        examples=["28.04", "28.142(3)(b)"]
    )

    title: str = Field(
        ...,
        description="The title/name of this ordinance section",
        examples=["Fence Regulations", "Short-Term Rentals"]
    )

    content: str = Field(
        ...,
        description="The full text content of the ordinance"
    )

    chapter: str = Field(
        ...,
        description="The chapter this belongs to, e.g., 'Chapter 28 - Zoning'",
        examples=["Chapter 28 - Zoning Code", "Chapter 9 - Public Safety"]
    )

    # Optional fields use Optional[type] and have defaults
    jurisdiction: str = Field(
        default="Madison, WI",
        description="The city/jurisdiction this ordinance belongs to"
    )

    last_updated: Optional[datetime] = Field(
        default=None,
        description="When this ordinance was last amended"
    )

    url: Optional[str] = Field(
        default=None,
        description="Link to the official source"
    )

    # === MODEL CONFIGURATION ===
    model_config = {
        # This creates an example for documentation/testing
        "json_schema_extra": {
            "examples": [
                {
                    "section_number": "28.142(1)",
                    "title": "Fence Height Limits",
                    "content": "No fence in a required front yard shall exceed 4 feet in height...",
                    "chapter": "Chapter 28 - Zoning Code",
                    "jurisdiction": "Madison, WI",
                }
            ]
        }
    }


class SearchResult(BaseModel):
    """
    Represents a single search result when someone queries ordinances.

    This is what we return when Claude asks "find ordinances about fences"
    """

    ordinance: Ordinance = Field(
        ...,
        description="The matching ordinance"
    )

    relevance_score: float = Field(
        ...,
        ge=0.0,  # ge = "greater than or equal to" (minimum 0)
        le=1.0,  # le = "less than or equal to" (maximum 1)
        description="How relevant this result is (0.0 to 1.0)"
    )

    matched_terms: list[str] = Field(
        default_factory=list,  # default_factory creates a new empty list each time
        description="Which search terms matched in this ordinance"
    )

    snippet: str = Field(
        default="",
        description="A relevant excerpt from the ordinance highlighting the match"
    )


class SearchQuery(BaseModel):
    """
    Represents a search request from the user.
    """

    query: str = Field(
        ...,
        min_length=1,  # Must have at least 1 character
        description="The natural language search query",
        examples=["Can I build a fence?", "short term rental rules"]
    )

    jurisdiction: str = Field(
        default="Madison, WI",
        description="Which city to search"
    )

    max_results: int = Field(
        default=5,
        ge=1,   # At least 1 result
        le=20,  # At most 20 results
        description="Maximum number of results to return"
    )


# === TYPE ALIAS ===
# This creates a shorthand name for a complex type
# Instead of writing list[SearchResult] everywhere, we can write SearchResults
SearchResults = list[SearchResult]
