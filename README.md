# AI-Powered Training Optimization System

This repository hosts the implementation of the AI-driven training optimizer described in `AI_Training_Optimizer_Specification.md`.

## Getting Started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
python scripts/run_scheduler.py
```

Populate `.env` using `.env.example` and refer to the specification for detailed feature requirements.
