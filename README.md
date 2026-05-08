# GALDR Engine
**High-performance Asynchronous AI Orchestration.**

GALDR is an AI orchestration engine built on a single premise: most agent failures come from letting the LLM control its own execution flow. GALDR separates state machine logic from LLM calls entirely. The directed graph defines what can happen. The model decides content within each node. Deterministic, testable, auditable.

### Core Architectural Pillars
- **Strict State Management:** Pydantic-validated atomic state transitions.
- **Service Orchestration:** Dependency-injected AI backends (STT/LLM/TTS) via async protocols.
- **Latency Monitoring:** Integrated telemetry for every step of the 8-stage processing loop.
- **Offline-First Resilience:** Deterministic mechanical resolution (dice, flags, nodes) with optional AI enhancement.

### Tech Stack
Python 3.11+, FastAPI, Asyncio, Pydantic v2.

See `app/README.md` and `app/ARCHITECTURE.md` for technical deep-dives.
