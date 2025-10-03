# AssistedDiscovery
## 🏗️ Architecture

- **Backend**: FastAPI with Python
- **Frontend**: Streamlit UI
- **Database**: MySQL (current), CouchDB (future migration)
- **Caching**: Redis
- **LLM**: OpenAI GPT-4 Turbo

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- MySQL 8.0+
- Redis (optional, for caching)
- OpenAI API key

### 1. Clone and Setup

```bash
git clone <repository-url>
cd ad
```

### 2. Backend Setup

```bash
# Install backend dependencies
cd backend
pip install -r requirements.txt

# Setup environment
cp ../.env.example .env
# Edit .env with your configuration

# Setup database
mysql -u root -p < migrations/001_initial_schema.sql

# Start the FastAPI server
python -m app.main
```

The API will be available at http://localhost:8000

### 3. Frontend Setup

```bash
# Install frontend dependencies
cd ../frontend
pip install -r requirements.txt

# Start Streamlit UI
streamlit run streamlit_ui/main.py
```

The UI will be available at http://localhost:8501

## 📊 API Endpoints

### Runs Management
- `POST /api/v1/runs/?kind={discovery|identify}` - Create new run
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
# Database
MYSQL_HOST=localhost
MYSQL_USER=assisted_discovery
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=assisted_discovery

# LLM
OPENAI_API_KEY=your_openai_api_key
DEFAULT_MODEL=gpt-4-turbo-preview

# Processing
MAX_XML_SIZE_MB=100
PATTERN_CONFIDENCE_THRESHOLD=0.7
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

### Discovery Flow
1. Upload NDC XML file
2. Stream parse with memory-bounded processing
3. Extract NodeFacts with PII masking
4. Generate patterns via LLM micro-batching
5. Deduplicate patterns by signature hash
6. Store results and generate report

### Identify Flow
1. Upload NDC XML file
2. Extract NodeFacts from target sections
3. Retrieve Top-K candidate patterns
4. Apply hard constraint validation
5. LLM classify with confidence scoring
6. Generate gap analysis report

## 📊 Database Schema

Key tables:
- `ndc_target_paths` - Configuration for XML target paths
- `runs` - Processing run tracking
- `node_facts` - Extracted and masked XML nodes
- `patterns` - Discovered patterns with signatures
- `pattern_matches` - Pattern matching results

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest tests/

# API integration tests
pytest tests/integration/

# Load tests
pytest tests/load/
```

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

Current phase: **Phase 0 - Foundation & Infrastructure**

- ✅ Project structure and dependencies
- ✅ Database schema and models
- ✅ FastAPI application setup
- ✅ Basic Streamlit UI
- ✅ Environment configuration
- ⏳ XML processing core (Day 2)
- ⏳ Pattern discovery (Day 4)
- ⏳ Identify pipeline (Day 5)

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for detailed progress.

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