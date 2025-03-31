import asyncio
import os
import logging
from datetime import datetime
from typing import Dict, List

import aiohttp
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from pydantic import AnyUrl
import mcp.server.stdio

from dotenv import load_dotenv

load_dotenv()

# Mattermost Configuration
MATTERMOST_URL = os.environ.get('MATTERMOST_URL', 'localhost')
MATTERMOST_TOKEN = os.environ.get('MATTERMOST_TOKEN', '123')
MATTERMOST_SCHEME = os.environ.get('MATTERMOST_SCHEME', 'http')
MATTERMOST_PORT = int(os.environ.get('MATTERMOST_PORT', '8065'))
MATTERMOST_TEAM_NAME = os.environ.get('MATTERMOST_TEAM_NAME', 'test')
MATTERMOST_CHANNEL_NAME = os.environ.get('MATTERMOST_CHANNEL_NAME', 'MCP-Client')
MATTERMOST_CHANNEL_ID = os.environ.get('MATTERMOST_CHANNEL_ID', 'bkciffjkfbgp9g44safgbfh1ew') 

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

async def fetch_pinned_posts(channel_id: str):
    """Fetch pinned posts for a specific channel"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/channels/{channel_id}/pinned"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                pinned_posts = await response.json()
                return pinned_posts
            else:
                error = await response.text()
                raise ValueError(f"Failed to get pinned posts. Status: {response.status}, Error: {error}")

async def fetch_channel_stats(channel_id: str):
    """Fetch statistics for a specific channel"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/channels/{channel_id}/stats"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                stats = await response.json()
                return stats
            else:
                error = await response.text()
                raise ValueError(f"Failed to get channel stats. Status: {response.status}, Error: {error}")

