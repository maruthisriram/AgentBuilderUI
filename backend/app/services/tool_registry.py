"""
Tool registry — real LangChain tool implementations.
Simple single-parameter tools for Groq compatibility.
"""

import math
import json
import requests
from langchain_core.tools import tool

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger("tools")


@tool
def web_search(query: str) -> str:
    """Search the web for current information about any topic. Input should be a search query string."""
    try:
        from langchain_community.tools.tavily_search import TavilySearchResults
        tavily = TavilySearchResults(
            max_results=5,
            tavily_api_key=settings.tavily_api_key,
        )
        logger.info(f"Web search: {query}")
        results = tavily.invoke(query)
        if isinstance(results, list):
            return "\n\n".join(
                f"**{r.get('title', 'Result')}**\n{r.get('content', r.get('snippet', str(r)))}"
                for r in results[:5]
            )
        return str(results)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"Search error: {str(e)}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result. Input should be a math expression like '2 + 3 * 4' or 'sqrt(144)'."""
    try:
        allowed_names = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "log": math.log, "log10": math.log10,
            "pi": math.pi, "e": math.e, "abs": abs, "round": round,
            "pow": pow, "min": min, "max": max,
        }
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        logger.info(f"Calculator: {expression} = {result}")
        return str(result)
    except Exception as e:
        logger.error(f"Calculator error: {e}")
        return f"Calculation error: {str(e)}"


@tool
def code_interpreter(code: str) -> str:
    """Execute Python code and return the printed output. Input should be valid Python code. Use print() to produce output."""
    import io
    import sys
    logger.info(f"Code interpreter: executing {len(code)} chars")
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(code, {"__builtins__": __builtins__})
        output = sys.stdout.getvalue()
        return output if output else "Code executed successfully (no output)"
    except Exception as e:
        logger.error(f"Code interpreter error: {e}")
        return f"Execution error: {str(e)}"
    finally:
        sys.stdout = old_stdout


@tool
def api_call(url: str) -> str:
    """Make an HTTP GET request to a URL and return the response. Input should be a valid URL."""
    try:
        logger.info(f"API call: GET {url}")
        resp = requests.get(url, timeout=10)
        return f"Status: {resp.status_code}\n{resp.text[:2000]}"
    except Exception as e:
        logger.error(f"API call error: {e}")
        return f"API call error: {str(e)}"


@tool
def wikipedia_search(query: str) -> str:
    """Search Wikipedia for information about a topic. Input should be a search query string."""
    try:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 3,
            "utf8": 1,
        }
        headers = {
            "User-Agent": "AgentBuilderApp/1.0 (educational project)",
            "Accept": "application/json",
        }
        logger.info(f"Wikipedia search: {query}")
        resp = requests.get(url, params=params, headers=headers, timeout=10)

        if resp.status_code != 200:
            return f"Wikipedia returned status {resp.status_code}"

        content_type = resp.headers.get("Content-Type", "")
        if "json" not in content_type and "javascript" not in content_type:
            return f"Wikipedia returned unexpected content type: {content_type}"

        data = resp.json()
        results = data.get("query", {}).get("search", [])
        if not results:
            return f"No Wikipedia results found for: {query}"

        output = []
        for r in results:
            title = r.get("title", "Unknown")
            snippet = r.get("snippet", "")
            snippet = snippet.replace('<span class="searchmatch">', '').replace('</span>', '')
            snippet = snippet.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            output.append(f"**{title}**: {snippet}")
        return "\n\n".join(output)
    except json.JSONDecodeError:
        return f"Wikipedia returned invalid response for query: {query}. Try rephrasing your search."
    except requests.exceptions.Timeout:
        return f"Wikipedia request timed out for: {query}"
    except Exception as e:
        logger.error(f"Wikipedia error: {e}")
        return f"Wikipedia error: {str(e)}"


# Registry: toolId → tool function
TOOL_REGISTRY = {
    "tool-web-search": web_search,
    "tool-calculator": calculator,
    "tool-code-interpreter": code_interpreter,
    "tool-api-call": api_call,
    "tool-wikipedia": wikipedia_search,
}
