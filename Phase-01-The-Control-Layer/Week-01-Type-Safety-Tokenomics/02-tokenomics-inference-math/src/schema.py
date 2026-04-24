from pydantic import BaseModel, Field
from enum import Enum

class Priority(str, Enum):
    Low = 'Low'
    Medium = 'Medium'
    High = 'High'

class Department(str, Enum):
    Billing = 'Billing'
    Tech = 'Tech'
    General = 'General'

class Metadata(BaseModel):
    total_duration: float = Field(..., description='Total processing time in seconds.')
    usage: dict = Field(..., description='Token usage details from the API response.')

class SupportTicket(BaseModel):
    priority: Priority = Field(..., description='The priority level of the support ticket.')
    department: Department = Field(..., description='The department responsible for handling the issue.')
    summary: str = Field(..., description='A brief summary of the issue in 3 sentences or less.')