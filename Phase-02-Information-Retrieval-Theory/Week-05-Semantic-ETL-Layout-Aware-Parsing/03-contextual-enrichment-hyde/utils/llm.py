from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()
client.api_key = os.getenv("OPENAI_API_KEY")

def build_prompt(contexts, question):
    context = "\n\n".join(contexts)
    return f"""You are an assistant that answers questions based on the following context.

    Context:
    {context}

    Question: {question}
    """

def ask(question, contexts):
    prompt = build_prompt(contexts, question)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content