# AssistedDiscovery - System Diagrams

## Discovery Flow Sequence Diagram

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant JobOrch as Job Orchestrator
    participant Parser as XML Parser
    participant Extractor
    participant LLM as LLM Gateway
    participant Cache
    participant DB

    Client->>API: POST /v1/runs?kind=discovery
    API->>JobOrch: Create discovery job
    JobOrch->>DB: Insert run record (STARTED)

    JobOrch->>Parser: Parse XML file
    Parser->>Cache: Load target paths & aliases
    Cache-->>Parser: Return cached targets

    loop For each XML section
        Parser->>Parser: Stream parse with iterparse
        Parser->>Extractor: Extract from matched subtree

        alt Template extractor available
            Extractor->>Extractor: Apply template rules
        else Generic LLM extractor
            Extractor->>LLM: Extract NodeFacts (with PII masking)
            LLM-->>Extractor: Return structured NodeFacts
        end

        Extractor->>DB: Persist NodeFacts

        Note over Extractor,LLM: Micro-batch NodeFacts (3-6 per call)
        Extractor->>LLM: Discover patterns from NodeFact batch
        LLM-->>Extractor: Return candidate patterns

        Extractor->>Extractor: Normalize & generate signature_hash
        Extractor->>DB: Upsert patterns (dedup by signature)
    end

    JobOrch->>DB: Update run status (COMPLETED)
    JobOrch-->>API: Job completion notification
    API-->>Client: Return run_id and status

    Client->>API: GET /v1/runs/{run_id}/report
    API->>DB: Query patterns and metrics
    DB-->>API: Return discovery report
    API-->>Client: Return discovery results
```

## Identify Flow Sequence Diagram

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant JobOrch as Job Orchestrator
    participant Parser as XML Parser
    participant Extractor
    participant Retriever
    participant LLM as LLM Gateway
    participant DB

    Client->>API: POST /v1/runs?kind=identify
    API->>JobOrch: Create identify job
    JobOrch->>DB: Insert run record (STARTED)

    JobOrch->>Parser: Parse XML file
    loop For each XML section
        Parser->>Extractor: Extract NodeFacts
        Extractor->>DB: Persist NodeFacts

        loop For each NodeFact
            Extractor->>Retriever: Get Top-K candidate patterns
            Retriever->>DB: Query patterns (cheap similarity)
            DB-->>Retriever: Return ranked candidates

            Retriever->>Retriever: Apply hard constraints (decision_rule)

            alt Candidates pass constraints
                Retriever->>LLM: Classify NodeFact vs candidates
                LLM-->>Retriever: Return {pattern_id, confidence}

                alt Confidence > threshold
                    Retriever->>DB: Store pattern_match
                else
                    Note over Retriever: Mark as unmatched
                end
            else
                Note over Retriever: No valid candidates
            end
        end
    end

    JobOrch->>JobOrch: Generate Gap Report
    Note over JobOrch: Coverage analysis, missing sections, violations

    JobOrch->>DB: Update run status (COMPLETED)
    JobOrch-->>API: Job completion notification
    API-->>Client: Return run_id and status

    Client->>API: GET /v1/runs/{run_id}/report
    API->>DB: Query matches and gap analysis
    DB-->>API: Return identify report
    API-->>Client: Return identification results
```

## System Architecture Flowchart

```mermaid
flowchart TD
    subgraph "Client Layer"
        UI[Analyst UI]
        API_Client[API Client]
    end

    subgraph "API Gateway"
        LB[Load Balancer]
        Auth[Authentication]
        Rate[Rate Limiting]
    end

    subgraph "Application Layer"
        API[REST API]
        JobOrch[Job Orchestrator]

        subgraph "Worker Pool"
            DW[Discovery Workers]
            IW[Identify Workers]
            LW[Large XML Workers]
        end
    end

    subgraph "Core Services"
        Parser[XML Stream Parser]

        subgraph "Extractors"
            TE[Template Extractor]
            GE[Generic LLM Extractor]
        end

        Retriever[Pattern Retriever]
        Reporter[Report Builder]
    end

    subgraph "External Services"
        LLM_API[Azure OpenAI<br/>GPT-4o]
        ObjectStore[Local Storage<br/>workspaces/]
    end

    subgraph "Data Layer"
        subgraph "Workspace DBs"
            WS1[(workspace1.db<br/>SQLite)]
            WS2[(workspace2.db<br/>SQLite)]
            WS3[(workspace3.db<br/>SQLite)]
        end
        Note[Each workspace has<br/>isolated database]
    end

    subgraph "Monitoring"
        Metrics[Metrics Collection]
        Logs[Structured Logging]
        Alerts[Alerting System]
    end

    UI --> LB
    API_Client --> LB
    LB --> Auth
    Auth --> Rate
    Rate --> API

    API --> JobOrch
    JobOrch --> DW
    JobOrch --> IW
    JobOrch --> LW

    DW --> Parser
    IW --> Parser
    LW --> Parser

    Parser --> TE
    Parser --> GE
    TE --> WS1
    GE --> LLM_API
    GE --> WS1

    Retriever --> WS1
    Retriever --> LLM_API

    Reporter --> WS1

    JobOrch --> ObjectStore

    API --> Metrics
    JobOrch --> Metrics
    Parser --> Logs
    Metrics --> Alerts
```

