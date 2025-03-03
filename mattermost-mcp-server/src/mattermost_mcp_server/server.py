import asyncio
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

# Mattermost Configuration
MATTERMOST_URL = os.environ.get('MATTERMOST_URL', 'localhost')
MATTERMOST_TOKEN = os.environ.get('MATTERMOST_TOKEN', '548eya8qofdq7ygio958iirrco')
MATTERMOST_SCHEME = os.environ.get('MATTERMOST_SCHEME', 'http')
MATTERMOST_PORT = int(os.environ.get('MATTERMOST_PORT', '8065'))
MATTERMOST_TEAM_NAME = os.environ.get('MATTERMOST_TEAM_NAME', 'test')
MATTERMOST_CHANNEL_NAME = os.environ.get('MATTERMOST_CHANNEL_NAME', 'mcp-client')
MATTERMOST_CHANNEL_ID = os.environ.get('MATTERMOST_CHANNEL_ID', '5q39mmzqji8bddxyjzsqbziy9a')  # Will be auto-detected if empty

class config:
    LOG_LEVEL = "DEBUG"

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store messages and channels as in-memory cache
channels_cache: Dict[str, Dict] = {}
team_cache: Dict[str, Dict] = {}
posts_cache: Dict[str, List[Dict]] = {}
channel_id_to_name: Dict[str, str] = {}
team_id_to_name: Dict[str, str] = {}

server = Server("mattermost-mcp-server")

# Mattermost API helper functions
async def get_mattermost_headers():
    """Return headers for Mattermost API calls"""
    return {
        "Authorization": f"Bearer {MATTERMOST_TOKEN}",
        "Content-Type": "application/json"
    }

async def get_mattermost_base_url():
    """Return base URL for Mattermost API"""
    return f"{MATTERMOST_SCHEME}://{MATTERMOST_URL}:{MATTERMOST_PORT}/api/v4"

async def fetch_team_id(team_name: str):
    """Fetch team ID from team name"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    # Check cache first
    for team_id, team in team_cache.items():
        if team.get("name") == team_name:
            return team_id
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/teams/name/{team_name}"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                team_data = await response.json()
                team_id = team_data.get("id")
                team_cache[team_id] = team_data
                team_id_to_name[team_id] = team_name
                return team_id
            else:
                error = await response.text()
                raise ValueError(f"Failed to get team ID. Status: {response.status}, Error: {error}")

async def fetch_channel_id(team_id: str, channel_name: str):
    """Fetch channel ID from team ID and channel name"""
    # Check cache first
    for channel_id, channel in channels_cache.items():
        if channel.get("name") == channel_name and channel.get("team_id") == team_id:
            return channel_id
    
    # If not in cache, fetch from API
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/teams/{team_id}/channels/name/{channel_name}"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                channel_data = await response.json()
                channel_id = channel_data.get("id")
                channels_cache[channel_id] = channel_data
                channel_id_to_name[channel_id] = channel_name
                return channel_id
            else:
                error = await response.text()
                raise ValueError(f"Failed to get channel ID. Status: {response.status}, Error: {error}")

async def fetch_channels(team_id: str):
    """Fetch all channels for a team"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/users/me/teams/{team_id}/channels"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                channels_data = await response.json()
                # Update cache
                for channel in channels_data:
                    channel_id = channel.get("id")
                    channels_cache[channel_id] = channel
                    channel_id_to_name[channel_id] = channel.get("name")
                return channels_data
            else:
                error = await response.text()
                raise ValueError(f"Failed to get channels. Status: {response.status}, Error: {error}")

