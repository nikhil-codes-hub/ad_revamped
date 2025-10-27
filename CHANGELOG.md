# Changelog

All notable changes to AssistedDiscovery will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-10-27

### Major Release - Production Ready

This is a major release with significant improvements to stability, user experience, and data quality.

### Added

#### UI Improvements
- **Workspace Management**
  - Added confirmation dialog for workspace deletion to prevent accidental data loss
  - Implemented two-step deletion process (Delete → Confirm/Cancel)
  - Added per-workspace confirmation state tracking for safety

- **Node Manager**
  - Fixed "Clear & New Upload" button to properly reset file uploader
  - Implemented dynamic key counter to force widget remount on clear
  - Ensures clean state when uploading new XML files

- **Pattern Extractor Workflow**
  - Renamed from "Discovery" to "Pattern Extractor" for clarity
  - Streamlined UI by removing redundant navigation buttons
  - Improved workflow clarity and user experience

- **Pattern Verification**
  - Added intelligent validation scope - only validates explicitly specified requirements
  - Fixed terminology confusion between XML attributes vs child elements
  - Improved verification accuracy with clear examples and rules

#### LLM & Data Quality
- **Robust JSON Parsing**
  - Implemented state-machine approach for cleaning LLM JSON responses
  - Added comprehensive control character handling (newlines, tabs, carriage returns)
  - Automatic detection and preservation of already-escaped sequences
  - Removal of comments and trailing commas from LLM responses
  - Reduced JSON parsing errors from ~87% to near zero

- **Pattern Generation**
  - Added metadata field filtering to exclude internal tracking fields
  - Fixed 'missing_elements' being treated as required XML attributes
  - Improved pattern accuracy and reduced false verification failures

#### Distribution
- **Portable Build**
  - Platform-specific zip naming (Mac, Windows, Linux)
  - Simplified distribution file names for end users
  - Improved build success messages with platform detection

### Fixed

#### Critical Bugs
- **JSON Parsing Errors**
  - Fixed "Invalid control character" errors in LLM responses
  - Fixed "Expecting ',' delimiter" errors from unescaped newlines
  - Improved regex patterns to handle multi-line JSON strings with DOTALL flag
  - Prevents double-escaping of already-escaped sequences

- **Pattern Verification**
  - Fixed false negatives where valid XML failed verification
  - Corrected "Required Attributes" terminology to "Required Child Elements"
  - Fixed over-validation of nested structures
  - Added explicit validation scope to prevent inferred requirements

- **Node Manager**
  - Fixed file uploader not resetting between uploads
  - Resolved stale state issues when switching files

- **Workspace Management**
  - Added safeguards against accidental workspace deletion
  - Improved user feedback during deletion process

### Changed

#### Terminology Updates
- **UI Page Renaming**
  - "Discovery" workflow → "Pattern Extractor" workflow (for extracting patterns from existing XML)
  - "Identify" workflow → "Discovery" workflow (for validating new XML against patterns)
  - Backend services remain unchanged for API compatibility

- **Documentation Updates**
  - Updated all user guides to reflect UI terminology changes
  - Clarified backend vs UI naming in technical documentation
  - Added prominent notes about terminology mapping

#### Prompts & Instructions
- **LLM Prompt Improvements**
  - Added explicit JSON formatting rules to extraction prompts
  - Instructed LLM to keep XML snippets on single lines
  - Prohibited comments, trailing commas, and control characters
  - Added snippet formatting examples and constraints

- **Verification Instructions**
  - Clarified that "Required Attributes" means "Required Child Elements"
  - Added examples showing XML element structure vs attributes
  - Specified validation scope to prevent over-validation

### Technical Details

#### Performance
- **JSON Parsing Success Rate**: Improved from ~13% to ~100%
- **State Management**: Enhanced with dynamic widget keys for better UX
- **Error Handling**: Comprehensive logging with context around failures

#### Code Quality
- **Metadata Filtering**: Consistent exclusion of internal fields across all components
- **Error Messages**: More descriptive with exact error locations and context
- **Regex Patterns**: DOTALL flag support for multi-line string handling

### Migration Notes

#### For Users Upgrading from 1.x
1. **No Breaking Changes**: All existing workspaces and patterns remain compatible
2. **UI Terminology**: Page names have changed but functionality is identical
3. **Pattern Regeneration**: Recommended to regenerate patterns to exclude metadata fields
4. **Verification**: Existing patterns may show 'missing_elements' - regenerate to fix

#### For Developers
1. **Backend API**: No changes to endpoints or models
2. **Service Names**: Internal services still use original names (DiscoveryWorkflow, IdentifyWorkflow)
3. **Database Schema**: No migrations required

### Documentation

Updated documentation files:
- `USER_GUIDE.md` - Complete workflow rename throughout
- `DEMO_PREPARATION_GUIDE.md` - Updated demo script
- `README.md` - Updated quick start guide
- `CLAUDE.md` - Added UI terminology notes
- `backend/tests/README.md` - Clarified backend vs UI naming

### Known Issues

None critical. All known issues from 1.x have been resolved.

### Acknowledgments

This release includes contributions from:
- Core development team
- AI assistance from Claude Code for implementation and testing

---

## [1.0.0] - 2025-10-03

### Initial Release

First production-ready release of AssistedDiscovery.

### Features
- NDC XML parsing and pattern extraction
- AI-powered pattern generation with GPT-4o
- Workspace-based database isolation
- Multi-version NDC support (17.2, 18.1, 19.2, 21.3)
- Pattern matching with confidence scoring
- Relationship discovery between nodes
- Streamlit-based UI
- FastAPI backend
- SQLite workspace databases

---

[2.0.0]: https://github.com/nikhil-codes-hub/ad_revamped/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/nikhil-codes-hub/ad_revamped/releases/tag/v1.0.0
