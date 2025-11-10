# AssistedDiscovery - PlantUML Diagrams for Confluence

**Generated**: 2025-11-10
**Source**: System_Diagrams.md
**Purpose**: PlantUML macros for Confluence publishing
**Updates**: Added nested children support (recursive extraction, validation, UI display)

---

## 1. Pattern Extractor Flow (Backend: Discovery)

**Confluence Macro:**

```
{plantuml}
@startuml
!theme aws-orange

participant "Streamlit UI" as Client
participant "FastAPI" as API
participant "DiscoveryWorkflow" as DW
participant "XmlStreamingParser" as Parser
participant "LLMExtractor" as LLMExt
participant "PIIMasking" as PII
participant "BusinessIntelligence" as BI
participant "PatternGenerator" as PatGen
participant "Azure OpenAI\nGPT-4o" as Azure
database "Workspace\nSQLite DB" as WSDb

Client -> API: POST /api/v1/runs\n(kind=discovery, xml_file)
API -> DW: run_discovery(xml_file_path)

DW -> DW: detect_ndc_version_fast()
DW -> WSDb: _create_run_record(STARTED)
DW -> WSDb: Query NdcTargetPath\nfor version
WSDb --> DW: Return target paths
DW -> WSDb: Query NodeConfiguration\n(BA rules)
WSDb --> DW: Return BA configs

DW -> Parser: create_parser_for_version(target_paths)
Parser -> Parser: _build_path_trie()

loop For each XML subtree
    Parser -> Parser: stream_parse_targets()\nusing iterparse
    Parser --> DW: yield XmlSubtree

    DW -> LLMExt: extract_facts_from_subtree(subtree)

    LLMExt -> PII: mask_pii(xml_content)
    PII --> LLMExt: Masked XML

    LLMExt -> Azure: OpenAI API call with prompts
    note right
        Model: gpt-4o
        Max tokens: 16000
        Temperature: 0.0
    end note
    Azure --> LLMExt: Structured NodeFacts JSON

    LLMExt -> BI: enrich_fact(node_fact)
    BI -> BI: enrich_passenger_list()
    BI -> BI: Add PTC breakdown,\nrelationships
    BI --> LLMExt: Enriched NodeFact

    LLMExt --> DW: NodeFacts list

    DW -> WSDb: Persist NodeFacts\n(batch insert)
end

alt skip_pattern_generation=False
    DW -> PatGen: generate_patterns_from_run(run_id)

    PatGen -> WSDb: Query NodeFacts for run
    WSDb --> PatGen: NodeFacts list

    PatGen -> PatGen: Group by (node_type,\nsection_path)

    loop For each NodeFact group
        PatGen -> PatGen: _extract_decision_rule()
        PatGen -> PatGen: _get_child_structure_fingerprint()\n(recursive)
        note right
            Recursively extracts nested children
            e.g., Pax > Individual > {Birthdate, GivenName}
        end note
        PatGen -> PatGen: _normalize_child_structure_for_hash()
        PatGen -> PatGen: _generate_signature_hash(SHA-256)
        PatGen -> WSDb: find_or_create_pattern\n(dedup by signature)
        WSDb --> PatGen: Pattern created/updated
    end

    PatGen --> DW: Pattern generation complete
end

DW -> WSDb: _update_run_status(COMPLETED)
DW --> API: run_summary\n(run_id, stats)
API --> Client: {run_id, status,\nnode_facts_count,\npatterns_count}

note over Client, WSDb
    Client can query results
    via /api/v1/runs/{run_id}
end note

@enduml
{plantuml}
```

---

## 2. Discovery Flow (Backend: Identify)

**Confluence Macro:**

