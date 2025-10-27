#!/bin/bash

# Create Portable Distribution for AssistedDiscovery Revamp
set -e

echo "🚀 Creating Portable AssistedDiscovery Application"
echo "Platform: $(uname -s) $(uname -m)"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf portable_dist

# Create distribution directory
echo "📁 Creating distribution structure..."
mkdir -p portable_dist/backend
mkdir -p portable_dist/frontend
mkdir -p portable_dist/data/workspaces

# Copy backend files
echo "📋 Copying backend files..."
cp -r backend/app portable_dist/backend/
cp backend/requirements.txt portable_dist/backend/
cp -r backend/alembic* portable_dist/backend/ 2>/dev/null || true

# Copy frontend files
echo "📋 Copying frontend files..."
cp -r frontend/streamlit_ui portable_dist/frontend/
cp frontend/requirements.txt portable_dist/frontend/

# Copy .env template if exists
if [ -f ".env.example" ]; then
    cp .env.example portable_dist/.env.template
elif [ -f ".env" ]; then
    cp .env portable_dist/.env.template
fi

# Create setup script with virtual environment
echo "📝 Creating setup script..."
cat > portable_dist/setup.sh << 'EOF'
#!/bin/bash
echo "🔧 Setting up AssistedDiscovery..."
echo "This will create isolated Python environments for backend and frontend"
echo "No pollution of your system Python!"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9+ first."
    exit 1
fi

echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo "❌ Python 3.9+ is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"
echo ""

# Create backend virtual environment
echo "📦 Creating backend virtual environment..."
python3 -m venv backend_env
if [ $? -ne 0 ]; then
    echo "❌ Failed to create backend virtual environment"
    exit 1
fi

echo "Installing backend dependencies..."
backend_env/bin/pip install --upgrade pip
backend_env/bin/pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r backend/requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install backend dependencies"
    exit 1
fi

# Create frontend virtual environment
echo "📦 Creating frontend virtual environment..."
python3 -m venv frontend_env
if [ $? -ne 0 ]; then
    echo "❌ Failed to create frontend virtual environment"
    exit 1
fi

echo "Installing frontend dependencies..."
frontend_env/bin/pip install --upgrade pip
frontend_env/bin/pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r frontend/requirements.txt
if [ $? -ne 0 ]; then
    echo "❌ Failed to install frontend dependencies"
    exit 1
fi

# Create default .env if not exists
if [ ! -f ".env" ]; then
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo "⚙️  Created .env from template"
        echo "⚠️  Please update .env with your Azure OpenAI credentials"
    else
        cat > .env << 'ENVEOF'
# LLM Provider Configuration
# Supported providers: azure, gemini
LLM_PROVIDER=azure

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=your-endpoint-here
AZURE_OPENAI_KEY=your-api-key-here
AZURE_API_VERSION=2025-01-01-preview
MODEL_DEPLOYMENT_NAME=gpt-4o

# Google Gemini Configuration (if using gemini provider)
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-1.5-pro

# LLM Common Settings
MAX_TOKENS_PER_REQUEST=4000
LLM_TEMPERATURE=0.1
LLM_TOP_P=0.0

# Application Settings
LOG_LEVEL=INFO
WORKSPACE_DB_DIR=./data/workspaces
ENVEOF
        echo "⚙️  Created .env template"
        echo "⚠️  Please update .env with your Azure OpenAI credentials"
    fi
fi

echo ""
echo "✅ Setup complete! Isolated environments created."
echo ""
echo "📝 Next Steps:"
echo "   1. Update .env with your Azure OpenAI credentials"
echo "   2. Run ./start_app.sh to start the application"
EOF

chmod +x portable_dist/setup.sh

# Create launcher script
echo "📝 Creating launcher script..."
cat > portable_dist/start_app.sh << 'EOF'
#!/bin/bash
echo "🧞 Starting AssistedDiscovery..."
echo ""

