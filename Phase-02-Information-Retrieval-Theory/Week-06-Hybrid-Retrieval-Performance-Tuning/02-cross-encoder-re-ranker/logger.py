import logging
import os

if not os.path.exists('logs/interactions.log'):
    os.makedirs('logs', exist_ok=True)
    with open('logs/interactions.log', 'w', encoding='utf-8') as f:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/interactions.log'
)

logger = logging.getLogger(__name__)