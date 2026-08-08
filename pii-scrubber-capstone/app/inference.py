import boto3
import json
from dotenv import load_dotenv

load_dotenv()

bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

def redact_pii(text: str) -> str:
    """Sends text to Meta Llama 3 on AWS Bedrock for PII redaction."""
    model_id = "meta.llama3-8b-instruct-v1:0"
    
    system_instruction = "You are a strict PII redaction engine. Replace all names with [NAME], dates with [DATE], and medical conditions with [CONDITION]. Output ONLY the redacted text with zero conversation."
    
    formatted_prompt = f"""<|begin_of_text|><|start_header_id|>system<|end_header_id|>
{system_instruction}<|eot_id|><|start_header_id|>user<|end_header_id|>
Redact this text: {text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
"""

    prompt_payload = {
        "prompt": formatted_prompt,
        "max_gen_len": 500,
        "temperature": 0.1
    }

    try:
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(prompt_payload),
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body.get('generation').strip()
        
    except Exception as e:
        print(f"Bedrock Error: {e}")
        return "ERROR: Unable to process request through Bedrock."