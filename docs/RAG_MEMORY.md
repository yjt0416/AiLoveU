# RAG Memory Layer

This project includes a lightweight local RAG memory system for personalized multi-session conversation.

## What It Does

- Keeps short-term conversation turns for the current session
- Stores long-term user facts and preferences locally
- Extracts structured user memory with an LLM + JSON schema
- Retrieves relevant memories before each reply
- Injects recalled memory into the prompt as additional system context
- Separates memory by companion character namespace

## Architecture

1. User input enters `ChatBot.send_message`
2. `MemoryManager` reads recent turns from the current session
3. `MemoryManager` retrieves relevant long-term memories from the active character namespace
4. Retrieved context is appended as a system message
5. The main LLM generates a personalized reply
6. A second LLM pass extracts structured memory from the user utterance
7. Schema validation normalizes the extraction result
8. Valid profile fields and memories are persisted locally

## Key Modules

- [chat_bot_rag.py](/D:/ADesk/AIPartner/src/chat_bot_rag.py)
- [memory_engine.py](/D:/ADesk/AIPartner/src/memory_engine.py)
- [memory_schema.py](/D:/ADesk/AIPartner/src/memory_schema.py)
- [llm_memory_extractor.py](/D:/ADesk/AIPartner/src/llm_memory_extractor.py)

## Why It Matters

Compared with plain multi-turn chat history, this design demonstrates:

- persistent personalization
- retrieval-augmented prompting
- schema-constrained information extraction
- namespace-based isolation for multi-character conversation
- local-first memory storage without requiring a separate vector database

## Good Next Steps

- add embedding-based retrieval
- add memory CRUD management in GUI
- add memory importance decay
- add evaluation metrics such as recall hit rate and latency
