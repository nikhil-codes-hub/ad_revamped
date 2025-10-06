# AssistedDiscovery - Setup Guide

Complete setup instructions for running the project on a new machine.

## Prerequisites

- Python 3.10+
- MySQL 8.0+
- Git
- Node.js (optional, for any frontend tooling)

## 1. Clone Repository

```bash
git clone https://github.com/nikhil-codes-hub/ad_revamped.git
cd ad_revamped/ad
```

## 2. Database Setup

### Create Database and User

```bash
mysql -u root -p
```

```sql
-- Create database
CREATE DATABASE assisted_discovery CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create user with password
CREATE USER 'assisted_discovery'@'localhost' IDENTIFIED BY 'assisted_discovery_2025_secure';

-- Grant privileges
GRANT ALL PRIVILEGES ON assisted_discovery.* TO 'assisted_discovery'@'localhost';

FLUSH PRIVILEGES;

EXIT;
```

### Run Migrations (IN ORDER)

```bash
cd backend

# Run each migration in sequence
# Note: Use 001_initial_schema_fixed.sql if 001_initial_schema.sql doesn't exist
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery < migrations/001_initial_schema_fixed.sql
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery < migrations/002_add_airline_columns.sql

# Use SAFE versions to avoid "Duplicate column" errors
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery < migrations/003_add_airline_to_patterns_safe.sql
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery < migrations/004_add_node_configurations.sql
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery < migrations/005_add_pattern_description_safe.sql
```

**If you get "Duplicate column" errors:**
The safe versions (003_safe, 005_safe) check if columns exist before adding them. If you already ran the regular versions and got errors, the safe versions will skip the duplicate columns automatically.

**Verify migrations:**
```bash
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery -e "SHOW TABLES;"
```

Expected tables:
- ndc_target_paths
- ndc_path_aliases
- runs
- node_facts
- association_facts
- patterns
- pattern_matches
- node_configurations

## 3. Environment Configuration

### Create .env file

```bash
cd backend
cp .env.example .env  # If example exists, otherwise create new
```

### Edit .env with your settings:

```bash
# Database Configuration
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=assisted_discovery
MYSQL_PASSWORD=assisted_discovery_2025_secure
MYSQL_DATABASE=assisted_discovery

# Azure OpenAI Configuration (REQUIRED for LLM features)
AZURE_OPENAI_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-mini
LLM_MODEL=gpt-4o-mini

# Application Settings
DEBUG=true
ENVIRONMENT=development
MAX_XML_SIZE_MB=50
MAX_SUBTREE_SIZE_KB=500
PII_MASKING_ENABLED=true
```

## 4. Backend Setup

### Install Python Dependencies

```bash
cd backend

# Using pip
pip install -r requirements.txt

# OR using conda (if you prefer)
conda create -n ad_env python=3.10
conda activate ad_env
pip install -r requirements.txt
```

### Start Backend Server

```bash
# From backend directory
python3 -m uvicorn app.main:app --reload --port 8000

# OR run in background
nohup python3 -m uvicorn app.main:app --reload --port 8000 > backend.log 2>&1 &
```

**Verify backend is running:**
```bash
curl http://localhost:8000/api/v1/health
```

Expected response: `{"status": "healthy"}`

## 5. Frontend Setup

### Install Dependencies

```bash
cd frontend/streamlit_ui

# Install streamlit and dependencies
pip install -r requirements.txt  # If requirements.txt exists
# OR install manually:
pip install streamlit pandas requests
```

### Start Frontend

```bash
# From frontend/streamlit_ui directory
streamlit run main.py

# OR specify port
streamlit run main.py --server.port 8501
```

**Access UI:** http://localhost:8501

## 6. Initial Configuration (IMPORTANT!)

### Option A: Seed with Target Paths (Optional)

If you have an existing `ndc_target_paths` seeding script:

```bash
cd backend
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery < seeds/ndc_target_paths.sql
```

### Option B: Configure Nodes via UI (Recommended)

1. **Upload XML to discover nodes:**
   - Go to **📋 Node Manager** → **📤 Analyze XML** tab
   - Upload an 18.1 XML file
   - System will discover all nodes

2. **Configure extraction rules:**
   - Enable/disable nodes you want to extract
   - Add expected references (e.g., `infant_parent` for PaxList)
   - Add BA remarks
   - Click **💾 Save All Configurations**

3. **Copy to other versions:**
   - Go to **📋 Node Manager** → **📋 Copy to Versions** tab
   - Copy 18.1 configs to 17.2, 19.2, 21.3, 23.1
   - Click **🚀 Copy Configurations to All Versions**

4. **Run Discovery:**
   - Go to **🔬 Discovery** page
   - Upload an XML file
   - System will extract configured nodes and generate patterns

## 7. Testing the Setup

### Test Discovery Workflow

```bash
# Using curl
curl -X POST http://localhost:8000/api/v1/runs/discover \
  -F "file=@/path/to/sample.xml"
```

### Test via UI

1. **Discovery:** Upload XML → Wait for patterns to generate
2. **Identify:** Upload XML → View pattern matches
3. **Pattern Explorer:** Browse generated patterns
4. **Node Manager:** Manage extraction configurations

## 8. Troubleshooting

### Backend not starting?

```bash
# Check logs
tail -f backend/backend.log

# Check if port 8000 is in use
lsof -ti:8000

# Kill existing process
lsof -ti:8000 | xargs kill -9
```

### Database connection errors?

```bash
# Verify MySQL is running
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' -e "SELECT 1;"

# Check .env file credentials match database
cat backend/.env | grep MYSQL
```

### Frontend can't connect to backend?

```bash
# Verify backend is running
curl http://localhost:8000/api/v1/health

# Check API_BASE_URL in frontend/streamlit_ui/main.py
# Should be: API_BASE_URL = "http://localhost:8000/api/v1"
```

### Migration errors?

```bash
# Check which migrations were applied
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery -e "SHOW TABLES;"

# If you need to reset (CAREFUL - deletes all data!)
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery -e "DROP DATABASE assisted_discovery;"
# Then recreate and run migrations again
```

## 9. Development Workflow

### Making Changes

```bash
# Backend changes auto-reload (if using --reload flag)
# Frontend changes auto-reload (Streamlit watches files)

# To restart backend:
lsof -ti:8000 | xargs kill -9
python3 -m uvicorn app.main:app --reload --port 8000
```

### Creating New Migrations

```bash
cd backend/migrations

# Create new migration file
# Format: XXX_description.sql
# Example: 006_add_new_feature.sql

# Run migration
mysql -u assisted_discovery -p'assisted_discovery_2025_secure' assisted_discovery < migrations/006_add_new_feature.sql
```

## 10. Production Deployment Notes

- Set `DEBUG=false` in .env
- Use production-grade WSGI server (gunicorn, uvicorn workers)
- Enable HTTPS/TLS
- Use environment variables for secrets (not .env file)
- Set up proper logging and monitoring
- Configure database backups
- Use connection pooling for database
- Set up Redis for caching (optional)

## Additional Resources

- **API Documentation:** http://localhost:8000/docs (Swagger UI)
- **GitHub Repository:** https://github.com/nikhil-codes-hub/ad_revamped
- **Architecture Docs:** See `docs/` folder (if available)

## Support

For issues or questions:
- Check `backend.log` for backend errors
- Check browser console for frontend errors
- Review migrations in order
- Verify .env configuration matches database setup
