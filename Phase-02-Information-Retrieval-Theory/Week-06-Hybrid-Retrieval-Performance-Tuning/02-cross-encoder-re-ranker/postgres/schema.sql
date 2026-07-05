CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_store (
    id bigserial PRIMARY KEY,
    content TEXT UNIQUE,
    embedding vector
);