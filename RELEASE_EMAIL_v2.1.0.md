# AssistedDiscovery v2.1.0 Release Announcement

---

**Subject:** AssistedDiscovery v2.1.0 Now Available - File Sharing & Windows Fixes

---

Hi AssistedDiscovery Users,

We're pleased to announce **AssistedDiscovery v2.1.0** is now available with convenient new features and important Windows fixes!

## 🎯 What's New in v2.1.0

### ✨ Smart File Sharing Feature

**Save time with automatic file reuse across pages!**

When you upload an XML file in the Node Manager, it's now automatically available in the Pattern Extractor—no need to upload twice!

**Quick Example:**
1. Upload your XML file in **Node Manager** to configure nodes
2. Navigate to **Pattern Extractor**
3. See the notification: *"💡 File from Node Manager: yourfile.xml"*
4. Click **"Use This File"** and you're ready to go!

This simple enhancement makes your workflow faster and more convenient.

---

### 🪟 Critical Windows Fixes

If you're using Windows, this update includes **important fixes** for the portable distribution:

#### 1. PowerShell Detection ⚠️
- **Issue Fixed:** Running `setup.bat` in PowerShell caused startup failures
- **Solution:** Automatic detection now prevents this with clear instructions
- **Action Required:** Please use **Command Prompt (cmd.exe)** for setup, not PowerShell

**How to run setup correctly:**
```
1. Press Win+R
2. Type: cmd
3. Press Enter
4. Navigate to AssistedDiscovery folder
5. Run: setup.bat
```

#### 2. Better Error Messages
- Console windows now stay open when errors occur
- You can see the full error message for easier troubleshooting
- Helpful for diagnosing configuration issues

---

## 📥 Download v2.1.0

**Download Link:** [Your distribution link here]

**File Names:**
- Windows: `AssistedDiscovery-Windows.zip`
- macOS: `AssistedDiscovery-Mac.zip`
- Linux: `AssistedDiscovery-Linux.zip`

---

## 🚀 Installation

### New Users
1. Download and extract the ZIP file
2. Run `setup.bat` (Windows) or `./setup.sh` (Mac/Linux) **in Command Prompt**
3. Run `start_app.bat` or `./start_app.sh` to launch
4. Configure your LLM credentials in the **Config** page
5. Start analyzing your NDC XML files!

### Existing Users
Simply download and extract the new version. Your workspaces and patterns are automatically preserved—no migration needed!

---

## ⚠️ Important Note for Windows Users

**Always use Command Prompt (cmd.exe) for setup, not PowerShell.**

If you've already set up using PowerShell and see errors:
1. Delete the `backend_env` and `frontend_env` folders
2. Run `setup.bat` again in Command Prompt
3. Everything will work correctly

---

## 📚 Resources

- **Full Release Notes:** See `RELEASE_NOTES_v2.1.0.md` in the distribution
- **User Guide:** `USER_GUIDE.md` for detailed workflows
- **Quick Start:** `README.md` for getting started
- **Changelog:** `CHANGELOG.md` for technical details

---

## 💡 Tips

### Using the New File Sharing Feature
1. Upload XML in Node Manager → Configure nodes → Save
2. Switch to Pattern Extractor → Click "Use This File"
3. Start extraction—no re-upload needed!

### Windows Setup Best Practices
- Always use Command Prompt for `setup.bat`
- Keep console windows open to see any errors
- Check logs if you encounter issues (location shown in error messages)

---

## 🙏 Thank You

Thank you for using AssistedDiscovery and for your valuable feedback! Your input helps us make the tool better with each release.

If you encounter any issues or have suggestions, please don't hesitate to reach out.

---

**Happy Pattern Discovering!**

The AssistedDiscovery Team

---

**Version:** 2.1.0
**Release Date:** October 27, 2025
**Platform:** Windows, macOS, Linux
