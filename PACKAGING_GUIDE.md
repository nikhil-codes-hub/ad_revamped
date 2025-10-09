# AssistedDiscovery Packaging Guide

This guide explains how to create portable distributions of AssistedDiscovery for deployment to user machines.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Building the Distribution](#building-the-distribution)
- [Testing the Distribution](#testing-the-distribution)
- [Distribution to End Users](#distribution-to-end-users)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### For Building the Distribution

You need:
- Mac/Linux or Windows machine
- Python 3.9+ installed
- Access to the AD Revamp source code
- `zip` command (Mac/Linux) or PowerShell (Windows)

### What Gets Packaged

The build scripts will package:
- ✅ Backend application code (`backend/app/`)
- ✅ Frontend application code (`frontend/streamlit_ui/`)
- ✅ Requirements files for both backend and frontend
- ✅ Setup scripts for automated installation
- ✅ Launch scripts for starting/stopping services
- ✅ Comprehensive README for end users

**Note**: The following are NOT included and will be created during setup:
- Virtual environments (created by `setup.sh`/`setup.bat`)
- Python dependencies (installed by `setup.sh`/`setup.bat`)
- `.env` configuration (template created, user must fill in)

---

## Building the Distribution

### For Mac/Linux Users

1. **Navigate to project root**:
   ```bash
   cd /path/to/AD_revamp/ad
   ```

2. **Run the build script**:
   ```bash
   ./build_portable.sh
   ```

3. **Output files**:
   - `portable_dist/` - Distribution folder
   - `AssistedDiscovery-Portable-Darwin-arm64.zip` - Distribution archive

   (Filename varies by platform, e.g., `Darwin-x86_64`, `Linux-x86_64`)

### For Windows Users

1. **Open Command Prompt as Administrator**

2. **Navigate to project root**:
   ```cmd
   cd C:\path\to\AD_revamp\ad
   ```

3. **Run the build script**:
   ```cmd
   build_portable.bat
   ```

4. **Output files**:
   - `portable_dist\` - Distribution folder
   - `AssistedDiscovery-Portable-Windows.zip` - Distribution archive

---

## Testing the Distribution

Before distributing to users, test the package on a clean machine or VM.

### Mac/Linux Testing

1. **Extract the ZIP file**:
   ```bash
   unzip AssistedDiscovery-Portable-*.zip -d test_install
   cd test_install
   ```

2. **Run setup** (one-time):
   ```bash
   ./setup.sh
   ```

   Expected output:
   ```
   🔧 Setting up AssistedDiscovery...
   ✅ Python 3.x detected
   📦 Creating backend virtual environment...
   Installing backend dependencies...
   📦 Creating frontend virtual environment...
   Installing frontend dependencies...
   ⚙️  Created backend/.env template
   ✅ Setup complete!
   ```

3. **Start the application** (no .env editing needed):
   ```bash
   ./start_app.sh
   ```

   Expected output:
   ```
   🧞 Starting AssistedDiscovery...
   🔧 Starting backend API server...
   ⏳ Waiting for backend to start...
   ✅ Backend is healthy at http://localhost:8000
   🎨 Starting frontend UI...
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ✅ AssistedDiscovery is running!
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   📍 Frontend UI:  http://localhost:8501
   📍 Backend API:  http://localhost:8000
   📍 API Docs:     http://localhost:8000/docs
   ```

4. **Configure LLM Provider via UI**:
   - Browser opens automatically to http://localhost:8501
   - Click **⚙️ Config** in the sidebar
   - Select your LLM provider (Azure OpenAI or Google Gemini)
   - Enter your credentials:
     - **Azure**: Endpoint, API Key, API Version, Model Deployment
     - **Gemini**: API Key, Model Name
   - Click **💾 Save Configuration**
   - Click **🔍 Test Connection** to verify
   - **Important**: Stop and restart the app for changes to take effect

5. **Restart the backend**:
   ```bash
   # Press Ctrl+C to stop
   ./start_app.sh
   ```

6. **Verify in browser**:
   - Navigate to http://localhost:8501
   - Check that all pages load (Node Manager, Discovery, Pattern Manager, Identify)
   - Test uploading a sample XML file
   - Verify backend health at http://localhost:8000/health

7. **Stop the application**:
   ```bash
   # Press Ctrl+C in the terminal
   # or run:
   ./stop_app.sh
   ```

### Windows Testing

1. **Extract the ZIP file**:
   - Right-click `AssistedDiscovery-Portable-Windows.zip`
   - Choose "Extract All..."
   - Extract to `C:\test_install`

2. **Run setup** (one-time):
   - Double-click `setup.bat`
   - Wait for installation to complete
   - Press any key to close

3. **Start the application** (no .env editing needed):
   - Double-click `start_app.bat`
   - Two console windows will open (backend and frontend)
   - Browser should open automatically

4. **Configure LLM Provider via UI**:
   - Click **⚙️ Config** in the sidebar
   - Select your LLM provider (Azure OpenAI or Google Gemini)
   - Enter your credentials
   - Click **💾 Save Configuration**
   - Click **🔍 Test Connection** to verify

5. **Restart the application**:
   - Close both console windows
   - Double-click `start_app.bat` again

6. **Verify in browser**:
   - Navigate to http://localhost:8501
   - Test all features

7. **Stop the application**:
   - Double-click `stop_app.bat`
   - Or close both console windows

---

## Distribution to End Users

### Step 1: Prepare Distribution Package

After successful testing:

1. **Keep the ZIP file**:
   - `AssistedDiscovery-Portable-Darwin-arm64.zip` (Mac Apple Silicon)
   - `AssistedDiscovery-Portable-Darwin-x86_64.zip` (Mac Intel)
   - `AssistedDiscovery-Portable-Linux-x86_64.zip` (Linux)
   - `AssistedDiscovery-Portable-Windows.zip` (Windows)

2. **Create a distribution email/document** with:
   - Link to download the appropriate ZIP file
   - System requirements
   - Quick start instructions
   - Support contact information

### Step 2: User Instructions Template

Send this to your users:

```
Subject: AssistedDiscovery Installation Package

Hi [User],

Please find attached/linked the AssistedDiscovery installation package.

System Requirements:
- Python 3.9 or later (https://www.python.org/downloads/)
- 8GB RAM minimum
- Internet connection for initial setup
- 2GB free disk space

Quick Start:
1. Extract the ZIP file to a folder (e.g., C:\AssistedDiscovery)
2. Run setup.sh (Mac/Linux) or setup.bat (Windows) - ONE TIME ONLY
3. Edit backend/.env with Azure OpenAI credentials (I'll send separately)
4. Run start_app.sh (Mac/Linux) or start_app.bat (Windows)
5. Browser opens automatically to http://localhost:8501

Full instructions are in the README.txt file included in the package.

Need help? Check the Troubleshooting section in README.txt or contact [support email].
```

### Step 3: Send Azure OpenAI Credentials Separately

**IMPORTANT**: Send credentials separately (not in the same email as the package):

```
Subject: AssistedDiscovery - Configuration Credentials

Edit the file backend/.env and update these values:

AZURE_OPENAI_ENDPOINT=https://[your-resource].openai.azure.com/
AZURE_OPENAI_API_KEY=[your-api-key]
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-15-preview

Keep these credentials secure and do not share them.
```

### Step 4: User Support

Common user questions:

**Q: "Python not found"**
- Install Python from python.org
- On Windows, check "Add Python to PATH" during installation
- Restart computer after installation

**Q: "Setup fails at installing dependencies"**
- Check internet connection
- Run: `python -m pip install --upgrade pip`
- Try setup again

**Q: "Backend won't start"**
- Verify Azure OpenAI credentials in backend/.env
- Check no other service is using port 8000
- Look for error messages in the backend console window

**Q: "Can't access the UI"**
- Verify both backend and frontend started successfully
- Check http://localhost:8000/health shows "healthy"
- Try http://localhost:8501 manually in browser
- Check firewall isn't blocking ports 8000 or 8501

---

## Troubleshooting

### Build Script Fails

**Mac/Linux**:
```bash
# Make sure script is executable
chmod +x build_portable.sh

# Check you're in the correct directory
pwd  # Should show: .../AD_revamp/ad

# Verify required directories exist
ls -la backend/app
ls -la frontend/streamlit_ui
```

**Windows**:
```cmd
# Verify required directories exist
dir backend\app
dir frontend\streamlit_ui

# Run PowerShell as Administrator if zip creation fails
```

### Missing Dependencies in Package

If users report missing Python packages:

1. **Check requirements files**:
   ```bash
   cat backend/requirements.txt
   cat frontend/requirements.txt
   ```

2. **Add missing packages**:
   - Edit the appropriate requirements.txt
   - Rebuild the package

3. **Verify in test installation**:
   ```bash
   ./setup.sh
   # Check for any installation errors
   ```

### Large Package Size

If the ZIP file is too large (>100MB):

1. **Check what's being copied**:
   ```bash
   du -sh portable_dist/*
   ```

2. **Exclude unnecessary files**:
   - Edit build script to exclude `__pycache__`, `.pyc` files
   - Exclude `.git` directories if accidentally included
   - Exclude test files and sample data

3. **Example exclusions in build script**:
   ```bash
   # Add before copying
   find backend/app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
   find frontend/streamlit_ui -name "*.pyc" -delete 2>/dev/null || true
   ```

### Platform-Specific Issues

**Mac Apple Silicon (M1/M2/M3)**:
- Some Python packages may need Rosetta 2
- Install Rosetta: `softwareupdate --install-rosetta`

**Windows Corporate Environment**:
- May need administrator rights for installation
- Firewall might block ports 8000/8501
- Antivirus might flag Python scripts

**Linux**:
- Different distributions may need different Python package names
- Use `python3` instead of `python` on most systems

---

## Advanced: Customizing the Build

### Changing Default Ports

Edit `start_app.sh` or `start_app.bat`:

```bash
# Change backend port (default 8000)
uvicorn app.main:app --host 0.0.0.0 --port 9000

# Change frontend port (default 8501)
streamlit run AssistedDiscovery.py --server.port 9501
```

### Adding Environment-Specific Configurations

Create different `.env.template` files for different environments:

```bash
# In build script, before copying .env
if [ "$BUILD_ENV" = "production" ]; then
    cp backend/.env.production portable_dist/backend/.env.template
elif [ "$BUILD_ENV" = "staging" ]; then
    cp backend/.env.staging portable_dist/backend/.env.template
fi
```

### Including Sample Data

Add to build script:

```bash
# Create samples directory
mkdir -p portable_dist/samples

# Copy sample XML files
cp samples/*.xml portable_dist/samples/
```

---

## Checklist for Release

Before sending to users:

- [ ] Build package on target platform
- [ ] Test complete setup on clean machine/VM
- [ ] Verify all features work (Node Manager, Discovery, Pattern Manager, Identify)
- [ ] Test with sample XML files
- [ ] Check README.txt is clear and complete
- [ ] Verify requirements.txt files are complete
- [ ] Test both setup and start scripts
- [ ] Confirm Azure OpenAI credentials work
- [ ] Document any platform-specific issues
- [ ] Prepare user support documentation
- [ ] Create rollback plan if needed

---

## Version History

Track your releases:

| Version | Date | Platform | Notes |
|---------|------|----------|-------|
| 1.0.0 | 2024-10-09 | Mac/Win | Initial release |
| | | | |

---

## Support

For issues with packaging or distribution:
- Check this guide first
- Review logs in backend and frontend console windows
- Test on a clean installation
- Document exact error messages

For end-user support:
- Direct them to README.txt first
- Verify their Python version
- Check their Azure OpenAI credentials
- Confirm ports 8000/8501 are available
