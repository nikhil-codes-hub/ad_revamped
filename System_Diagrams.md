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
        LLM_API[LLM API<br/>GPT-4 Turbo]
        ObjectStore[Object Storage<br/>S3/GCS]
    end

    subgraph "Data Layer"
        Cache[(Redis Cache<br/>Targets & Aliases)]
        MySQL[(MySQL Database<br/>Facts & Patterns)]
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
    TE --> MySQL
    GE --> LLM_API
    GE --> MySQL

    Retriever --> MySQL
    Retriever --> LLM_API

    Parser --> Cache
    Reporter --> MySQL

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

## Caching Strategy Diagram

```mermaid
flowchart TD
    subgraph "Cache Layers"
        L1[L1: In-Memory<br/>Path Trie]
        L2[L2: Redis<br/>Pattern Catalog]
        L3[L3: MySQL<br/>Persistent Store]
    end

    subgraph "Cache Operations"
        Startup[Worker Startup]
        Request[Process Request]
        Refresh[Periodic Refresh]
        Invalidate[Cache Invalidation]
    end

    subgraph "Data Sources"
        TargetPaths[ndc_target_paths]
        PathAliases[ndc_path_aliases]
        Patterns[patterns table]
    end

    Startup --> TargetPaths
    Startup --> PathAliases
    TargetPaths --> L1
    PathAliases --> L1

    Request --> L1
    L1 -->|Miss| L2
    L2 -->|Miss| L3
    L3 --> Patterns

    Refresh -->|Every 15min| L2
    Refresh -->|On webhook| L1

    Invalidate -->|New patterns| L2
    Invalidate -->|Config change| L1

    L2 --> L1
    L3 --> L2
```