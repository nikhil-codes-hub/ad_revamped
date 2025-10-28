# AssistedDiscovery - Enhanced Sections

## 14.5 Enhanced Error Handling & Retry Strategies

### Retry Classification Matrix

| Error Type | Max Retries | Backoff Strategy | Recovery Action |
|------------|-------------|------------------|-----------------|
| LLM Rate Limit | 3 | Exponential (2s, 4s, 8s) | Switch to different model endpoint |
| LLM Timeout | 2 | Linear (5s, 10s) | Reduce batch size by 50% |
| JSON Parse Error | 1 | Immediate | Retry with repair prompt template |
| DB Connection | 5 | Exponential (1s, 2s, 4s, 8s, 16s) | Circuit breaker after 5 failures |
| XML Parse Error | 0 | None | Fail fast with detailed error location |
| Token Limit Exceeded | 1 | Immediate | Fallback to template extractor |

### Partial Failure Recovery

**Sectional Recovery Pattern:**
```
Run State: PARTIAL_FAILURE
├── Completed Sections: Store results, mark as COMPLETED
├── Failed Sections: Log error, mark as FAILED with reason
├── Pending Sections: Continue processing if > 70% success rate
└── Recovery Decision:
    ├── If critical sections failed → ABORT_RUN
    └── If non-critical sections failed → CONTINUE_WITH_GAPS
```

**Circuit Breaker Implementation:**
- Monitor failure rates per service (LLM Gateway, DB)
- Half-open state after 30s cooldown
- Auto-recovery when success rate > 80% over 10 requests

### Progressive Degradation Strategies

1. **LLM Extractor → Template Extractor**
   - Trigger: Token limit exceeded or 3+ consecutive JSON failures
   - Fallback: Use pre-built template for section if available

2. **Batch Size Reduction**
   - Start: 6 NodeFacts per batch
   - Degrade: 6 → 4 → 2 → 1 → Template fallback

3. **Model Fallback Chain**
   - Primary: GPT-4 Turbo
   - Secondary: GPT-3.5 Turbo (for simple extractions)
   - Tertiary: Template-based extraction

## 13.5 Enhanced Monitoring & Pattern Coverage Metrics

### Pattern Coverage Dashboard

**Core Coverage Metrics:**
```json
{
  "overall_coverage": {
    "sections_discovered": 45,
    "sections_expected": 52,
    "coverage_percentage": 86.5,
    "missing_critical_sections": ["PaymentMethod", "Baggage"]
  },
  "pattern_quality": {
    "avg_confidence": 0.84,
    "high_confidence_patterns": 38,  // > 0.8
    "low_confidence_patterns": 7,    // < 0.6
    "unmatched_nodes": 156
  },
  "extraction_efficiency": {
    "nodes_per_pattern": 12.3,
    "duplicate_patterns": 4,
    "signature_collision_rate": 0.02
  }
}
```

**Pattern Evolution Tracking:**
- Pattern stability score (how often patterns change)
- New pattern discovery rate per run
- Pattern obsolescence detection (unused for N runs)

**Gap Analysis Metrics:**
```json
{
  "coverage_by_importance": {
    "critical": {"covered": 12, "total": 15, "percentage": 80.0},
    "high": {"covered": 18, "total": 20, "percentage": 90.0},
    "medium": {"covered": 15, "total": 17, "percentage": 88.2}
  },
  "section_completeness": {
    "fully_covered": 35,     // All required patterns found
    "partially_covered": 10, // Some patterns missing
    "uncovered": 7           // No patterns found
  },
  "constraint_violations": {
    "missing_required_children": 8,
    "invalid_data_formats": 3,
    "reference_integrity_failures": 2
  }
}
```

### Real-time Monitoring Alerts

**Alert Thresholds:**
- Coverage drops below 80% → WARNING
- Confidence average drops below 0.7 → WARNING
- Unmatched nodes exceed 20% → WARNING
- Pattern signature collisions > 5% → CRITICAL

## 12.5 Horizontal Scaling Architecture

### Worker Pool Management

**Master-Worker Pattern:**
```
Load Balancer
├── API Gateway (Stateless)
├── Job Orchestrator (1 instance, Redis-backed)
└── Worker Pool (N instances)
    ├── Discovery Workers (CPU-intensive)
    ├── Identify Workers (I/O-intensive)
    └── Specialist Workers (Large XML handlers)
```

**Scaling Strategies:**

1. **Auto-scaling Triggers:**
   - Queue depth > 50 jobs → Scale up Discovery workers
   - Average response time > 30s → Scale up Identify workers
   - Memory usage > 80% → Scale up Large XML handlers

2. **Work Distribution:**
   ```python
   def distribute_work(xml_size, section_count):
       if xml_size > 100MB:
           return "large_xml_worker"
       elif section_count > 50:
           return "discovery_worker"
       else:
           return "standard_worker"
   ```

### Resource Optimization

**Worker Specialization:**
- **Discovery Workers:** High CPU, 8GB RAM, optimized for LLM calls
- **Identify Workers:** Medium CPU, 4GB RAM, optimized for DB queries
- **Large XML Workers:** Low CPU, 16GB RAM, optimized for streaming

**Shared State Management:**
- Pattern catalog cached in Redis with 15-min TTL
- Target path trie replicated to each worker on startup
- Database connection pooling (10 connections per worker)

### Failure Isolation

**Bulkhead Pattern:**
- Separate worker pools prevent cascade failures
- Circuit breakers per external service (LLM API, DB)
- Resource quotas prevent memory exhaustion

**Graceful Degradation:**
- If Discovery workers unavailable → Queue jobs with extended timeout
- If Identify workers down → Return basic extraction without classification
- If LLM API down → Fall back to template extraction only

### Performance Targets

| Metric | Target | Scaling Action |
|--------|---------|----------------|
| Jobs/minute | 100 | Add 2 workers per 50 jobs queued |
| P95 latency | < 2 minutes | Scale when > 3 minutes |
| Memory per worker | < 12GB | Restart worker if > 15GB |
| DB connections | < 80% pool | Add connection pool if > 90% |

**Load Testing Scenarios:**
1. **Burst Load:** 500 small XMLs submitted in 1 minute
2. **Large File:** Single 500MB XML with 200+ sections
3. **Mixed Workload:** 70% Discovery + 30% Identify concurrent