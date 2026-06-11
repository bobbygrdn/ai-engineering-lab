import os
import logging
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from concurrent.futures import ProcessPoolExecutor

# Setup logging to capture errors and log events without stopping the pipeline
logging.basicConfig(filename='conversions.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
GLOBAL_OUTPUT_DIR = "northwind_data_md"


def init_worker(options):
    """
    Initialize the worker process with the DocumentConverter instance.
    """
    global worker_converter
    worker_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=options
            )
        }
    )

def process_batch(file_batch):
    """
    Process a batch of files using the worker_converter instance.
    """
    # Create a results list to store the output paths
    results = []
    for result in worker_converter.convert_all(file_batch):
        try:
            if result.document:
                output_file = Path(GLOBAL_OUTPUT_DIR) / f"{result.input.file.stem}.md"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(result.document.export_to_markdown())
                results.append(f"Success: {result.input.file} -> {output_file}")
        except Exception as e:
            logging.error(f"Failed to process {result.input.file.name}: {str(e)}")
    return results

def run_pipeline(input_dir):
    # Ensure output directory exists
    os.makedirs(GLOBAL_OUTPUT_DIR, exist_ok=True)

    # Gather all PDF files from the input directory as a list of Path objects
    files = list(Path(input_dir).glob('*.pdf'))

    # Configure: 2 workers, 2 threads each = 4 cores total
    options = PdfPipelineOptions()
    options.accelerator_options = AcceleratorOptions(
        device=AcceleratorDevice.CPU,
        num_threads=2,
    )
    options.do_ocr = False  # Disable OCR for better performance if not needed

    # Split into batches for efficient processing
    batch_size = 5
    batches = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]

    with ProcessPoolExecutor(max_workers=2, initializer=init_worker, initargs=(options,)) as executor:
        list(executor.map(process_batch, batches))

if __name__ == "__main__":
    run_pipeline("northwind_data")