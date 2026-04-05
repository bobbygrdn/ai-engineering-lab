import os
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

class Urgency(str, Enum):
    High = "high"
    Medium = "medium"
    Low = "low"

class TechnicalEntity(BaseModel):
    name: str = Field(
        description="The official name of the software, language or cloud service (e.g., 'PostgreSQL', not 'indexes')."
    )
    category: str = Field(
        description="The architectural category (e.g., 'Database', 'Frontend Framework')."
    )
    assigned_to: Optional[str] = Field(
        description="The person mentioned in relation to this tech"
    )
    urgency_level: Urgency

class ExtractionResult(BaseModel):
    entities: List[TechnicalEntity]
    summary: str

def extract_tech_stack(messy_input: str) -> ExtractionResult:
    completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": "Extract all technical tools, languages, and services mentioned in the text."},
                {"role": "user", "content": messy_input},
        ],
        response_format=ExtractionResult,
    )
    return completion.choices[0].message.parsed

messy_text = """
The PostgreSQL database is redlining; Sarah needs to look at the indexes immediately. 
Also, Bob mentioned we should eventually migration the frontend to React, but it's not a priority.
The AWS Lambda timeout is a nagging issue that Joe is assigned to fix by Friday.
"""

if __name__ == "__main__":
    print("Parsing messy text...\n")
    data = extract_tech_stack(messy_text)

    print(f"Summary: {data.summary}\n")
    print(f"{'Technology':<15} | {'Owner':<10} | {'Urgency'}")
    print("-" * 45)
    for item in data.entities:
        owner = item.assigned_to or "N/A"
        print(f"{item.name:<15} | {owner:<10} | {item.urgency_level.value}")