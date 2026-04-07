# AiLoveU

AiLoveU is a desktop AI companion project for showcasing multimodal LLM application development.  
It combines LLM dialogue, local voice interaction, emotion recognition, Live2D avatars, character-card import, and a lightweight local RAG memory layer.

## Highlights

- Multimodal interaction: text chat, voice input/output, emotion-aware replies, Live2D avatar rendering
- Character Tavern PNG card import: extract persona metadata from PNG and load it as a new companion
- Multi-character companion switching: each character keeps isolated chat history, session context, and long-term memory
- Local RAG memory: short-term session memory, long-term user preference storage, structured memory extraction, retrieval-augmented prompting
- Multiple frontends: CLI, Tkinter GUI, and PyQt6 GUI
- Resume-friendly architecture: API orchestration, memory engine, voice pipeline, character registry, and GUI layers are modularized

## Core Features

### 1. Dialogue and Personalization

- DeepSeek-based conversation
- Automatic reply-language adaptation based on the user's latest input
- Adaptive response-length control for short, normal, and detailed replies
- Structured memory extraction with JSON schema validation
- Retrieval-augmented memory injection before each reply

### 2. Character Card Import

- Supports Character Tavern style PNG cards
- Reads the `chara` metadata block from PNG text chunks
- Decodes base64 JSON and extracts fields such as:
  - `name`
  - `description`
  - `personality`
  - `scenario`
  - `first_mes`
  - `system_prompt`
  - `tags`
- Converts imported cards into isolated local companion profiles

### 3. Multi-Character Isolation

- Switch between multiple AI companions in the GUI
- Each character has its own:
  - system prompt
  - opening message
  - transcript history
  - current session window
  - long-term memory namespace
- "Clear chat" starts a new session for the current character instead of deleting all stored history

### 4. Multimodal Desktop Experience

- Offline ASR with Vosk
- TTS with `edge-tts`
- Emotion recognition with OpenCV + local emotion model
- Live2D model rendering and interaction in the PyQt6 GUI

## Project Structure

```text
AiLoveU/
├── config/
│   ├── __init__.py
│   └── runtime_config.py
├── docs/
│   ├── CHARACTER_CARD_IMPORT.md
│   └── RAG_MEMORY.md
├── src/
│   ├── api_client.py
│   ├── character_card.py
│   ├── character_registry.py
│   ├── chat_bot.py
│   ├── chat_bot_rag.py
│   ├── face_emotion.py
│   ├── llm_memory_extractor.py
│   ├── memory_engine.py
│   ├── memory_schema.py
│   └── voice.py
├── gui.py
├── gui_beautiful.py
├── main.py
├── requirements.txt
└── README.md
```

## Environment

- Python 3.10+
- Windows recommended
- Conda environment optional but recommended

## Quick Start

### 1. Clone

```bash
git clone <your-repository-url>
cd AiLoveU
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your own values:

```env
API_KEY=your_deepseek_api_key_here
API_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-chat
TEMPERATURE=0.8
AI_NAME=AiLoveU
MEMORY_DB_PATH=data/aipartner_memory.db
CHARACTER_REGISTRY_PATH=data/characters.json
SHORT_TERM_MEMORY_TURNS=8
RAG_MEMORY_TOP_K=4
MEMORY_EXTRACTION_MODEL=deepseek-chat
MEMORY_EXTRACTION_TEMPERATURE=0.1
```

### 4. Prepare Local Models Manually

This repository does **not** include large local assets.

You need to prepare them yourself if you want the full multimodal experience:

- Vosk model directory, for example `vosk-model-small-cn-0.22/`
- Emotion model file such as `emotion_model.npy`
- Live2D model assets under `live2d_models/`

### 5. Run

```bash
# CLI
python main.py

# Tkinter GUI
python gui.py

# PyQt6 GUI
python gui_beautiful.py
```

## Resume Positioning

This project is suitable for describing as:

- Desktop multimodal AI companion application
- LLM application with RAG memory and user preference management
- Character-driven conversational AI with persona import and isolated memory namespaces
- Engineering-focused AI application integrating API, local models, GUI, and persistence

Example resume bullets:

- Built a desktop multimodal AI companion integrating LLM dialogue, offline ASR, TTS, emotion recognition, and Live2D avatar rendering.
- Designed a local RAG memory layer with short-term context, long-term preference storage, structured memory extraction, and retrieval-augmented prompting.
- Implemented Character Tavern PNG card import and multi-character switching with isolated transcript and memory namespaces.
- Modularized the system into API, memory, voice, emotion, character, and GUI layers to improve maintainability and extensibility.

## Privacy and Repository Hygiene

This public repository should **not** contain:

- real API keys
- local `.env` files
- chat logs or personal conversation history
- local memory databases / JSON stores
- locally downloaded ASR / TTS / Live2D model assets
- temporary audio recordings

These are ignored via `.gitignore` and should stay local only.

## Notes

- Imported character cards may contain English persona text. The application now adapts reply language based on the user's latest message.
- The first greeting stored in the original character card may still remain in the original card language unless you regenerate or localize it.

## License

MIT
