import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
BASE_MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"
LORA_ADAPTER_ID = "Bobbygrdn/pii-redactor-mistral-lora-v1"

print("Initializing PII Redaction Engine (Dynamic Merge)...")

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16
)

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID, token=HF_TOKEN)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_ID,
    quantization_config=bnb_config,
    device_map="auto",
    token=HF_TOKEN
)

print(f"Downloading and attaching LoRA adapter: {LORA_ADAPTER_ID}")
model = PeftModel.from_pretrained(base_model, LORA_ADAPTER_ID, token=HF_TOKEN)
model.eval() 

print("✅ AI Engine Ready.")

def redact(text: str) -> str:
    messages = [
        {
            "role": "system", 
            "content": "You are a medical document redactor specialized in protecting patient privacy. \nYour task is to redact personally identifiable information (PII) from medical emails by replacing it with standardized tags.\nSupported tags: [NAME], [SSN], [ADDRESS], [PHONE], [EMAIL], [DOB], [MRN]."
        },
        {"role": "user", "content": text}
    ]
    
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    
    with torch.no_grad():
        outputs = model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=250,
            temperature=0.1,
            repetition_penalty=1.1,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
            do_sample=True
        )
        
    input_length = inputs["input_ids"].shape[1]
    return tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()