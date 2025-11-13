# AssistedDiscovery

**Version 3.0.0** | AI-Powered NDC XML Analysis & Pattern Discovery

[![Release](https://img.shields.io/badge/release-v3.0.0-blue.svg)](https://github.com/nikhil-codes-hub/ad_revamped/releases/tag/v3.0.0)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **What's New in 3.0.0**: Major codebase cleanup (~8,000 lines removed), improved error handling with exponential backoff for rate limits, better architecture with pattern verification in backend services, and enhanced user experience. See [CHANGELOG.md](CHANGELOG.md) for details.

### Recent Improvements (v3.0.0)
- 🧹 **Codebase Cleanup**: Removed ~8,000 lines of dead code and obsolete files
  - Eliminated unused MySQL migration scripts (now using SQLite with auto-migrations)
  - Removed orphaned test files and duplicate requirements files
  - Cleaned up frontend utilities and old backup files
- 🏗️ **Architecture Refactoring**: Moved pattern verification to backend services layer
- ⚡ **Rate Limit Handling**: Added exponential backoff retry logic for Azure OpenAI
- 📝 **Error Messages**: Simplified and improved error messages for non-technical users
- 🎨 **UI Improvements**: Better workspace management and pattern verification interface

## 🏗️ Architecture

- **Backend**: FastAPI with Python 3.10
- **Frontend**: Streamlit UI
- **Database**: SQLite (workspace-based isolation)
- **LLM**: Azure OpenAI GPT-4o
- **Parser**: lxml (streaming)

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Azure OpenAI API access (with GPT-4o deployment)
- No external database required (uses SQLite)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ad
```

### 2. Backend Setup

```bash
# Create virtual environment
python3 -m venv assisted_discovery_env
source assisted_discovery_env/bin/activate  # On Windows: assisted_discovery_env\Scripts\activate

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Setup environment
cp ../.env.example .env
# Edit .env with your Azure OpenAI credentials

# Start the FastAPI server (database auto-creates on first run)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at http://localhost:8000
API documentation: http://localhost:8000/docs

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend/streamlit_ui

# Start Streamlit UI
streamlit run AssistedDiscovery.py --server.port 8501
```

The UI will be available at http://localhost:8501

## 📊 API Endpoints

### Runs Management
- `POST /api/v1/runs/?kind={pattern_extractor|discovery}` - Create new run
- `GET /api/v1/runs/{run_id}` - Get run status
- `GET /api/v1/runs/{run_id}/report` - Get run report
- `GET /api/v1/runs/` - List recent runs

### Patterns
- `GET /api/v1/patterns/` - List discovered patterns
- `GET /api/v1/patterns/{pattern_id}` - Get pattern details
- `GET /api/v1/patterns/stats/coverage` - Coverage statistics

### Node Facts
- `GET /api/v1/node_facts/` - List extracted node facts
- `GET /api/v1/node_facts/{node_fact_id}` - Get node fact details

### Health Check
- `GET /health` - API health status

## 🔧 Configuration

Key environment variables in `.env`:

```bash
# Azure OpenAI Configuration
AZURE_AUTH_METHOD=api_key              # Authentication: 'api_key' or 'bdp' (Azure AD)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_azure_openai_key  # For api_key auth
MODEL_DEPLOYMENT_NAME=gpt-4o
AZURE_API_VERSION=2025-01-01-preview

# For BDP (Azure AD) Authentication
# AZURE_TENANT_ID=your-tenant-id
# AZURE_CLIENT_ID=your-client-id
# AZURE_CLIENT_SECRET=your-client-secret

# Rate Limiting & Retry
MAX_LLM_RETRIES=3                      # Retry attempts on rate limit
RETRY_BACKOFF_FACTOR=2.0               # Exponential backoff (2s, 4s, 8s...)

# XML Processing
MAX_XML_SIZE_MB=100
MAX_SUBTREE_SIZE_KB=20
MICRO_BATCH_SIZE=6

# Pattern Discovery
PATTERN_CONFIDENCE_THRESHOLD=0.7
LLM_TEMPERATURE=0.1
MAX_PARALLEL_NODES=2                   # Parallel nodes (1-2 recommended to avoid rate limits)
```

## 📁 Project Structure

```
ad/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/            # API endpoints
│   │   ├── core/              # Core configuration
│   │   ├── models/            # Database models & schemas
│   │   ├── prompts/           # LLM prompt templates
│   │   ├── services/          # Business logic services
│   │   │   ├── pattern_verifier.py    # LLM-based pattern verification
│   │   │   ├── llm_extractor.py       # LLM extraction service
│   │   │   └── workspace_db.py        # Workspace database management
│   │   └── utils/             # Utility functions
│   ├── data/                  # SQLite workspace databases
│   │   └── workspaces/        # Per-workspace .db files
│   └── tests/                 # Backend tests
│       ├── unit/              # Unit tests
│       └── integration/       # Integration tests
├── frontend/                  # Streamlit frontend
│   ├── streamlit_ui/          # UI components
│   │   ├── pages/             # Streamlit pages
│   │   ├── utils/             # Frontend utilities
│   │   ├── AssistedDiscovery.py   # Main app entry
│   │   └── pattern_manager.py     # Pattern management UI
│   └── requirements.txt
├── docs/                      # Documentation
├── resources/                 # Sample XML files and test data
├── scripts/                   # Build and utility scripts
└── .env                       # Environment configuration
```

## 🔄 Processing Flows

### Pattern Extractor Flow
1. Upload NDC XML file from existing airline
2. Stream parse with memory-bounded processing
3. Extract NodeFacts with PII masking
4. Generate patterns via LLM micro-batching
5. Deduplicate patterns by signature hash
6. Store results and generate report

### Discovery Flow
1. Upload NDC XML file from new airline
2. Extract NodeFacts from target sections
3. Retrieve Top-K candidate patterns
4. Apply hard constraint validation
5. Calculate confidence scores with pattern matching
6. Generate gap analysis report

## 📊 Database Schema

**Database Location**: `backend/data/workspaces/{workspace_name}.db` (SQLite)

Key tables:
- `runs` - Processing run tracking (discovery/pattern extraction)
- `node_facts` - Extracted and masked XML nodes with PII protection
- `patterns` - Discovered patterns with signature hashes and superseded_by tracking
- `pattern_matches` - Pattern matching results with confidence scores
- `node_configurations` - BA-configured extraction rules
- `node_relationships` - Discovered relationships between nodes

**Multi-workspace Support**: Each workspace has its own isolated SQLite database with automatic schema migrations applied on first access via `workspace_db.py`

## 🧪 Testing

```bash
# Unit tests (fast - 1.3s)
cd backend
pytest tests/unit/ -v

# With coverage report
pytest tests/unit/ --cov=app --cov-report=html --cov-report=term

# VS Code: Press F5 → Select "AD 🧪 Run Unit Tests"

# View coverage report
open htmlcov/index.html
```

**Current Test Status** (as of 2025-10-17):
- 40% coverage (honest metric)
- 69/120 tests passing (58%)
- Unit tests: 81% pass rate
- Core services: 70-92% coverage (production-ready)

## 📈 Monitoring

- Health check: `GET /health`
- Metrics: Prometheus format at `:9090/metrics`
- Logs: Structured JSON logging to stdout

## 🔐 Security

- PII masking for emails, phones, dates, IDs
- Server-side PII validation gate
- Snippet length restrictions (≤120 chars)
- No raw XML stored in database

## ✨ Key Features

### Completed ✅
- ✅ **XML Processing**: Streaming parser with memory-bounded processing for large files
- ✅ **NodeFacts Extraction**: LLM-based extraction with business intelligence enrichment
- ✅ **PII Protection**: Automatic masking for emails, phones, dates, IDs (11 pattern types)
- ✅ **Pattern Discovery**: SHA256 signature hashing, deduplication, decision rule extraction
- ✅ **Pattern Matching**: Version-filtered matching with 4-factor weighted confidence scoring
- ✅ **Pattern Verification**: LLM-based AI verification of patterns against XML samples
- ✅ **Relationship Discovery**: Automatic detection of parent-child relationships
- ✅ **Conflict Resolution**: Pattern hierarchy management with superseded_by tracking
- ✅ **Multi-workspace**: Isolated SQLite databases per workspace with auto-migrations
- ✅ **Rate Limit Handling**: Exponential backoff retry logic for Azure OpenAI rate limits
- ✅ **Comprehensive API**: FastAPI backend with full CRUD operations
- ✅ **Modern UI**: Streamlit interface with workspace management and pattern tools

### Verdict Types
- `EXACT` - Perfect match with existing pattern
- `HIGH` - High confidence match (>85%)
- `PARTIAL` - Partial match (50-85%)
- `LOW` - Low confidence match (<50%)
- `NO_MATCH` - No matching pattern found
- `NEW_PATTERN` - New pattern detected

## 🗺️ Roadmap

### Future Enhancements
- Embeddings-based pattern retrieval for improved matching
- Cross-message pattern analysis
- Advanced PII detection with custom patterns
- Pattern evolution tracking and versioning
- Performance optimization for very large XML files (>100MB)
- Horizontal scaling for multi-tenant deployments
- Monitoring dashboard with metrics visualization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## 📜 License

[Add license information]

## 📞 Support

For issues and questions:
- Create GitHub issues for bugs/features
- Check [CHANGELOG.md](CHANGELOG.md) for version history
- Review API documentation at http://localhost:8000/docs (when server is running)
- See release notes in `docs/` directory for detailed updates