```
{plantuml}
@startuml
!theme aws-orange

participant "Streamlit UI" as Client
participant "FastAPI" as API
participant "IdentifyWorkflow" as IW
participant "DiscoveryWorkflow" as DW
participant "PatternGenerator" as PatGen
participant "Azure OpenAI\nGPT-4o" as Azure
database "Workspace\nSQLite DB" as WSDb

Client -> API: POST /api/v1/runs\n(kind=identify, xml_file)
API -> IW: run_identify(xml_file_path)

IW -> DW: run_discovery(\nskip_pattern_generation=True)
note right
    Reuse discovery workflow
    to extract NodeFacts
end note

DW -> DW: Extract NodeFacts\n(same as Discovery)
DW -> WSDb: Persist NodeFacts
DW --> IW: run_id, NodeFacts extracted

IW -> WSDb: Query all Patterns\nfor spec_version
WSDb --> IW: Pattern library\n(version-filtered)

IW -> WSDb: Query NodeFacts\nfor run_id
WSDb --> IW: NodeFacts to match

loop For each NodeFact
    IW -> IW: Filter patterns by node_type
    note right
        _normalize_node_type()
        Handle PaxList/PassengerList variants
    end note

    loop For each candidate Pattern
        IW -> IW: calculate_pattern_similarity()
        note right
            4-Factor Scoring:
            1. Node type (30%)
            2. Must-have attrs (30%)
            3. Child structure (25%)
            4. References (15%)
        end note
        IW -> IW: validate_nested_children()\n(recursive)
        note right
            Recursively validates nested child structures
            e.g., validates Pax > Individual > Birthdate
        end note
    end

    IW -> IW: Select best match\n(highest confidence)

    alt Confidence >= 95%
        IW -> WSDb: Create PatternMatch\n(EXACT_MATCH)
    else Confidence >= 85%
        IW -> WSDb: Create PatternMatch\n(HIGH_MATCH)
    else Confidence >= 70%
        IW -> WSDb: Create PatternMatch\n(PARTIAL_MATCH)
    else Confidence >= 50%
        IW -> WSDb: Create PatternMatch\n(LOW_MATCH)
    else Confidence > 0%
        IW -> WSDb: Create PatternMatch\n(NO_MATCH)
    else No candidates
        IW -> IW: Detect NEW_PATTERN
        IW -> PatGen: _create_new_pattern_from_fact()
        PatGen -> WSDb: Create new Pattern
        IW -> WSDb: Create PatternMatch\n(NEW_PATTERN, confidence=0)
    end
end

IW -> IW: _generate_gap_report()
note right
    Calculate:
    - Match rate by importance
    - Coverage statistics
    - Missing critical sections
    - Quality score
end note

IW -> WSDb: Update run status\n(COMPLETED)
IW -> WSDb: Store gap_analysis\nin metadata

IW --> API: run_summary with gap_report
API --> Client: {run_id, status,\nmatches, gap_analysis}

note over Client, WSDb
    Client displays:
    - Matched patterns with confidence
    - NEW_PATTERN discoveries
    - Gap analysis dashboard
end note

@enduml
{plantuml}
```

---

## 3. System Architecture Overview

**Confluence Macro:**

```
{plantuml}
@startuml
!theme aws-orange

package "Frontend Layer" {
    [Streamlit UI\nPort 8501] as UI

    package "UI Pages" {
        [0_Config] as Config
        [1_Node_Manager] as NodeMgr
        [2_Pattern_Extractor 🔬\n(Backend: DiscoveryWorkflow)] as PatExt
        [3_Pattern_Manager] as PatMgr
        [4_Discovery 🎯\n(Backend: IdentifyWorkflow)] as Disc
    }

    UI --> Config
    UI --> NodeMgr
    UI --> PatExt
    UI --> PatMgr
    UI --> Disc
}

package "API Layer" {
    [FastAPI Application\nPort 8000] as FastAPI
    [CORS Middleware] as CORS
    FastAPI --> CORS

    package "API Endpoints" {
        [Runs API\n/api/v1/runs] as RunsAPI
        [Patterns API\n/api/v1/patterns] as PatternsAPI
        [NodeFacts API\n/api/v1/node_facts] as NodeFactsAPI
        [Identify API\n/api/v1/identify] as IdentifyAPI
        [NodeConfigs API\n/api/v1/node-configs] as NodeConfigsAPI
        [Relationships API\n/api/v1/relationships] as RelationsAPI
        [LLM Config API\n/api/v1/llm-config] as LLMConfigAPI
    }
}

package "Service Layer" {
    package "Workflow Orchestrators" {
        [DiscoveryWorkflow\n(UI: Pattern Extractor)\nPattern Extraction] as DiscWF #10b981
        [IdentifyWorkflow\n(UI: Discovery)\nPattern Matching] as IdentWF #3b82f6
    }

    package "Core Services" {
        [XmlStreamingParser\nPath Trie Matching] as XMLParser
        [LLMExtractor\nAzure OpenAI] as LLMExt
        [PatternGenerator\nSHA-256 Signatures] as PatGen
        [PIIMasking\nSensitive Data] as PIIMask
        [BusinessIntelligence\nEnrichment] as BIEnrich
        [ParallelProcessor\nThread-Safe DB] as ParProc
    }

    package "Data Access" {
        [WorkspaceSessionFactory\nSQLite Management] as WSFactory #f59e0b
    }
}

cloud "External Services" {
    [Azure OpenAI\nGPT-4o\nModel: gpt-4o\nTemp: 0.0] as Azure #0078D4
}

database "Data Layer" {
    package "Workspace Databases" {
        database "default.db\nSQLite" as WS_Default
        database "airline1.db\nSQLite" as WS_Airline1
        database "airline2.db\nSQLite" as WS_Airline2
    }
    folder "Local Storage\nbackend/data/workspaces/" as Storage
}

package "Observability" {
    [Structured Logging\nstructlog] as Logger
    [Health Check\n/health] as Health
}

UI --> CORS : HTTP
CORS --> RunsAPI
CORS --> PatternsAPI
CORS --> NodeFactsAPI
CORS --> IdentifyAPI
CORS --> NodeConfigsAPI
CORS --> RelationsAPI
CORS --> LLMConfigAPI

RunsAPI --> DiscWF
RunsAPI --> IdentWF
PatternsAPI --> PatGen
IdentifyAPI --> IdentWF

DiscWF --> XMLParser
DiscWF --> LLMExt
DiscWF --> PatGen
DiscWF --> WSFactory

IdentWF --> DiscWF
IdentWF --> PatGen
IdentWF --> WSFactory

XMLParser --> WSFactory
LLMExt --> PIIMask
LLMExt --> BIEnrich
LLMExt --> Azure
LLMExt --> WSFactory

PatGen --> WSFactory
ParProc --> WSFactory

WSFactory --> WS_Default
WSFactory --> WS_Airline1
WSFactory --> WS_Airline2

WS_Default ..> Storage
WS_Airline1 ..> Storage
WS_Airline2 ..> Storage

FastAPI --> Logger
FastAPI --> Health
DiscWF --> Logger
IdentWF --> Logger
XMLParser --> Logger

@enduml
{plantuml}
```