# Check if setup was run
if [ ! -d "backend_env" ] || [ ! -d "frontend_env" ]; then
    echo "❌ Virtual environments not found. Please run ./setup.sh first."
    exit 1
fi

# Check if .env exists and has credentials
if [ ! -f ".env" ]; then
    echo "❌ .env not found. Please run ./setup.sh first."
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down AssistedDiscovery..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    echo "✅ Shutdown complete"
    exit 0
}

# Set up trap for cleanup
trap cleanup SIGINT SIGTERM

# Start backend
echo "🔧 Starting backend API server..."
cd backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
../backend_env/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "⏳ Waiting for backend to start..."
sleep 5

# Check if backend is running
if ! ps -p $BACKEND_PID > /dev/null; then
    echo "❌ Backend failed to start. Check .env configuration."
    exit 1
fi

BACKEND_URL="http://localhost:8000"
for i in {1..10}; do
    if curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
        echo "✅ Backend is healthy at $BACKEND_URL"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Backend health check failed"
        kill $BACKEND_PID
        exit 1
    fi
    sleep 1
done

# Start frontend
echo "🎨 Starting frontend UI..."
cd frontend/streamlit_ui
../../frontend_env/bin/streamlit run AssistedDiscovery.py --server.port 8501 --server.headless true &
FRONTEND_PID=$!
cd ../..

# Wait for frontend to start
echo "⏳ Waiting for frontend to start..."
sleep 3

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ AssistedDiscovery is running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Frontend UI:  http://localhost:8501"
echo "📍 Backend API:  http://localhost:8000"
echo "📍 API Docs:     http://localhost:8000/docs"
echo ""
echo "🌐 Opening browser automatically..."

# Try to open browser
sleep 2
if command -v open >/dev/null 2>&1; then
    # macOS
    open http://localhost:8501
elif command -v xdg-open >/dev/null 2>&1; then
    # Linux
    xdg-open http://localhost:8501
else
    echo "Please open http://localhost:8501 in your browser"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Press Ctrl+C to stop the application"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Wait for user to stop
wait $BACKEND_PID $FRONTEND_PID
EOF

chmod +x portable_dist/start_app.sh

# Create stop script
echo "📝 Creating stop script..."
cat > portable_dist/stop_app.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping AssistedDiscovery..."

# Kill backend
pkill -f "uvicorn app.main:app" && echo "✅ Backend stopped"

# Kill frontend
pkill -f "streamlit run AssistedDiscovery.py" && echo "✅ Frontend stopped"

echo "✅ All services stopped"
EOF

chmod +x portable_dist/stop_app.sh

# Create README
echo "📝 Creating README..."
cat > portable_dist/README.txt << EOF
# AssistedDiscovery Application

AssistedDiscovery Revamp - A comprehensive tool for analyzing and managing NDC
(New Distribution Capability) message structures across different airline implementations.

## Quick Setup

1. Ensure Python 3.9+ is installed
2. Run ./setup.sh to install dependencies (one time only)
3. Run ./start_app.sh to start the application
4. Configure LLM credentials via the Config page in the UI
5. Restart the app for changes to take effect
6. Start using AssistedDiscovery!

## System Requirements

- Python 3.9 or later
- pip3 (Python package manager)
- Internet connection for initial setup
- 8GB RAM minimum (recommended)
- Browser: Chrome, Firefox, Safari, or Edge
- Disk space: 2GB for dependencies

## Features

- 🗄️ Node Manager - Configure extraction rules and expected references
- 🔬 Discovery - Analyze XML files to extract node structures and patterns
- 🎨 Pattern Manager - Review patterns, explore library, manage exports
- 🎯 Identify - Match new XML files against known patterns
- 💾 Workspace Support - Isolate patterns by workspace
- 🔍 Relationship Discovery - Automatic relationship detection between nodes
- 🤖 AI-Powered Analysis - Azure OpenAI integration for intelligent extraction

