# AssistedDiscovery v2.1.1 - Release Notes

**Release Date**: October 28, 2025
**Type**: Feature Enhancement & Bug Fixes

---

## ✨ What's New

### 🎯 UI Terminology Updates (User-Friendly Naming)
- **"Discovery" → "Pattern Extractor"** - Extract patterns from existing airline XML
- **"Identify" → "Discovery"** - Validate new airline XML against patterns
- Clearer workflow names that better reflect their purpose

### ⚡ Performance Improvements
- **Parallel processing** for pattern extraction and discovery
- **Runtime reduced from ~10 minutes to ~3 minutes** (70% faster)
- Improved responsiveness during large XML processing

### 📊 Missing Patterns Detection
- New **"Missing Patterns" tab** in Discovery workflow
- Shows patterns present in library but not found in current XML
- Helps identify incomplete or evolving airline implementations

### 🔄 File Sharing Enhancement
- **Share XML files between Node Config and Pattern Extractor** pages
- No need to re-upload same file across workflows
- Streamlined user experience

---

## 🐛 Bug Fixes

### Pattern Verification
- ✅ **"Verify Patterns" functionality now working correctly**
- Validates pattern library integrity
- Identifies duplicate or conflicting patterns

### Windows Installation
- ✅ Fixed batch file syntax errors ("instead" keyword issue)
- ✅ Fixed backend startup command (uvicorn syntax)
- ✅ Removed false PowerShell detection warnings
- ✅ Fixed URL formatting in generated scripts

---

## 📦 Installation

### System Requirements
- Windows 10/11
- Python 3.9+ (3.12 recommended)
- 8GB RAM minimum

### Quick Start
1. Extract `AssistedDiscovery-Windows.zip`
2. Run `setup.bat` (one-time setup)
3. Run `start_app.bat`
4. Open `http://localhost:8501`
5. Configure LLM credentials via Config page
6. Restart application

**Important**: Always use Command Prompt (cmd.exe), not PowerShell

---

## 🔄 Upgrade from v2.1.0

1. Stop current application (`stop_app.bat`)
2. Extract v2.1.1 to new directory
3. Copy `.env` file from old installation (if configured)
4. Copy `data/workspaces/` to preserve existing patterns
5. Run `setup.bat` and `start_app.bat`

No database migrations required.

---

## 📊 Performance Comparison

| Metric | v2.1.0 | v2.1.1 | Improvement |
|--------|--------|--------|-------------|
| Pattern Extraction | ~10 min | ~3 min | **70% faster** |
| Parallel Processing | ❌ | ✅ | **New** |
| Missing Patterns Detection | ❌ | ✅ | **New** |
| File Sharing | ❌ | ✅ | **New** |
| Verify Patterns | ⚠️ Broken | ✅ Fixed | **Fixed** |

---

## 📝 Documentation

- **User Guide**: `docs/USER_GUIDE.md`
- **Installation**: `docs/USER_INSTALLATION_GUIDE.md`
- **Demo Guide**: `docs/DEMO_PREPARATION_GUIDE.md`
- **Debugging**: `docs/DEBUGGING_GUIDE.md`

---

## 🔮 Coming Soon (v2.2.0)

- Enhanced pattern matching algorithms
- Additional LLM provider support
- Batch processing for multiple files
- Pattern export/import functionality

---

**Full Changelog**: https://github.com/nikhil-codes-hub/ad_revamped/compare/v2.1.0...v2.1.1