---

## 4. Core Transactional Models (Class Diagram)

**Confluence Macro:**

```
{plantuml}
@startuml
!theme aws-orange

class Run {
    +String id <<PK>>
    +String kind
    +String status
    +String spec_version
    +String message_root
    +String airline_code
    +String airline_name
    +String filename
    +BigInteger file_size_bytes
    +String file_hash
    +DateTime started_at
    +DateTime finished_at
    +JSON metadata_json
    +Text error_details
    --
    +duration_seconds() : int
    +is_completed() : bool
}

class NodeFact {
    +BigInteger id <<PK>>
    +String run_id <<FK>>
    +String spec_version
    +String message_root
    +String section_path
    +String node_type
    +Integer node_ordinal
    +JSON fact_json
    +Boolean pii_masked
    +DateTime created_at
}

class Pattern {
    +BigInteger id <<PK>>
    +String spec_version
    +String message_root
    +String airline_code
    +String node_type
    +String section_path
    +String signature_hash <<UNIQUE>>
    +JSON decision_rule
    +Integer times_seen
    +DateTime first_seen
    +DateTime last_seen
    +Boolean is_active
    +JSON metadata_json
}

class PatternMatch {
    +BigInteger id <<PK>>
    +String run_id <<FK>>
    +BigInteger node_fact_id <<FK>>
    +BigInteger pattern_id <<FK>> (nullable)
    +String verdict
    +Decimal confidence_score
    +JSON metadata_json
    +DateTime created_at
}

class NodeRelationship {
    +BigInteger id <<PK>>
    +String run_id <<FK>>
    +BigInteger source_node_fact_id <<FK>>
    +String source_node_type
    +String source_section_path
    +BigInteger target_node_fact_id <<FK>> (nullable)
    +String target_node_type
    +String target_section_path
    +String reference_type
    +String reference_field
    +String reference_value
    +Boolean is_valid
    +Boolean was_expected
    +Decimal confidence
    +String discovered_by
    +String model_used
    +DateTime created_at
}

enum RunKind {
    DISCOVERY
    IDENTIFY
}

enum RunStatus {
    STARTED
    IN_PROGRESS
    COMPLETED
    FAILED
    PARTIAL_FAILURE
}

enum ImportanceLevel {
    CRITICAL
    HIGH
    MEDIUM
    LOW
}

Run "1" --> "*" NodeFact : contains
Run "1" --> "*" PatternMatch : has
Run "1" --> "*" NodeRelationship : defines
NodeFact "1" --> "0..1" PatternMatch : matched_by
NodeFact "1" --> "*" NodeRelationship : source_node
NodeFact "1" --> "*" NodeRelationship : target_node
Pattern "1" --> "*" PatternMatch : used_in

Run ..> RunKind
Run ..> RunStatus

@enduml
{plantuml}
```

---

## 5. Database Schema (ER Diagram)

**Confluence Macro:**

