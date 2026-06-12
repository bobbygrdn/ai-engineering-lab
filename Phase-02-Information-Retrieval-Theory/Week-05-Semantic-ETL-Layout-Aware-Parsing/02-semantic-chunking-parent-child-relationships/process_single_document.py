# 1. Imports
# Import the necessary classes from your chosen library (e.g., docling)
from docling.document_converter import DocumentConverter
import argparse

def parse_pdf_to_markdown(pdf_path: str):
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
    # Write the resulting string to the output_path by replacing the .pdf extension with .md and changing the directory to raw_files_md
    output_path = pdf_path.replace("raw_files", "raw_files_md").replace(".pdf", ".md").replace(".PDF", ".md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown_string)

    return output_path

if __name__ == "__main__":
    # Define your input PDF and desired output file
    # Call the function and print a success message
    parser = argparse.ArgumentParser(description="Convert a PDF document to Markdown format.")
    parser.add_argument("pdf_path", type=str, help="Path to the input PDF file")

    args = parser.parse_args()

    try:
        output_path = parse_pdf_to_markdown(args.pdf_path)
        print(f"Successfully converted {args.pdf_path} to {output_path}")
    except Exception as e:
        print(f"An error occurred while processing {args.pdf_path}: {str(e)}")