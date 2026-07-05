import pandas as pd
import re
import unicodedata
from logger import logger

PARQUET_PATH = r"C:\Users\bobby\Desktop\code\ai-engineering-lab\Phase-02-Information-Retrieval-Theory\Week-06-Hybrid-Retrieval-Performance-Tuning\02-cross-encoder-re-ranker\data\slack_messages.parquet"

df = pd.read_parquet(PARQUET_PATH)

TEXT_COL = "content"

def clean_text(txt: str) -> str:
    txt = unicodedata.normalize("NFKC", txt)

    txt = re.sub(r"[\r\n\t]+", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()

    txt = txt.lower()

    txt = "".join(ch for ch in txt if ord(ch) < 128)

    return txt

def get_clean_texts() -> list[str]:
    df = pd.read_parquet(PARQUET_PATH)
    df = df[[TEXT_COL]].copy()
    df = df.dropna(subset=[TEXT_COL])
    df = df[df[TEXT_COL].str.strip().astype(bool)]
    df[TEXT_COL] = df[TEXT_COL].apply(clean_text)
    logger.info(f"Cleaned {len(df)} texts from the dataset.")
    return df[TEXT_COL].tolist()