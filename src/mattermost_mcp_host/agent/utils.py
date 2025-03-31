from typing import List
from langchain.schema import BaseMessage, AIMessage


def get_final_response(messages: List[BaseMessage]) -> str:
    """Extract the final response from the messages.
    
    Args:
        messages: The messages from the agent run
        
    Returns:
        The final response as a string
    """
    
    messages_to_send = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            if hasattr(msg, 'additional_kwargs') and msg.additional_kwargs != {} and msg.content == "":
                tool_calls = msg.additional_kwargs.get('tool_calls', [])
                for tool_call in tool_calls:
                    if tool_call.get('type') == 'function':
                        tool_call_message = f"Called tool: {tool_call.get('function', {}).get('name')} with arguments: {tool_call.get('function', {}).get('arguments')}"
                    messages_to_send.append(tool_call_message)
            else:
                messages_to_send.append(msg.content)
            
    return messages_to_send
    # ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
    
    # # Return the content of the last AI message
    # if ai_messages:
    #     return ai_messages[-1].content
    
    # return "No response generated."