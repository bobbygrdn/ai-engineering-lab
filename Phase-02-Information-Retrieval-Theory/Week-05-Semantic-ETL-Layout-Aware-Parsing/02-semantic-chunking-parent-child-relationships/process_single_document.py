# 1. Imports
# Import the necessary classes from your chosen library (e.g., docling)
from docling.document_converter import DocumentConverter

def parse_pdf_to_markdown(pdf_path: str, output_path: str):
    """
    Converts a PDF to high-fidelity Markdown preserving hierarchy.
    """
    # 2. Initialize the Parser
    # Create an instance of the DocumentConverter or equivalent
    converter = DocumentConverter()
    # 3. Perform the Conversion
    # Use the converter to process the pdf_path
    # This step typically returns a document object containing the layout tree
    doc = converter.convert(pdf_path).document
    # 4. Export to Markdown
    # Convert the document object into a markdown string
    markdown_string = doc.export_to_markdown()
    # 5. Persistence
    # Write the resulting string to the output_path
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_string)

if __name__ == "__main__":
    # Define your input PDF and desired output file
    # Call the function and print a success message
    input_pdf = "2020_Cybersecurity_and_Privacy_Annual_Report.pdf"
    output_markdown = "2020_Cybersecurity_and_Privacy_Annual_Report.md"
    parse_pdf_to_markdown(input_pdf, output_markdown)
    print(f"Successfully converted {input_pdf} to {output_markdown}")