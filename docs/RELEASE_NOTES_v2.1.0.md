# AssistedDiscovery v2.1.0 - Release Notes

**Release Date:** October 27, 2025
**Version:** 2.1.0

---

## 🎉 What's New

We're excited to announce AssistedDiscovery v2.1.0 with important improvements to the Windows portable distribution and a convenient new file-sharing feature!

---

## ✨ New Features

### 📁 Smart File Sharing Between Pages

**Save time by reusing uploaded files across workflows!**

When you upload an XML file in the **Node Manager**, it's now automatically available in the **Pattern Extractor** workflow—no need to upload twice!

**How it works:**
1. Upload your XML file in **🗄️ Node Manager** to analyze node structure
2. Navigate to **🔬 Pattern Extractor**
3. See a notification: *"💡 File from Node Manager: `yourfile.xml`"*
4. Click **"✅ Use This File"** to instantly reuse it
5. Or click **"❌ Dismiss"** if you want to upload a different file

**Benefits:**
- ⚡ **Faster workflow** - No duplicate uploads
- 🎯 **Consistency** - Same file analyzed and extracted
- 💡 **Convenient** - Seamless page-to-page experience

---

## 🐛 Bug Fixes & Improvements

### 🪟 Windows Portable Distribution Fixes

We've resolved several critical issues affecting Windows users running the portable distribution:

#### 1. **PowerShell Detection & Prevention**
   - **Problem:** Running `setup.bat` in PowerShell created a `bin/` folder instead of `Scripts/`, breaking the startup process
   - **Solution:** Added automatic PowerShell detection with clear error message and instructions
   - **Action Required:** Always run `setup.bat` in **Command Prompt (cmd.exe)**, not PowerShell

   **How to run correctly:**
   ```
   1. Press Win+R
   2. Type: cmd
   3. Press Enter
   4. Navigate to the AssistedDiscovery folder
   5. Run: setup.bat
   ```

#### 2. **Better Error Visibility**
   - **Problem:** Backend/frontend console windows closed immediately on errors, making troubleshooting difficult
   - **Solution:** Console windows now stay open when errors occur, showing complete error messages
   - **Benefit:** You can now see what went wrong and troubleshoot configuration issues easily

#### 3. **Consistent File Naming**
   - **Changed:** Distribution file renamed from `AssistedDiscovery-Portable-Windows.zip` to `AssistedDiscovery-Windows.zip`
   - **Benefit:** Cleaner, more consistent naming across all platforms (Mac, Windows, Linux)

### 🎨 UI Polish

- **Button Label Fix:** Changed "🚀 Start Discovery" to "🚀 Start Extraction" in Pattern Extractor page for clarity
- **Consistent Terminology:** Pattern Extractor page now uses appropriate action labels throughout

---

## 📋 Important Notes for Windows Users

### ⚠️ Must Use Command Prompt, Not PowerShell

If you're on Windows and setting up the portable distribution:

**✅ DO:** Use Command Prompt (cmd.exe)
**❌ DON'T:** Use PowerShell

**Why?** Python's virtual environment behaves differently in PowerShell, creating incompatible folder structures.

**If you see errors about missing `Scripts` folder:**
1. Delete the `backend_env` and `frontend_env` folders
2. Close PowerShell
3. Open Command Prompt (Win+R → type `cmd` → Enter)
4. Run `setup.bat` again

---

## 🚀 Getting Started

### For New Users

1. **Download:** Get `AssistedDiscovery-Windows.zip` (or Mac/Linux version)
2. **Extract:** Unzip to your desired location
3. **Setup (one-time):** Run `setup.bat` (Windows) or `./setup.sh` (Mac/Linux) in **Command Prompt**
4. **Start:** Run `start_app.bat` (Windows) or `./start_app.sh` (Mac/Linux)
5. **Configure:** Use the **⚙️ Config** page to set up your Azure OpenAI or Gemini credentials
6. **Enjoy:** Start discovering patterns in your NDC XML files!

### For Existing Users

Simply download the new version and extract over your existing installation. Your workspaces, patterns, and configurations are preserved.

**Note:** If you already have virtual environments created, you can skip the setup step and just run `start_app.bat/sh`.

---

## 📚 Workflow Guide

### Using the New File Sharing Feature

**Scenario:** You want to configure nodes and then extract patterns from the same file.

1. Go to **🗄️ Node Manager**
2. Upload your XML file and analyze it
3. Configure which nodes to extract
4. **Save** your configuration
5. Navigate to **🔬 Pattern Extractor**
6. You'll see: *"💡 File from Node Manager: `yourfile.xml`"*
7. Click **"✅ Use This File"**
8. Click **"🚀 Start Extraction"** to process

No re-uploading needed! The same file is used seamlessly.

---

## 🔧 System Requirements

- **Python:** 3.9 or later
- **RAM:** 8GB minimum (recommended)
- **Disk Space:** 2GB for dependencies
- **Browser:** Chrome, Firefox, Safari, or Edge
- **Windows:** Windows 10 or later
- **macOS:** macOS 10.15 (Catalina) or later
- **Linux:** Modern distribution with Python 3.9+

---

## 📞 Support

### Having Issues?

1. **Check the logs:**
   - **Windows:** `%LOCALAPPDATA%\AssistedDiscovery\Logs\assisted_discovery.log`
   - **macOS:** `~/Library/Logs/AssistedDiscovery/assisted_discovery.log`
   - **Linux:** `~/.local/share/AssistedDiscovery/logs/assisted_discovery.log`

2. **Common Problems:**
   - **Backend won't start:** Check your `.env` file has correct LLM credentials
   - **Port already in use:** Run `stop_app.bat/sh` to kill existing processes
   - **PowerShell errors (Windows):** Use Command Prompt instead

3. **Documentation:**
   - See `USER_GUIDE.md` for detailed workflows
   - See `README.md` for quick start
   - See `TROUBLESHOOTING.md` for common issues

### Reporting Bugs

If you encounter a bug, please provide:
- Error message from the logs
- Steps to reproduce
- Your operating system and Python version
- The XML file (if applicable and non-sensitive)

---

## 🙏 Acknowledgments

Thank you to all our users who provided valuable feedback on v2.0.0! Your insights helped shape this release.

Special thanks to:
- Users who reported the PowerShell/Command Prompt issue
- Early testers who requested cross-page file sharing
- The development team for rapid bug fixes

---

## 📅 What's Next?

We're working on:
- Enhanced pattern visualization
- Batch processing for multiple XML files
- Advanced filtering and search in Pattern Manager
- Export improvements with custom templates

Stay tuned for v2.2.0!

---

## 📖 Complete Changelog

For a detailed list of all changes, see [CHANGELOG.md](CHANGELOG.md).

---

**Enjoy AssistedDiscovery v2.1.0!** 🎊

Questions? Check out our documentation or reach out to your support contact.
