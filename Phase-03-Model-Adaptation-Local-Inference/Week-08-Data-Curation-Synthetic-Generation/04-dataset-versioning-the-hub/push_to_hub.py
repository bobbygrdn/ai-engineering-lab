from datasets import load_dataset
from huggingface_hub import login
import os
from dotenv import load_dotenv

load_dotenv()

# 1. Login to Hugging Face
hf_token = os.getenv("HF_TOKEN") # Put your Hugging Face Write Token in your .env file
login(token=hf_token)

# 2. Define your repository name
# Replace 'your-username' with your actual Hugging Face username
REPO_ID = "Bobbygrdn/pii-redactor-training-v1" 

print("Loading local clean JSONL dataset...")
# 3. Load the clean dataset you just validated
dataset = load_dataset("json", data_files="clean_training_data.jsonl", split="train")

print(f"Total rows loaded: {len(dataset)}")

# 4. Create the Train/Test Split (90% Train, 10% Test)
print("Splitting data into Training and Testing sets...")
split_dataset = dataset.train_test_split(test_size=0.10, seed=42)

print(f"Train rows: {len(split_dataset['train'])}")
print(f"Test rows: {len(split_dataset['test'])}")

# 5. Push to the Hub
print(f"Pushing dataset to {REPO_ID} on the Hugging Face Hub...")
split_dataset.push_to_hub(REPO_ID, private=True) # Keep it private so your data doesn't leak!

print("✅ Success! Dataset is live in the cloud and ready for use.")