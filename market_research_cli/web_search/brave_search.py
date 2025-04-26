#!/usr/bin/env python3

import os
import requests
import time
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class BraveSearchError(Exception):
    """Custom exception for Brave Search API errors."""
    pass

class AbstractSearchProvider:
    """Abstract base class for search providers to support future extensions."""
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for the given query and return results.
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            
        Returns:
            List of dictionaries containing title, description, and URL
        """
        raise NotImplementedError("Subclasses must implement search()")

class BraveSearch(AbstractSearchProvider):
    """Implementation of Brave Search API."""
    
    BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Brave Search API client.
        
        Args:
            api_key: Brave Search API key (if None, will try to read from environment)
        """
        self.api_key = api_key or os.getenv("BRAVE_API_KEY")
        if not self.api_key:
            raise BraveSearchError("Brave Search API key not found. Please set BRAVE_API_KEY in your .env file.")
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search using Brave Search API.
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            
        Returns:
            List of dictionaries containing title, description, and URL
        """
        try:
            headers = {
                "X-Subscription-Token": self.api_key,
                "Accept": "application/json",
            }
            
            params = {
                "q": query,
                "count": min(limit, 20),  # Brave API limit is 20 per request
            }
            
            response = requests.get(
                self.BASE_URL,
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code != 200:
                raise BraveSearchError(f"Brave Search API returned status code: {response.status_code}, response: {response.text}")
            
            data = response.json()
            
            # Parse the results
            results = []
            if "web" in data and "results" in data["web"]:
                for result in data["web"]["results"][:limit]:
                    results.append({
                        "title": result.get("title", ""),
                        "description": result.get("description", ""),
                        "url": result.get("url", "")
                    })
            
            return results
            
        except requests.RequestException as e:
            raise BraveSearchError(f"Error making request to Brave Search API: {str(e)}")
        except (KeyError, ValueError) as e:
            raise BraveSearchError(f"Error parsing Brave Search API response: {str(e)}")

def get_search_provider(provider_name: str = "brave") -> AbstractSearchProvider:
    """
    Factory function to get the appropriate search provider.
    This allows for easy extension to other search providers in the future.
    
    Args:
        provider_name: Name of the search provider ("brave" for now)
        
    Returns:
        An instance of a search provider
    """
    if provider_name.lower() == "brave":
        return BraveSearch()
    else:
        raise ValueError(f"Unknown search provider: {provider_name}")

def format_search_results_for_prompt(results: List[Dict[str, str]]) -> str:
    """
    Format search results for inclusion in AI prompt.
    
    Args:
        results: List of search result dictionaries
        
    Returns:
        Markdown formatted string for prompt
    """
    if not results:
        return "No web search results found."
    
    output = "Based on the following web search results:\n\n"
    
    for i, result in enumerate(results, 1):
        output += f"{i}. [{result['title']}] - {result['description']} ({result['url']})\n\n"
    
    output += "Generate a comprehensive, professional market research report using ONLY the information from these sources.\n"
    output += "Please ensure all information is factual and based on these search results. Do not hallucinate or include information not found in these sources.\n"
    
    return output 