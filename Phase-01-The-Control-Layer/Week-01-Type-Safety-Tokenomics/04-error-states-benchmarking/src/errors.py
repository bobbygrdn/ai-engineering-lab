from pydantic import BaseModel, Field

class RateLimitError(Exception):
    """Exception raised when the API rate limit is exceeded."""
    def __init__(self, message: str = "API rate limit exceeded. Please try again later."):
        self.message = message
        super().__init__(self.message)

class EmptyPromptError(Exception):
    """Exception raised when the input prompt is empty."""
    def __init__(self, message: str = "Input prompt cannot be empty."):
        self.message = message
        super().__init__(self.message)

class RefusalError(Exception):
    """Exception raised when the model refuses to generate a response."""
    def __init__(self, message: str = "The model refused to generate a response."):
        self.message = message
        super().__init__(self.message)

class ModelError(Exception):
    """General exception for model-related errors."""
    def __init__(self, message: str = "An error occurred while processing the request."):
        self.message = message
        super().__init__(self.message)