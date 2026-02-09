# Medical Knowledge Graph Agent

An AI-powered chatbot system that identifies medication-induced nutrient depletions and recommends personalized supplement products using Neo4j knowledge graphs and LangGraph agents.

## Overview

This system connects medications with their nutrient depletion effects, symptoms, and recommended products through a graph-based approach. It uses an agentic AI architecture to understand causal relationships between pharmaceuticals and nutritional deficiencies.

```
Medication → DepletionEvent → Nutrient → Symptom → Recommended Product
     ↑                                              ↑
     └────────────── User Profile ──────────────────┘
```
## Key Features

- **Conversational AI** - Natural language interface for medical queries
- **Knowledge Graph** - Neo4j-powered graph with medications, nutrients, symptoms, studies, products
- **Intelligent Routing** - LangGraph agent with specialized nodes for analysis and response
- **Multi-tier Entity Resolution** - Exact matching, full-text search, semantic similarity
- **Product Recommendations** - Context-aware supplement suggestions
- **Prompt Management** - Langfuse integration for monitoring LLM prompts


## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 2. Deploy all services
make deploy
```

## Services

| Service | URL | Description |
|---------|-----|-------------|
| Streamlit UI | http://localhost:8510 | Chat interface |
| FastAPI | http://localhost:8010 | Backend API & docs |
| Neo4j Browser | http://localhost:7476 | Graph database |

## Project Structure

```
.
├── agent_service/          # Main chatbot service
│   ├── api/               # FastAPI backend
│   ├── src/agent/         # LangGraph agent nodes, state and graph
│   ├── src/database/      # Neo4j integration
│   ├── src/prompts/       # LLM prompt templates
│   └── streamlit_app/     # Web UI
├── ingest_service/        # Data ingestion pipeline
├── documentation/         # Full documentation
├── deploy.sh             # One-command deployment
└── docker-compose.yml    # Service orchestration
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Agent | LangGraph + LangChain |
| LLM | Azure OpenAI (GPT-4) |
| Backend | FastAPI |
| Database | Neo4j (Graph Database) |
| Vector Search | Neo4j Vector Index |
| Prompt Management | Langfuse |
| Frontend | Streamlit |
| Deployment | Docker + Docker Compose |

## Documentation

- **[Quick Start Guide](documentation/QUICK_START.md)** - Get running in minutes
- **[Architecture Overview](documentation/ARCHITECTURE.md)** - System design & components
- **[Documentation Index](documentation/README.md)** - Full documentation

