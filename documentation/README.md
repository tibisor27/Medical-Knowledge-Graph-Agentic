# Medical Chatbot - AI Knowledge Graph

An intelligent medical chatbot system that identifies nutrient depletions caused by medications and recommends personalized supplement products using Neo4j knowledge graphs and LangGraph agents.

## Overview

This project implements an agentic AI system that connects medications with their nutrient depletion effects, symptoms, and recommended products. It uses a graph-based approach to understand the causal relationships between pharmaceuticals and nutritional deficiencies.

### Core Concept

```
Medication → DepletionEvent → Nutrient → Symptom → Recommended Product
     ↑                                              ↑
     └────────────── User Profile ──────────────────┘
```

**Scientific Value:**
- Root cause analysis instead of symptomatic treatment
- Evidence-based connections between drugs and nutritional deficiencies
- Personalized recommendations based on user context

## Key Features

- **Conversational AI**: Natural language interface for medical queries
- **Knowledge Graph**: Neo4j-powered graph database with medications, nutrients, symptoms, studies and products
- **Intelligent Routing**: LangGraph agent with specialized nodes for analysis, extraction, and response synthesis
- **Multi-tier Entity Resolution**: Exact matching, full-text search, and semantic similarity
- **Product Recommendations**: Context-aware supplement suggestions based on identified deficiencies
- **Prompt Management**: Langfuse integration for monitoring and managing LLM prompts

## Project Structure

```
ai-knowledgebase-neo4j-graph/
├── agent_service/          # Main API service
│   ├── api/               # FastAPI backend
│   ├── src/agent/         # LangGraph agent nodes
│   ├── src/database/      # Neo4j client and queries
│   ├── src/prompts/       # LLM prompt templates
│   └── streamlit_app/     # Web UI
├── ingest_service/        # Data ingestion pipeline
├── docker-compose.yml     # Service orchestration
└── documentation/         # Project documentation
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI |
| AI Agent | LangGraph + LangChain |
| LLM | Azure OpenAI (GPT-4.1-mini) |
| Database | Neo4j (Graph Database) |
| Vector Search | Neo4j Vector Index |
| Prompt Management | Langfuse |
| Frontend | Streamlit |
| Deployment | Docker + Docker Compose |

## Documentation

- [Quick Start Guide](QUICK_START.md) - Get up and running in minutes
- [Architecture Overview](ARCHITECTURE.md) - System design and component interactions

## Quick Links

- API Documentation: `http://localhost:8010/docs` (when running)
- Streamlit UI: `http://localhost:8510` (when running)
- Neo4j Browser: `http://localhost:7476` (when running)

