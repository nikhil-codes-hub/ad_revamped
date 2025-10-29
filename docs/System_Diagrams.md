# AssistedDiscovery - System Diagrams

**Last Updated**: 2025-10-29
**Note**: All diagrams reflect the current implementation with SQLite workspace databases and Azure OpenAI GPT-4o

## ⚠️ Terminology Note

**UI vs Backend Naming**:
- **UI: "Pattern Extractor"** → Backend: `DiscoveryWorkflow` service
- **UI: "Discovery"** → Backend: `IdentifyWorkflow` service

This document uses **UI terminology** for user-facing descriptions but references actual backend class names for code accuracy.

## Table of Contents
1. [Pattern Extractor Flow (Backend: Discovery)](#pattern-extractor-flow-backend-discovery)
2. [Discovery Flow (Backend: Identify)](#discovery-flow-backend-identify)
3. [System Architecture Overview](#system-architecture-overview)
4. [Component Architecture](#component-architecture)
5. [Class Diagrams](#class-diagrams)
6. [Database Schema Relationships](#database-schema-relationships)
7. [Data Flow Diagram](#data-flow-diagram)
8. [Error Handling Flow](#error-handling-flow)
9. [Workspace Architecture](#workspace-architecture)

---

## Pattern Extractor Flow (Backend: Discovery)

**Purpose**: Extract patterns from airline XML files to build a pattern library.

**Backend Service**: `DiscoveryWorkflow` (code name: "discovery")
**UI Page**: 🔬 Pattern Extractor
**API Endpoint**: `/api/v1/runs` with `kind=discovery`

```mermaid
sequenceDiagram
    participant Client as Streamlit UI
    participant API as FastAPI
    participant DW as DiscoveryWorkflow
    participant Parser as XmlStreamingParser
    participant LLMExt as LLMExtractor
    participant PII as PIIMasking
    participant BI as BusinessIntelligence
    participant PatGen as PatternGenerator
    participant Azure as Azure OpenAI GPT-4o
    participant WSDb as Workspace SQLite DB

    Client->>API: POST /api/v1/runs (kind=discovery, xml_file)
    API->>DW: run_discovery(xml_file_path)

    DW->>DW: detect_ndc_version_fast()
    DW->>WSDb: _create_run_record(STARTED)
    DW->>WSDb: Query NdcTargetPath for version
    WSDb-->>DW: Return target paths
    DW->>WSDb: Query NodeConfiguration (BA rules)
    WSDb-->>DW: Return BA configs

    DW->>Parser: create_parser_for_version(target_paths)
    Parser->>Parser: _build_path_trie()

    loop For each XML subtree
        Parser->>Parser: stream_parse_targets() using iterparse
        Parser-->>DW: yield XmlSubtree

        DW->>LLMExt: extract_facts_from_subtree(subtree)

        LLMExt->>PII: mask_pii(xml_content)
        PII-->>LLMExt: Masked XML

        LLMExt->>Azure: OpenAI API call with prompts
        Note over LLMExt,Azure: Model: gpt-4o<br/>Max tokens: 4096<br/>Temperature: 0.0
        Azure-->>LLMExt: Structured NodeFacts JSON

        LLMExt->>BI: enrich_fact(node_fact)
        BI->>BI: enrich_passenger_list()
        BI->>BI: Add PTC breakdown, relationships
        BI-->>LLMExt: Enriched NodeFact

        LLMExt-->>DW: NodeFacts list

        DW->>WSDb: Persist NodeFacts (batch insert)
    end

    alt skip_pattern_generation=False
        DW->>PatGen: generate_patterns_from_run(run_id)

        PatGen->>WSDb: Query NodeFacts for run
        WSDb-->>PatGen: NodeFacts list

        PatGen->>PatGen: Group by (node_type, section_path)

        loop For each NodeFact group
            PatGen->>PatGen: _extract_decision_rule()
            PatGen->>PatGen: _generate_signature_hash(SHA-256)
            PatGen->>WSDb: find_or_create_pattern(dedup by signature)
            WSDb-->>PatGen: Pattern created/updated
        end

        PatGen-->>DW: Pattern generation complete
    end

    DW->>WSDb: _update_run_status(COMPLETED)
    DW-->>API: run_summary (run_id, stats)
    API-->>Client: {run_id, status, node_facts_count, patterns_count}

    Note over Client,WSDb: Client can query results via /api/v1/runs/{run_id}
```

## Discovery Flow (Backend: Identify)

**Purpose**: Discover differences in new airline XML by validating against known patterns.

**Backend Service**: `IdentifyWorkflow` (code name: "identify")
**UI Page**: 🎯 Discovery
**API Endpoint**: `/api/v1/runs` with `kind=identify`

```mermaid
sequenceDiagram
    participant Client as Streamlit UI
    participant API as FastAPI
    participant IW as IdentifyWorkflow
    participant DW as DiscoveryWorkflow
    participant PatGen as PatternGenerator
    participant Azure as Azure OpenAI GPT-4o
    participant WSDb as Workspace SQLite DB

    Client->>API: POST /api/v1/runs (kind=identify, xml_file)
    API->>IW: run_identify(xml_file_path)

    IW->>DW: run_discovery(skip_pattern_generation=True)
    Note over IW,DW: Reuse discovery workflow<br/>to extract NodeFacts

    DW->>DW: Extract NodeFacts (same as Discovery)
    DW->>WSDb: Persist NodeFacts
    DW-->>IW: run_id, NodeFacts extracted

    IW->>WSDb: Query all Patterns for spec_version
    WSDb-->>IW: Pattern library (version-filtered)

    IW->>WSDb: Query NodeFacts for run_id
    WSDb-->>IW: NodeFacts to match

    loop For each NodeFact
        IW->>IW: Filter patterns by node_type
        Note over IW: _normalize_node_type()<br/>Handle PaxList/PassengerList variants

        loop For each candidate Pattern
            IW->>IW: calculate_pattern_similarity()
            Note over IW: 4-Factor Scoring:<br/>1. Node type (30%)<br/>2. Must-have attrs (30%)<br/>3. Child structure (25%)<br/>4. References (15%)
        end

        IW->>IW: Select best match (highest confidence)

        alt Confidence >= 95%
            IW->>WSDb: Create PatternMatch (EXACT_MATCH)
        else Confidence >= 85%
            IW->>WSDb: Create PatternMatch (HIGH_MATCH)
        else Confidence >= 70%
            IW->>WSDb: Create PatternMatch (PARTIAL_MATCH)
        else Confidence >= 50%
            IW->>WSDb: Create PatternMatch (LOW_MATCH)
        else Confidence > 0%
            IW->>WSDb: Create PatternMatch (NO_MATCH)
        else No candidates
            IW->>IW: Detect NEW_PATTERN
            IW->>PatGen: _create_new_pattern_from_fact()
            PatGen->>WSDb: Create new Pattern
            IW->>WSDb: Create PatternMatch (NEW_PATTERN, confidence=0)
        end
    end

    IW->>IW: _generate_gap_report()
    Note over IW: Calculate:<br/>- Match rate by importance<br/>- Coverage statistics<br/>- Missing critical sections<br/>- Quality score

    IW->>WSDb: Update run status (COMPLETED)
    IW->>WSDb: Store gap_analysis in metadata

    IW-->>API: run_summary with gap_report
    API-->>Client: {run_id, status, matches, gap_analysis}

    Note over Client,WSDb: Client displays:<br/>- Matched patterns with confidence<br/>- NEW_PATTERN discoveries<br/>- Gap analysis dashboard
```

## System Architecture Overview

```mermaid
flowchart TB
    subgraph "Frontend Layer"
        UI[Streamlit UI<br/>Port 8501]
        subgraph "UI Pages"
            Config[0_Config]
            NodeMgr[1_Node_Manager]
            PatExt["2_Pattern_Extractor 🔬<br/>(Backend: DiscoveryWorkflow)"]
            PatMgr[3_Pattern_Manager]
            Disc["4_Discovery 🎯<br/>(Backend: IdentifyWorkflow)"]
        end
        UI --> Config
        UI --> NodeMgr
        UI --> PatExt
        UI --> PatMgr
        UI --> Disc
    end

    subgraph "API Layer"
        FastAPI[FastAPI Application<br/>Port 8000]
        CORS[CORS Middleware]
        FastAPI --> CORS

        subgraph "API Endpoints"
            RunsAPI["Runs API<br/>/api/v1/runs"]
            PatternsAPI["Patterns API<br/>/api/v1/patterns"]
            NodeFactsAPI["NodeFacts API<br/>/api/v1/node_facts"]
            IdentifyAPI["Identify API<br/>/api/v1/identify"]
            NodeConfigsAPI["NodeConfigs API<br/>/api/v1/node-configs"]
            RefTypesAPI["ReferenceTypes API<br/>/api/v1/reference-types"]
            RelationsAPI["Relationships API<br/>/api/v1/relationships"]
            LLMConfigAPI["LLM Config API<br/>/api/v1/llm-config"]
        end
    end

    subgraph "Service Layer"
        subgraph "Workflow Orchestrators"
            DiscWF["DiscoveryWorkflow<br/>(UI: Pattern Extractor)<br/>Pattern Extraction"]
            IdentWF["IdentifyWorkflow<br/>(UI: Discovery)<br/>Pattern Matching"]
        end

        subgraph "Core Services"
            XMLParser[XmlStreamingParser<br/>Path Trie Matching]
            LLMExt[LLMExtractor<br/>Azure OpenAI]
            PatGen[PatternGenerator<br/>SHA-256 Signatures]
            PIIMask[PIIMasking<br/>Sensitive Data]
            BIEnrich[BusinessIntelligence<br/>Enrichment]
            ParProc[ParallelProcessor<br/>Thread-Safe DB]
        end

        subgraph "Data Access"
            WSFactory[WorkspaceSessionFactory<br/>SQLite Management]
        end
    end

    subgraph "External Services"
        Azure[Azure OpenAI<br/>GPT-4o<br/>Model: gpt-4o<br/>Temp: 0.0]
    end

    subgraph "Data Layer"
        subgraph "Workspace Databases"
            WS_Default[(default.db<br/>SQLite)]
            WS_Airline1[(airline1.db<br/>SQLite)]
            WS_Airline2[(airline2.db<br/>SQLite)]
        end
        Storage["Local Storage<br/>backend/data/workspaces/"]
    end

    subgraph "Observability"
        Logger["Structured Logging<br/>structlog"]
        Health["Health Check<br/>/health"]
    end

    UI -->|HTTP| CORS
    CORS --> RunsAPI
    CORS --> PatternsAPI
    CORS --> NodeFactsAPI
    CORS --> IdentifyAPI
    CORS --> NodeConfigsAPI
    CORS --> RefTypesAPI
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

    WS_Default -.-> Storage
    WS_Airline1 -.-> Storage
    WS_Airline2 -.-> Storage

    FastAPI --> Logger
    FastAPI --> Health
    DiscWF --> Logger
    IdentWF --> Logger
    XMLParser --> Logger

    style Azure fill:#0078D4,color:#fff
    style DiscWF fill:#10b981,color:#fff
    style IdentWF fill:#3b82f6,color:#fff
    style WSFactory fill:#f59e0b,color:#fff
```

---

## Component Architecture

### Backend Component Diagram

```mermaid
graph TB
    subgraph "app/"
        subgraph "main.py"
            FastAPIApp[FastAPI Application<br/>- create_application<br/>- CORS middleware<br/>- Global exception handler]
        end

        subgraph "api/v1/"
            APIRouter[API Router]
            subgraph "endpoints/"
                RunsEP[runs.py<br/>Run management]
                PatternsEP[patterns.py<br/>Pattern CRUD]
                NodeFactsEP[node_facts.py<br/>NodeFact queries]
                IdentifyEP[identify.py<br/>Identify endpoint]
                NodeConfigsEP[node_configs.py<br/>BA configurations]
                RefTypesEP[reference_types.py<br/>Reference mgmt]
                RelationsEP[relationships.py<br/>Relationship queries]
                LLMConfigEP[llm_config.py<br/>LLM settings]
            end
        end

        subgraph "services/"
            DiscWF["discovery_workflow.py<br/>DiscoveryWorkflow<br/>(UI: Pattern Extractor)<br/>- run_discovery<br/>- get_run_summary"]
            IdentWF["identify_workflow.py<br/>IdentifyWorkflow<br/>(UI: Discovery)<br/>- run_identify<br/>- calculate_similarity<br/>- generate_gap_report"]
            XMLParse[xml_parser.py<br/>XmlStreamingParser<br/>- stream_parse_targets<br/>- detect_ndc_version]
            LLMExt[llm_extractor.py<br/>LLMExtractor<br/>- extract_facts<br/>- Azure/OpenAI client]
            PatGen[pattern_generator.py<br/>PatternGenerator<br/>- generate_patterns<br/>- signature_hash]
            BIEnrich[business_intelligence.py<br/>BusinessIntelligence<br/>- enrich_passenger_list<br/>- PTC breakdown]
            PIIMask[pii_masking.py<br/>PIIMasking<br/>- mask_pii]
            WSDb[workspace_db.py<br/>WorkspaceSessionFactory<br/>- get_session<br/>- init_engine]
            ParProc[parallel_processor.py<br/>ParallelProcessor<br/>- process_nodes_parallel]
            Utils[utils.py<br/>- normalize_iata_prefix<br/>- validation helpers]
        end

        subgraph "models/"
            Database[database.py<br/>SQLAlchemy Models:<br/>- Run<br/>- NodeFact<br/>- Pattern<br/>- PatternMatch<br/>- NodeConfiguration<br/>- NdcTargetPath<br/>- NdcPathAlias<br/>- AssociationFact<br/>- NodeRelationship]
            Schemas[schemas.py<br/>Pydantic Models:<br/>Request/Response DTOs]
        end

        subgraph "core/"
            Config[config.py<br/>Settings<br/>Environment vars]
            Logging[logging.py<br/>Structured logging<br/>setup_logging]
        end

        subgraph "prompts/"
            Prompts[__init__.py<br/>LLM Prompts:<br/>- System prompt<br/>- Container prompt<br/>- Item prompt]
        end
    end

    FastAPIApp --> APIRouter
    APIRouter --> RunsEP
    APIRouter --> PatternsEP
    APIRouter --> NodeFactsEP
    APIRouter --> IdentifyEP
    APIRouter --> NodeConfigsEP
    APIRouter --> RefTypesEP
    APIRouter --> RelationsEP
    APIRouter --> LLMConfigEP

    RunsEP --> DiscWF
    RunsEP --> IdentWF
    IdentifyEP --> IdentWF
    PatternsEP --> PatGen

    DiscWF --> XMLParse
    DiscWF --> LLMExt
    DiscWF --> PatGen
    DiscWF --> WSDb

    IdentWF --> DiscWF
    IdentWF --> PatGen
    IdentWF --> WSDb

    XMLParse --> WSDb
    LLMExt --> PIIMask
    LLMExt --> BIEnrich
    LLMExt --> Prompts
    LLMExt --> WSDb

    PatGen --> WSDb
    ParProc --> WSDb

    DiscWF --> Utils
    IdentWF --> Utils
    XMLParse --> Utils
    PatGen --> Utils

    WSDb --> Database
    RunsEP --> Schemas
    PatternsEP --> Schemas

    FastAPIApp --> Config
    FastAPIApp --> Logging
    DiscWF --> Logging
    IdentWF --> Logging

    style FastAPIApp fill:#3b82f6,color:#fff
    style DiscWF fill:#10b981,color:#fff
    style IdentWF fill:#3b82f6,color:#fff
    style Database fill:#f59e0b,color:#fff
    style WSDb fill:#f59e0b,color:#fff
```

---

## Class Diagrams

### Core Transactional Models

**Note**: These models represent the primary data entities with transactional relationships.

```mermaid
classDiagram
    class Run {
        +String id PK
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
        +duration_seconds() int
        +is_completed() bool
    }

    class NodeFact {
        +BigInteger id PK
        +String run_id FK
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
        +BigInteger id PK
        +String spec_version
        +String message_root
        +String airline_code
        +String node_type
        +String section_path
        +String signature_hash UNIQUE
        +JSON decision_rule
        +Integer times_seen
        +DateTime first_seen
        +DateTime last_seen
        +Boolean is_active
        +JSON metadata_json
    }

    class PatternMatch {
        +BigInteger id PK
        +String run_id FK
        +BigInteger node_fact_id FK
        +BigInteger pattern_id FK (nullable)
        +String verdict
        +Decimal confidence_score
        +JSON metadata_json
        +DateTime created_at
    }

    class AssociationFact {
        +BigInteger id PK
        +String run_id FK
        +String spec_version
        +String from_node_type
        +String to_node_type
        +String from_node_id
        +String to_node_id
        +String association_type
        +JSON metadata_json
        +DateTime created_at
    }

    class NodeRelationship {
        +BigInteger id PK
        +String run_id FK
        +String relationship_type
        +String parent_node_type
        +String child_node_type
        +String parent_node_id
        +String child_node_id
        +JSON metadata_json
        +DateTime created_at
    }

    Run "1" --> "*" NodeFact : contains
    Run "1" --> "*" PatternMatch : has
    Run "1" --> "*" AssociationFact : tracks
    Run "1" --> "*" NodeRelationship : defines
    NodeFact "1" --> "0..1" PatternMatch : matched_by
    Pattern "1" --> "*" PatternMatch : used_in
    Pattern "1" --> "*" Pattern : similar_to

    class RunKind {
        <<enumeration>>
        DISCOVERY
        IDENTIFY
    }

    class RunStatus {
        <<enumeration>>
        STARTED
        IN_PROGRESS
        COMPLETED
        FAILED
        PARTIAL_FAILURE
    }

    class ImportanceLevel {
        <<enumeration>>
        CRITICAL
        HIGH
        MEDIUM
        LOW
    }

    Run --> RunKind
    Run --> RunStatus
```

### Configuration & Lookup Models

**Note**: These models store system configuration and are queried by services, but have no foreign key relationships to transactional data.

```mermaid
classDiagram
    class NodeConfiguration {
        +BigInteger id PK
        +String spec_version
        +String message_root
        +String airline_code (nullable)
        +String section_path
        +String node_type
        +JSON extraction_config
        +Boolean enabled
        +String created_by
        +DateTime created_at
        +DateTime updated_at
    }

    class NdcTargetPath {
        +Integer id PK
        +String spec_version
        +String message_root
        +Text path_local
        +String extractor_key
        +Boolean is_required
        +String importance
        +JSON constraints_json
        +Text notes
        +DateTime created_at
        +DateTime updated_at
    }

    class NdcPathAlias {
        +Integer id PK
        +String from_spec_version
        +String from_message_root
        +Text from_path_local
        +String to_spec_version
        +String to_message_root
        +Text to_path_local
        +Boolean is_bidirectional
        +String reason
        +DateTime created_at
    }

    class ImportanceLevel {
        <<enumeration>>
        CRITICAL
        HIGH
        MEDIUM
        LOW
    }

    NdcTargetPath --> ImportanceLevel

    note for NodeConfiguration "Actively used: 97 configurations\nQueried by DiscoveryWorkflow\nto control node extraction"

    note for NdcTargetPath "Fallback mechanism (currently unused)\nTable exists but empty (0 rows)\nHardcoded paths used instead"

    note for NdcPathAlias "Cross-version path mapping\nSupports NDC version migration"
```

### Service Layer Classes

```mermaid
classDiagram
    class DiscoveryWorkflow {
        <<UI: Pattern Extractor>>
        -Session db_session
        -Optional~str~ message_root
        +__init__(db_session)
        +run_discovery(xml_file_path, skip_pattern_generation) Dict
        +get_run_summary(run_id) Dict
        -_calculate_file_hash(file_path) str
        -_get_target_paths_from_db(spec_version, message_root) List
        -_get_node_configurations(spec_version, message_root, airline_code) Dict
        -_create_run_record(kind, metadata) Run
        -_update_run_status(run_id, status, error_details)
        -_process_subtree(subtree, run_id) List~NodeFact~
    }

    class IdentifyWorkflow {
        <<UI: Discovery>>
        -Session db_session
        -DiscoveryWorkflow discovery
        -PatternGenerator pattern_gen
        +__init__(db_session)
        +run_identify(xml_file_path) Dict
        +calculate_pattern_similarity(node_fact, pattern_rule) float
        -_normalize_node_type(node_type) str
        -_match_node_facts_to_patterns(run_id, patterns) List
        -_generate_gap_report(run_id, pattern_matches) Dict
        -_create_new_pattern_from_fact(node_fact) Pattern
    }

    class XmlStreamingParser {
        -List target_paths
        -PathTrieNode path_trie
        -NdcVersionInfo version_info
        +__init__(target_paths)
        +stream_parse_targets(xml_file_path) Iterator~XmlSubtree~
        +detect_ndc_version(xml_file_path) NdcVersionInfo
        -_build_path_trie()
        -_extract_subtree(element, path) XmlSubtree
        -_is_target_path(path) bool
    }

    class LLMExtractor {
        -AsyncClient client
        -str model
        -int max_tokens
        -float temperature
        -str provider
        +__init__()
        +extract_facts_from_subtree(subtree) LLMExtractionResult
        -_init_client()
        -_call_llm_async(prompt, xml_content) Dict
        -_parse_llm_response(response) List~NodeFact~
    }

    class PatternGenerator {
        -Session db_session
        +__init__(db_session)
        +generate_patterns_from_run(run_id) List~Pattern~
        +find_or_create_pattern(decision_rule, metadata) Pattern
        +generate_signature_hash(decision_rule) str
        -_extract_decision_rule(node_facts) Dict
        -_normalize_path(path, message_root) str
        -_extract_required_attributes(fact_json) List
        -_extract_optional_attributes(facts_group) List
        -_get_child_structure_fingerprint(children) Dict
    }

    class BusinessIntelligenceEnricher {
        +enrich_fact(fact, context) Dict
        +enrich_passenger_list(fact) Dict
        +enrich_contact_info_list(fact) Dict
        +enrich_baggage_list(fact) Dict
        +enrich_service_list(fact) Dict
        -_extract_passenger_relationships(children) List
        -_count_by_ptc(children) Dict
    }

    class PIIMasking {
        -List pii_patterns
        +mask_pii(text) str
        +is_pii(text) bool
        -_mask_email(text) str
        -_mask_phone(text) str
        -_mask_credit_card(text) str
    }

    class WorkspaceSessionFactory {
        -str workspace_name
        -Path db_dir
        -Path db_path
        -Engine engine
        -SessionLocal SessionLocal
        +__init__(workspace_name)
        +get_session() Session
        -_get_db_dir() Path
        -_init_engine()
        -_fix_sqlite_autoincrement()
    }

    DiscoveryWorkflow --> XmlStreamingParser : uses
    DiscoveryWorkflow --> LLMExtractor : uses
    DiscoveryWorkflow --> PatternGenerator : uses
    DiscoveryWorkflow --> WorkspaceSessionFactory : uses

    IdentifyWorkflow --> DiscoveryWorkflow : delegates to
    IdentifyWorkflow --> PatternGenerator : uses
    IdentifyWorkflow --> WorkspaceSessionFactory : uses

    LLMExtractor --> PIIMasking : uses
    LLMExtractor --> BusinessIntelligenceEnricher : uses

    XmlStreamingParser --> WorkspaceSessionFactory : queries config
```

---

## Database Schema Relationships

### Transactional Data Schema

**Note**: Shows foreign key relationships between core entities.

```mermaid
erDiagram
    Run ||--o{ NodeFact : "contains"
    Run ||--o{ PatternMatch : "has"
    Run ||--o{ AssociationFact : "tracks"
    Run ||--o{ NodeRelationship : "defines"

    Pattern ||--o{ PatternMatch : "used_in"
    NodeFact ||--o| PatternMatch : "matched_by"

    Run {
        string id PK
        string kind "discovery|identify"
        string status "started|completed|failed"
        string spec_version "17.2|19.2|21.3"
        string message_root "OrderViewRS"
        string airline_code "SQ|AF|BA"
        string airline_name
        string filename
        bigint file_size_bytes
        string file_hash "SHA-256"
        datetime started_at
        datetime finished_at
        json metadata_json
        text error_details
    }

    NodeFact {
        bigint id PK
        string run_id FK
        string spec_version
        string message_root
        string section_path
        string node_type
        int node_ordinal
        json fact_json "Extracted data"
        bool pii_masked
        datetime created_at
    }

    Pattern {
        bigint id PK
        string spec_version
        string message_root
        string airline_code
        string node_type
        string section_path
        string signature_hash UK "SHA-256"
        json decision_rule "Match criteria"
        int times_seen
        datetime first_seen
        datetime last_seen
        bool is_active
        json metadata_json
    }

    PatternMatch {
        bigint id PK
        string run_id FK
        bigint node_fact_id FK
        bigint pattern_id FK "nullable for NEW_PATTERN"
        string verdict "EXACT|HIGH|PARTIAL|LOW|NO_MATCH|NEW_PATTERN"
        decimal confidence_score "0.0-1.0"
        json metadata_json
        datetime created_at
    }

    AssociationFact {
        bigint id PK
        string run_id FK
        string spec_version
        string from_node_type
        string to_node_type
        string from_node_id
        string to_node_id
        string association_type "reference|link"
        json metadata_json
        datetime created_at
    }

    NodeRelationship {
        bigint id PK
        string run_id FK
        string relationship_type "adult_infant|pax_contact"
        string parent_node_type
        string child_node_type
        string parent_node_id
        string child_node_id
        json metadata_json
        datetime created_at
    }
```

### Configuration & Lookup Schema

**Note**: These tables store system configuration with no foreign key relationships. Queried by services but not related to transactional data.

```mermaid
erDiagram
    NodeConfiguration {
        bigint id PK
        string spec_version
        string message_root
        string airline_code "nullable - global if null"
        string section_path
        string node_type
        json extraction_config "BA rules"
        bool enabled "97 active configs"
        string created_by
        datetime created_at
        datetime updated_at
    }

    NdcTargetPath {
        int id PK
        string spec_version
        string message_root
        text path_local "XPath pattern"
        string extractor_key "template or generic_llm"
        bool is_required
        string importance "critical, high, medium, low"
        json constraints_json
        text notes
        datetime created_at
        datetime updated_at
    }

    NdcPathAlias {
        int id PK
        string from_spec_version
        string from_message_root
        text from_path_local
        string to_spec_version
        string to_message_root
        text to_path_local
        bool is_bidirectional
        string reason "Version migration mapping"
        datetime created_at
    }

    ReferenceType {
        bigint id PK
        string type_name UK "e.g., pax_reference"
        string description
        json metadata_json
        datetime created_at
    }
```

**Usage Notes**:
- **NodeConfiguration**: Actively used (97 rows). Queried by `DiscoveryWorkflow._should_extract_node()` to control node extraction. Has API: `/api/v1/node-configs`.
- **NdcTargetPath**: Fallback mechanism (0 rows - empty). Code queries it but uses hardcoded paths. Designed for dynamic configuration.
- **NdcPathAlias**: Cross-version path mapping. Supports NDC version migration scenarios.
- **ReferenceType**: Lookup table for relationship types used by `NodeRelationship`.

---

## Data Flow Diagram

### Pattern Extractor Data Flow (Backend: Discovery)

```mermaid
flowchart LR
    subgraph "Input"
        XML["NDC XML File<br/>17.2/19.2/21.3"]
        ConfigDB[(Configuration DB<br/>NdcTargetPath<br/>NodeConfiguration)]
    end

    subgraph "XML Processing"
        Detect[Version Detection<br/>detect_ndc_version_fast]
        Parser[Streaming Parser<br/>Path Trie Matching]
        Subtree[XML Subtrees<br/>4KB chunks]
    end

    subgraph "Extraction & Enrichment"
        PIIMask[PII Masking<br/>Email, Phone, CC]
        LLMExt[Azure OpenAI<br/>GPT-4o Extraction]
        BIEnrich[Business Intelligence<br/>PTC, Relationships]
        NodeFacts[NodeFacts<br/>Structured JSON]
    end

    subgraph "Pattern Generation"
        Group[Group by<br/>node_type + section]
        DecRule[Extract Decision Rule<br/>must_have/optional attrs]
        SigHash[Generate Signature<br/>SHA-256 hash]
        Dedup[Deduplicate<br/>by signature_hash]
    end

    subgraph "Storage"
        RunDB[(Run<br/>Metadata)]
        NodeDB[(NodeFact<br/>Extracted Data)]
        PatternDB[(Pattern<br/>Decision Rules)]
    end

    subgraph "Output"
        Summary[Run Summary<br/>Stats & Metrics]
        Report[Pattern Report<br/>Discovered Patterns]
    end

    XML --> Detect
    ConfigDB --> Parser
    Detect --> Parser
    Parser --> Subtree

    Subtree --> PIIMask
    PIIMask --> LLMExt
    LLMExt --> BIEnrich
    BIEnrich --> NodeFacts

    NodeFacts --> NodeDB
    NodeFacts --> Group

    Group --> DecRule
    DecRule --> SigHash
    SigHash --> Dedup
    Dedup --> PatternDB

    Detect --> RunDB
    NodeDB --> Summary
    PatternDB --> Report

    style LLMExt fill:#0078D4,color:#fff
    style PatternDB fill:#10b981,color:#fff
    style NodeDB fill:#3b82f6,color:#fff
```

### Discovery Data Flow (Backend: Identify)

```mermaid
flowchart LR
    subgraph "Input"
        XML[New NDC XML<br/>To Validate]
        PatternLib[(Pattern Library<br/>Version-Filtered)]
    end

    subgraph "NodeFact Extraction"
        DiscWF[Discovery Workflow<br/>skip_pattern_generation=True]
        NodeFacts[Extracted NodeFacts]
    end

    subgraph "Pattern Matching"
        Filter[Filter by<br/>node_type]
        CalcSim[Calculate Similarity<br/>4-Factor Scoring]
        Score[Confidence Score<br/>0.0 - 1.0]
    end

    subgraph "Verdict Assignment"
        V95["EXACT_MATCH<br/>≥95%"]
        V85["HIGH_MATCH<br/>≥85%"]
        V70["PARTIAL_MATCH<br/>≥70%"]
        V50["LOW_MATCH<br/>≥50%"]
        V0["NO_MATCH<br/><50%"]
        VNew["NEW_PATTERN<br/>No candidates"]
    end

    subgraph "Gap Analysis"
        Coverage[Coverage by<br/>Importance Level]
        Missing[Missing Critical<br/>Sections]
        Quality[Quality Score<br/>Match Rate]
    end

    subgraph "Storage"
        MatchDB[(PatternMatch<br/>Verdict + Confidence)]
        NewPatternDB[(New Patterns<br/>Auto-Created)]
    end

    subgraph "Output"
        GapReport[Gap Report<br/>Quality Dashboard]
        MatchReport[Match Report<br/>Pattern Coverage]
    end

    XML --> DiscWF
    DiscWF --> NodeFacts

    NodeFacts --> Filter
    PatternLib --> Filter
    Filter --> CalcSim
    CalcSim --> Score

    Score --> V95
    Score --> V85
    Score --> V70
    Score --> V50
    Score --> V0
    Score --> VNew

    V95 --> MatchDB
    V85 --> MatchDB
    V70 --> MatchDB
    V50 --> MatchDB
    V0 --> MatchDB
    VNew --> NewPatternDB
    VNew --> MatchDB

    MatchDB --> Coverage
    MatchDB --> Missing
    MatchDB --> Quality

    Coverage --> GapReport
    Missing --> GapReport
    Quality --> GapReport

    MatchDB --> MatchReport
    NewPatternDB --> MatchReport

    style V95 fill:#10b981,color:#fff
    style V85 fill:#fbbf24,color:#000
    style V0 fill:#ef4444,color:#fff
    style VNew fill:#8b5cf6,color:#fff
```

## Error Handling Flow

```mermaid
flowchart TD
    Start[Process XML Subtree]

    subgraph "XML Parsing"
        ParseXML{XML Parse<br/>Success?}
        XMLError[Log XML Parse Error<br/>Skip Subtree]
    end

    subgraph "Version Detection"
        DetectVer{Version<br/>Detected?}
        UnknownVer[Log Unknown Version<br/>Use Default Paths]
    end

    subgraph "LLM Extraction"
        CallLLM[Call Azure OpenAI]
        LLMError{LLM Error<br/>Type?}

        Timeout[Timeout Error<br/>120s exceeded]
        RateLimit[Rate Limit<br/>429 error]
        TokenLimit[Token Limit<br/>Context too large]
        InvalidResp[Invalid JSON<br/>Parse failure]
        APIError[API Error<br/>500/503]
    end

    subgraph "Retry Logic"
        RetryCount{Retry Count<br/>< 3?}
        ExpBackoff[Exponential Backoff<br/>2^n seconds]
        RetryLLM[Retry LLM Call]
    end

    subgraph "Fallback Handling"
        TemplateAvail{Template<br/>Extractor<br/>Available?}
        UseTemplate[Use Template<br/>Extraction]
        SkipSubtree[Skip Subtree<br/>Log Warning]
    end

    subgraph "Result Processing"
        ValidateJSON{Valid JSON<br/>Structure?}
        RepairJSON[Repair JSON<br/>Remove invalid chars]
        EnrichFacts[Enrich with BI]
        StoreFacts[Store NodeFacts]
    end

    subgraph "Run Status"
        CheckCritical{Critical<br/>Section<br/>Failed?}
        PartialFailure[Mark Run as<br/>PARTIAL_FAILURE]
        CompletedOK[Mark Run as<br/>COMPLETED]
        Failed[Mark Run as<br/>FAILED]
    end

    Start --> ParseXML
    ParseXML -->|Success| DetectVer
    ParseXML -->|Failure| XMLError --> CheckCritical

    DetectVer -->|Success| CallLLM
    DetectVer -->|Failure| UnknownVer --> CallLLM

    CallLLM --> LLMError
    LLMError -->|No Error| ValidateJSON
    LLMError -->|Timeout| RetryCount
    LLMError -->|Rate Limit| RetryCount
    LLMError -->|Token Limit| TemplateAvail
    LLMError -->|Invalid Response| RetryCount
    LLMError -->|API Error| RetryCount

    RetryCount -->|Yes| ExpBackoff
    RetryCount -->|No| TemplateAvail

    ExpBackoff --> RetryLLM
    RetryLLM --> CallLLM

    TemplateAvail -->|Yes| UseTemplate
    TemplateAvail -->|No| SkipSubtree

    UseTemplate --> StoreFacts
    SkipSubtree --> CheckCritical

    ValidateJSON -->|Valid| EnrichFacts
    ValidateJSON -->|Invalid| RepairJSON
    RepairJSON --> EnrichFacts

    EnrichFacts --> StoreFacts
    StoreFacts --> Start

    CheckCritical -->|Yes| Failed
    CheckCritical -->|No| PartialFailure
    StoreFacts -->|All Subtrees Done| CompletedOK

    style Failed fill:#ef4444,color:#fff
    style PartialFailure fill:#fbbf24,color:#000
    style CompletedOK fill:#10b981,color:#fff
    style CallLLM fill:#0078D4,color:#fff
```

---

## Workspace Architecture

### Workspace Isolation Design

```mermaid
flowchart TB
    subgraph "Frontend"
        UI[Streamlit UI]
        WSSelector[Workspace Selector]
    end

    subgraph "Backend API"
        FastAPI[FastAPI Server<br/>Port 8000]
        WSFactory[WorkspaceSessionFactory]
    end

    subgraph "Workspace Storage"
        DataDir["backend/data/workspaces/"]

        subgraph "default workspace"
            Default[default.db]
            DefaultUploads["uploads/"]
        end

        subgraph "SQ workspace"
            SQ[SQ.db]
            SQUploads["uploads/"]
        end

        subgraph "AF workspace"
            AF[AF.db]
            AFUploads["uploads/"]
        end

        subgraph "BA workspace"
            BA[BA.db]
            BAUploads["uploads/"]
        end
    end

    subgraph "Database Schema (Each Workspace)"
        Tables[Tables per Workspace:<br/>- runs<br/>- node_facts<br/>- patterns<br/>- pattern_matches<br/>- node_configurations<br/>- ndc_target_paths<br/>- ndc_path_aliases<br/>- association_facts<br/>- node_relationships]
    end

    UI --> WSSelector
    WSSelector -->|workspace: default| FastAPI
    WSSelector -->|workspace: SQ| FastAPI
    WSSelector -->|workspace: AF| FastAPI
    WSSelector -->|workspace: BA| FastAPI

    FastAPI --> WSFactory

    WSFactory -->|get_session: default| Default
    WSFactory -->|get_session: SQ| SQ
    WSFactory -->|get_session: AF| AF
    WSFactory -->|get_session: BA| BA

    Default -.-> Tables
    SQ -.-> Tables
    AF -.-> Tables
    BA -.-> Tables

    Default --> DefaultUploads
    SQ --> SQUploads
    AF --> AFUploads
    BA --> BAUploads

    style WSFactory fill:#f59e0b,color:#fff
    style Default fill:#10b981,color:#fff
    style SQ fill:#3b82f6,color:#fff
    style AF fill:#8b5cf6,color:#fff
    style BA fill:#ec4899,color:#fff
```

### Workspace Characteristics

**Complete Isolation**:
- Each workspace has its own SQLite database file
- No shared data between workspaces
- Patterns are workspace-specific (airline-specific patterns)
- Runs and NodeFacts are scoped to workspace

**Use Cases**:
1. **default**: Generic patterns, multi-airline testing
2. **SQ**: Singapore Airlines patterns and runs
3. **AF**: Air France patterns and runs
4. **BA**: British Airways patterns and runs

**Advantages**:
- Data isolation for different clients/airlines
- Pattern libraries don't interfere
- Easy backup/restore per workspace
- Portable (copy .db file)
- No cross-workspace queries (security)

**Database Initialization**:
- Databases created on-demand when workspace is first accessed
- Schema automatically created via SQLAlchemy `Base.metadata.create_all()`
- Foreign key constraints enabled via PRAGMA
- AUTOINCREMENT fixed for SQLite compatibility

---

## Storage Structure

### Directory Layout

```
ad/
├── backend/
│   ├── data/
│   │   └── workspaces/          # Workspace databases
│   │       ├── default.db       # Default workspace SQLite
│   │       ├── SQ.db           # Singapore Airlines workspace
│   │       ├── AF.db           # Air France workspace
│   │       └── BA.db           # British Airways workspace
│   │
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── api/                 # API endpoints
│   │   ├── services/            # Business logic
│   │   ├── models/              # Data models
│   │   ├── core/                # Config & logging
│   │   └── prompts/             # LLM prompts
│   │
│   └── tests/
│       ├── unit/                # Unit tests
│       └── integration/         # Integration tests
│
├── frontend/
│   └── streamlit_ui/
│       ├── AssistedDiscovery.py # Main Streamlit app
│       ├── pages/               # UI pages
│       │   ├── 0_Config.py
│       │   ├── 1_Node_Manager.py
│       │   ├── 2_Pattern_Extractor.py  # Pattern extraction (uses DiscoveryWorkflow)
│       │   ├── 3_Pattern_Manager.py
│       │   └── 4_Discovery.py          # Pattern validation (uses IdentifyWorkflow)
│       └── utils/               # UI utilities
│
└── docs/                        # Documentation
    ├── System_Diagrams.md       # This file
    ├── CLAUDE.md                # Project context
    ├── README.md                # Quick start
    └── ...
```

### Database File Structure

Each workspace SQLite database contains:

```
workspace.db (SQLite)
├── runs                    # Processing runs (discovery/identify)
├── node_facts              # Extracted XML node information
├── patterns                # Learned patterns (signature_hash unique)
├── pattern_matches         # Pattern matching results
├── node_configurations     # BA-configured extraction rules
├── ndc_target_paths        # NDC version target paths
├── ndc_path_aliases        # Cross-version path aliases
├── association_facts       # Cross-references between nodes
└── node_relationships      # Business relationships (e.g., adult-infant)
```

**File Sizes** (typical):
- Empty database: ~100 KB
- After 1 discovery run (10 MB XML): ~5-10 MB
- After 100 patterns generated: ~2-3 MB
- After 10 identify runs: ~15-20 MB

**Backup Strategy**:
- Simple: Copy `.db` file
- Recommended: `sqlite3 workspace.db .dump > backup.sql`
- Cloud sync compatible (Dropbox, Google Drive)

---

## Performance Characteristics

### Memory Usage

**XML Streaming Parser**:
- Memory-bounded: Processes 4KB subtrees
- Large files (100MB+) use constant memory ~500MB
- No full document load into memory

**LLM Extraction**:
- Per-subtree extraction: ~1-5 MB context
- Azure OpenAI limits: 128K tokens input
- Batch processing: 10-20 subtrees concurrently

**Database**:
- SQLite cache: ~2GB default
- Connection pool: StaticPool (single connection)
- Write batch size: 50-100 NodeFacts per transaction

### Processing Speed

**Typical Performance** (measured):
- Small XML (1 MB): 30-60 seconds
- Medium XML (10 MB): 5-8 minutes
- Large XML (50 MB): 20-30 minutes

**Bottlenecks**:
1. Azure OpenAI API calls (rate limits, latency)
2. JSON parsing and validation
3. Database write transactions

**Optimization Strategies**:
- Parallel subtree processing (4-8 workers)
- Batch database inserts
- Connection pooling
- Response caching (future)

### Cost Estimation

**Azure OpenAI Costs** (GPT-4o):
- Input tokens: $0.005 per 1K tokens
- Output tokens: $0.015 per 1K tokens
- Average: $0.50 - $2.00 per 10 MB XML
- Discovery runs (IdentifyWorkflow): $0.10 - $0.50 per run (fewer LLM calls)

**Storage Costs**:
- SQLite: Free (local storage)
- Cloud backup: Depends on provider
- Average workspace size: 50-200 MB

---

## Summary

This document provides comprehensive architectural diagrams for the AssistedDiscovery system, including:

✅ **Sequence Diagrams**: Pattern Extractor and Discovery workflows with actual service calls
✅ **System Architecture**: Complete component view with FastAPI, services, and Azure OpenAI
✅ **Component Diagrams**: Backend structure with all modules and dependencies
✅ **Class Diagrams**: Data models and service classes with methods
✅ **Database Schema**: ER diagrams showing all relationships
✅ **Data Flow**: Separate flows for Pattern Extractor and Discovery processes
✅ **Error Handling**: Comprehensive error handling with retry logic
✅ **Workspace Architecture**: SQLite-based isolation design
✅ **Performance Notes**: Memory, speed, and cost characteristics

**Key Technologies**:
- **Backend**: FastAPI, SQLAlchemy, lxml, Azure OpenAI GPT-4o
- **Frontend**: Streamlit
- **Database**: SQLite (workspace-based isolation)
- **LLM**: Azure OpenAI GPT-4o (not OpenAI)
- **Logging**: structlog

**Last Updated**: 2025-10-29
**Reflects**: Current implementation in `ad/` codebase