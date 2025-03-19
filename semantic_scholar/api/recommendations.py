"""
Recommendation-related API endpoints for the Semantic Scholar API.
"""

from typing import Dict, List, Optional
from fastmcp import Context
import httpx

# Import mcp from centralized location instead of server
from ..mcp import mcp
from ..config import Config, ErrorType
from ..utils.http import rate_limiter, get_api_key
from ..utils.errors import create_error_response

@mcp.tool()
async def get_paper_recommendations_single(
    context: Context,
    paper_id: str,
    fields: Optional[str] = None,
    limit: int = 100,
    from_pool: str = "recent"
) -> Dict:
    """
    Get paper recommendations based on a single seed paper.
    This endpoint is optimized for finding papers similar to a specific paper.

    Args:
        paper_id (str): Paper identifier in one of the following formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - CorpusId:<id> (e.g., "CorpusId:215416146")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")

        fields (Optional[str]): Comma-separated list of fields to return for each paper.
            paperId is always returned.

        limit (int): Maximum number of recommendations to return.
            Default: 100
            Maximum: 500

        from_pool (str): Which pool of papers to recommend from.
            Options:
            - "recent": Recent papers (default)
            - "all-cs": All computer science papers
            Default: "recent"

    Returns:
        Dict: {
            "recommendedPapers": List[Dict] # List of recommended papers with requested fields
        }
    """
    try:
        # Apply rate limiting
        endpoint = "/recommendations"
        await rate_limiter.acquire(endpoint)

        # Validate limit
        if limit > 500:
            return create_error_response(
                ErrorType.VALIDATION,
                "Cannot request more than 500 recommendations",
                {"max_limit": 500, "requested": limit}
            )

        # Validate pool
        if from_pool not in ["recent", "all-cs"]:
            return create_error_response(
                ErrorType.VALIDATION,
                "Invalid paper pool specified",
                {"valid_pools": ["recent", "all-cs"]}
            )

        # Build request parameters
        params = {
            "limit": limit,
            "from": from_pool
        }
        if fields:
            params["fields"] = fields

        # Make the API request
        async with httpx.AsyncClient(timeout=Config.TIMEOUT) as client:
            api_key = get_api_key()
            headers = {"x-api-key": api_key} if api_key else {}
            
            url = f"https://api.semanticscholar.org/recommendations/v1/papers/forpaper/{paper_id}"
            response = await client.get(url, params=params, headers=headers)
            
            # Handle specific error cases
            if response.status_code == 404:
                return create_error_response(
                    ErrorType.VALIDATION,
                    "Paper not found",
                    {"paper_id": paper_id}
                )
            
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return create_error_response(
                ErrorType.RATE_LIMIT,
                "Rate limit exceeded. Consider using an API key for higher limits.",
                {
                    "retry_after": e.response.headers.get("retry-after"),
                    "authenticated": bool(get_api_key())
                }
            )
        return create_error_response(
            ErrorType.API_ERROR,
            f"HTTP error {e.response.status_code}",
            {"response": e.response.text}
        )
    except httpx.TimeoutException:
        return create_error_response(
            ErrorType.TIMEOUT,
            f"Request timed out after {Config.TIMEOUT} seconds"
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error in recommendations: {str(e)}")
        return create_error_response(
            ErrorType.API_ERROR,
            "Failed to get recommendations",
            {"error": str(e)}
        )

@mcp.tool()
async def get_paper_recommendations_multi(
    context: Context,
    positive_paper_ids: List[str],
    negative_paper_ids: Optional[List[str]] = None,
    fields: Optional[str] = None,
    limit: int = 100
) -> Dict:
    """
    Get paper recommendations based on multiple positive and optional negative examples.
    This endpoint is optimized for finding papers similar to a set of papers while
    avoiding papers similar to the negative examples.

    Args:
        positive_paper_ids (List[str]): List of paper IDs to use as positive examples.
            Papers similar to these will be recommended.
            Each ID can be in any of these formats:
            - Semantic Scholar ID (e.g., "649def34f8be52c8b66281af98ae884c09aef38b")
            - CorpusId:<id> (e.g., "CorpusId:215416146")
            - DOI:<doi> (e.g., "DOI:10.18653/v1/N18-3011")
            - ARXIV:<id> (e.g., "ARXIV:2106.15928")
            - MAG:<id> (e.g., "MAG:112218234")
            - ACL:<id> (e.g., "ACL:W12-3903")
            - PMID:<id> (e.g., "PMID:19872477")
            - PMCID:<id> (e.g., "PMCID:2323736")
            - URL:<url> (e.g., "URL:https://arxiv.org/abs/2106.15928v1")

        negative_paper_ids (Optional[List[str]]): List of paper IDs to use as negative examples.
            Papers similar to these will be avoided in recommendations.
            Uses same ID formats as positive_paper_ids.

        fields (Optional[str]): Comma-separated list of fields to return for each paper.
            paperId is always returned.

        limit (int): Maximum number of recommendations to return.
            Default: 100
            Maximum: 500

    Returns:
        Dict: {
            "recommendedPapers": List[Dict] # List of recommended papers with requested fields
        }
    """
    try:
        # Apply rate limiting
        endpoint = "/recommendations"
        await rate_limiter.acquire(endpoint)

        # Validate inputs
        if not positive_paper_ids:
            return create_error_response(
                ErrorType.VALIDATION,
                "Must provide at least one positive paper ID"
            )

        if limit > 500:
            return create_error_response(
                ErrorType.VALIDATION,
                "Cannot request more than 500 recommendations",
                {"max_limit": 500, "requested": limit}
            )

        # Build request parameters
        params = {"limit": limit}
        if fields:
            params["fields"] = fields

        request_body = {
            "positivePaperIds": positive_paper_ids,
            "negativePaperIds": negative_paper_ids or []
        }

        # Make the API request
        async with httpx.AsyncClient(timeout=Config.TIMEOUT) as client:
            api_key = get_api_key()
            headers = {"x-api-key": api_key} if api_key else {}
            
            url = "https://api.semanticscholar.org/recommendations/v1/papers"
            response = await client.post(url, params=params, json=request_body, headers=headers)
            
            # Handle specific error cases
            if response.status_code == 404:
                return create_error_response(
                    ErrorType.VALIDATION,
                    "One or more input papers not found",
                    {
                        "positive_ids": positive_paper_ids,
                        "negative_ids": negative_paper_ids
                    }
                )
            
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            return create_error_response(
                ErrorType.RATE_LIMIT,
                "Rate limit exceeded. Consider using an API key for higher limits.",
                {
                    "retry_after": e.response.headers.get("retry-after"),
                    "authenticated": bool(get_api_key())
                }
            )
        return create_error_response(
            ErrorType.API_ERROR,
            f"HTTP error {e.response.status_code}",
            {"response": e.response.text}
        )
    except httpx.TimeoutException:
        return create_error_response(
            ErrorType.TIMEOUT,
            f"Request timed out after {Config.TIMEOUT} seconds"
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error in recommendations: {str(e)}")
        return create_error_response(
            ErrorType.API_ERROR,
            "Failed to get recommendations",
            {"error": str(e)}
        ) 