# AssistedDiscovery

**Version 2.0.0** | AI-Powered NDC XML Analysis & Pattern Discovery

[![Release](https://img.shields.io/badge/release-v2.0.0-blue.svg)](https://github.com/nikhil-codes-hub/ad_revamped/releases/tag/v2.0.0)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **What's New in 2.0.0**: Major stability improvements, enhanced UI/UX, near-perfect JSON parsing success rate, and improved pattern verification. See [CHANGELOG.md](CHANGELOG.md) for details.

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

Key environment variables (see `.env.example`):

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your_azure_openai_key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Application
MAX_XML_SIZE_MB=100
MAX_SUBTREE_SIZE_KB=500
ENABLE_PARALLEL_PROCESSING=true
MAX_PARALLEL_NODES=4

# Processing
PATTERN_CONFIDENCE_THRESHOLD=0.85
```

## 📁 Project Structure

```
ad/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/            # API endpoints
│   │   ├── core/              # Core configuration
│   │   ├── models/            # Database models & schemas
│   │   ├── services/          # Business logic services
│   │   └── utils/             # Utility functions
│   ├── migrations/            # Database migrations
│   └── tests/                 # Backend tests
├── frontend/                  # Streamlit frontend
│   ├── streamlit_ui/          # UI components
│   └── requirements.txt
├── docs/                      # Documentation
├── scripts/                   # Utility scripts
└── .env.example              # Environment template
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

**Database Location**: `workspaces/{workspace_name}/workspace.db` (SQLite)

Key tables:
- `ndc_target_paths` - Configuration for XML target paths
- `runs` - Processing run tracking (discovery/identify)
- `node_facts` - Extracted and masked XML nodes
- `patterns` - Discovered patterns with signature hashes
- `pattern_matches` - Pattern matching results with confidence scores
- `node_configurations` - BA-configured extraction rules

**Multi-workspace Support**: Each workspace has its own isolated SQLite database

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

## 🚧 Implementation Status

**Current Phase**: Phase 4 - API & Monitoring (40% complete)
**Overall Progress**: 90% complete (as of 2025-10-03)

### Completed Phases ✅
- ✅ **Phase 0**: Foundation & Infrastructure (100%)
- ✅ **Phase 1**: Extraction & Storage (100%)
  - XML streaming parser with memory-bounded processing
  - LLM-based NodeFacts extraction
  - Business intelligence enrichment
  - PII masking (11 pattern types)
- ✅ **Phase 2**: Pattern Discovery (100%)
  - Pattern generator with SHA256 signature hashing
  - Decision rule extraction
  - Pattern deduplication (times_seen tracking)
  - 19 patterns generated from 82 NodeFacts
- ✅ **Phase 3**: Pattern Matching (100%)
  - Version-filtered pattern matching
  - 4-factor weighted confidence scoring
  - 6 verdict types (EXACT, HIGH, PARTIAL, LOW, NO_MATCH, NEW_PATTERN)
  - Gap analysis and NEW_PATTERN detection

### In Progress 🔄
- 🔄 **Phase 4**: API & Monitoring (40%)
  - Run reports endpoint
  - Coverage statistics API
  - Pattern match history
  - Monitoring endpoints

### Pending ⏳
- ⏳ **Phase 5**: Testing & Validation
  - Comprehensive testing suite (currently 40% coverage)
  - Performance benchmarking
  - End-to-end validation

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for detailed progress tracking.

## 📋 Development Roadmap

### Week 1: MVP Implementation
- Days 1-2: Foundation & XML processing
- Day 3: Fact extraction & storage
- Day 4: Pattern discovery with LLM
- Day 5: Identify & classification
- Days 6-7: API, monitoring, testing

### Week 2-3: Production Hardening
- Multi-airline support
- Horizontal scaling
- Advanced error handling
- Monitoring dashboard

### Month 2: Advanced Features
- Embeddings-based retrieval
- Cross-message patterns
- Advanced PII detection
- Pattern evolution tracking

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
- Check [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for current progress
- Review [AssistedDiscovery_Enhanced_Design_Document.md](AssistedDiscovery_Enhanced_Design_Document.md) for architecture details