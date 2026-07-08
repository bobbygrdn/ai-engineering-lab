from openai import OpenAI
import os
from logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

client = OpenAI()
client.api_key = os.environ.get("OPENAI_API_KEY")

def complete(prompt: str, model: str = "gpt-4o-mini") -> str:
    start = datetime.now()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = (datetime.now() - start).total_seconds()
    usage = response.usage
    logger.info(
        f"OpenAI call – tokens: {usage.total_tokens}, "
        f"latency: {elapsed:.2f}s"
    )
    return response.choices[0].message.content.strip()