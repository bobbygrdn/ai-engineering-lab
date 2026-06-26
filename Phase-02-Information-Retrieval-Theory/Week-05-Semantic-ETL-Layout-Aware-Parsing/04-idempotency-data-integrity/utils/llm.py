from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel

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

def generate_hypothetical_answer(question):
    prompt = f"""Write a detailed, one-paragraph answer to the following question. Do not say 'I don't know' or 'I cannot answer that'. Write the answer as if it were a fact in a document: 
    {question}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

def ask(question, contexts):
    prompt = build_prompt(contexts, question)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

class Metadata(BaseModel):
    summary: str
    questions: list[str]

def create_metadata(chunk):
    """
    Create metadata for a given chunk of text.
    """
    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": f"Summarize this in one sentence and provide 3 questions it answers:\n\n{chunk}"}
        ],
        text_format=Metadata,
    )
    return response.output_parsed