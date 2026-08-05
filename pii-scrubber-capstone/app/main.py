from fastapi import FastAPI, HTTPException
from app.schemas import RedactionRequest, RedactionResponse
from app.inference import redact_pii

app = FastAPI(
    title="Enterprise Local PII Scrubber Engine",
    description="Locally hosted, fine-tuned SLM microservice for HIPAA-compliant medical data sanitization.",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    """Health check endpoint for Docker/Kubernetes container monitoring."""
    return {"status": "healthy", "engine": "meta.llama3-8b-instruct-v1:0-bedrock"}

@app.post("/v1/redact", response_model=RedactionResponse)
def redact_document(request: RedactionRequest):
    """
    Main endpoint: Accepts raw text and returns sanitized text 
    using the locally hosted fine-tuned model.
    """
    try:
        safe_text = redact_pii(request.text)
        return RedactionResponse(
            redacted_text=safe_text,
            model_version="meta.llama3-8b-instruct-v1:0-bedrock",
            status="success"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Local Inference Engine Error: {str(e)}"
        )