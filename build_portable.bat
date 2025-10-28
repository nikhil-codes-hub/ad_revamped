@echo off
REM Create Portable Distribution for AssistedDiscovery Revamp
echo 🚀 Creating Portable AssistedDiscovery Application
echo Platform  Windows

REM Clean previous builds
echo 🧹 Cleaning previous builds...
if exist portable_dist rmdir /s /q portable_dist

REM Create distribution directory
echo 📁 Creating distribution structure...
mkdir portable_dist
mkdir portable_dist\backend
mkdir portable_dist\frontend
mkdir portable_dist\data
mkdir portable_dist\data\workspaces

REM Copy backend files
echo 📋 Copying backend files...
xcopy /E /I backend\app portable_dist\backend\app
copy backend\requirements.txt portable_dist\backend\
if exist backend\alembic.ini copy backend\alembic.ini portable_dist\backend\
if exist backend\alembic xcopy /E /I backend\alembic portable_dist\backend\alembic

REM Copy frontend files
echo 📋 Copying frontend files...
xcopy /E /I frontend\streamlit_ui portable_dist\frontend\streamlit_ui
copy frontend\requirements.txt portable_dist\frontend\

REM Copy .env template if exists
if exist .env.example (
    copy .env.example portable_dist\.env.template
) else if exist .env (
    copy .env portable_dist\.env.template
)

