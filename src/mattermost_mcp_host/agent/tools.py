import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

@tool
def search(query: str) -> str:
    """Mock implementation of Search for information based on a query."""
    # This is a mock implementation
    logger.info(f"Searching for: {query}")
    return f"Results for query: {query}"

@tool
def calculator(expression: str) -> str:
    """Calculate the result of a mathematical expression."""
    try:
        # Simple and safe evaluation of mathematical expressions
        # In a real implementation, you would use a safer method
        result = eval(expression, {"__builtins__": {}}, {"abs": abs, "round": round, "max": max, "min": min})
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error calculating {expression}: {str(e)}"

@tool
def weather(location: str) -> str:
    """Get the weather for a location."""
    # This is a mock implementation
    logger.info(f"Getting weather for: {location}")
    return f"The weather in {location} is sunny and 72°F"


@tool
def get_current_date_time() -> str:
    """Get the current date and time. Returns the current date and time in ISO format."""
    import datetime
    # This is a mock implementation
    now = datetime.datetime.now()
    # return f"The current date and time is: {now}"
    # return the current date and time in iso format with timezone
    return now.isoformat()


# List of available tools
tools = [search, calculator, weather, get_current_date_time]