from pydantic import BaseModel, Field
from enum import Enum

class Priority(str, Enum):
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'

class Department(str, Enum):
    BILLING = 'Billing'
    TECHNICAL = 'Technical Support'
    GENERAL = 'General Inquiry'

class SupportTicket(BaseModel):
    priority: Priority = Field(..., description="The priority level of the support ticket")
    department: Department = Field(..., description="The department responsible for handling the ticket")
    summary: str = Field(..., description="A brief summary of the issue in 3 sentences or less")

class ClassifyRequest(BaseModel):
    email_text: str = Field(..., description="The text of the customer email to classify")