## Configuration

**No manual .env editing required!**

Configure LLM credentials via the web UI:

1. Start the application (./start_app.sh)
2. Open http://localhost:8501 in your browser
3. Click ⚙️ Config in the sidebar
4. Select your LLM provider:
   - Azure OpenAI: Enter Endpoint, API Key, API Version, Model Deployment
   - Google Gemini: Enter API Key, Model Name
5. Click 💾 Save Configuration
6. Click 🔍 Test Connection to verify
7. Restart the app (Ctrl+C, then ./start_app.sh again)

## Scripts

- setup.sh - One-time dependency installer (creates virtual environments)
- start_app.sh - Start both backend and frontend services
- stop_app.sh - Stop all running services

## Ports

- Frontend (Streamlit): 8501
- Backend (FastAPI): 8000

## Troubleshooting

### Python Not Found
- Install Python 3.9+ from python.org
- Ensure python3 command is available in PATH

### Permission Issues (macOS)
- Run: chmod +x setup.sh start_app.sh stop_app.sh
- May need to allow execution in System Preferences > Security & Privacy

### Dependencies Install Failed
- Ensure internet connection is active
- Try: python3 -m pip install --upgrade pip
- Then run setup.sh again

### Backend Fails to Start
- Verify no other service is using port 8000
- Check logs in terminal for specific errors
- Backend will start even without LLM credentials configured

### Frontend Can't Connect to Backend
- Ensure backend started successfully (check for "Backend is healthy" message)
- Verify backend is accessible at http://localhost:8000/health
- Check firewall settings

### Port Already in Use
- Stop existing services: ./stop_app.sh
- Or manually: pkill -f uvicorn; pkill -f streamlit

## File Structure

backend/
  app/           - Backend application code
  requirements.txt - Backend Python dependencies
  .env           - Configuration (create from .env.template)

frontend/
  streamlit_ui/  - Frontend UI code
  requirements.txt - Frontend Python dependencies

data/
  workspaces/    - SQLite databases for each workspace

backend_env/     - Backend virtual environment (created by setup.sh)
frontend_env/    - Frontend virtual environment (created by setup.sh)

## Support

For issues and feedback:
- Check logs in the terminal where you ran start_app.sh
- Verify all requirements are met
- Ensure Azure OpenAI credentials are valid

Platform: $(uname -s) $(uname -r)
Build Date: $(date)
EOF

# Create .gitignore for portable dist
cat > portable_dist/.gitignore << 'EOF'
backend_env/
frontend_env/
.env
data/workspaces/*.db
__pycache__/
*.pyc
.DS_Store
EOF

# Detect platform for zip naming
PLATFORM_OS=$(uname -s)
case "$PLATFORM_OS" in
    Darwin*)
        PLATFORM_NAME="Mac"
        ;;
    Linux*)
        PLATFORM_NAME="Linux"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        PLATFORM_NAME="Windows"
        ;;
    *)
        PLATFORM_NAME="Unknown"
        ;;
esac

# Create zip archive for distribution
echo "🗜️ Creating distribution archive..."
cd portable_dist
ZIP_NAME="AssistedDiscovery-${PLATFORM_NAME}.zip"
zip -r -q "../${ZIP_NAME}" .
cd ..

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Portable distribution created successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📦 Files created:"
echo "  - portable_dist/ (distribution folder)"
echo "  - ${ZIP_NAME} (archive)"
echo ""
echo "🖥️  Platform: ${PLATFORM_NAME}"
echo ""
echo "📋 User Instructions:"
echo "  1. Extract ${ZIP_NAME}"
echo "  2. Run ./setup.sh (one time setup)"
echo "  3. Run ./start_app.sh to start application"
echo "  4. Configure LLM via Config page (⚙️) in the UI"
echo "  5. Restart app for changes to take effect"
echo ""
echo "✅ Ready for distribution!"
echo ""
