from datetime import datetime

def log_invalid_output(email_text, output, error):
    with open('invalid_outputs.log', 'a') as log_file:
        log_file.write(f"Timestamp: {datetime.now()}\n")
        log_file.write(f"Email Text: {email_text}\n")
        log_file.write(f"Output: {output}\n")
        log_file.write(f"Error: {error}\n")
        log_file.write("-" * 80 + "\n")