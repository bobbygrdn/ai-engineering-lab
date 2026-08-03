from fastapi import FastAPI, HTTPException
from app.schemas import RedactionRequest, RedactionResponse
from app.inference import redact

app = FastAPI(
    title="Enterprise Local PII Scrubber Engine",
    description="Locally hosted, fine-tuned SLM microservice for HIPAA-compliant medical data sanitization.",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    """Health check endpoint for Docker/Kubernetes container monitoring."""
    return {"status": "healthy", "engine": "mistral-7b-lora-v1"}

@app.post("/v1/redact", response_model=RedactionResponse)
def redact_document(request: RedactionRequest):
    """
    Main endpoint: Accepts raw text and returns sanitized text 
    using the locally hosted fine-tuned model.
    """
    try:
        # Route directly to your locally hosted model
        safe_text = redact(request.text)
        return RedactionResponse(
            redacted_text=safe_text,
            model_version="bobbygrdn/pii-redactor-mistral-lora-v1",
            status="success"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Local Inference Engine Error: {str(e)}"
        )