import logging
import os

if not os.path.exists('interactions.log'):
    with open('interactions.log', 'w', encoding='utf-8') as f:
        pass 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='interactions.log'
)

logger = logging.getLogger(__name__)