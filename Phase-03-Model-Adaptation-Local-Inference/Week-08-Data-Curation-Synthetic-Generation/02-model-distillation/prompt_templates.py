def get_domain_template(domain):
    templates = {
        'doctor_notes': """Generate a realistic doctor's note containing these PII elements:
        - Patient name: [Provide a name with potential misspelling or foreign origin]
        - Date of birth: [Use non-standard format like DD/MM/YY or Month DD, YYYY]
        - Medical record number: [Format: XXX-XX-XXXX or similar]
        - Address: [Include potential formatting inconsistencies]
        - Phone number: [Format with varied spacing/punctuation]
        - Email: [Include possible typos in domain]
        Make it sound like a real clinical note with medical terminology and natural flow.""",
        
        'hr_complaints': """Generate a realistic HR workplace complaint containing:
        - Employee name: [Foreign name or name with common misspelling]
        - Employee ID: [Alphanumeric format]
        - Date of incident: [Non-standard date format]
        - Department: [Typical corporate department]
        - Supervisor name: [Another name variation]
        - Contact information: [Phone/email with intentional inconsistencies]
        Describe the complaint in natural workplace language.""",
        
        'bank_logs': """Generate a realistic bank transaction log entry containing:
        - Account holder name: [Name with cultural variation or typo]
        - Account number: [Standard bank format]
        - Transaction date: [Non-standard format like YY-MM-DD]
        - Transaction amount: [Currency format]
        - Reference number: [Alphanumeric]
        - Branch location: [Address with potential formatting issues]
        - Employee ID: [Teller/agent identifier]
        Make it look like an actual bank system log."""
    }
    return templates.get(domain, templates['doctor_notes'])  # default fallback
