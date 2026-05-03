from dotenv import load_dotenv
import openai
import os

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

def send_to_llm(prompt: str, model: str) -> str:
    '''
    Send the assembled prompt to the LLM and return the response.
    '''
    client = openai.OpenAI()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Error communicating with LLM: {e}")