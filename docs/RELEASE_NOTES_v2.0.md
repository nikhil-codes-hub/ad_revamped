# AssistedDiscovery v2.0 - Release Notes

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

---

## 📦 Installation

Same as V1.0

