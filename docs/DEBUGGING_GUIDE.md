# 🐛 AssistedDiscovery Debugging Guide for WindSurf IDE

## 🚀 Quick Start Debug Configurations

Your project now includes comprehensive debugging configurations for both Streamlit frontend and FastAPI backend.

### Available Debug Configurations:

#### 1. **AD 🎯 Debug Streamlit Frontend**
- Debugs the AssistedDiscovery Streamlit UI application
- Runs on port 8501
- Full debugging with breakpoints enabled
- Environment: Development with CORS enabled

#### 2. **AD 🚀 Debug FastAPI Backend**
- Debugs the AssistedDiscovery FastAPI application directly
- Simple Python debugging without Uvicorn
- Good for debugging startup issues

#### 3. **AD 🔥 Debug FastAPI with Uvicorn**
- Debugs AssistedDiscovery FastAPI with hot reload enabled
- Production-like environment
- Automatically reloads on code changes
- Best for API development

#### 4. **AD 🧪 Debug Current Python File**
- Debug any currently open Python file within AssistedDiscovery
- Flexible debugging for individual modules

#### 5. **AD 🧩 Debug XML Parser Service**
- Specifically for debugging the AssistedDiscovery XML parser
- Pre-configured with correct paths

#### 6. **AD 🏃‍♂️ Run Streamlit (No Debug)**
- Run AssistedDiscovery Streamlit without debugging overhead
- Faster startup for quick testing

#### 7. **AD 🚀🎯 Debug Full Stack (Compound)**
- **Launches both AssistedDiscovery FastAPI backend AND Streamlit frontend simultaneously**
- Best option for full-stack debugging
- Allows debugging both services at once
- **RECOMMENDED for debugging UI-API issues**

## 🔧 How to Use the Debugging Configurations

### Method 1: Using the Debug Panel
1. Open WindSurf IDE
2. Go to the **Debug and Run** panel (Ctrl+Shift+D / Cmd+Shift+D)
3. Select your desired configuration from the dropdown
4. Click the green play button ▶️

### Method 2: Using the Command Palette
1. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
2. Type "Debug: Select and Start Debugging"
3. Choose your configuration

### Method 3: Using F5 Keyboard Shortcut
1. Open any Python file
2. Press `F5` to start debugging with the default configuration

## 🎯 Recommended Debugging Workflow

### For Frontend Development:
1. Start with **"AD 🎯 Debug Streamlit Frontend"**
2. Set breakpoints in your Streamlit code
3. Navigate through the UI to trigger breakpoints

### For Backend API Development:
1. Use **"AD 🔥 Debug FastAPI with Uvicorn"** for hot reloading
2. Set breakpoints in your API endpoints
3. Test API calls using curl, Postman, or the frontend

### For Full-Stack Development:
1. Use **"AD 🚀🎯 Debug Full Stack (Compound)"** - **RECOMMENDED**
2. This launches both services simultaneously
3. Debug both frontend and backend interactions
4. Perfect for troubleshooting UI-API communication issues

## 🛠️ Additional Build Tasks

The project includes several helpful tasks (Ctrl+Shift+P → "Tasks: Run Task"):

- **AD 🚀 Start FastAPI Backend** - Run AssistedDiscovery backend without debugging
- **AD 🎯 Start Streamlit Frontend** - Run AssistedDiscovery frontend without debugging
- **AD 🔥 Start Uvicorn with Hot Reload** - Production-like AssistedDiscovery backend
- **AD 🧪 Run Tests** - Execute AssistedDiscovery test suite
- **AD 🔍 Install Dependencies (Backend)** - Install Python packages for AssistedDiscovery
- **AD 🗄️ Reset Database** - Reset the AssistedDiscovery database to clean state

## 🐛 Common Debugging Scenarios

### Debugging API Endpoints:
```python
# Set breakpoints in your API routes
@router.post("/")
async def create_run():
    breakpoint()  # Or set IDE breakpoint here
    # Your code here
```

### Debugging Streamlit Components:
```python
# Set breakpoints in your Streamlit app
def main():
    st.title("AssistedDiscovery")
    breakpoint()  # Or set IDE breakpoint here
    # Your UI code here
```

### Debugging XML Processing:
1. Use **"🧩 Debug XML Parser Service"** configuration
2. Set breakpoints in `xml_parser.py`
3. Debug with sample XML files

## 🔍 Debugging Tips

### Breakpoint Best Practices:
- Set breakpoints on meaningful lines (not imports/comments)
- Use conditional breakpoints for specific scenarios
- Inspect variables in the Debug Console

### Environment Variables:
All configurations include proper `PYTHONPATH` settings:
- Backend: `${workspaceFolder}/backend`
- Frontend: `${workspaceFolder}`
- Debug mode enabled with `DEBUG=true`

### Hot Reloading:
- FastAPI configurations include `--reload` for automatic restarts
- Streamlit automatically watches for file changes
- No need to restart debugger for most code changes

## 🚨 Troubleshooting

### Port Conflicts:
- Backend runs on **port 8000**
- Frontend runs on **port 8501**
- Check if ports are already in use: `lsof -i :8000` or `lsof -i :8501`

### Python Path Issues:
- All configurations set proper `PYTHONPATH`
- Virtual environment should be: `./assisted_discovery_env/bin/python`
- Check interpreter in bottom status bar

### Import Errors:
- Ensure virtual environment is activated
- Check that `PYTHONPATH` includes backend directory
- Verify all dependencies are installed

### Database Connection Issues:
- Use **"🗄️ Reset Database"** task to reinitialize
- Check database configuration in `app/core/config.py`

## 🎉 Quick Debug Commands

| Action | Shortcut | Description |
|--------|----------|-------------|
| Start Debugging | `F5` | Start with default configuration |
| Step Over | `F10` | Execute next line |
| Step Into | `F11` | Step into function calls |
| Step Out | `Shift+F11` | Step out of current function |
| Continue | `F5` | Continue execution |
| Stop Debugging | `Shift+F5` | Stop current debug session |
| Restart | `Ctrl+Shift+F5` | Restart debug session |

---

## 🎯 **RECOMMENDED: Start with "AD 🚀🎯 Debug Full Stack (Compound)"**

This compound configuration is your best bet for debugging the complete AssistedDiscovery application. It launches both the FastAPI backend and Streamlit frontend simultaneously, allowing you to:

- Debug API calls from the UI
- See real-time interaction between frontend and backend
- Set breakpoints in both services
- Troubleshoot the exact issue you're experiencing with NULL values
- Perfect for debugging the AssistedDiscovery XML processing and API responses

All configurations are now prefixed with "AD" to clearly identify them as AssistedDiscovery-specific configurations, making it easier to distinguish them from other project configurations you may have.

Happy Debugging! 🐛✨