## Data Flow Diagram

```mermaid
flowchart LR
    subgraph "Input"
        XML[XML File<br/>OrderViewRS 17.2]
        Targets[Target Paths<br/>ndc_target_paths]
        Aliases[Path Aliases<br/>ndc_path_aliases]
    end

    subgraph "Processing Pipeline"
        Parse[Stream Parse<br/>lxml.iterparse]
        Extract[Extract NodeFacts<br/>PII Masked]

        subgraph "Discovery Branch"
            Batch[Micro-batch<br/>3-6 NodeFacts]
            LLM_D[LLM Discovery<br/>Pattern Generation]
            Normalize[Normalize<br/>signature_hash]
            Dedup[Deduplicate<br/>by signature]
        end

        subgraph "Identify Branch"
            Retrieve[Retrieve Top-K<br/>Pattern Candidates]
            Filter[Hard Constraints<br/>decision_rule]
            LLM_C[LLM Classify<br/>Confidence Score]
            Match[Pattern Matches<br/>Threshold Filter]
        end
    end

    subgraph "Storage"
        NodeDB[(node_facts<br/>association_facts)]
        PatternDB[(patterns<br/>signature_hash)]
        MatchDB[(pattern_matches<br/>confidence)]
    end

    subgraph "Output"
        DiscRep[Discovery Report<br/>New Patterns Found]
        IdentRep[Identify Report<br/>Gap Analysis]
        Coverage[Coverage Metrics<br/>by Importance]
    end

    XML --> Parse
    Targets --> Parse
    Aliases --> Parse

    Parse --> Extract
    Extract --> NodeDB

    Extract --> Batch
    Batch --> LLM_D
    LLM_D --> Normalize
    Normalize --> Dedup
    Dedup --> PatternDB

    Extract --> Retrieve
    PatternDB --> Retrieve
    Retrieve --> Filter
    Filter --> LLM_C
    LLM_C --> Match
    Match --> MatchDB

    PatternDB --> DiscRep
    MatchDB --> IdentRep
    NodeDB --> Coverage
    MatchDB --> Coverage
```

## Error Handling Flow

```mermaid
flowchart TD
    Start[Process XML Section]
    Parse{Parse Success?}
    TokenLimit{Token Limit<br/>Exceeded?}
    JSONValid{Valid JSON<br/>Response?}
    Retry{Retry Count<br/>< Max?}

    TemplateAvail{Template<br/>Available?}
    UseTemplate[Use Template<br/>Extractor]

    RepairPrompt[Send Repair<br/>Prompt]
    Backoff[Exponential<br/>Backoff]

    Success[Store Results]
    Fail[Log Error &<br/>Continue]
    Critical{Critical<br/>Section?}
    AbortRun[Abort Entire<br/>Run]

    Start --> Parse
    Parse -->|Yes| TokenLimit
    Parse -->|No| Critical

    TokenLimit -->|Yes| TemplateAvail
    TokenLimit -->|No| JSONValid

    TemplateAvail -->|Yes| UseTemplate
    TemplateAvail -->|No| Fail

    JSONValid -->|Yes| Success
    JSONValid -->|No| Retry

    Retry -->|Yes| RepairPrompt
    Retry -->|No| TemplateAvail

    RepairPrompt --> Backoff
    Backoff --> JSONValid

    UseTemplate --> Success

    Critical -->|Yes| AbortRun
    Critical -->|No| Fail

    Success --> Start
    Fail --> Start
```

## Workspace Architecture Diagram

```mermaid
flowchart TD
    subgraph "Application Layer"
        API[FastAPI Application]
        SessionMgr[Session Manager]
    end

    subgraph "Workspace Isolation"
        WS1[Workspace: default]
        WS2[Workspace: airline1]
        WS3[Workspace: airline2]
    end

    subgraph "SQLite Databases"
        DB1[(default/workspace.db<br/>Runs, NodeFacts,<br/>Patterns, Matches)]
        DB2[(airline1/workspace.db<br/>Runs, NodeFacts,<br/>Patterns, Matches)]
        DB3[(airline2/workspace.db<br/>Runs, NodeFacts,<br/>Patterns, Matches)]
    end

    API --> SessionMgr
    SessionMgr -->|get_session("default")| WS1
    SessionMgr -->|get_session("airline1")| WS2
    SessionMgr -->|get_session("airline2")| WS3

    WS1 --> DB1
    WS2 --> DB2
    WS3 --> DB3

    Note1[Each workspace is<br/>completely isolated]
    Note2[No cross-workspace<br/>data access]
    Note3[Patterns are<br/>workspace-specific]
```

## Storage Structure

```
workspaces/
├── default/
│   ├── workspace.db          # SQLite database
│   └── uploads/              # XML files
├── airline1/
│   ├── workspace.db
│   └── uploads/
└── airline2/
    ├── workspace.db
    └── uploads/
```