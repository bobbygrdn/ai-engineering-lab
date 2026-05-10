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

def summarize_buffer(messages: list, model: str) -> str:
    '''
    Summarize the 10 messages in the buffer with a 2-sentence summary.
    '''
    client = openai.OpenAI()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Summarize the following messages while retaining key information."},
                *messages
            ],
            temperature=0,
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        raise RuntimeError(f"Error during summarization loop: {e}")

def classify_message(message: str, model: str = "gpt-4o-mini") -> str:
    prompt = (
        'Classify the following message as one of: "preference", "past_issue", or "system_context".\n'
        'If the message expresses a user preference, such as "I prefer...", "I like...", "I want...", or "I dislike...", classify as "preferences".\n'
        '{role: "user", content: "I do not like the way you phrased that."} should be classified as "preferences".\n'
        f'Message: "{message}"\n'
        "Classification:"
    )
    classification = send_to_llm(prompt, model)
    return classification.strip().lower()