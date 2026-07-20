from dotenv import load_dotenv
from llama_cpp import Llama
import instructor
import openai
import os
import json
import re
from pydantic import ValidationError
from schema import SupportTicket

load_dotenv()

instructor_client = instructor.from_provider(
    "openai/gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0)

openai_client = openai.OpenAI()
openai_client.api_key = os.getenv("OPENAI_API_KEY")

llama = Llama(
    model_path="./" + os.getenv("LLAMA_MODEL_PATH"),
    n_ctx=2048,
    n_threads=8,
    n_batch=8,
    n_gpu_layers=40,
    seed=42
)

# Interface for the llm model to be used in the application
class LLMInterface:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def generate_response(self, prompt: str) -> str:
        if self.model_name == "instructor":
            return self._generate_instructor_response(prompt)
        elif self.model_name == "openai":
            return self._generate_openai_response(prompt)
        elif self.model_name == "llama":
            return self._generate_llama_response(prompt)
        else:
            raise ValueError(f"Unsupported model: {self.model_name}")

    def generate_structured_response(self, prompt: str, response_model) -> object:
        """Generate structured output that conforms to a Pydantic model"""
        if self.model_name == "instructor":
            return self._generate_instructor_structured_response(prompt, response_model)
        elif self.model_name == "openai":
            return self._generate_openai_structured_response(prompt, response_model)
        elif self.model_name == "llama":
            return self._generate_llama_structured_response(prompt, response_model)
        else:
            raise ValueError(f"Unsupported model: {self.model_name}")

    def _generate_instructor_response(self, prompt: str) -> str:
        response = instructor_client.generate(
            prompt=prompt,
            max_tokens=150
        )
        return response.text

    def _generate_openai_response(self, prompt: str) -> str:
        response = openai_client.Completion.create(
            engine="text-davinci-003",
            prompt=prompt,
            max_tokens=150
        )
        return response.choices[0].text.strip()

    def _generate_llama_response(self, prompt: str) -> str:
        response = llama.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
            response_format={
                "type": "json_object",
                "schema": {
                    "type": "object",
                    "properties": {
                        "priority": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "department": {"type": "string", "enum": ["Billing", "Tech", "General"]},
                        "summary": {"type": "string"}
                    },
                    "required": ["priority", "department", "summary"]
                }
            }
        )
        return response['choices'][0]['message']['content'].strip()

    def _generate_instructor_structured_response(self, prompt: str, response_model) -> object:
        try:
            response = instructor_client.chat.completions.create_with_completion(
                response_model=response_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            return response
        except Exception as e:
            # Fallback to text generation and parsing
            text_response = self._generate_instructor_response(prompt)
            return self._parse_json_response(text_response, response_model)

    def _generate_openai_structured_response(self, prompt: str, response_model) -> object:
        try:
            response = openai_client.chat.completions.create_with_completion(
                model="gpt-4o-mini",
                response_model=response_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            return response
        except Exception as e:
            # Fallback to text generation and parsing
            text_response = self._generate_openai_response(prompt)
            return self._parse_json_response(text_response, response_model)

    def _generate_llama_structured_response(self, prompt: str, response_model) -> object:
        text_response = self._generate_llama_response(prompt)
        return self._parse_json_response(text_response, response_model)

    def _parse_json_response(self, text: str, response_model) -> object:
        """Extract JSON from text and validate against Pydantic model"""
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                return response_model.model_validate_json(json_str)
            except (ValidationError, json.JSONDecodeError):
                # If direct JSON parsing fails, try to fix common issues
                try:
                    # Replace single quotes with double quotes
                    fixed_json = json_str.replace("'", '"')
                    # Ensure property names are quoted
                    fixed_json = re.sub(r'(\w+):', r'"\1":', fixed_json)
                    return response_model.model_validate_json(fixed_json)
                except:
                    pass
        
        # If we can't parse JSON, return a default response
        return response_model(
            priority="Medium",
            department="General",
            summary="Unable to parse model response as valid JSON"
        )

    def set_model(self, model_name: str):
        if model_name not in ["instructor", "openai", "llama"]:
            raise ValueError(f"Unsupported model: {model_name}")
        self.model_name = model_name

    def get_model(self) -> str:
        return self.model_name