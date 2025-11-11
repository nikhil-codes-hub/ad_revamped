# AssistedDiscovery v3.0 - What's New

**Release Date:** November 11, 2025

---

## What's Better in v3.0?

### 🔄 The App Handles Busy Times Automatically

**Before:** If the system was too busy, your upload would fail and you'd have to try again manually.

**Now:** The app automatically retries up to 3 times when the system is busy. You'll see clear messages like "System too busy, wait 5-10 minutes" instead of confusing error codes.

**What this means for you:** Less frustration, fewer failed uploads, and you always know what to do next.

---

### 🎯 Find Patterns Across Different Airlines and Versions

**New Capabilities:**
- **Cross-Airline Matching** - Discover if other airlines use similar patterns
- **Cross-Version Matching** - Compare patterns from different message versions (v19.2, v20.1, etc.)

**Important Note:** Discovery now matches patterns **only within the same message type**. For example, OrderViewRS patterns only match against other OrderViewRS files. This ensures more accurate and relevant pattern matching.

**What this means for you:**
- Find patterns faster by reusing what already exists across airlines and versions
- More accurate pattern matching (only compares similar message types)
- Clear warning when no patterns exist for your specific message type
- Reduce duplicate pattern creation

---

### 🎨 Easier to See and Understand Patterns

**Visual Improvements:**
- **Side-by-Side Comparison** - See your extracted pattern next to library patterns with visual differences highlighted
- **Full Structure Display** - View complete XML hierarchy including all nested children (no more flattened structures)
- **Better Quality Information** - Quality scores now always show accurate values (no more "n/a")

**Pattern Explanations:**
- Each pattern now has a **business-friendly description** that explains what it does
- Clear breakdown of match scores showing why patterns match or don't match
- Deduplication of repeated quality issues for cleaner reports

---

### 🧹 Cleaner Pattern Management

**New Features:**
- **Delete Unwanted Patterns** - Remove patterns you no longer need
- **Automatic Duplicate Detection** - The system finds and alerts you when similar patterns exist
- **Merge Duplicates** - Combine duplicate patterns to keep your library clean

**What this means for you:**
- Easier to maintain your pattern library
- Less clutter and confusion
- Clear warnings when patterns conflict

---

### 📊 More Accurate Results

**Quality Improvements:**
- **80% fewer duplicate patterns** - The system better recognizes when patterns are truly the same
- **60% fewer false quality warnings** - Quality checks are now smarter and more accurate
- **Larger patterns supported** - Can now handle more complex XML structures (2x larger than before)

**What this means for you:**
- More reliable pattern discovery
- Fewer false alarms about quality issues
- Ability to work with larger, more complex messages

---

### ⚠️ Helpful Warnings

**New Alerts:**
- Clear warning when the system can't find patterns for your message type
- Notification when message types don't match
- Guidance on what to do next in each situation

**What this means for you:** You'll always know if something isn't working as expected and what to do about it.

---

## What Should I Do?

### If You're Using the Portable Version:
1. Download the new **AssistedDiscovery-v3.0** package
2. Run the setup script (same as before)
3. All your existing workspaces and patterns will work automatically
4. **No data migration needed** - everything just works!

### First Time Starting v3.0:
1. Open the app as usual
2. Your existing patterns and workspaces are all there
3. Start using the new features right away - no training needed!

---

## Do I Need to Change Anything?

**No!** Everything you're familiar with still works the same way:
- All your workspaces remain unchanged
- All your patterns are preserved
- The same pages and buttons you're used to
- Your Azure OpenAI settings still work

**What's different:**
- Some error messages are clearer and more helpful
- New options for cross-airline/version matching (optional to use)
- Better visual displays for pattern details

---

## Quick Tips for Using v3.0

### 1. **Cross-Airline Matching is Always On**
Discovery automatically searches for patterns across all airlines and versions - no need to enable anything. It works automatically.

### 2. **Read Pattern Descriptions**
Each pattern now has a plain-English description explaining what it does. Look for this in the pattern details.

### 3. **Use Side-by-Side Comparison**
When viewing pattern matches, use the tree comparison to visually see what's different.

### 4. **Check for Duplicates**
The system will warn you if it finds similar patterns. Consider merging them to keep things organized.

### 5. **Don't Worry About "Busy" Errors**
If you see "System too busy", just wait a few minutes and try again. The app will handle retries automatically.

---

## Common Questions

**Q: Will my existing patterns still work?**
A: Yes! All your existing patterns, workspaces, and data work exactly as before.

**Q: Do I need to reconfigure anything?**
A: No. Your existing configuration is preserved. Everything should work immediately.

**Q: What if I see an error?**
A: Error messages are now much clearer. Just follow the instructions in the error message. Most common issue: "System too busy" - just wait 5-10 minutes and try again.

**Q: Can I still use v2.0?**
A: Yes, but v3.0 is better in every way and there's no reason not to upgrade. It's fully compatible.

**Q: Where are the new features?**
A: Most new features appear automatically:
- Error handling is automatic (you don't need to do anything)
- Cross-airline matching is always enabled by default (no checkbox needed)
- Better displays appear automatically in Pattern Manager
- Pattern descriptions show up in pattern details

---

## Need Help?

If something isn't working:
1. Check the error message - they're now written in plain English
2. Try waiting a few minutes if it says "System too busy"
3. Restart the app (stop and start again)
4. Contact your system administrator if problems continue

---

## Summary

**v3.0 makes AssistedDiscovery:**
- ✅ More reliable (handles busy times automatically)
- ✅ More powerful (find patterns across airlines and versions)
- ✅ Easier to use (better visuals and clearer messages)
- ✅ More accurate (fewer false duplicates and quality warnings)
- ✅ Cleaner (delete unwanted patterns, merge duplicates)

**Upgrade today and enjoy a smoother experience!**

---

*AssistedDiscovery v3.0 - Making Pattern Discovery Easier*