```
{plantuml}
@startuml
!theme aws-orange

entity "Run" as run {
    * id : string <<PK>>
    --
    * kind : string (discovery|identify)
    * status : string (started|completed|failed)
    spec_version : string (17.2|19.2|21.3)
    message_root : string (OrderViewRS)
    airline_code : string (SQ|AF|BA)
    airline_name : string
    filename : string
    file_size_bytes : bigint
    file_hash : string (SHA-256)
    started_at : datetime
    finished_at : datetime
    metadata_json : json
    error_details : text
}

entity "NodeFact" as node_fact {
    * id : bigint <<PK>>
    --
    * run_id : string <<FK>>
    spec_version : string
    message_root : string
    section_path : string
    node_type : string
    node_ordinal : int
    * fact_json : json (Extracted data)
    pii_masked : bool
    created_at : datetime
}

entity "Pattern" as pattern {
    * id : bigint <<PK>>
    --
    spec_version : string
    message_root : string
    airline_code : string
    node_type : string
    section_path : string
    * signature_hash : string <<UK>> (SHA-256)
    * decision_rule : json (Match criteria)
    times_seen : int
    first_seen : datetime
    last_seen : datetime
    is_active : bool
    metadata_json : json
}

entity "PatternMatch" as pattern_match {
    * id : bigint <<PK>>
    --
    * run_id : string <<FK>>
    * node_fact_id : bigint <<FK>>
    pattern_id : bigint <<FK>> (nullable for NEW_PATTERN)
    * verdict : string (EXACT|HIGH|PARTIAL|LOW|NO_MATCH|NEW_PATTERN)
    * confidence_score : decimal (0.0-1.0)
    metadata_json : json
    created_at : datetime
}

entity "NodeRelationship" as node_relationship {
    * id : bigint <<PK>>
    --
    * run_id : string <<FK>>
    * source_node_fact_id : bigint <<FK>>
    source_node_type : string
    source_section_path : string
    target_node_fact_id : bigint <<FK>> (nullable)
    target_node_type : string
    target_section_path : string
    * reference_type : string (pax_reference, segment_reference, etc.)
    reference_field : string
    reference_value : string
    is_valid : bool
    was_expected : bool
    confidence : decimal
    discovered_by : string
    model_used : string
    created_at : datetime
}

run ||--o{ node_fact : "contains"
run ||--o{ pattern_match : "has"
run ||--o{ node_relationship : "defines"
pattern ||--o{ pattern_match : "used_in"
node_fact ||--o| pattern_match : "matched_by"
node_fact ||--o{ node_relationship : "source"
node_fact ||--o{ node_relationship : "target"

@enduml
{plantuml}
```

---

## 6. Workspace Architecture

**Confluence Macro:**

```
{plantuml}
@startuml
!theme aws-orange

package "Frontend" {
    [Streamlit UI] as UI
    [Workspace Selector] as WSSelector
}

package "Backend API" {
    [FastAPI Server\nPort 8000] as FastAPI
    [WorkspaceSessionFactory] as WSFactory #f59e0b
}

package "Workspace Storage" {
    folder "backend/data/workspaces/" as DataDir

    package "default workspace" {
        database "default.db" as Default #10b981
        folder "uploads/" as DefaultUploads
    }

    package "SQ workspace" {
        database "SQ.db" as SQ #3b82f6
        folder "uploads/" as SQUploads
    }

    package "AF workspace" {
        database "AF.db" as AF #8b5cf6
        folder "uploads/" as AFUploads
    }

    package "BA workspace" {
        database "BA.db" as BA #ec4899
        folder "uploads/" as BAUploads
    }
}

note right of WSFactory
    Tables per Workspace:
    - runs
    - node_facts
    - patterns
    - pattern_matches
    - node_configurations
    - node_relationships
end note

UI --> WSSelector
WSSelector --> FastAPI : workspace: default
WSSelector --> FastAPI : workspace: SQ
WSSelector --> FastAPI : workspace: AF
WSSelector --> FastAPI : workspace: BA

FastAPI --> WSFactory

WSFactory --> Default : get_session: default
WSFactory --> SQ : get_session: SQ
WSFactory --> AF : get_session: AF
WSFactory --> BA : get_session: BA

Default --> DefaultUploads
SQ --> SQUploads
AF --> AFUploads
BA --> BAUploads

@enduml
{plantuml}
```

---

## 7. Pattern Matching Flow (Detailed)

**Confluence Macro:**

