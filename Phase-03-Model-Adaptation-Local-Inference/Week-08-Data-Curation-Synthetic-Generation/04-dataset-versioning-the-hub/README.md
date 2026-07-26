# Part 4: Dataset Versioning & The Hub

## Terms

- datasets library
- Hugging Face Hub
- Dataset versioning
- Reproducibility

## Key Concepts

- Data as Code
- Reproducibility in ML
- Centralized Data Storage
- Access Control
- Metadata Embedding

## Implementation Overview

This script demonstrates the practice of treating data as code by versioning and publishing a cleaned training dataset to the Hugging Face Hub. It combines the key concepts of reproducibility, centralized storage, and metadata embedding by loading a locally validated dataset, splitting it into train/test splits for reproducibility, and pushing it to a centralized, access-controlled repository on the Hub with embedded metadata (via the dataset card that can be added separately).

**Primary Capabilities:**

- Load a local JSONL dataset using the 🤗 Datasets library.
- Split the dataset into training and testing sets with a fixed seed for reproducibility.
- Authenticate with the Hugging Face Hub using a secure token from environment variables.
- Push the dataset split to a specified repository on the Hub, configured as private to prevent data leakage.
- Provide feedback on the success of the upload.

## How It Works

The data flow in `push_to_hub.py` is as follows:

1. **Load Environment Variables:** The script loads the Hugging Face API token from a `.env` file using `python-dotenv`.
2. **Authenticate with Hugging Face Hub:** It logs in to the Hub using the loaded token.
3. **Define Repository ID:** The target repository on the Hub is specified (e.g., `"username/pii-redactor-training-v1"`).
4. **Load Local Dataset:** The clean, validated JSONL dataset (`clean_training_data.jsonl`) is loaded into a `datasets.Dataset` object.
5. **Report Dataset Size:** The total number of rows in the loaded dataset is printed.
6. **Create Train/Test Split:** The dataset is split into 90% training and 10% testing sets using a fixed random seed (`seed=42`) to ensure reproducibility.
7. **Report Split Sizes:** The number of examples in the training and test sets are printed.
8. **Push to Hub:** The split dataset is pushed to the Hugging Face Hub repository as a private dataset.
9. **Confirm Success:** A success message is printed indicating the dataset is live and ready for use.

## Example Usage

The following is the actual code from `push_to_hub.py` that demonstrates the workflow. To run this script, you must have a `.env` file containing your `HF_TOKEN` (Hugging Face Write token) and a `clean_training_data.jsonl` file in the same directory.

```python
python push_to_hub.py
```

```python
# You will see this message upon sucess
"✅ Success! Dataset is live in the cloud and ready for use."
```

## Next Steps

- **Versioning:** Implement dataset versioning on the Hugging Face Hub by using commit messages or tags to track changes over time, enhancing reproducibility.
- **Metadata Enrichment:** Automatically generate and upload a dataset README (dataset card) with detailed metadata, including dataset description, collection process, and intended use cases.
- **Pipeline Automation:** Integrate this script into an automated pipeline that runs after data generation and validation, ensuring the latest validated dataset is always available on the Hub.
- **Error Handling & Logging:** Add robust error handling (e.g., for network failures, authentication issues) and detailed logging to track each step of the push process for debugging and auditing.
- **Access Control Refinement:** Explore more granular access control settings on the Hub (e.g., specific user or organization access) if the dataset needs to be shared selectively.
