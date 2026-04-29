import logging
import json

logging.basicConfig(
    filename='support_ticket.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_invalid_output(email_text, output, error):
    with open('invalid_outputs.jsonl', 'a') as f:
        f.write(json.dumps({
            'email_text': email_text,
            'output': output,
            'error': str(error)
        }) + '\n')