async def fetch_posts(channel_id: str, limit: int = 30):
    """Fetch posts from a channel with pagination"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/channels/{channel_id}/posts?per_page={limit}"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                posts_data = await response.json()
                # Extract posts list and update cache
                posts = []
                for post_id, post in posts_data.get("posts", {}).items():
                    posts.append(post)
                
                # Sort by create_at (timestamp)
                posts.sort(key=lambda x: x.get("create_at", 0))
                
                # Update cache
                posts_cache[channel_id] = posts
                return posts
            else:
                error = await response.text()
                raise ValueError(f"Failed to get posts. Status: {response.status}, Error: {error}")

async def create_post(channel_id: str, message: str):
    """Create a new post in the specified channel"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    post_data = {
        "channel_id": channel_id,
        "message": message
    }
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/posts"
        async with session.post(url, headers=headers, json=post_data) as response:
            if response.status == 201:
                post = await response.json()
                # Update cache
                if channel_id in posts_cache:
                    posts_cache[channel_id].append(post)
                else:
                    posts_cache[channel_id] = [post]
                return post
            else:
                error = await response.text()
                raise ValueError(f"Failed to create post. Status: {response.status}, Error: {error}")

async def fetch_teams():
    """Fetch all teams the user is a member of"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/users/me/teams"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                teams_data = await response.json()
                # Update cache
                for team in teams_data:
                    team_id = team.get("id")
                    team_cache[team_id] = team
                    team_id_to_name[team_id] = team.get("name")
                return teams_data
            else:
                error = await response.text()
                raise ValueError(f"Failed to get teams. Status: {response.status}, Error: {error}")

# Load initial data from Mattermost on startup
async def initialize_mattermost_data():
    """Initialize data from Mattermost on startup"""
    try:
        # Fetch teams
        teams = await fetch_teams()
        
        # Find or create specified team
        team_id = None
        for team in teams:
            if team.get("name") == MATTERMOST_TEAM_NAME:
                team_id = team.get("id")
                break
                
        if not team_id:
            raise ValueError(f"Team '{MATTERMOST_TEAM_NAME}' not found")
            
        # Fetch channels for the team
        channels = await fetch_channels(team_id)
        
        # Find or use specified channel
        channel_id = MATTERMOST_CHANNEL_ID
        if not channel_id or channel_id == '5q39mmzqji8bddxyjzsqbziy9a':  # Default value
            # Find channel by name
            for channel in channels:
                if channel.get("name") == MATTERMOST_CHANNEL_NAME:
                    channel_id = channel.get("id")
                    break
            
            if not channel_id or channel_id == '5q39mmzqji8bddxyjzsqbziy9a':
                raise ValueError(f"Channel '{MATTERMOST_CHANNEL_NAME}' not found in team '{MATTERMOST_TEAM_NAME}'")
        
        # Fetch posts for the channel
        await fetch_posts(channel_id)
        
        return {
            "team_id": team_id,
            "channel_id": channel_id
        }
    except Exception as e:
        # Log error but don't crash - server will continue with limited functionality
        print(f"Error initializing Mattermost data: {str(e)}")
        return {}

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Mattermost resources.
    Each channel and post is exposed as a resource.
    """
    resources = []
    
    try:
        # Fetch teams if not in cache
        if not team_cache:
            await fetch_teams()
            
        # Add team resources
        for team_id, team in team_cache.items():
            team_name = team.get("name")
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"mattermost://team/{team_id}"),
                    name=f"Team: {team_name}",
                    description=f"Mattermost team: {team_name}",
                    mimeType="application/json",
                )
            )
            
            # Fetch channels for this team if not in cache
            if not any(channel.get("team_id") == team_id for channel in channels_cache.values()):
                await fetch_channels(team_id)
                
            # Add channel resources
            for channel_id, channel in channels_cache.items():
                if channel.get("team_id") == team_id:
                    channel_name = channel.get("name")
                    resources.append(
                        types.Resource(
                            uri=AnyUrl(f"mattermost://channel/{channel_id}"),
                            name=f"Channel: {channel_name}",
                            description=f"Mattermost channel: {channel_name}",
                            mimeType="application/json",
                        )
                    )
                    
                    # Fetch posts for this channel if not in cache
                    if channel_id not in posts_cache:
                        try:
                            await fetch_posts(channel_id)
                        except Exception as e:
                            # Skip if we can't fetch posts
                            print(f"Error fetching posts for channel {channel_id}: {str(e)}")
                            continue
                    
                    # Add post resources (only the recent ones)
                    if channel_id in posts_cache:
                        for post in posts_cache[channel_id][-10:]:  # Show last 10 posts
                            post_id = post.get("id")
                            message = post.get("message", "")
                            # Truncate message for display
                            short_message = message[:30] + "..." if len(message) > 30 else message
                            resources.append(
                                types.Resource(
                                    uri=AnyUrl(f"mattermost://post/{post_id}"),
                                    name=f"Post: {short_message}",
                                    description=f"Mattermost post in channel {channel_name}",
                                    mimeType="text/plain",
                                )
                            )
    except Exception as e:
        print(f"Error listing resources: {str(e)}")
    
    return resources

