# GALDR Engine
**Asynchronous Voice-First AI Orchestration.**

GALDR is an event-driven engine for real-time voice-AI interaction, optimized for p95 <500ms latency via asynchronous flow control and strict state persistence.

## Architecture
1. **Voice Layer:** Audio stream processing (STT/TTS).
2. **Logic Layer:** Asynchronous FastAPI orchestration.
3. **Content Layer:** Context management and RAG logic.
4. **Persistence Layer:** Pydantic-driven state management.

## Stack
Python 3.11+, FastAPI, Asyncio, Pydantic v2, NumPy.
