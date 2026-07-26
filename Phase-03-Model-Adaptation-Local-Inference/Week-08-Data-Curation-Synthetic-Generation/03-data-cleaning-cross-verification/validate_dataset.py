import json
import re
import spacy

# Load the spaCy NER model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Error: Model not found. Please run: python -m spacy download en_core_web_sm")
    exit()

input_file = "training_data.jsonl"
clean_file = "clean_training_data.jsonl"
quarantine_file = "quarantined_data.jsonl"

# LAYER 1: REGEX (Structured PII)
patterns = {
    "Email Leak": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    "Phone Leak": r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
    "SSN Leak": r'\d{3}-\d{2}-\d{4}'
}

def validate_dataset():
    clean_count = 0
    quarantine_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(clean_file, 'w', encoding='utf-8') as clean_out, \
         open(quarantine_file, 'w', encoding='utf-8') as quar_out:
        
        for index, line in enumerate(infile):
            try:
                data = json.loads(line)
                messages = data.get("messages", [])
                
                assistant_content = ""
                for msg in messages:
                    if msg.get("role") == "assistant":
                        assistant_content = msg.get("content", "")
                        break
                
                is_safe = True
                flag_reason = ""
                
                # --- LAYER 1: REGEX CHECK ---
                for leak_type, pattern in patterns.items():
                    if re.search(pattern, assistant_content):
                        is_safe = False
                        flag_reason = leak_type
                        break
                
                # --- LAYER 2: NER CHECK (Unstructured PII) ---
                if is_safe:
                    doc = nlp(assistant_content)
                    
                    # An allow-list of words spaCy commonly mistakes for people in medical texts
                    false_positives = [
                        "amoxicillin", "lisinopril", "strep", "patient", 
                        "clinic", "tylenol", "ibuprofen", "hypertension", "covid"
                    ]
                    
                    for ent in doc.ents:
                        # We are ONLY checking for leaked Names (PERSON) now
                        if ent.label_ == "PERSON":
                            
                            # Clean the text to check against our allow-list
                            clean_text = ent.text.lower().strip()
                            
                            # 1. Ignore our own tags
                            if not re.match(r'\[(?:NAME|SSN|ADDRESS|PHONE|EMAIL|DOB|MRN)\]', ent.text):
                                # 2. Ignore known spaCy medical hallucinations
                                if not any(fp in clean_text for fp in false_positives):
                                    is_safe = False
                                    flag_reason = f"NER Leak ({ent.label_}): '{ent.text}'"
                                    break
                
                # Route the data
                if is_safe:
                    clean_out.write(line)
                    clean_count += 1
                else:
                    data["QUARANTINE_REASON"] = flag_reason
                    quar_out.write(json.dumps(data) + "\n")
                    quarantine_count += 1
                    
            except json.JSONDecodeError:
                print(f"Row {index + 1} is malformed JSON. Skipping.")
                continue

    print("--- VALIDATION COMPLETE ---")
    print(f"Clean Rows: {clean_count}")
    print(f"Quarantined Rows: {quarantine_count} (Moved to {quarantine_file})")
    
    total = clean_count + quarantine_count
    if total > 0:
        print(f"Survival Rate: {(clean_count/total)*100:.2f}%")

if __name__ == "__main__":
    validate_dataset()