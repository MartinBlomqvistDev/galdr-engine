# GALDR Engine
**High-performance Asynchronous AI Orchestration.**

GALDR is a specialized engine for voice-first interactive fiction, designed for sub-500ms p95 latency. It implements a strict separation between narrative structure (directed graphs) and generative improvisation.

### Core Architectural Pillars
- **Strict State Management:** Pydantic-validated atomic state transitions.
- **Service Orchestration:** Dependency-injected AI backends (STT/LLM/TTS) via async protocols.
- **Latency Monitoring:** Integrated telemetry for every step of the 8-stage processing loop.
- **Offline-First Resilience:** Deterministic mechanical resolution (dice, flags, nodes) with optional AI enhancement.

### Tech Stack
Python 3.11+, FastAPI, Asyncio, Pydantic v2.

See `app/README.md` and `app/ARCHITECTURE.md` for technical deep-dives.