REM Create setup script
echo 📝 Creating setup script...
echo @echo off > portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo REM Check if running in PowerShell ^(causes bin/ instead of Scripts/^) >> portable_dist\setup.bat
echo if defined PSModulePath ^( >> portable_dist\setup.bat
echo     echo ❌ ERROR  Do not run this in PowerShell! >> portable_dist\setup.bat
echo     echo. >> portable_dist\setup.bat
echo     echo PowerShell creates bin/ folder instead of Scripts/, which breaks this script. >> portable_dist\setup.bat
echo     echo. >> portable_dist\setup.bat
echo     echo Please run setup.bat in Command Prompt ^(cmd.exe^) instead. >> portable_dist\setup.bat
echo     echo    1. Press Win+R >> portable_dist\setup.bat
echo     echo    2. Type  cmd >> portable_dist\setup.bat
echo     echo    3. Press Enter >> portable_dist\setup.bat
echo     echo    4. Navigate to this folder and run  setup.bat >> portable_dist\setup.bat
echo     echo. >> portable_dist\setup.bat
echo     pause >> portable_dist\setup.bat
echo     exit /b 1 >> portable_dist\setup.bat
echo ^) >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo echo 🔧 Setting up AssistedDiscovery... >> portable_dist\setup.bat
echo echo This will create isolated Python environments for backend and frontend >> portable_dist\setup.bat
echo echo No pollution of your system Python! >> portable_dist\setup.bat
echo echo. >> portable_dist\setup.bat
echo pause >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo REM Check if Python is installed >> portable_dist\setup.bat
echo python --version ^>nul 2^>^&1 >> portable_dist\setup.bat
echo if errorlevel 1 ^( >> portable_dist\setup.bat
echo     echo ❌ Python is not installed. Please install Python 3.12 first. >> portable_dist\setup.bat
echo     echo Download from  https //www.python.org/downloads/ >> portable_dist\setup.bat
echo     pause >> portable_dist\setup.bat
echo     exit /b 1 >> portable_dist\setup.bat
echo ^) >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo echo Checking Python version... >> portable_dist\setup.bat
echo python --version >> portable_dist\setup.bat
echo echo. >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo REM Create backend virtual environment >> portable_dist\setup.bat
echo echo 📦 Creating backend virtual environment... >> portable_dist\setup.bat
echo python -m venv backend_env >> portable_dist\setup.bat
echo if errorlevel 1 ^( >> portable_dist\setup.bat
echo     echo ❌ Failed to create backend virtual environment >> portable_dist\setup.bat
echo     pause >> portable_dist\setup.bat
echo     exit /b 1 >> portable_dist\setup.bat
echo ^) >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo echo Installing backend dependencies... >> portable_dist\setup.bat
echo backend_env\Scripts\python -m pip install --upgrade pip >> portable_dist\setup.bat
echo backend_env\Scripts\pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r backend\requirements.txt >> portable_dist\setup.bat
echo if errorlevel 1 ^( >> portable_dist\setup.bat
echo     echo ❌ Failed to install backend dependencies >> portable_dist\setup.bat
echo     pause >> portable_dist\setup.bat
echo     exit /b 1 >> portable_dist\setup.bat
echo ^) >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo REM Create frontend virtual environment >> portable_dist\setup.bat
echo echo 📦 Creating frontend virtual environment... >> portable_dist\setup.bat
echo python -m venv frontend_env >> portable_dist\setup.bat
echo if errorlevel 1 ^( >> portable_dist\setup.bat
echo     echo ❌ Failed to create frontend virtual environment >> portable_dist\setup.bat
echo     pause >> portable_dist\setup.bat
echo     exit /b 1 >> portable_dist\setup.bat
echo ^) >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo echo Installing frontend dependencies... >> portable_dist\setup.bat
echo frontend_env\Scripts\python -m pip install --upgrade pip >> portable_dist\setup.bat
echo frontend_env\Scripts\pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r frontend\requirements.txt >> portable_dist\setup.bat
echo if errorlevel 1 ^( >> portable_dist\setup.bat
echo     echo ❌ Failed to install frontend dependencies >> portable_dist\setup.bat
echo     pause >> portable_dist\setup.bat
echo     exit /b 1 >> portable_dist\setup.bat
echo ^) >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo REM Create default .env if not exists >> portable_dist\setup.bat
echo if not exist .env ^( >> portable_dist\setup.bat
echo     if exist .env.template ^( >> portable_dist\setup.bat
echo         copy .env.template .env >> portable_dist\setup.bat
echo         echo Created .env from template >> portable_dist\setup.bat
echo         echo Please update .env with your LLM credentials >> portable_dist\setup.bat
echo     ^) else ^( >> portable_dist\setup.bat
echo         ^(echo # LLM Provider Configuration^) ^> .env >> portable_dist\setup.bat
echo         ^(echo # Supported providers  azure, gemini^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo LLM_PROVIDER=azure^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo.^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo # Azure OpenAI Configuration^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo AZURE_OPENAI_ENDPOINT=your-endpoint-here^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo AZURE_OPENAI_KEY=your-api-key-here^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo AZURE_API_VERSION=2025-01-01-preview^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo MODEL_DEPLOYMENT_NAME=gpt-4o^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo.^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo # Google Gemini Configuration^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo GEMINI_API_KEY=your-gemini-api-key-here^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo GEMINI_MODEL=gemini-1.5-pro^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo.^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo # LLM Common Settings^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo MAX_TOKENS_PER_REQUEST=4000^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo LLM_TEMPERATURE=0.1^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo LLM_TOP_P=0.0^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo.^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo # Application Settings^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo LOG_LEVEL=INFO^) ^>^> .env >> portable_dist\setup.bat
echo         ^(echo WORKSPACE_DB_DIR=./data/workspaces^) ^>^> .env >> portable_dist\setup.bat
echo         echo Created .env template >> portable_dist\setup.bat
echo         echo Please update .env with your LLM credentials >> portable_dist\setup.bat
echo     ^) >> portable_dist\setup.bat
echo ^) >> portable_dist\setup.bat
echo. >> portable_dist\setup.bat
echo echo. >> portable_dist\setup.bat
echo echo ✅ Setup complete! Isolated environments created. >> portable_dist\setup.bat
echo echo. >> portable_dist\setup.bat
echo echo 📝 Next Steps  >> portable_dist\setup.bat
echo echo    1. Update .env with your Azure OpenAI credentials >> portable_dist\setup.bat
echo echo    2. Run start_app.bat to start the application >> portable_dist\setup.bat
echo pause >> portable_dist\setup.bat

REM Create launcher script
echo 📝 Creating launcher script...
echo @echo off > portable_dist\start_app.bat
echo echo 🧞 Starting AssistedDiscovery... >> portable_dist\start_app.bat
echo echo. >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo REM Check if setup was run >> portable_dist\start_app.bat
echo if not exist backend_env ^( >> portable_dist\start_app.bat
echo     echo ❌ Virtual environments not found. Please run setup.bat first. >> portable_dist\start_app.bat
echo     pause >> portable_dist\start_app.bat
echo     exit /b 1 >> portable_dist\start_app.bat
echo ^) >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo if not exist frontend_env ^( >> portable_dist\start_app.bat
echo     echo ❌ Virtual environments not found. Please run setup.bat first. >> portable_dist\start_app.bat
echo     pause >> portable_dist\start_app.bat
echo     exit /b 1 >> portable_dist\start_app.bat
echo ^) >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo REM Check if .env exists >> portable_dist\start_app.bat
echo if not exist .env ^( >> portable_dist\start_app.bat
echo     echo ❌ .env not found. Please run setup.bat first. >> portable_dist\start_app.bat
echo     pause >> portable_dist\start_app.bat
echo     exit /b 1 >> portable_dist\start_app.bat
echo ^) >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo REM Start backend >> portable_dist\start_app.bat
echo echo 🔧 Starting backend API server... >> portable_dist\start_app.bat
echo cd /d backend >> portable_dist\start_app.bat
echo set PYTHONPATH=%%cd%% >> portable_dist\start_app.bat
echo start "AssistedDiscovery-Backend" cmd /k "..\backend_env\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000" >> portable_dist\start_app.bat
echo cd /d .. >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo REM Wait for backend to start >> portable_dist\start_app.bat
echo echo ⏳ Waiting for backend to start... >> portable_dist\start_app.bat
echo timeout /t 5 /nobreak ^>nul >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo REM Start frontend >> portable_dist\start_app.bat
echo echo 🎨 Starting frontend UI... >> portable_dist\start_app.bat
echo cd /d frontend\streamlit_ui >> portable_dist\start_app.bat
echo start "AssistedDiscovery-Frontend" cmd /k "..\..\frontend_env\Scripts\streamlit run AssistedDiscovery.py --server.port 8501 --server.headless true" >> portable_dist\start_app.bat
echo cd /d ..\.. >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo REM Wait for frontend to start >> portable_dist\start_app.bat
echo echo ⏳ Waiting for frontend to start... >> portable_dist\start_app.bat
echo timeout /t 3 /nobreak ^>nul >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo echo. >> portable_dist\start_app.bat
echo echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ >> portable_dist\start_app.bat
echo echo ✅ AssistedDiscovery is running! >> portable_dist\start_app.bat
echo echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ >> portable_dist\start_app.bat
echo echo. >> portable_dist\start_app.bat
echo echo 📍 Frontend UI   http //localhost 8501 >> portable_dist\start_app.bat
echo echo 📍 Backend API   http //localhost 8000 >> portable_dist\start_app.bat
echo echo 📍 API Docs      http //localhost 8000/docs >> portable_dist\start_app.bat
echo echo. >> portable_dist\start_app.bat
echo echo 🌐 Opening browser... >> portable_dist\start_app.bat
echo timeout /t 2 /nobreak ^>nul >> portable_dist\start_app.bat
echo start http //localhost 8501 >> portable_dist\start_app.bat
echo. >> portable_dist\start_app.bat
echo echo. >> portable_dist\start_app.bat
echo echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ >> portable_dist\start_app.bat
echo echo To stop the application, close both console windows >> portable_dist\start_app.bat
echo echo or run stop_app.bat >> portable_dist\start_app.bat
echo echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ >> portable_dist\start_app.bat
echo echo. >> portable_dist\start_app.bat
echo pause >> portable_dist\start_app.bat

REM Create stop script
echo 📝 Creating stop script...
echo @echo off > portable_dist\stop_app.bat
echo echo 🛑 Stopping AssistedDiscovery... >> portable_dist\stop_app.bat
echo. >> portable_dist\stop_app.bat
echo REM Kill backend >> portable_dist\stop_app.bat
echo taskkill /FI "WINDOWTITLE eq AssistedDiscovery-Backend*" /F ^>nul 2^>^&1 >> portable_dist\stop_app.bat
echo if errorlevel 1 ^( >> portable_dist\stop_app.bat
echo     echo No backend process found >> portable_dist\stop_app.bat
echo ^) else ^( >> portable_dist\stop_app.bat
echo     echo ✅ Backend stopped >> portable_dist\stop_app.bat
echo ^) >> portable_dist\stop_app.bat
echo. >> portable_dist\stop_app.bat
echo REM Kill frontend >> portable_dist\stop_app.bat
echo taskkill /FI "WINDOWTITLE eq AssistedDiscovery-Frontend*" /F ^>nul 2^>^&1 >> portable_dist\stop_app.bat
echo if errorlevel 1 ^( >> portable_dist\stop_app.bat
echo     echo No frontend process found >> portable_dist\stop_app.bat
echo ^) else ^( >> portable_dist\stop_app.bat
echo     echo ✅ Frontend stopped >> portable_dist\stop_app.bat
echo ^) >> portable_dist\stop_app.bat
echo. >> portable_dist\stop_app.bat
echo echo ✅ All services stopped >> portable_dist\stop_app.bat
echo pause >> portable_dist\stop_app.bat

REM Create README
echo 📝 Creating README...
echo # AssistedDiscovery Application > portable_dist\README.txt
echo. >> portable_dist\README.txt
echo AssistedDiscovery Revamp - A comprehensive tool for analyzing and managing NDC >> portable_dist\README.txt
echo (New Distribution Capability) message structures across different airline implementations. >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## Quick Setup >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo 1. Ensure Python 3.9+ is installed >> portable_dist\README.txt
echo 2. Run setup.bat to install dependencies (one time only) >> portable_dist\README.txt
echo 3. Run start_app.bat to start the application >> portable_dist\README.txt
echo 4. Configure LLM credentials via the Config page in the UI >> portable_dist\README.txt
echo 5. Restart the app for changes to take effect >> portable_dist\README.txt
echo 6. Start using AssistedDiscovery! >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## System Requirements >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo - Python 3.9 or later >> portable_dist\README.txt
echo - Windows 10 or later >> portable_dist\README.txt
echo - Internet connection for initial setup >> portable_dist\README.txt
echo - 8GB RAM minimum (recommended) >> portable_dist\README.txt
echo - Browser  Chrome, Firefox, Safari, or Edge >> portable_dist\README.txt
echo - Disk space  2GB for dependencies >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## Features >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo - Node Manager - Configure extraction rules and expected references >> portable_dist\README.txt
echo - Discovery - Analyze XML files to extract node structures and patterns >> portable_dist\README.txt
echo - Pattern Manager - Review patterns, explore library, manage exports >> portable_dist\README.txt
echo - Identify - Match new XML files against known patterns >> portable_dist\README.txt
echo - Workspace Support - Isolate patterns by workspace >> portable_dist\README.txt
echo - Relationship Discovery - Automatic relationship detection between nodes >> portable_dist\README.txt
echo - AI-Powered Analysis - Azure OpenAI integration for intelligent extraction >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## Configuration >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo **No manual .env editing required!** >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo Configure LLM credentials via the web UI  >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo 1. Start the application (start_app.bat) >> portable_dist\README.txt
echo 2. Open http //localhost 8501 in your browser >> portable_dist\README.txt
echo 3. Click Config in the sidebar >> portable_dist\README.txt
echo 4. Select your LLM provider (Azure OpenAI or Google Gemini) >> portable_dist\README.txt
echo 5. Enter your credentials >> portable_dist\README.txt
echo 6. Click Save Configuration >> portable_dist\README.txt
echo 7. Click Test Connection to verify >> portable_dist\README.txt
echo 8. Restart the app (close windows, run start_app.bat again) >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## Scripts >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo - setup.bat - One-time dependency installer (creates virtual environments) >> portable_dist\README.txt
echo - start_app.bat - Start both backend and frontend services >> portable_dist\README.txt
echo - stop_app.bat - Stop all running services >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## Ports >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo - Frontend (Streamlit)  8501 >> portable_dist\README.txt
echo - Backend (FastAPI)  8000 >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## Troubleshooting >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ### Python Not Found >> portable_dist\README.txt
echo - Install Python 3.9+ from python.org >> portable_dist\README.txt
echo - During installation, check "Add Python to PATH" >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ### Dependencies Install Failed >> portable_dist\README.txt
echo - Ensure internet connection is active >> portable_dist\README.txt
echo - Try  python -m pip install --upgrade pip >> portable_dist\README.txt
echo - Then run setup.bat again >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ### Backend Fails to Start >> portable_dist\README.txt
echo - Verify no other service is using port 8000 >> portable_dist\README.txt
echo - Check backend window for specific errors >> portable_dist\README.txt
echo - Backend will start even without LLM credentials configured >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ### Port Already in Use >> portable_dist\README.txt
echo - Run stop_app.bat to stop existing services >> portable_dist\README.txt
echo - Or close all AssistedDiscovery console windows >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo ## File Structure >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo backend\ >> portable_dist\README.txt
echo   app\           - Backend application code >> portable_dist\README.txt
echo   requirements.txt - Backend Python dependencies >> portable_dist\README.txt
echo   .env           - Configuration (create from .env.template) >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo frontend\ >> portable_dist\README.txt
echo   streamlit_ui\  - Frontend UI code >> portable_dist\README.txt
echo   requirements.txt - Frontend Python dependencies >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo data\ >> portable_dist\README.txt
echo   workspaces\    - SQLite databases for each workspace >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo backend_env\     - Backend virtual environment (created by setup.bat) >> portable_dist\README.txt
echo frontend_env\    - Frontend virtual environment (created by setup.bat) >> portable_dist\README.txt
echo. >> portable_dist\README.txt
echo Build Date  Created with build_portable.bat >> portable_dist\README.txt

REM Create .gitignore
echo backend_env/ > portable_dist\.gitignore
echo frontend_env/ >> portable_dist\.gitignore
echo backend/.env >> portable_dist\.gitignore
echo data/workspaces/*.db >> portable_dist\.gitignore
echo __pycache__/ >> portable_dist\.gitignore
echo *.pyc >> portable_dist\.gitignore

REM Create zip archive
echo 🗜️ Creating distribution archive...
powershell -command "Compress-Archive -Path 'portable_dist\*' -DestinationPath 'AssistedDiscovery-Windows.zip' -Force"

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo 🎉 Portable distribution created successfully!
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo 📦 Files created 
echo   - portable_dist\ (distribution folder)
echo   - AssistedDiscovery-Windows.zip (archive)
echo.
echo 📋 User Instructions 
echo   1. Extract AssistedDiscovery-Windows.zip
echo   2. Run setup.bat (one time setup)
echo   3. Run start_app.bat to start application
echo   4. Configure LLM via Config page in the UI
echo   5. Restart app for changes to take effect
echo.
echo ✅ Ready for distribution!
echo.
pause