```
{plantuml}
@startuml
!theme aws-orange

start

:Upload New XML;

:Extract NodeFacts\n(via Discovery Workflow);

:Load Pattern Library\n(version-filtered);

partition "For Each NodeFact" {
    :Filter Patterns\nby node_type;

    partition "For Each Candidate Pattern" {
        :Calculate Similarity Score;

        note right
            4-Factor Scoring:
            - Node type: 30%
            - Must-have attrs: 30%
            - Child structure: 25%
            - References: 15%
        end note

        :Track Best Match;
    }

    if (Confidence >= 95%) then (yes)
        #10b981:EXACT_MATCH;
    elseif (Confidence >= 85%) then (yes)
        #fbbf24:HIGH_MATCH;
    elseif (Confidence >= 70%) then (yes)
        #f8d7da:PARTIAL_MATCH;
    elseif (Confidence >= 50%) then (yes)
        #f8d7da:LOW_MATCH;
    elseif (Confidence > 0%) then (yes)
        #ef4444:NO_MATCH;
    else (No candidates)
        #8b5cf6:NEW_PATTERN;
        :Create New Pattern;
    endif

    :Store PatternMatch;
}

:Generate Gap Report;

note right
    Calculate:
    - Coverage by importance
    - Missing critical sections
    - Quality score
    - Match rate statistics
end note

:Update Run Status;

:Return Results to UI;

stop

@enduml
{plantuml}
```

---

## Usage Instructions for Confluence

### Step 1: Insert PlantUML Macro

1. Edit your Confluence page
2. Type `/plantuml` or click Insert > Other Macros > PlantUML
3. Copy the PlantUML code (between `{plantuml}` and `{plantuml}`)
4. Paste into the macro editor
5. Click "Insert"

### Step 2: Diagram Naming

Recommended page structure:
```
Architecture Overview
├── 1. Pattern Extractor Flow
├── 2. Discovery Flow
├── 3. System Architecture
├── 4. Database Schema
├── 5. Workspace Architecture
└── 6. Pattern Matching Flow
```

### Step 3: Theme Customization

To change colors, modify the `!theme` directive:
- `!theme aws-orange` - Orange theme (current)
- `!theme bluegray` - Blue-gray professional
- `!theme plain` - Black and white
- `!theme cerulean-outline` - Blue outline style

### Step 4: Size Adjustment

Add scale parameter after `@startuml`:
```
@startuml
scale 1.5
...
@enduml
```

---

## Diagram Descriptions

### 1. Pattern Extractor Flow
**Purpose**: Shows how XML is processed to extract and store patterns
**Key Points**:
- Streaming XML parser (memory efficient)
- Azure OpenAI integration for extraction
- Pattern deduplication via signature hash
- PII masking for sensitive data

### 2. Discovery Flow
**Purpose**: Shows how new XML is validated against pattern library
**Key Points**:
- Reuses Discovery workflow for extraction
- 4-factor confidence scoring algorithm
- 6 verdict types (EXACT to NEW_PATTERN)
- Gap analysis for quality reporting

### 3. System Architecture
**Purpose**: Complete system component view
**Key Points**:
- 3-layer architecture (Frontend, API, Service)
- SQLite workspace isolation
- Azure OpenAI as external service
- Structured logging with structlog

### 4. Database Schema
**Purpose**: Entity-relationship diagram showing all tables
**Key Points**:
- Run → NodeFact relationship (1:N)
- Pattern → PatternMatch relationship (1:N)
- Transactional vs Configuration tables separated
- Foreign key relationships clearly marked

### 5. Workspace Architecture
**Purpose**: Shows multi-tenant workspace isolation
**Key Points**:
- Each workspace = separate SQLite database
- Complete data isolation between airlines
- Portable (copy .db file)
- On-demand database creation

### 6. Pattern Matching Flow
**Purpose**: Activity diagram for pattern matching logic
**Key Points**:
- Confidence threshold decision tree
- Color-coded match verdicts
- Gap report generation
- NEW_PATTERN auto-creation

---

## Export Tips

### For PDF/Word Export
1. Use `!theme plain` for better print quality
2. Add `scale 0.8` to fit on page
3. Remove color backgrounds for B&W printing

### For Presentations
1. Use `!theme cerulean-outline` for projector visibility
2. Increase `scale 1.5` for large screens
3. Split complex diagrams into multiple slides

### For Documentation
1. Keep `!theme aws-orange` for web viewing
2. Add notes with `note` keyword for context
3. Use `title` at top of diagram for captions

---

**End of PlantUML Diagrams**

*Generated from System_Diagrams.md for Confluence publishing*
*Last Updated: 2025-11-10*
*Includes: Nested children support (recursive extraction, validation, UI display)*
