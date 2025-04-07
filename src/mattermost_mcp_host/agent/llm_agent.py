from mattermost_mcp_host.agent.utils import get_final_response
from mattermost_mcp_host.agent.tools import tools

import os
import logging
from typing import Dict, List, Optional, TypedDict, Any, Annotated
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, AnyMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END, START, add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)
# Set logging level to DEBUG
# logging.basicConfig(level=logging.DEBUG)

# Define the agent state
# class AgentState(TypedDict):
#     messages: List[BaseMessage]

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    metadata: Optional[Dict[Any, Any]]

# Define the agent class
class LangGraphAgent:
    def __init__(self, 
                 name: str,
                 provider: str = "azure", 
                 model: str = None, 
                 system_prompt: str = None, 
                 tools: List[callable] = tools,
                 ):
        """Initialize the LangGraph agent.
        
        Args:
            provider: The LLM provider (default: azure)
            model: The model to use
            system_prompt: Optional system prompt to use for the agent
        """
        self.provider = provider
        self.model = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        self.system_prompt_template = system_prompt or "You are a helpful AI assistant. Below is the context of the conversation for Mattermost: \n \n {context} \n\nCurrent date and time: {current_date_time}"
        
        # Initialize the LangChain LLM
        self.llm = AzureChatOpenAI(
            azure_deployment=self.model,
            openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        )
        self.name = name
        
        # log the tools
        logger.info(f"Tools: {tools}")
        self.tools = tools

        self.llm_with_tools = self.llm.bind_tools(tools)
        
        # Create the agent graph
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the agent graph."""
        # Define the prompt template
        # prompt = ChatPromptTemplate.from_messages(
        #     [
        #         SystemMessage(content=self.system_prompt),
        #         MessagesPlaceholder(variable_name="messages"),
        #     ]
        # )
        
        # Define the agent node
        async def agent_node(state: AgentState):
            """Agent node that processes messages and decides on actions."""
            messages = state["messages"]
            
            logger.info(f"Agent Node: {messages}")
            # Use the prompt template to format messages
            # formatted_messages = prompt.invoke({"messages": messages})
            response = await self.llm_with_tools.ainvoke(messages)
            return {"messages": [response]}
        
        def should_continue(state: AgentState) -> str:
            """Determine if we should continue or end."""
            messages = state["messages"]
            last_message = messages[-1]
            # Check if the last message has tool calls
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"
            return END

        # Create the tool execution node
        tool_node = ToolNode(tools=self.tools)
        
        # Create the graph with a memory checkpointer
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)

        workflow.add_edge(START, "agent")
         
        # Add edges
        workflow.add_conditional_edges("agent", should_continue, ["tools", END])
        workflow.add_edge("tools", "agent")
        
        # # Set the entry point
        # workflow.set_entry_point("agent")
        
        # TODO: Add a reliable checkpointer for production, Postgres 
        return workflow.compile(checkpointer=MemorySaver())
    
    async def run(self, query: str, history: List[Dict[str, str]], user_id: Optional[str] = None, metadata: Optional[Dict[Any, Any]] = None) -> Dict[str, List[BaseMessage]]:
        """Run the agent with a query.
        
        Args:
            query: The user query
            
        Returns:
            The state containing messages from the agent run
        """
        logger.info(f"System Prompt: {self.system_prompt_template}")
        
        if self.name == "github":            
            github_tools = [tool for tool in self.tools if tool.name.lower() in ["list_issues", "list_pull_requests"]]
            
            github_context = ""
            for tool in github_tools:
                tool_context = tool.ainvoke(input={'owner': metadata.get('github_username'), 'repo': metadata.get('github_repo')})
                github_context += f"\n\n{tool.name}: {tool_context}"

            messages = [SystemMessage(content=self.system_prompt_template.format(context=metadata, 
                                                                                current_date_time=datetime.now().isoformat(), 
                                                                                github_context=github_context))]
        else:
            messages = [SystemMessage(content=self.system_prompt_template.format(context=metadata, 
                                                                                current_date_time=datetime.now().isoformat()))]
        # Add history messages if available
        for msg in history:
            if msg["content"] == query:
                continue
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                if msg["content"] != "Processing your request...":
                    messages.append(AIMessage(content=msg["content"]))
        
        # Add the current query as the latest message
        messages.append(HumanMessage(content=query))
        state = {"messages": messages}

        # TODO: Add metadata as config for Agent's memory, currently does not work
        config = {
                "configurable": {
                    "user_id": user_id or "unknown",
                    "thread_id": "user-123-conversation-456",
                    "checkpoint_ns": "my-app",
                    "checkpoint_id": "optional-specific-checkpoint-id"
                }
            }        
        
        result = await self.graph.ainvoke(state, config)
        
        return result

    def extract_response(self, messages: List[BaseMessage]) -> str:
        """Extract the final response from the messages.
        
        Args:
            messages: The messages from the agent run
            
        Returns:
            The final response as a string
        """
        return get_final_response(messages)
        
    def set_tools(self, tools: List[callable]):
        """Add tools to the agent.

        Args:
            tools: The tools to add
        """
        self.tools = tools
        self.llm_with_tools = self.llm.bind_tools(tools)
        self.graph = self._build_graph()


async def test_agent():
    # Load the env variables in the .env file
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env")

    agent = LangGraphAgent()
    messages = []
    while True:
        query = input("Enter your query: ")
        # query = "What is the weather in Boston?"

        # Run the agent with a query and print the results
        result = await agent.run(query=query, history=messages, user_id="123")
        for message in result["messages"]:
            print(f"{message.type}: {message.content}")
            if message.type == "ai":
                messages.append({"role": "assistant", "content": message.content})
            elif message.type == "human":
                messages.append({"role": "user", "content": message.content})
        
        print("----------------------------------------")
        print("History: ", messages)
        print("----------------------------------------")


# For testing directly
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent())
    
