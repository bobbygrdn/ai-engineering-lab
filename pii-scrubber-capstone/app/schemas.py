from pydantic import BaseModel, Field

class RedactionRequest(BaseModel):
    text: str = Field(..., description="The raw medical text containing potential PII.", min_length=10)

class RedactionResponse(BaseModel):
    redacted_text: str = Field(..., description="The sanitized text with PII safely masked.")
    model_version: str = "mistral-7b-lora-v1"
    status: str = "success"