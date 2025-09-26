# AssistedDiscovery Installation Guide

## Prerequisites

- Python 3.10+ (works with Anaconda/Conda environments)
- MySQL 8.0+ or access to existing MySQL instance
- Redis (optional, for caching)
- Azure OpenAI access

## Installation Options

### Option 1: Standard Installation

```bash
# Backend dependencies
cd backend
pip install -r requirements.txt

# Frontend dependencies
cd ../frontend
pip install -r requirements.txt
```

### Option 2: Conda Environment (Recommended)

If you're using Anaconda/Miniconda and encounter lxml build issues:

```bash
# Install lxml via conda first (avoids build issues)
conda install -c conda-forge lxml

# Backend dependencies (excluding lxml)
cd backend
pip install -r requirements-conda.txt

# Frontend dependencies
cd ../frontend
pip install -r requirements.txt
```

## Environment Setup

1. **Copy environment template:**
```bash
cp .env.example .env
```

2. **Configure Azure OpenAI:**
```bash
# Edit .env file with your Azure OpenAI credentials:
AZURE_OPENAI_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2025-01-01-preview
MODEL_DEPLOYMENT_NAME=gpt-4o
```

3. **Configure MySQL:**
```bash
# Database settings in .env:
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=assisted_discovery
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=assisted_discovery
```

## Database Setup

1. **Create database and user:**
```sql
CREATE DATABASE assisted_discovery CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'assisted_discovery'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON assisted_discovery.* TO 'assisted_discovery'@'localhost';
FLUSH PRIVILEGES;
```

2. **Run schema migration:**
```bash
mysql -u assisted_discovery -p assisted_discovery < backend/migrations/001_initial_schema.sql
```

## Verify Installation

1. **Test Backend:**
```bash
cd backend
python -c "from app.main import app; print('✅ Backend OK')"
```

2. **Test Frontend:**
```bash
cd frontend
python -c "import streamlit; print('✅ Frontend OK')"
```

## Quick Start

1. **Start Backend API:**
```bash
cd backend
python -m app.main
```
Access at: http://localhost:8000

2. **Start Frontend UI:**
```bash
cd frontend
streamlit run streamlit_ui/main.py
```
Access at: http://localhost:8501

## Troubleshooting

### lxml Installation Issues

**Error:** `ERROR: Can not execute setup.py since setuptools failed to import`

**Solution:** Use conda to install lxml:
```bash
conda install -c conda-forge lxml
pip install -r requirements-conda.txt  # Excludes lxml
```

### Database Connection Issues

**Error:** `Can't connect to MySQL server`

**Solutions:**
- Verify MySQL is running: `brew services start mysql` (macOS) or `sudo systemctl start mysql` (Linux)
- Check credentials in `.env` file
- Verify database and user exist
- Test connection: `mysql -u assisted_discovery -p`

### Azure OpenAI Issues

**Error:** `Invalid API key` or `Endpoint not found`

**Solutions:**
- Verify `AZURE_OPENAI_KEY` in `.env`
- Check `AZURE_OPENAI_ENDPOINT` format
- Ensure deployment name matches your Azure resource
- Verify API version is supported

### Port Already in Use

**Error:** `Port 8000 already in use`

**Solutions:**
- Kill existing process: `lsof -ti:8000 | xargs kill`
- Use different port: `uvicorn app.main:app --port 8001`

## Development Setup

For development with auto-reload:

```bash
# Backend with auto-reload
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend with auto-reload (already default)
cd frontend
streamlit run streamlit_ui/main.py
```

## Production Deployment

See [Production Deployment Guide](docs/DEPLOYMENT.md) for production-specific setup including:
- Environment configuration
- Database optimization
- Load balancing
- Security hardening
- Monitoring setup