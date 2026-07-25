from openai import OpenAI
from dotenv import load_dotenv
import os
import logging
import time
import random

load_dotenv()
client = OpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key=os.getenv("NVIDIA_API_KEY"),
  timeout=120.0,
  max_retries=0
)

class CircuitBreaker:
    """Simple circuit breaker to prevent hammering a failing service"""
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED" 
    
    def call_succeeded(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def call_failed(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
    
    def can_attempt(self):
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else: 
            return True

circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=45)

def generate_response(prompt):
    max_retries = 5
    base_delay = 2 
    
    for attempt in range(max_retries):
        if not circuit_breaker.can_attempt():
            wait_time = circuit_breaker.recovery_timeout - (time.time() - circuit_breaker.last_failure_time)
            logging.warning(f"Circuit breaker OPEN. Waiting {wait_time:.1f}s for recovery...")
            time.sleep(wait_time)
        
        try:
            logging.info(f"Sending prompt (length: {len(prompt)} chars)")
            start_time = time.time()
            
            completion = client.chat.completions.create(
                model="mistralai/mistral-nemotron",
                messages=[
                    {"role": "system", "content": "You are an expert at generating realistic documents containing personally identifiable information (PII) for synthetic data creation. Your outputs should contain realistic names, dates, addresses, phone numbers, emails, and other identifiers with natural variations including misspellings, foreign name formats, and non-standard date formats. Generate only the requested document content without additional commentary."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                top_p=1,
                max_tokens=1024,
            )
            
            end_time = time.time()
            elapsed = end_time - start_time
            logging.info(f"API call took {elapsed:.2f} seconds")
            
            content = completion.choices[0].message.content
            if content is not None:
                circuit_breaker.call_succeeded()
                return content
            else:
                raise ValueError("Empty response from API")
                
        except Exception as e:
            is_retryable = False
            error_msg = str(e).lower()
            
            if hasattr(e, 'status_code') and e.status_code == 429:
                is_retryable = True
                error_type = "rate limit (429)"
            
            elif any(keyword in error_msg for keyword in [
                'timeout', 'timed out', 'readtimeout', 'connecttimeout', 
                'request timeout', 'read timeout', 'connection timeout'
            ]):
                is_retryable = True
                error_type = "timeout"
            
            elif any(keyword in error_msg for keyword in [
                'connectionerror', 'network error', 'failed to establish connection',
                'max retries exceeded', 'nodename nor servname provided'
            ]):
                is_retryable = True
                error_type = "network error"
            
            elif hasattr(e, 'status_code') and 500 <= e.status_code < 600:
                is_retryable = True
                error_type = f"server error ({e.status_code})"
            
            if is_retryable:
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), 30)
                    logging.warning(f"{error_type} hit (attempt {attempt+1}/{max_retries}). Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    logging.error(f"Max retries exceeded for {error_type}: {e}")
                    circuit_breaker.call_failed()
                    return ""
            else:
                logging.error(f"Error generating response (non-retryable): {e}")
                circuit_breaker.call_failed()
                return ""
    
    circuit_breaker.call_failed()
    return ""
