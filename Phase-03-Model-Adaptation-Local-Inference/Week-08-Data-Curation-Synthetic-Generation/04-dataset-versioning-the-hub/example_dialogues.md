# Example Dialogues

## Introduction

The following examples demonstrate the redaction behavior of the schema in practice. Each example shows a user input (raw medical email) and the corresponding assistant output (redacted with [NAME], [SSN] tags).

## Example 1: Name Redaction

### User Message

Raw medical email with PII (name):

Dear Dr. Smith,
I am writing to inform you that my patient, John Doe, has been diagnosed with diabetes.

### Assistant Message

Redacted email with [NAME] tag:

Dear Dr. [NAME],
I am writing to inform you that my patient, [NAME], has been diagnosed with diabetes.

## Example 2: SSN Redaction

### User Message

Raw medical email with PII (SSN):

Dear Dr. Smith,
I am writing to inform you that my patient, John Doe, with SSN 123-45-6789, has been diagnosed with diabetes.

### Assistant Message

Redacted email with [SSN] tag:

Dear Dr. [NAME],
I am writing to inform you that my patient, [NAME], with SSN [SSN], has been diagnosed with diabetes.

## Example 3: Multiple PII Redaction

### User Message

Raw medical email with multiple PII (name, SSN, address):

Dear Dr. Smith,
I am writing to inform you that my patient, John Doe, with SSN 123-45-6789, living at 123 Main St, has been diagnosed with diabetes.

### Assistant Message

Redacted email with [NAME], [SSN], and [ADDRESS] tags:

Dear Dr. [NAME],
I am writing to inform you that my patient, [NAME], with SSN [SSN], living at [ADDRESS], has been diagnosed with diabetes.

## Conclusion

These examples demonstrate how the schema redacts PII in medical emails, replacing names, SSNs, and addresses with corresponding tags. This redaction behavior is designed to protect sensitive patient information while allowing for the exchange of necessary medical data.
