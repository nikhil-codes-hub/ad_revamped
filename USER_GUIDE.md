# AssistedDiscovery - Complete User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Configuration](#configuration)
4. [Core Workflows](#core-workflows)
5. [Node Configuration](#node-configuration)
6. [Discovery Workflow](#discovery-workflow)
7. [Pattern Manager](#pattern-manager)
8. [Identify Workflow](#identify-workflow)
9. [Workspaces](#workspaces)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)

---

## Introduction

### What is AssistedDiscovery?

AssistedDiscovery is an AI-powered tool that helps you understand and document NDC (New Distribution Capability) XML message structures. It:

- **Extracts node structures** from XML files automatically
- **Discovers relationships** between nodes (who references whom)
- **Generates reusable patterns** for future validation
- **Identifies changes** in XML structure over time
- **Validates XML files** against known patterns

### Who Should Use This Tool?

- **Business Analysts**: Understanding airline XML message formats
- **Integration Developers**: Documenting API message structures
- **QA Teams**: Validating XML message consistency
- **Technical Writers**: Creating implementation documentation

### Key Concepts

**NodeFact**: A discovered piece of information about an XML node (its structure, attributes, children)

**Pattern**: A reusable template describing how a specific node type should look

**Relationship**: A reference from one node to another (e.g., Passenger → Segment)

**Discovery**: The process of extracting NodeFacts and relationships from XML

**Identify**: The process of comparing XML against known patterns

**Workspace**: An isolated environment for a specific airline or project

---

## Getting Started

### Installation

#### Option 1: Portable Distribution (Recommended for Users)

1. **Extract the ZIP file**:
   ```bash
   unzip AssistedDiscovery-Portable-*.zip
   cd AssistedDiscovery-Portable-*
   ```

2. **Run setup** (one-time only):
   ```bash
   # macOS/Linux
   ./setup.sh

   # Windows
   setup.bat
   ```

3. **Start the application**:
   ```bash
   # macOS/Linux
   ./start_app.sh

   # Windows
   start_app.bat
   ```

4. **Access the UI**:
   - Open your browser
   - Go to: `http://localhost:8501`

#### Option 2: Development Setup

For developers who want to modify the code:

```bash
# Clone repository
git clone <repository-url>
cd ad

# Setup backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup frontend
cd ../frontend/streamlit_ui
pip install -r requirements.txt

# Start backend (terminal 1)
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Start frontend (terminal 2)
cd frontend/streamlit_ui
streamlit run AssistedDiscovery.py --server.port 8501
```

### First-Time Setup Checklist

- [ ] Application installed and running
- [ ] Browser opens to `http://localhost:8501`
- [ ] LLM credentials configured (see [Configuration](#configuration))
- [ ] Test workspace created
- [ ] Sample XML file ready for testing

---

## Configuration

### LLM Configuration

AssistedDiscovery uses AI (Large Language Model) to extract information from XML. You need to configure your LLM provider.

#### Step 1: Access Configuration

1. Click **⚙️ Config** in the sidebar
2. Scroll to **🤖 LLM Configuration** section

#### Step 2: Select Provider

**Supported Providers**:
- **Azure OpenAI** (Recommended for enterprise)
- **Google Gemini** (Alternative option)

#### Step 3: Configure Azure OpenAI

**Required Information**:
- **Endpoint**: Your Azure OpenAI endpoint URL
  - Format: `https://your-resource.openai.azure.com/`
- **API Key**: Your Azure OpenAI API key
  - Found in Azure Portal → OpenAI Resource → Keys
- **API Version**: API version (default: `2025-01-01-preview`)
- **Model Deployment**: Your deployment name (e.g., `gpt-4o`)

**Configuration Steps**:

1. Select **azure** from LLM Provider dropdown
2. Enter your **Azure OpenAI Endpoint**
3. Enter your **API Key**
4. Verify **API Version** (usually default is correct)
5. Enter your **Model Deployment Name**
6. Configure common settings:
   - **Max Tokens**: 4000 (default, adjust if needed)
   - **Temperature**: 0.1 (low for consistency)
   - **Top P**: 0.0 (deterministic)

7. Click **💾 Save Configuration**
8. Click **🔍 Test Connection** to verify

**Expected Result**:
```
✅ Connection successful!
Provider: azure
```

#### Step 4: Configure Google Gemini (Alternative)

If using Gemini instead of Azure:

1. Select **gemini** from LLM Provider dropdown
2. Enter your **Gemini API Key**
3. Select **Model** (default: `gemini-1.5-pro`)
4. Configure common settings (same as Azure)
5. Click **💾 Save Configuration**
6. Click **🔍 Test Connection**

#### Step 5: Restart Backend

**Important**: After saving LLM configuration, **restart the backend** for changes to take effect.

**Portable Distribution**:
```bash
# Stop the app (Ctrl+C in terminal)
# Restart
./start_app.sh  # or start_app.bat on Windows
```

**Development Setup**:
```bash
# Stop backend (Ctrl+C)
# Restart
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Log File Location

Application logs are stored in platform-specific locations:

- **macOS**: `~/Library/Logs/AssistedDiscovery/assisted_discovery.log`
- **Windows**: `%LOCALAPPDATA%\AssistedDiscovery\Logs\assisted_discovery.log`
- **Linux**: `~/.local/share/AssistedDiscovery/logs/assisted_discovery.log`

**To view logs via UI**:
1. Go to **⚙️ Config** page
2. Scroll to **📋 Application Logs** section
3. Click **📂 Open Log Folder** button

---

## Core Workflows

AssistedDiscovery has four main workflows:

### 1. Discovery Workflow 🔍

**Purpose**: Extract structure and relationships from XML

**When to use**:
- First time analyzing an airline's XML format
- New XML message type received
- Need to understand XML structure

**Output**:
- NodeFacts (extracted structures)
- Relationships (node references)
- Patterns (reusable templates)

**Typical Duration**: 2-5 minutes for standard XML

---

### 2. Identify Workflow 🎯

**Purpose**: Validate XML against known patterns

**When to use**:
- After Discovery has generated patterns
- Validating new XML files from same airline
- Checking for structural changes

**Output**:
- Pattern matches (what changed, what stayed same)
- Confidence scores
- Deviation reports

**Typical Duration**: 30 seconds for standard XML

---

### 3. Pattern Management 🎨

**Purpose**: View, export, and manage discovered patterns

**When to use**:
- Review extracted patterns
- Export patterns for documentation
- Import patterns from another workspace

**Output**:
- Pattern library
- Exportable JSON files

---

### 4. Node Configuration 📋

**Purpose**: Configure which nodes to extract and their expected references

**When to use**:
- Before Discovery (optional, for guided extraction)
- After Discovery (to refine extraction rules)

**Output**:
- Node Configuration rules
- Expected reference definitions

---

## Node Configuration

Node Configuration tells AssistedDiscovery **which nodes to extract** and **what references to expect**.

### Why Configure Nodes?

**Benefits**:
- ✅ **Faster Discovery**: Only extract nodes you care about
- ✅ **Better Relationships**: Define expected references between nodes
- ✅ **Consistent Results**: Same extraction rules across runs

**Optional**: You can skip this and let Discovery auto-detect everything. However, configuration gives you more control.

### Access Node Configuration

1. Click **📋 Node Config** in sidebar
2. You'll see four tabs:
   - **📤 Analyze XML**: Upload XML to see available nodes
   - **⚙️ Manage Configurations**: Create/edit node configs
   - **📋 Copy to Versions**: Copy configs across NDC versions
   - **🔖 Reference Types**: Define reference type taxonomy

---

### Tab 1: Analyze XML

**Purpose**: Discover which nodes exist in your XML without running full Discovery.

#### Steps:

1. **Upload XML File**:
   - Click **Browse** or drag-and-drop
   - Select your NDC XML file

2. **Review Detected Nodes**:
   ```
   Message: OrderViewRS
   Version: 19.2
   Airline: LA (LATAM)

   Available Sections:
   ✓ OrderViewRS/Response/DataLists/PassengerList
   ✓ OrderViewRS/Response/DataLists/SegmentList
   ✓ OrderViewRS/Response/DataLists/FareList
   ✓ OrderViewRS/Response/Order
   ... (more sections)
   ```

3. **Note Section Paths**: These are the paths you'll use in configuration

4. **Optionally Create Configs**: Click **Create Configuration** next to any section

---

### Tab 2: Manage Configurations

**Purpose**: Create and edit node extraction rules.

#### View Existing Configurations

The table shows all configured nodes:

| Section Path | Version | Message | Enabled | Priority | Has Expected Refs |
|-------------|---------|---------|---------|----------|-------------------|
| PassengerList | 19.2 | OrderViewRS | ✓ | high | Yes |
| SegmentList | 19.2 | OrderViewRS | ✓ | high | Yes |

#### Create New Configuration

**Steps**:

1. Click **➕ Add New Configuration**

2. Fill in the form:

   **Section Path** (Required):
   ```
   OrderViewRS/Response/DataLists/PassengerList
   ```
   - Copy from "Analyze XML" tab
   - Use the exact path from XML

   **Spec Version** (Required):
   ```
   19.2
   ```
   - NDC specification version
   - Common values: 17.2, 18.1, 19.2, 21.3

   **Message Root** (Required):
   ```
   OrderViewRS
   ```
   - Root element of the XML message
   - Examples: OrderViewRS, AirShoppingRS, OfferPriceRS

   **Enabled**:
   - ✅ Checked: Extract this node during Discovery
   - ❌ Unchecked: Skip this node

   **Importance** (Optional):
   ```
   Options: critical, high, medium, low
   ```
   - Used for prioritization and reporting
   - Default: medium

   **Expected References** (Optional):
   ```
   segment_reference, fare_reference, service_reference
   ```
   - Comma-separated list
   - Semantic names for expected relationships
   - Example: "segment_reference" means Passenger should reference Segment
   - Leave empty to auto-discover all relationships

3. Click **💾 Save Configuration**

#### Example: Configure PassengerList

```
Section Path: OrderViewRS/Response/DataLists/PassengerList
Spec Version: 19.2
Message Root: OrderViewRS
Enabled: ✓ Yes
Importance: high
Expected References: segment_reference, fare_reference, service_reference
```

**What this means**:
- Extract PassengerList nodes during Discovery
- This is a high-priority node
- We expect Passengers to reference Segments, Fares, and Services
- Discovery will validate these expected references exist

#### Edit Existing Configuration

1. Find the configuration in the table
2. Click **✏️ Edit** button
3. Modify fields
4. Click **💾 Update**

#### Delete Configuration

1. Find the configuration in the table
2. Click **🗑️ Delete** button
3. Confirm deletion

**Note**: Deleting config doesn't delete extracted NodeFacts, just the extraction rule.

---

### Tab 3: Copy to Versions

**Purpose**: Copy node configurations across NDC versions or message types.

**Use Case**: You configured nodes for NDC 19.2, now you receive NDC 21.3 files with similar structure.

#### Steps:

1. **Select Source**:
   - Spec Version: `19.2`
   - Message Root: `OrderViewRS`

2. **Select Target**:
   - Spec Version: `21.3`
   - Message Root: `OrderViewRS`

3. **Review Configs to Copy**:
   ```
   ✓ PassengerList
   ✓ SegmentList
   ✓ FareList
   (3 configurations selected)
   ```

4. Click **📋 Copy Configurations**

5. **Result**:
   ```
   ✅ Copied 3 configurations from 19.2/OrderViewRS to 21.3/OrderViewRS
   ```

**What happens**: All selected configs are duplicated with new version/message.

---

### Tab 4: Reference Types

**Purpose**: Define a taxonomy of reference types for your domain.

**Use Case**: Standardize reference naming across configurations.

#### View Reference Types

| Reference Type | Description | Category |
|---------------|-------------|----------|
| segment_reference | Passenger to flight segment | Booking |
| fare_reference | Passenger to fare component | Pricing |
| infant_parent | Infant to parent passenger | Passenger |

#### Create Reference Type

1. Click **➕ Add Reference Type**
2. Fill in:
   - **Reference Type**: `segment_reference`
   - **Description**: `Reference from Passenger to Segment`
   - **Category**: `Booking` (optional)
3. Click **💾 Save**

**Benefits**:
- Standardized naming
- Documentation
- Autocomplete in configuration forms

---

## Discovery Workflow

Discovery is the core workflow that extracts structure and relationships from XML.

### When to Run Discovery

**First Time with XML**:
- New airline partner
- New message type
- New NDC version

**Periodic Updates**:
- XML structure changes
- New fields added
- Validate current understanding

### Step-by-Step: Running Discovery

#### Step 1: Access Discovery Page

Click **🔍 Discovery** in the sidebar

#### Step 2: Select Workspace

```
Workspace: [Dropdown: default, LATAM, United, ...]
```

- Select existing workspace or create new one
- Each workspace isolates data per airline/project
- See [Workspaces](#workspaces) section for details

#### Step 3: Upload XML File

**Option A: Drag & Drop**
- Drag XML file into the upload area

**Option B: Browse**
- Click **Browse** button
- Select XML file from your computer

**Supported Formats**:
- ✅ `.xml` files
- ✅ NDC messages (OrderViewRS, AirShoppingRS, etc.)
- ✅ With or without `IATA_` prefix
- ✅ Any NDC version (17.2, 18.1, 19.2, 21.3)

**File Size Limits**:
- Maximum: 100 MB
- Recommended: < 10 MB for faster processing

#### Step 4: Review Upload Confirmation

```
✅ File uploaded successfully!

File: LATAM_OrderView_19.2.xml
Size: 2.3 MB
Message Type: OrderViewRS
NDC Version: 19.2
Airline: LA (LATAM)
```

#### Step 5: Start Discovery

Click **🚀 Start Discovery** button

**What Happens Next**:

1. **Version Detection** (5 seconds)
   ```
   🔍 Detecting NDC version and message type...
   ```

2. **Node Extraction** (1-3 minutes)
   ```
   📥 Extracting node structures from XML...
   Progress: [=========>          ] 45%
   ```
   - Parses XML into subtrees
   - Sends subtrees to LLM for analysis
   - LLM extracts structure information

3. **Relationship Analysis** (1-2 minutes)
   ```
   🔗 Analyzing relationships between nodes...
   ```
   - Discovers references between nodes
   - Validates expected references
   - Classifies relationships

4. **Pattern Generation** (30 seconds)
   ```
   🎨 Generating reusable patterns...
   ```
   - Creates pattern templates from NodeFacts
   - Deduplicates similar patterns
   - Stores for future Identify runs

5. **Completion**
   ```
   ✅ Discovery completed successfully!
   ```

#### Step 6: Review Results

After Discovery completes, you'll see comprehensive results:

---

### Discovery Results: Run Summary

```
📊 Discovery Results

Run ID: 7322e7bb-fda6-4544-9bf3-cf2bc8e6e476
Status: ✅ Completed
Duration: 3m 42s

NDC Version: 19.2
Message Root: OrderViewRS
Airline: LA (LATAM)
```

---

### Discovery Results: Statistics

```
📈 Extraction Statistics

NodeFacts Extracted: 47
Relationships Found: 18
Patterns Generated: 12

Breakdown by Section:
├─ PassengerList: 8 nodes
├─ SegmentList: 6 nodes
├─ FareList: 12 nodes
├─ ServiceList: 5 nodes
└─ Order: 16 nodes
```

---

### Discovery Results: Relationships

```
🔗 Relationship Summary

✅ Valid Relationships: 15
❌ Broken Relationships: 3
📋 Expected Validated: 12
⚠️ Expected Missing: 2
🔍 Unexpected Discovered: 4
```

**Expand to see details**:

**Expected & Validated** ✅📋:
```
PassengerList → SegmentList
Reference: SegmentRefID
Status: Valid
Confidence: 95%
```

**Expected but Missing** ❌📋:
```
PassengerList → ServiceList
Reference: ServiceRefID (expected but not found)
Status: Broken
```

**Unexpected Discoveries** ✅🔍:
```
PassengerList → BaggageList
Reference: BaggageRefID
Status: Valid (newly discovered)
Confidence: 87%
Note: This reference was not configured but AI found it
```

---

### Discovery Results: Extracted NodeFacts

Table showing all extracted nodes:

| Node Type | Section Path | Attributes | Children | References | Confidence |
|-----------|-------------|------------|----------|------------|------------|
| Passenger | PassengerList | 8 | 12 | 3 | 95% |
| Segment | SegmentList | 6 | 8 | 2 | 92% |
| Fare | FareList | 5 | 6 | 1 | 90% |

**Actions**:
- Click any row to see full JSON structure
- Export table to CSV

---

### Discovery Results: Generated Patterns

```
🎨 Generated Patterns: 12

Patterns are now available in Pattern Manager for:
- Future validation (Identify workflow)
- Export/documentation
- Cross-airline comparison
```

Click **View in Pattern Manager** to see patterns.

---

### Common Discovery Scenarios

#### Scenario 1: First Discovery for Airline

**Situation**: Never analyzed this airline's XML before.

**Steps**:
1. Create new workspace: `Airline_Code` (e.g., `LATAM`)
2. Upload sample XML
3. Run Discovery without pre-configuration
4. Review all relationships (validate unexpected discoveries)
5. Configure expected references for next time

**Result**: Full understanding of XML structure.

---

#### Scenario 2: Validating Expected Structure

**Situation**: You know what references should exist (BA knowledge).

**Steps**:
1. Configure node configs with expected_references BEFORE Discovery
2. Upload XML
3. Run Discovery
4. Check "Expected Missing" section for broken references

**Result**: Validation of business assumptions.

---

#### Scenario 3: Detecting Changes

**Situation**: Previously analyzed airline, checking for changes.

**Steps**:
1. Use same workspace as previous Discovery
2. Upload new XML file
3. Run Discovery
4. Compare:
   - New unexpected discoveries = structural additions
   - Missing expected references = structural changes/breaks

**Result**: Change detection report.

---

## Pattern Manager

After Discovery generates patterns, manage them in Pattern Manager.

### Access Pattern Manager

Click **🎨 Pattern Manager** in sidebar

---

### View Patterns

**Pattern Table**:

| Section Path | Node Type | Version | Airline | Message | Must-Have Attrs | Has Children |
|-------------|-----------|---------|---------|---------|-----------------|--------------|
| PassengerList | Passenger | 19.2 | LA | OrderViewRS | 5 | ✓ |
| SegmentList | Segment | 19.2 | LA | OrderViewRS | 3 | ✓ |

**Summary Metrics**:
```
Total Patterns: 12
Versions: 1 (19.2)
Node Types: 8
```

---

### Filter Patterns

**Filter by Version**:
```
Version: [All ▼]
Options: All, 17.2, 18.1, 19.2, 21.3
```

**Filter by Node Type**:
```
Node Type: [All ▼]
Options: All, Passenger, Segment, Fare, Service...
```

---

### Export Patterns

**Purpose**: Share patterns with team, backup, or import to another workspace.

**Steps**:

1. **Select Patterns to Export**:
   - Check the **Select** checkbox for patterns you want
   - Or select all

2. Click **📤 Export Selected Patterns (JSON)**

3. **Downloaded File**:
   ```
   patterns_LATAM_2025-10-09.json
   ```

**Use Cases**:
- Documentation: Include in API specs
- Backup: Save pattern library
- Sharing: Send to other team members
- Migration: Import to different workspace

---

### Import Patterns

**Purpose**: Load patterns from another workspace or external source.

**Steps**:

1. Click **📥 Import Patterns**

2. **Upload JSON File**:
   - Must be valid pattern export file
   - Format: Same as export

3. **Preview**:
   ```
   Importing 12 patterns from LATAM workspace
   Spec Version: 19.2
   Message Root: OrderViewRS
   ```

4. Click **Confirm Import**

5. **Result**:
   ```
   ✅ Successfully imported 12 patterns
   ```

**Notes**:
- Duplicate patterns (same signature_hash) are skipped
- Import doesn't overwrite existing patterns

---

### Pattern Details

Click any pattern row to see full details:

**Pattern Information**:
```
ID: 42
Section Path: OrderViewRS/Response/DataLists/PassengerList
Node Type: Passenger
Version: 19.2 / OrderViewRS
Airline: LA
```

**Decision Rule**:
```json
{
  "node_type": "Passenger",
  "must_have_attributes": ["PaxID", "GivenName", "Surname"],
  "optional_attributes": ["MiddleName", "Title"],
  "must_have_children": ["ContactInfo"],
  "optional_children": ["FrequentFlyer", "SSR"],
  "child_structure": {
    "has_children": true,
    "min_children": 1,
    "max_children": 20
  }
}
```

**Examples**:
```
Sample XML snippets that match this pattern
```

---

## Identify Workflow

Identify validates new XML files against existing patterns.

### When to Use Identify

**After Discovery**:
- You've run Discovery and generated patterns
- Now you want to validate new XML files

**Use Cases**:
- Testing: Validate test XML files
- Monitoring: Check production files for deviations
- Regression: Ensure changes don't break structure

### Prerequisites

✅ **Patterns must exist** in workspace (from Discovery)
✅ **Patterns must match XML type** (same message_root)

### Step-by-Step: Running Identify

#### Step 1: Access Identify Page

Click **🎯 Identify** in sidebar

#### Step 2: Select Workspace

```
Workspace: [Dropdown]
```

Same workspace where you ran Discovery.

#### Step 3: Upload XML File

- Upload the XML file you want to validate
- Must be same message type as patterns (e.g., OrderViewRS)

**Version Compatibility**:
- ✅ Same version as patterns: Full validation
- ⚠️ Different version: Partial validation (structure may differ)

#### Step 4: Start Identify

Click **🔍 Start Identify**

**What Happens**:

1. **Extract NodeFacts** (1-2 minutes)
   - Same extraction as Discovery
   - But no relationship analysis
   - No pattern generation

2. **Match Against Patterns** (30 seconds)
   - Compare each NodeFact to existing patterns
   - Calculate similarity scores
   - Classify matches

3. **Generate Report** (instant)

---

### Identify Results

#### Pattern Matching Summary

```
📊 Pattern Matching Results

Total NodeFacts: 45
Match Rate: 87.5%

Verdict Breakdown:
✅ EXACT_MATCH: 32 (71%)
🟡 HIGH_MATCH: 7 (16%)
🟠 PARTIAL_MATCH: 3 (7%)
⚪ NO_MATCH: 2 (4%)
🔴 NEW_PATTERN: 1 (2%)
```

**What the verdicts mean**:

**EXACT_MATCH** ✅ (Confidence ≥ 95%):
- NodeFact perfectly matches known pattern
- All must-have attributes present
- Structure identical

**HIGH_MATCH** 🟡 (Confidence 85-95%):
- Close match to pattern
- Minor differences (optional fields)
- Generally acceptable

**PARTIAL_MATCH** 🟠 (Confidence 70-85%):
- Some differences from pattern
- Missing some expected fields or extra fields
- Review recommended

**LOW_MATCH/NO_MATCH** ⚪ (Confidence < 70%):
- Significant deviation from pattern
- Structure changed
- Investigation required

**NEW_PATTERN** 🔴:
- No matching pattern found
- Completely new node structure
- Consider running Discovery

---

#### Pattern Matches Table

| Node Type | Section Path | Explanation | Confidence | Verdict |
|-----------|-------------|-------------|------------|---------|
| Passenger | PassengerList | Perfect match: All expected fields present | 100% | EXACT_MATCH ✅ |
| Segment | SegmentList | Close match: Optional field 'OperatingCarrier' missing | 89% | HIGH_MATCH 🟡 |
| Service | ServiceList | No matching pattern found | N/A | NEW_PATTERN 🔴 |

---

#### Detailed Match Analysis

**Click any match to see detailed comparison**:

**Match Summary**:
```
Node: Passenger at /PassengerList
Pattern ID: 42
Verdict: HIGH_MATCH 🟡
Confidence: 89%
```

**Quick Explanation**:
```
✅ Strong match: 'Passenger' closely matches the expected pattern
with 89% confidence. Optional field 'MiddleName' is present but not required.
```

**Detailed Comparison**:

**Attributes**:
```
✅ Matched: PaxID, GivenName, Surname, PaxRefID
✅ Extra (OK): MiddleName (optional field present)
❌ Missing: (none)
```

**Children**:
```
✅ Matched: ContactInfo
✅ Extra: FrequentFlyer (bonus data)
❌ Missing: (none)
```

**References**:
```
✅ Matched: SegmentRefID → SegmentList
✅ Matched: FareRefID → FareList
```

**Full JSON Comparison**:
- Expand to see side-by-side NodeFact vs Pattern

---

#### Get AI Explanation

**For complex deviations**, click **🤖 Get Detailed AI Explanation**:

```
🤖 AI Analysis

The Passenger node in this XML file is structurally similar to the
known pattern, with 89% confidence. The main differences are:

1. Additional Field: 'MiddleName' is present but was marked optional
   in the pattern. This is acceptable and common for middle name variations.

2. All required fields are present: PaxID, GivenName, Surname match
   the pattern requirements exactly.

3. References are valid: Both SegmentRefID and FareRefID correctly
   point to existing nodes in the XML.

Recommendation: This is a HIGH_MATCH and acceptable variation. No
action needed unless 'MiddleName' should be mandatory.
```

**Cached**: Explanations are cached for performance.

---

### Identify Workflow Tips

**Best Practices**:

1. **Run Discovery First**: Always have patterns before Identify
2. **Same Message Type**: Identify OrderViewRS against OrderViewRS patterns
3. **Review NEW_PATTERN**: These may indicate structure changes
4. **Investigate NO_MATCH**: Could be data quality issues

**Common Issues**:

**"No pattern matches found"**:
- Cause: No patterns exist for this message type
- Solution: Run Discovery first to generate patterns

**Low confidence scores**:
- Cause: XML structure changed since Discovery
- Solution: Review differences, possibly re-run Discovery

---

## Workspaces

Workspaces isolate data per airline or project.

### What is a Workspace?

A **workspace** is an isolated environment containing:
- NodeFacts
- Relationships
- Patterns
- Node Configurations
- Discovery/Identify runs

**Benefits**:
- ✅ **Separation**: LATAM data separate from United data
- ✅ **Organization**: One workspace per project
- ✅ **Clean Comparison**: Compare airlines side-by-side

---

### Managing Workspaces

Access workspace management in **⚙️ Config** page.

#### Create New Workspace

1. Go to **⚙️ Config**
2. Scroll to **📁 Workspace Management**
3. Enter workspace name:
   ```
   New Workspace: LATAM
   ```
   - Use airline code or project name
   - Alphanumeric only (no spaces)
   - Examples: `LATAM`, `United`, `Test`, `Production`

4. Click **➕ Add Workspace**

5. **Result**:
   ```
   ✅ Workspace 'LATAM' created successfully!
   ```

---

#### Switch Workspace

**In Sidebar**:
```
Workspace: [LATAM ▼]
```

**Or in Config Page**:
```
Current Workspace: LATAM
Switch to: [United ▼] → Switch
```

**Effect**: All pages now show data from selected workspace.

---

#### Delete Workspace

**⚠️ Warning**: This permanently deletes ALL data in workspace!

1. Go to **⚙️ Config** → **Delete Workspace**
2. Select workspace to delete:
   ```
   Workspace to delete: [Test ▼]
   ```
   - Cannot delete "default" workspace
   - Must have at least one workspace

3. **Warning message**:
   ```
   ⚠️ This will permanently delete the workspace and all its data
   (patterns, runs, node facts)!
   ```

4. Click **🗑️ Delete Workspace**

5. Confirmation:
   ```
   ✅ Workspace 'Test' and its database deleted.
   ```

**What gets deleted**:
- All NodeFacts
- All Relationships
- All Patterns
- All Node Configurations
- All Discovery/Identify runs
- Workspace database file (`.db` file deleted from disk)

---

### Workspace Best Practices

**Organization Strategy**:

```
Workspaces:
├─ LATAM          (LATAM Airlines - production)
├─ LATAM_Test     (LATAM Airlines - testing)
├─ United         (United Airlines)
├─ Delta          (Delta Airlines)
└─ Development    (Experiments and testing)
```

**Naming Conventions**:
- ✅ Airline code: `LATAM`, `UA`, `DL`
- ✅ Project name: `Phase1`, `Migration`
- ✅ Environment: `Production`, `Test`, `Dev`
- ❌ Avoid: Spaces, special characters

**Workflow**:
1. Create workspace per airline
2. Run Discovery in airline workspace
3. Patterns stay isolated to that airline
4. Switch workspaces to compare different airlines

---

## Troubleshooting

### LLM Connection Issues

#### "Connection error" or "Cannot connect to endpoint"

**Causes**:
- Invalid API key
- Incorrect endpoint URL
- Network/proxy issues
- SSL certificate issues (corporate proxy)

**Solutions**:

1. **Verify Configuration**:
   - Go to ⚙️ Config → LLM Configuration
   - Click **🔍 Test Connection**
   - Check error message

2. **Check Endpoint Format**:
   ```
   ✅ Correct: https://your-resource.openai.azure.com/
   ❌ Wrong: https://your-resource.openai.azure.com (missing trailing /)
   ❌ Wrong: your-resource.openai.azure.com (missing https://)
   ```

3. **Verify API Key**:
   - Check Azure Portal for correct key
   - Key should be ~40+ characters
   - No spaces or line breaks

4. **Check Logs**:
   - Open log folder (Config → Application Logs)
   - Look for detailed error messages
   - Check for "SSL" or "certificate" errors

5. **Corporate Proxy**:
   - If behind corporate proxy, SSL verification is disabled (built-in)
   - If still failing, contact IT for proxy whitelist

---

#### "LLM INITIALIZATION FAILED: No API keys found"

**Cause**: .env file not loaded or missing credentials

**Solutions**:

1. **Configure via UI**:
   - Go to ⚙️ Config → LLM Configuration
   - Enter credentials
   - Save Configuration
   - **Restart backend** (important!)

2. **Check .env file** (advanced):
   ```bash
   # Check if file exists
   ls -la .env

   # View contents (backend directory)
   cat .env | grep AZURE_OPENAI_KEY
   ```

3. **Restart Backend**:
   - Configuration changes require restart
   - Stop and restart backend service

---

### Discovery/Identify Issues

#### "No NodeFacts extracted"

**Causes**:
- XML file empty or corrupted
- LLM not configured
- XML format not supported

**Solutions**:

1. **Verify XML File**:
   - Open in text editor
   - Check it's valid XML
   - Ensure it's NDC format (not random XML)

2. **Check LLM**:
   - Test LLM connection in Config
   - Check logs for LLM errors

3. **Check Node Configurations**:
   - If configured, ensure nodes are "Enabled"
   - Try disabling configs to allow auto-detection

---

#### "No patterns found" when running Identify

**Cause**: No patterns exist for this message type/version

**Solution**: Run Discovery first to generate patterns

**Example**:
```
Patterns in workspace: 19.2/OrderViewRS
Your XML: 21.3/AirShoppingRS

❌ Mismatch: Different message types
```

**Fix**: Either:
- Run Discovery on AirShoppingRS to create patterns
- Use OrderViewRS file for Identify

---

#### "Relationship analysis failed"

**Causes**:
- LLM timeout
- Invalid XML snippets
- Network interruption

**Solutions**:

1. **Check Logs**: Look for specific error
2. **Retry**: Re-run Discovery
3. **Smaller XML**: Try with smaller sample file first
4. **Increase Timeout**: Contact administrator if persistent

---

### UI Issues

#### "Backend connection failed"

**Causes**:
- Backend not running
- Wrong port
- Firewall blocking

**Solutions**:

1. **Check Backend Status**:
   ```bash
   # Check if backend is running
   curl http://localhost:8000/health

   # Expected response:
   {"status": "healthy"}
   ```

2. **Start Backend**:
   ```bash
   # Portable distribution
   ./start_app.sh

   # Development
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

3. **Check Port**:
   - Backend should be on port 8000
   - Frontend should be on port 8501
   - Ensure no conflicts

---

#### Page not loading or spinning forever

**Causes**:
- Backend slow response
- Large data set
- Browser cache

**Solutions**:

1. **Wait**: Discovery/Identify can take 3-5 minutes
2. **Check Logs**: Backend logs show progress
3. **Refresh**: Ctrl+F5 (hard refresh)
4. **Clear Cache**: Browser → Clear cache and cookies

---

### Data Issues

#### "Workspace not found" after switching

**Cause**: Workspace database not created yet

**Solution**: Create workspace first in Config page

---

#### "Patterns still show after deletion"

**Cause**: Frontend cache

**Solution**: Refresh page (F5 or Ctrl+R)

---

### Performance Issues

#### Discovery is very slow (>10 minutes)

**Causes**:
- Large XML file (>10MB)
- Many node types (>50)
- Slow LLM API responses

**Solutions**:

1. **Configure Nodes**: Only extract important nodes
2. **Smaller Sample**: Use smaller XML file for initial Discovery
3. **Check Logs**: See which step is slow

---

#### UI becomes unresponsive

**Causes**:
- Large result set (>1000 rows)
- Browser memory
- Slow rendering

**Solutions**:

1. **Use Pagination**: Limit results to 50-100 per page
2. **Filter Data**: Apply filters before viewing
3. **Restart Browser**: Clear memory

---

## Best Practices

### Discovery Workflow

**Do**:
- ✅ Configure expected references before Discovery
- ✅ Use representative XML samples (not minimal test files)
- ✅ Review unexpected discoveries (they may reveal issues)
- ✅ Run Discovery when XML format changes
- ✅ Use one workspace per airline/project

**Don't**:
- ❌ Skip node configuration for important nodes
- ❌ Run Discovery on every single file (use Identify instead)
- ❌ Ignore broken references (investigate root cause)
- ❌ Mix airlines in same workspace

---

### Pattern Management

**Do**:
- ✅ Export patterns for backup
- ✅ Document pattern changes
- ✅ Review patterns periodically
- ✅ Share patterns with team

**Don't**:
- ❌ Delete patterns without backup
- ❌ Manually edit pattern JSON (use Discovery)
- ❌ Import untrusted patterns

---

### Identify Workflow

**Do**:
- ✅ Run Identify on test files before production
- ✅ Investigate NEW_PATTERN verdicts
- ✅ Use Identify for regression testing
- ✅ Archive identify results for audit trail

**Don't**:
- ❌ Ignore low confidence matches
- ❌ Run Identify without patterns
- ❌ Skip AI explanations for deviations

---

### Workspace Management

**Do**:
- ✅ Create workspace per airline
- ✅ Use clear naming conventions
- ✅ Switch workspace before operations
- ✅ Backup workspace data (export patterns)

**Don't**:
- ❌ Delete workspace without backup
- ❌ Mix unrelated data in one workspace
- ❌ Forget to switch workspace

---

### Configuration

**Do**:
- ✅ Test LLM connection after configuration
- ✅ Restart backend after config changes
- ✅ Document configuration settings
- ✅ Set expected references for known node types

**Don't**:
- ❌ Share API keys
- ❌ Use production keys in test environment
- ❌ Skip configuration validation

---

## Appendix

### Supported NDC Versions

- ✅ NDC 17.2
- ✅ NDC 18.1
- ✅ NDC 19.2
- ✅ NDC 21.3
- ✅ Any future version (auto-detected)

### Supported Message Types

- ✅ OrderViewRS / IATA_OrderViewRS
- ✅ AirShoppingRS / IATA_AirShoppingRS
- ✅ OfferPriceRS / IATA_OfferPriceRS
- ✅ OrderCreateRQ / IATA_OrderCreateRQ
- ✅ OrderChangeRQ / IATA_OrderChangeRQ
- ✅ Any NDC message type (dynamic support)

### Supported Formats

- ✅ With IATA_ prefix (NDC 19.2+)
- ✅ Without IATA_ prefix (NDC 17.2)
- ✅ Mixed formats in same XML

### System Requirements

**Minimum**:
- 4 GB RAM
- 2 CPU cores
- 1 GB disk space
- Python 3.9+

**Recommended**:
- 8 GB RAM
- 4 CPU cores
- 5 GB disk space
- Python 3.10+

### Browser Compatibility

- ✅ Chrome/Edge (Recommended)
- ✅ Firefox
- ✅ Safari
- ❌ Internet Explorer (not supported)

---

## Getting Help

### Documentation

- **This User Guide**: Complete reference
- **Relationship Discovery Logic**: Technical deep-dive
- **Packaging Guide**: Deployment instructions
- **API Documentation**: Backend API reference

### Support Channels

**Issues & Bugs**:
- GitHub Issues: `<repository-url>/issues`

**Questions**:
- Team Chat: Contact development team
- Email: `<support-email>`

### Log Files

Always include log files when reporting issues:

**Location**:
- macOS: `~/Library/Logs/AssistedDiscovery/`
- Windows: `%LOCALAPPDATA%\AssistedDiscovery\Logs\`
- Linux: `~/.local/share/AssistedDiscovery/logs/`

**Access via UI**:
1. Go to ⚙️ Config
2. Scroll to 📋 Application Logs
3. Click 📂 Open Log Folder

---

## Frequently Asked Questions

**Q: Can I use AssistedDiscovery offline?**
A: No, it requires internet connection for LLM API calls (Azure OpenAI or Gemini).

**Q: How much does it cost to run?**
A: Cost depends on LLM provider usage. Azure OpenAI charges per token. Typical Discovery run costs $0.10-$0.50.

**Q: Can multiple users share workspaces?**
A: Not directly. Export/import patterns to share data between users.

**Q: What happens to my data?**
A: All data stored locally in SQLite databases. No data sent to AssistedDiscovery servers (only to your configured LLM provider).

**Q: Can I modify extracted patterns?**
A: Not directly through UI. Export, edit JSON, and re-import. Or run Discovery again with refined configuration.

**Q: How accurate is relationship discovery?**
A: LLM-based discovery has ~90-95% accuracy. Always validate unexpected discoveries.

**Q: Can I automate Discovery?**
A: Yes, via API. See API documentation for automation examples.

---

**Document Version**: 1.0
**Last Updated**: 2025-10-09
**For**: AssistedDiscovery v1.0
