import logging
import os

os.makedirs(os.path.dirname('logs/interactions/interactions.log'), exist_ok=True)
if not os.path.exists('logs/interactions/interactions.log'):
    with open('logs/interactions/interactions.log', 'w', encoding='utf-8') as f:
        pass  

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/interactions/interactions.log'
)

logger = logging.getLogger(__name__)