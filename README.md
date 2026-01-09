# PulseGraph

PulseGraph is a freshness-aware AI analyst that turns live web data into a time-aware knowledge graph for reliable AI reasoning.

## Prerequisites

- Python 3.9 or higher
- Neo4j database running locally (default: `bolt://localhost:7687`)
- [uv](https://github.com/astral-sh/uv) package manager

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd PulseGraph
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Configure environment variables**

   Create or update the `.env` file in the project root:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password_here
   ```

4. **Ensure Neo4j is running**

   Verify Neo4j is accessible:
   ```bash
   lsof -i :7687
   ```

## Running the Project

### Seed the Database

Populate Neo4j with minimal test data:

```bash
uv run scripts/seed_minimal.py
```

This creates sample data including:
- Companies (NVIDIA)
- Events (Q3-2025, Q2-2025)
- Source documents
- Claims
- Sentiment signals

### Start the API Server

Run the FastAPI development server:

```bash
uv run fastapi dev api/main.py
```

The API will be available at:
- **API**: http://127.0.0.1:8000
- **Interactive docs**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

### API Endpoints

**POST /ask** - Query the knowledge graph

Example request:
```bash
curl -X POST "http://127.0.0.1:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How did NVIDIA perform?",
    "company": "NVIDIA",
    "period_a": "Q3-2025",
    "period_b": "Q2-2025",
    "window": "post_earnings_7d"
  }'
```

## Project Structure

```
PulseGraph/
├── api/              # FastAPI application
│   ├── __init__.py
│   └── main.py       # API routes and models
├── graph/            # Neo4j graph operations
│   ├── __init__.py
│   ├── db.py         # Database connection
│   ├── schema.py     # Graph schema management
│   ├── queries.py    # Cypher queries
│   └── upsert.py     # Data insertion logic
├── extract/          # Data extraction contracts
│   └── __init__.py
├── scripts/          # Utility scripts
│   └── seed_minimal.py
├── .env              # Environment configuration
├── pyproject.toml    # Project dependencies
└── README.md
```

## Development

### Install in Editable Mode

For active development:

```bash
uv pip install -e .
```

### Run Tests

```bash
uv run pytest
```

## Troubleshooting

**"No module named graph" error**

Make sure you're running commands from the project root and have run `uv sync`.

**Neo4j authentication failed**

Verify your `.env` file has the correct Neo4j credentials and that Neo4j is running.

**Port 8000 already in use**

Stop any existing FastAPI processes or specify a different port:
```bash
uv run fastapi dev api/main.py --port 8001
```
