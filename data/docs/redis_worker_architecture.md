# What is the architecture of the worker system?
The system uses Redis-backed ARQ workers for async task processing including ingestion and evaluation.

# How does the semantic cache work?
The semantic cache stores query embeddings in Redis and returns cached answers for similar queries above a similarity threshold.