@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific Mattermost resource by its URI.
    """
    if uri.scheme != "mattermost":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    path = uri.path
    if path.startswith("/"):
        path = path[1:]
    
    parts = path.split("/")
    
    if len(parts) != 2:
        raise ValueError(f"Invalid URI format: {uri}")
    
    resource_type, resource_id = parts
    
    if resource_type == "team":
        # Return team info
        if resource_id in team_cache:
            return str(team_cache[resource_id])
        else:
            # Fetch team
            base_url = await get_mattermost_base_url()
            headers = await get_mattermost_headers()
            
            async with aiohttp.ClientSession() as session:
                url = f"{base_url}/teams/{resource_id}"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        team_data = await response.json()
                        team_cache[resource_id] = team_data
                        return str(team_data)
                    else:
                        error = await response.text()
                        raise ValueError(f"Failed to get team. Status: {response.status}, Error: {error}")
    
    elif resource_type == "channel":
        # Return channel info
        if resource_id in channels_cache:
            return str(channels_cache[resource_id])
        else:
            # Fetch channel
            base_url = await get_mattermost_base_url()
            headers = await get_mattermost_headers()
            
            async with aiohttp.ClientSession() as session:
                url = f"{base_url}/channels/{resource_id}"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        channel_data = await response.json()
                        channels_cache[resource_id] = channel_data
                        return str(channel_data)
                    else:
                        error = await response.text()
                        raise ValueError(f"Failed to get channel. Status: {response.status}, Error: {error}")
    
    elif resource_type == "post":
        # Find post in cache
        for channel_id, posts in posts_cache.items():
            for post in posts:
                if post.get("id") == resource_id:
                    username = post.get("username", "unknown")
                    create_time = datetime.fromtimestamp(post.get("create_at", 0)/1000)
                    message = post.get("message", "")
                    channel_name = channel_id_to_name.get(post.get("channel_id"), "unknown channel")
                    
                    return f"Post by {username} at {create_time} in {channel_name}:\n\n{message}"
        
        # If not found in cache, fetch from API
        base_url = await get_mattermost_base_url()
        headers = await get_mattermost_headers()
        
        async with aiohttp.ClientSession() as session:
            url = f"{base_url}/posts/{resource_id}"
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    post_data = await response.json()
                    username = post_data.get("username", "unknown")
                    create_time = datetime.fromtimestamp(post_data.get("create_at", 0)/1000)
                    message = post_data.get("message", "")
                    channel_name = channel_id_to_name.get(post_data.get("channel_id"), "unknown channel")
                    
                    return f"Post by {username} at {create_time} in {channel_name}:\n\n{message}"
                else:
                    error = await response.text()
                    raise ValueError(f"Failed to get post. Status: {response.status}, Error: {error}")
    
    raise ValueError(f"Unsupported resource type: {resource_type}")

@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available Mattermost-related prompts.
    """
    return [
        types.Prompt(
            name="summarize-channel",
            description="Summarizes recent messages in a Mattermost channel",
            arguments=[
                types.PromptArgument(
                    name="channel_id",
                    description="ID of the channel to summarize",
                    required=True,
                ),
                types.PromptArgument(
                    name="format",
                    description="Format of the summary (bullet/narrative/topics)",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="analyze-discussion",
            description="Analyzes a discussion thread for key points and action items",
            arguments=[
                types.PromptArgument(
                    name="post_id",
                    description="ID of the root post to analyze",
                    required=True,
                )
            ],
        )
    ]

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate Mattermost-related prompts.
    """
    if not arguments:
        raise ValueError("Missing required arguments")
    
    if name == "summarize-channel":
        channel_id = arguments.get("channel_id")
        if not channel_id:
            raise ValueError("Missing required argument: channel_id")
            
        format_type = arguments.get("format", "bullet")
        
        # Fetch posts for the channel if not in cache
        if channel_id not in posts_cache:
            await fetch_posts(channel_id)
            
        # Get channel name
        channel_name = "unknown channel"
        if channel_id in channels_cache:
            channel_name = channels_cache[channel_id].get("name", "unknown channel")
            
        # Format posts for the prompt
        posts_text = ""
        if channel_id in posts_cache:
            for post in posts_cache[channel_id]:
                username = post.get("username", "unknown")
                create_time = datetime.fromtimestamp(post.get("create_at", 0)/1000)
                message = post.get("message", "")
                
                posts_text += f"[{create_time}] {username}: {message}\n\n"
        
        format_instructions = ""
        if format_type == "bullet":
            format_instructions = "Format the summary as a bullet point list of key discussion points."
        elif format_type == "narrative":
            format_instructions = "Format the summary as a narrative paragraph describing the overall discussion flow."
        elif format_type == "topics":
            format_instructions = "Group the summary by discussion topics, with bullet points under each topic."
            
        return types.GetPromptResult(
            description=f"Summarize recent messages in Mattermost channel: {channel_name}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please summarize the following Mattermost channel conversation from '{channel_name}'. {format_instructions}\n\n{posts_text}",
                    ),
                )
            ],
        )
    
    elif name == "analyze-discussion":
        post_id = arguments.get("post_id")
        if not post_id:
            raise ValueError("Missing required argument: post_id")
            
        # Find post and replies in cache
        root_post = None
        replies = []
        
        # Find post in cache first
        for channel_posts in posts_cache.values():
            for post in channel_posts:
                if post.get("id") == post_id:
                    root_post = post
                    break
            if root_post:
                break
                
        # If not found in cache, fetch from API
        if not root_post:
            base_url = await get_mattermost_base_url()
            headers = await get_mattermost_headers()
            
            async with aiohttp.ClientSession() as session:
                url = f"{base_url}/posts/{post_id}"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        root_post = await response.json()
                    else:
                        error = await response.text()
                        raise ValueError(f"Failed to get post. Status: {response.status}, Error: {error}")
        
        # Fetch thread
        if root_post:
            base_url = await get_mattermost_base_url()
            headers = await get_mattermost_headers()
            
            async with aiohttp.ClientSession() as session:
                url = f"{base_url}/posts/{post_id}/thread"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        thread_data = await response.json()
                        # Extract replies
                        for post_id, post in thread_data.get("posts", {}).items():
                            if post_id != root_post.get("id"):
                                replies.append(post)
        
        # Format thread for the prompt
        thread_text = ""
        
        if root_post:
            root_username = root_post.get("username", "unknown")
            root_time = datetime.fromtimestamp(root_post.get("create_at", 0)/1000)
            root_message = root_post.get("message", "")
            
            thread_text += f"[ROOT] [{root_time}] {root_username}: {root_message}\n\n"
            
            # Sort replies by timestamp
            replies.sort(key=lambda x: x.get("create_at", 0))
            
            for reply in replies:
                username = reply.get("username", "unknown")
                create_time = datetime.fromtimestamp(reply.get("create_at", 0)/1000)
                message = reply.get("message", "")
                
                thread_text += f"[REPLY] [{create_time}] {username}: {message}\n\n"
            
        return types.GetPromptResult(
            description="Analyze Mattermost discussion thread",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please analyze this Mattermost discussion thread. Identify the main topic, key points raised by participants, any decisions made, and action items that were mentioned or implied.\n\n{thread_text}",
                    ),
                )
            ],
        )
        
    raise ValueError(f"Unknown prompt: {name}")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available Mattermost tools.
    """
    return [
        types.Tool(
            name="post-message",
            description="Post a message to a Mattermost channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel_id", "message"],
            },
        ),
        types.Tool(
            name="list-channels",
            description="List channels in a team",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {"type": "string"},
                },
                "required": ["team_id"],
            },
        ),
        types.Tool(
            name="search-posts",
            description="Search for posts with specific keywords",
            inputSchema={
                "type": "object",
                "properties": {
                    "terms": {"type": "string"},
                    "is_or_search": {"type": "boolean", "default": False},
                },
                "required": ["terms"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle Mattermost tool execution requests.
    """
    logger.info(f"Arguments: {arguments}")
    if not arguments:
        raise ValueError("Missing required arguments")
        
    if name == "post-message":
        channel_id = arguments.get("channel_id")
        message = arguments.get("message")
        
        if not channel_id or not message:
            raise ValueError("Missing required arguments: channel_id and message")
            
        try:
            post = await create_post(channel_id, message)
            
            channel_name = channel_id_to_name.get(channel_id, channel_id)
            
            # Notify clients that resources have changed
            await server.request_context.session.send_resource_list_changed()
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Message posted successfully to channel '{channel_name}'.\nPost ID: {post.get('id')}",
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error posting message: {str(e)}",
                )
            ]
    
    elif name == "list-channels":
        team_id = arguments.get("team_id")
        
        if not team_id:
            raise ValueError("Missing required argument: team_id")
            
        try:
            channels = await fetch_channels(team_id)
            
            channel_list = []
            for channel in channels:
                channel_list.append({
                    "id": channel.get("id"),
                    "name": channel.get("name"),
                    "display_name": channel.get("display_name"),
                    "type": channel.get("type"),
                    "purpose": channel.get("purpose")
                })
                
            team_name = team_id_to_name.get(team_id, team_id)
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Channels in team '{team_name}':\n\n" + 
                         "\n".join([f"- {c['display_name']} ({c['name']}) [ID: {c['id']}]" for c in channel_list])
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error listing channels: {str(e)}",
                )
            ]
    
    elif name == "search-posts":
        terms = arguments.get("terms")
        is_or_search = arguments.get("is_or_search", False)
        
        if not terms:
            raise ValueError("Missing required argument: terms")
            
        try:
            base_url = await get_mattermost_base_url()
            headers = await get_mattermost_headers()
            
            search_params = {
                "terms": terms,
                "is_or_search": is_or_search
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{base_url}/posts/search"
                async with session.post(url, headers=headers, json=search_params) as response:
                    if response.status == 200:
                        search_results = await response.json()
                        
                        posts = []
                        for post_id, post in search_results.get("posts", {}).items():
                            channel_id = post.get("channel_id")
                            channel_name = channel_id_to_name.get(channel_id, "unknown")
                            username = post.get("username", "unknown")
                            create_time = datetime.fromtimestamp(post.get("create_at", 0)/1000)
                            message = post.get("message", "")
                            
                            posts.append({
                                "id": post_id,
                                "channel_name": channel_name,
                                "username": username,
                                "create_time": str(create_time),
                                "message": message
                            })
                        
                        # Update cache with these posts
                        for post in posts:
                            channel_id = post.get("channel_id")
                            if channel_id in posts_cache:
                                # Add to cache if not already present
                                if not any(p.get("id") == post.get("id") for p in posts_cache[channel_id]):
                                    posts_cache[channel_id].append(post)
                        
                        # Notify clients that resources have changed
                        await server.request_context.session.send_resource_list_changed()
                        
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Search results for '{terms}':\n\n" + 
                                     "\n\n".join([f"[{p['create_time']}] {p['username']} in {p['channel_name']}:\n{p['message']}" for p in posts])
                            )
                        ]
                    else:
                        error = await response.text()
                        return [
                            types.TextContent(
                                type="text",
                                text=f"Error searching posts. Status: {response.status}, Error: {error}",
                            )
                        ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error searching posts: {str(e)}",
                )
            ]
    
    raise ValueError(f"Unknown tool: {name}")

async def main():
    # Attempt to initialize Mattermost data
    await initialize_mattermost_data()
    
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mattermost-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())