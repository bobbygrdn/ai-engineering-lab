import logging
import json

logging.basicConfig(
    filename='interactions.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)