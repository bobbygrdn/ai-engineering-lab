from dotenv import load_dotenv
import instructor
import openai
import os

load_dotenv()

instructor_client = instructor.from_provider(
    "openai/gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0)

openai_client = openai
openai_client.api_key = os.getenv("OPENAI_API_KEY")