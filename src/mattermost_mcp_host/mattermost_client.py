import json
from mattermostdriver import Driver
import asyncio
import logging

logger = logging.getLogger(__name__)

class MattermostClient:
    def __init__(self, url, token, scheme='https', port=443, websocket=True):
        """Initialize Mattermost client"""
        self.url = url
        self.token = token
        self.scheme = scheme
        self.port = port
        self.use_websocket = websocket
        self.driver = Driver({
            'url': url,
            'token': token,
            'scheme': scheme,
            'port': port,
            'debug': False,
            'keepalive': False,
            'keepalive_delay': 5,
        })
        self.websocket_client = None
        self.message_handlers = []
        self._running = False

    def connect(self):
        """Connect to the Mattermost server"""
        self.driver.login()
        return self

    async def start_websocket(self):
        """Start the websocket connection for real-time events"""
        if not self.use_websocket:
            return
            
        self._running = True
        try:
            # Initialize websocket with a custom event handler
            async def websocket_event_handler(event):
                if isinstance(event, str):
                    event = json.loads(event)
                logger.info(f'Event: {event}')
                if event.get('event') == 'posted':
                    post = event.get('data', {}).get('post')
                    if post:
                        try:
                            post_data = json.loads(post)
                            for handler in self.message_handlers:
                                await handler(post_data)
                        except Exception as e:
                            logger.error(f"Error handling post: {str(e)}")

            # Initialize websocket with the event handler
            self.driver.init_websocket(websocket_event_handler)
            await asyncio.sleep(1)  # Give the websocket time to initialize
            self.websocket_client = self.driver.websocket.websocket
            
            # Keep the websocket connection alive
            while self._running:
                if not self.websocket_client or self.websocket_client.closed:
                    logger.info("Reconnecting websocket...")
                    self.driver.init_websocket(websocket_event_handler)
                    await asyncio.sleep(1)
                    self.websocket_client = self.driver.websocket.websocket
                await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Failed to initialize websocket: {str(e)}")
            self._running = False

    def add_message_handler(self, handler):
        """
        Add a message handler function
        
        Args:
            handler: Async function that handles new messages
        """
        self.message_handlers.append(handler)

    def post_message(self, channel_id, message, root_id=None):
        """
        Post a message to a channel
        
        Args:
            channel_id: Channel ID
            message: Message text
            root_id: Optional ID of the parent message for threading
        """
        post_data = {
            'channel_id': channel_id,
            'message': message
        }
        
        # If root_id is provided, add it to create a threaded reply
        if root_id:
            post_data['root_id'] = root_id
        
        return self.driver.posts.create_post(post_data)

    def get_messages(self, channel_id, limit=10):
        """
        Get recent messages from a channel
        
        Args:
            channel_id: Channel ID
            limit: Maximum number of messages to retrieve
        """
        return self.driver.posts.get_posts_for_channel(channel_id, params={'page': 0, 'per_page': limit})

    def get_channel_by_name(self, team_id, channel_name):
        """
        Get channel by name
        
        Args:
            team_id: Team ID
            channel_name: Channel name
        """
        return self.driver.channels.get_channel_by_name_and_team_name(team_id, channel_name)

    def get_teams(self):
        """Get all teams the bot has access to"""
        return self.driver.teams.get_teams()

    def get_thread_posts(self, post_id):
        """
        Get all posts in a thread
        
        Args:
            post_id: ID of the root post in the thread
            
        Returns:
            Dictionary of posts in the thread
        """
        return self.driver.posts.get_thread(post_id)

    def close(self):
        """Close the connection to the Mattermost server"""
        self._running = False
        if self.websocket_client:
            self.websocket_client.close()
        self.driver.logout()