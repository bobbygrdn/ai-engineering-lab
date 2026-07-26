from llm import generate_response
import random
import re
import json
import time
from datetime import datetime, timedelta
from prompt_templates import get_domain_template
from utils import save_checkpoint, validate_pii_content,  save_final_dataset
from logger import logging

def inject_misspellings(text, probability=0.3):
    words_to_misspell = [
        'patient', 'employee', 'account', 'doctor', 'hospital', 'clinic', 'department', 'section', 'number', 'date', 'birth', 'address', 'phone', 'email', 'name', 'record'
    ]

    words = text.split()
    for i in range(len(words)):
        if words[i].lower() in words_to_misspell and random.random() < probability:
            # Simple misspelling strategies
            word = words[i]
            if len(word) > 3:
                # Swap adjacent characters
                if len(word) > 3 and random.choice([True, False]):
                    pos = random.randint(0, len(word)-2)
                    words[i] = word[:pos] + word[pos+1] + word[pos] + word[pos+2:]
                # Delete random character
                elif random.choice([True, False]):
                    pos = random.randint(0, len(word)-1)
                    words[i] = word[:pos] + word[pos+1:]
                # Add extra character
                else:
                    pos = random.randint(0, len(word))
                    words[i] = word[:pos] + 'x' + word[pos:]
    return ' '.join(words)

def generate_foreign_name(culture_pool=['hispanic', 'asian', 'middle_eastern', 'european']):
    name_db = {
        'hispanic': {
            'first': ['Maria', 'Jose', 'Carlos', 'Ana', 'Luis', 'Isabel', 'Juan', 'Elena'],
            'last': ['Garcia', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez']
        },
        'asian': {
            'first': ['Wei', 'Li', 'Zhang', 'Wang', 'Liu', 'Chen', 'Yang', 'Huang'],
            'last': ['Wang', 'Li', 'Zhang', 'Liu', 'Chen', 'Yang', 'Huang', 'Zhou']
        },
        'middle_eastern': {
            'first': ['Ahmed', 'Mohammed', 'Yousef', 'Khaled', 'Fatima', 'Aisha', 'Zara'],
            'last': ['Al-Masri', 'Hussein', 'Khalil', 'Said', 'Hassan', 'Mahmoud']
        },
        'european': {
            'first': ['Johann', 'Marie', 'Hans', 'Anna', 'Peter', 'Elena', 'Carlos', 'Sophie'],
            'last': ['Müller', 'Dubois', 'Rossi', 'Novak', 'Kowalski', 'Popov']
        }
    }
    
    culture = random.choice(culture_pool)
    first = random.choice(name_db[culture]['first'])
    last = random.choice(name_db[culture]['last'])
    
    # Occasionally swap order (some cultures put family name first)
    if random.random() < 0.3 and culture in ['asian', 'middle_eastern']:
        return f"{last} {first}"
    return f"{first} {last}"

def vary_date_format(base_date=None):
    if base_date is None:
        # Generate random date between 1940-2010
        start_date = datetime(1940, 1, 1)
        end_date = datetime(2010, 12, 31)
        time_between = end_date - start_date
        days_random = random.randint(0, time_between.days)
        base_date = start_date + timedelta(days=days_random)
    
    formats = [
        lambda d: d.strftime('%m/%d/%Y'),      # MM/DD/YYYY
        lambda d: d.strftime('%d/%m/%Y'),      # DD/MM/YYYY
        lambda d: d.strftime('%Y-%m-%d'),      # YYYY-MM-DD
        lambda d: d.strftime('%m-%d-%y'),      # MM-DD-YY
        lambda d: d.strftime('%d-%m-%y'),      # DD-MM-YY
        lambda d: d.strftime('%B %d, %Y'),     # Month DD, YYYY
        lambda d: d.strftime('%d %B %Y'),      # DD Month YYYY
        lambda d: f"{d.month}/{d.day}/{str(d.year)[2:]}",  # M/D/YY (no leading zeros)
        lambda d: f"{d.day}.{d.month}.{d.year}", # DD.MM.YYYY
    ]
    
    return random.choice(formats)(base_date)

def apply_edge_case_strategy(prompt, strategy):
    if strategy == 'misspelling':
        return prompt + "\n\nPlease include some subtle misspellings in common words (like 'patient', 'address', 'department')."
    elif strategy == 'foreign_name':
        return prompt + "\n\nPlease use a name that reflects diverse cultural origins (Hispanic, Asian, Middle Eastern, or European)."
    elif strategy == 'date_variation':
        return prompt + "\n\nPlease use non-standard date formats (like DD/MM/YY, Month DD, YYYY, or MM-DD-YY)."
    else:
        return prompt  # no strategy

def generate_pii_dataset(num_examples=1000, batch_size=25, start_index=0, initial_examples=None):
    domains = ['doctor_notes', 'hr_complaints', 'bank_logs']
    
    # Start with initial examples if provided (for resuming)
    examples = initial_examples if initial_examples is not None else []
    
    print(f"Starting generation of {num_examples} examples...")
    print(f"Batch size: {batch_size} (with extended pauses between batches)")
    print(f"Estimated time per example: 2-4 seconds")
    print(f"Estimated total time: {num_examples * 3 / 60:.1f} hours\n")
    if initial_examples:
        print(f"Starting with {len(initial_examples)} loaded examples")
    
    for i in range(num_examples):
        # Calculate actual example number for logging and checkpointing
        actual_example_num = start_index + i + 1
        
        if i % 10 == 0 and i > 0:
            print(f"Progress: {actual_example_num}/{start_index + num_examples} examples generated ({(actual_example_num/(start_index + num_examples))*100:.1f}%)")
        
        domain = random.choice(domains)
        strategy = random.choice(["misspelling", "foreign_name", "date_variation", None])
        
        base_prompt = get_domain_template(domain)
        if strategy != None:
            base_prompt = apply_edge_case_strategy(base_prompt, strategy)
        
        raw_response = generate_response(base_prompt)
        
        if not isinstance(raw_response, str) or not raw_response.strip():
            print(f"Warning: Empty response for example {actual_example_num}")
            continue
        
        if validate_pii_content(raw_response):
            examples.append({
                'text': raw_response.strip(),
                'domain': domain,
                'edge_case': strategy if strategy else 'none',
                'timestamp': datetime.now().isoformat()
            })
            if (i+1) % 5 == 0:
                print(f"✓ Example {actual_example_num} valid ({domain}/{strategy})")
            
            # Save checkpoint every 25 VALID examples (using actual example count)
            if len(examples) % 25 == 0:
                save_checkpoint(examples, len(examples))
                print(f"💾 Checkpoint saved: {len(examples)} examples")
        else:
            if (i+1) % 5 == 0:
                print(f"✗ Example {actual_example_num} failed PII validation ({domain}/{strategy})")
        
        # Batch pausing every batch_size examples (but not at the very end)
        if (actual_example_num) % batch_size == 0 and actual_example_num < (start_index + num_examples):
            pause_time = 30
            print(f"Batch complete. Pausing for {pause_time} seconds to let server recover...")
            time.sleep(pause_time)
            print(f"Resuming generation...")
    
    print(f"Generation complete: {len(examples)} total examples")
    return examples
