from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from modules.logic.agentic_logic import classify_support_ticket_with_retries
from modules.schemas.type_safety import ClassifyRequest
from modules.utils.helpers import log_invalid_output
from pydantic import ValidationError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/heartbeat")
def heartbeat():
    return {"status": "ok"}

@app.post("/api/classify")
def classify(request: ClassifyRequest):
    try:
        ticket, metadata = classify_support_ticket_with_retries(request.email_text)
        if ticket is None:
            raise HTTPException(status_code=500, detail="Failed to classify the support ticket.")
        return {"ticket": ticket.model_dump(), "metadata": metadata.model_dump()}
    except ValueError as e:
        try:
            log_invalid_output(request.email_text, None, str(e))
        except Exception as log_error:
            print(f"Logging error: {log_error}")
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationError as e:
        try:
            log_invalid_output(request.email_text, None, "Validation Error")
        except Exception as log_error:
            print(f"Logging error: {log_error}")
        raise HTTPException(status_code=500, detail="Failed to classify the support ticket.")
    except Exception as e:
        try:
            log_invalid_output(request.email_text, None, f"Unexpected error: {str(e)}")
        except Exception as log_error:
            print(f"Logging error: {log_error}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")