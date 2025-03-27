from typing import List
from langchain.schema import BaseMessage, AIMessage


def get_final_response(messages: List[BaseMessage]) -> str:
    """Extract the final response from the messages.
    
    Args:
        messages: The messages from the agent run
        
    Returns:
        The final response as a string
    """
    # Filter for AI messages only
    ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
    
    # Return the content of the last AI message
    if ai_messages:
        return ai_messages[-1].content
    
    return "No response generated."