async def fetch_channel_members(channel_id: str):
    """Fetch members of a specific channel"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/channels/{channel_id}/members"
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                members = await response.json()
                return members
            else:
                error = await response.text()
                raise ValueError(f"Failed to get channel members. Status: {response.status}, Error: {error}")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List available Mattermost resources.
    Each channel, post, and data point is exposed as a resource.
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
            
            # Add pinned posts resources
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"mattermost://pinned/{channel_id}"),
                    name=f"Pinned Posts: {channel_name}",
                    description=f"Pinned posts in Mattermost channel: {channel_name}",
                    mimeType="application/json",
                )
            )
            
            # Add channel statistics resources
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"mattermost://stats/{channel_id}"),
                    name=f"Channel Stats: {channel_name}",
                    description=f"Statistics for Mattermost channel: {channel_name}",
                    mimeType="application/json",
                )
            )
            
            # Add channel members resources
            resources.append(
                types.Resource(
                    uri=AnyUrl(f"mattermost://members/{channel_id}"),
                    name=f"Channel Members: {channel_name}",
                    description=f"Members of Mattermost channel: {channel_name}",
                    mimeType="application/json",
                )
            )
    except Exception as e:
        logger.error(f"Error listing resources: {str(e)}")
    
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
    
    elif resource_type == "pinned":
        # Get pinned posts for a channel
        try:
            pinned_posts = await fetch_pinned_posts(resource_id)
            formatted_posts = []
            
            for post in pinned_posts:
                username = post.get("username", "unknown")
                create_time = datetime.fromtimestamp(post.get("create_at", 0)/1000)
                message = post.get("message", "")
                
                formatted_posts.append(f"[{create_time}] {username}: {message}")
            
            return "\n\n".join(formatted_posts)
        except Exception as e:
            return f"Error retrieving pinned posts: {str(e)}"
    
    elif resource_type == "stats":
        # Get channel statistics
        try:
            stats = await fetch_channel_stats(resource_id)
            member_count = stats.get("member_count", 0)
            
            return f"Channel Statistics\n-------------------\nMembers: {member_count}"
        except Exception as e:
            return f"Error retrieving channel statistics: {str(e)}"
    
    elif resource_type == "members":
        # Get channel members
        try:
            members = await fetch_channel_members(resource_id)
            member_list = []
            
            for member in members:
                # You might want to enhance this with additional user information
                user_id = member.get("user_id", "unknown")
                member_list.append(f"- User ID: {user_id}")
            
            return f"Channel Members\n---------------\n" + "\n".join(member_list)
        except Exception as e:
            return f"Error retrieving channel members: {str(e)}"
    
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
        ),
        types.Prompt(
            name="meeting-notes-template",
            description="Generate a meeting notes template for team meetings",
            arguments=[
                types.PromptArgument(
                    name="meeting_type",
                    description="Type of meeting (standup, planning, retrospective, etc.)",
                    required=True,
                ),
                types.PromptArgument(
                    name="team_name",
                    description="Name of the team",
                    required=True,
                ),
                types.PromptArgument(
                    name="agenda_items",
                    description="Comma-separated list of agenda items",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="project-status-update",
            description="Generate a project status update template",
            arguments=[
                types.PromptArgument(
                    name="project_name",
                    description="Name of the project",
                    required=True,
                ),
                types.PromptArgument(
                    name="milestones",
                    description="Comma-separated list of project milestones",
                    required=False,
                ),
                types.PromptArgument(
                    name="challenges",
                    description="Any challenges or blockers to mention",
                    required=False,
                )
            ],
        ),
        types.Prompt(
            name="team-onboarding",
            description="Generate onboarding information for new team members",
            arguments=[
                types.PromptArgument(
                    name="team_name",
                    description="Name of the team",
                    required=True,
                ),
                types.PromptArgument(
                    name="key_channels",
                    description="Comma-separated list of key channels to join",
                    required=False,
                ),
                types.PromptArgument(
                    name="key_resources",
                    description="Comma-separated list of key resources or links",
                    required=False,
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
    
    elif name == "meeting-notes-template":
        meeting_type = arguments.get("meeting_type")
        team_name = arguments.get("team_name")
        agenda_items = arguments.get("agenda_items", "")
        
        if not meeting_type or not team_name:
            raise ValueError("Missing required arguments: meeting_type and team_name")
        
        # Format agenda items if provided
        agenda_formatted = ""
        if agenda_items:
            items = [item.strip() for item in agenda_items.split(",")]
            agenda_formatted = "\n".join([f"- {item}" for item in items])
        
        return types.GetPromptResult(
            description=f"Meeting Notes Template for {team_name} {meeting_type} meeting",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please create a detailed meeting notes template for a {meeting_type} meeting for the {team_name} team. The template should include standard sections like attendees, agenda, discussion points, action items, and next steps.\n\nAgenda items to include:\n{agenda_formatted}",
                    ),
                )
            ],
        )
    
    elif name == "project-status-update":
        project_name = arguments.get("project_name")
        milestones = arguments.get("milestones", "")
        challenges = arguments.get("challenges", "")
        
        if not project_name:
            raise ValueError("Missing required argument: project_name")
        
        # Format milestones if provided
        milestones_formatted = ""
        if milestones:
            items = [item.strip() for item in milestones.split(",")]
            milestones_formatted = "\n".join([f"- {item}" for item in items])
        
        return types.GetPromptResult(
            description=f"Project Status Update for {project_name}",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please create a comprehensive project status update for the {project_name} project. Include sections for overall status, recent accomplishments, upcoming milestones, any risks or challenges, and next steps.\n\nMilestones to include:\n{milestones_formatted}\n\nChallenges to address:\n{challenges}",
                    ),
                )
            ],
        )
    
    elif name == "team-onboarding":
        team_name = arguments.get("team_name")
        key_channels = arguments.get("key_channels", "")
        key_resources = arguments.get("key_resources", "")
        
        if not team_name:
            raise ValueError("Missing required argument: team_name")
        
        return types.GetPromptResult(
            description=f"Onboarding Information for {team_name} team",
            messages=[
                types.PromptMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=f"Please create a comprehensive onboarding guide for new members joining the {team_name} team. Include sections for team overview, key contacts, communication channels, important resources, and getting started steps.\n\nKey channels to join: {key_channels}\n\nKey resources: {key_resources}",
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
                    "team_name": {"type": "string"},
                    "channel_name": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["channel_name", "message"],
            },
        ),
        types.Tool(
            name="create-project-channel",
            description="Create a new channel for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "team_id": {"type": "string"},
                    "project_name": {"type": "string"},
                    "description": {"type": "string"},
                    "members": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["team_id", "project_name"],
            },
        ),
        types.Tool(
            name="pin-important-message",
            description="Pin an important message in a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string"},
                },
                "required": ["post_id"],
            },
        ),
        types.Tool(
            name="add-reaction",
            description="Add a reaction emoji to a post",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "post_id": {"type": "string"},
                    "emoji_name": {"type": "string"},
                },
                "required": ["user_id", "post_id", "emoji_name"],
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
        team_name = arguments.get("team_name")
        channel_name = arguments.get("channel_name")
        message = arguments.get("message")
        
        team_id = await fetch_team_id(team_name)
        
        channel_id = await fetch_channel_id(team_id, channel_name)
        if not channel_id or not message:
            raise ValueError("Missing required arguments: team_name or channel_name or message")
            
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
    
    elif name == "create-project-channel":
        team_id = arguments.get("team_id")
        project_name = arguments.get("project_name")
        description = arguments.get("description", "")
        
        if not team_id or not project_name:
            raise ValueError("Missing required arguments: team_id and project_name")
            
        try:
            # Convert project name to valid channel name (lowercase, no spaces)
            channel_name = project_name.lower().replace(" ", "-")[:64]
            
            options = {
                "name": channel_name,
                "display_name": project_name,
                "purpose": description,
                "type": "O"  # Open channel
            }
            
            channel = await create_channel(team_id, options)
            
            # Notify clients that resources have changed
            await server.request_context.session.send_resource_list_changed()
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Project channel created successfully.\nName: {channel_name}\nChannel ID: {channel.get('id')}",
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error creating project channel: {str(e)}",
                )
            ]
    
    elif name == "pin-important-message":
        post_id = arguments.get("post_id")
        
        if not post_id:
            raise ValueError("Missing required argument: post_id")
            
        try:
            pinned_post = await pin_post(post_id)
            
            # Notify clients that resources have changed
            await server.request_context.session.send_resource_list_changed()
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Message pinned successfully.\nPost ID: {post_id}",
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error pinning message: {str(e)}",
                )
            ]
    
    elif name == "add-reaction":
        user_id = arguments.get("user_id")
        post_id = arguments.get("post_id")
        emoji_name = arguments.get("emoji_name")
        
        if not user_id or not post_id or not emoji_name:
            raise ValueError("Missing required arguments: user_id, post_id, and emoji_name")
            
        try:
            reaction = await add_reaction(user_id, post_id, emoji_name)
            
            # Notify clients that resources have changed
            await server.request_context.session.send_resource_list_changed()
            
            return [
                types.TextContent(
                    type="text",
                    text=f"Reaction added successfully.\nEmoji: {emoji_name}\nPost ID: {post_id}",
                )
            ]
        except Exception as e:
            return [
                types.TextContent(
                    type="text",
                    text=f"Error adding reaction: {str(e)}",
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

async def create_channel(team_id: str, options: dict):
    """Create a new channel in a team"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/channels"
        options["team_id"] = team_id
        async with session.post(url, headers=headers, json=options) as response:
            if response.status == 201:
                channel = await response.json()
                return channel
            else:
                error = await response.text()
                raise ValueError(f"Failed to create channel. Status: {response.status}, Error: {error}")

async def pin_post(post_id: str):
    """Pin a post to a channel"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/posts/{post_id}/pin"
        async with session.post(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.text()
                raise ValueError(f"Failed to pin post. Status: {response.status}, Error: {error}")

async def add_reaction(user_id: str, post_id: str, emoji_name: str):
    """Add a reaction to a post"""
    base_url = await get_mattermost_base_url()
    headers = await get_mattermost_headers()
    
    reaction_data = {
        "user_id": user_id,
        "post_id": post_id,
        "emoji_name": emoji_name
    }
    
    async with aiohttp.ClientSession() as session:
        url = f"{base_url}/reactions"
        async with session.post(url, headers=headers, json=reaction_data) as response:
            if response.status == 201:
                return await response.json()
            else:
                error = await response.text()
                raise ValueError(f"Failed to add reaction. Status: {response.status}, Error: {error}")

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