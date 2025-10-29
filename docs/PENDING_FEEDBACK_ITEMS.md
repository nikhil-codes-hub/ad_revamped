# AssistedDiscovery - Pending Feedback Items

**Document Created**: October 15, 2025
**Status**: Awaiting Clarification from Stakeholders

---

## Overview

This document tracks feedback items that require additional clarification or details from stakeholders before implementation can begin. Each item includes the requesting stakeholder, context, and specific information needed.

---

## Items Requiring Clarification

### 1. Multi-Pattern Comparison from Single Node

**Stakeholder**: Sukumar Ravishekharan (@Sukumar RAVISHEKHARAN)
**Date Reported**: October 14, 2025
**Priority**: TBD (pending details)
**Context**: Conversation during demo session

**Description**:
Ability to compare multiple patterns from a single node.

**Questions Needing Clarification**:
- What specific use case requires comparing multiple patterns?
- Should this be for the same node type appearing in different positions?
- Do you want to compare patterns across different versions/airlines?
- What output format is expected (side-by-side diff, merged view, variance report)?
- Is this for Discovery mode, Identify mode, or both?

**Next Steps**:
- [ ] Schedule follow-up meeting with Sukumar
- [ ] Document specific requirements and use cases
- [ ] Create technical specification once requirements are clear

---

### 2. Benchmark Values for Node Comparison

**Stakeholder**: Chetan Palekar (@Chetan PALEKAR)
**Date Reported**: October 14, 2025
**Priority**: TBD
**Context**: Conversation during demo session

**Description**:
Add an ability to enter benchmark values for comparing nodes efficiently. For example, if the provider sample always has n Pax nodes with a definite number of ADT (Adult), CHD (Child), and INF (Infant), then it would be easy to verify the pattern.

**Questions Needing Clarification**:
- What specific benchmark values should be configurable?
  - Passenger counts (ADT/CHD/INF)?
  - Segment counts?
  - Baggage allowances?
  - Other node-specific values?
- Where should these benchmarks be defined?
  - Per airline?
  - Per message type?
  - Per route/market?
- How should the tool handle deviations from benchmarks?
  - Display warnings?
  - Flag as errors?
  - Generate variance reports?
- Is this feature for validation during Identify mode or for pattern quality checks?

**Next Steps**:
- [ ] Get consolidated list of benchmark value types from Chetan
- [ ] Understand the validation rules (strict vs. flexible matching)
- [ ] Design UI/API for benchmark configuration
- [ ] Create technical specification

---

### 3. Auto-Detect Missing XML Enclosing Tags

**Stakeholder**: Harsha Indavara Dharnesh (@Harsha INDAVARA DHARNESH)
**Date Reported**: October 14, 2025
**Priority**: TBD
**Context**: Conversation during demo session

**Description**:
Sometimes provider messages are not completely formatted and might have missing enclosing tags. Add a feature to find if there are any missing enclosing tags, fill up the information, and confirm with the user.

**Questions Needing Clarification**:
- What types of missing tags are most common?
  - Root element tags?
  - Container element tags?
  - Specific NDC elements?
- Should the tool attempt auto-repair or just detect and report?
- How should the confirmation workflow work?
  - Interactive prompt during upload?
  - Review screen before processing?
  - Post-processing report?
- What should happen if auto-repair is not possible?
- Are there specific XML validation rules beyond well-formedness?

**Example Scenarios Needed**:
- [ ] Sample XML files with missing tags
- [ ] Expected behavior for each scenario
- [ ] Acceptance criteria for auto-repair feature

**Next Steps**:
- [ ] Collect sample malformed XML files from Harsha
- [ ] Document common tag-missing patterns
- [ ] Design validation and repair logic
- [ ] Create user confirmation workflow

---

### 4. Multi-File Booking Test Capability

**Stakeholder**: Siddhartha Baidya (@Siddhartha BAIDYA)
**Date Reported**: October 14, 2025
**Priority**: TBD
**Context**: Conversation with Josepha during demo

**Description**:
Ability to test the complete booking flow by uploading multiple test files.

**Questions Needing Clarification**:
- What constitutes a "complete booking"?
  - AirShoppingRS → OrderCreateRQ → OrderViewRS sequence?
  - Other message sequences?
- How should multiple files be uploaded?
  - Batch upload in a single operation?
  - Sequential upload with linking?
  - ZIP file with multiple XMLs?
- What validation should be performed?
  - Message sequence validation?
  - Reference consistency (OrderID, BookingRefID)?
  - Data continuity (passenger names, flight segments)?
- What output format is expected?
  - End-to-end flow visualization?
  - Discrepancy report?
  - Pattern coverage across the entire flow?

**Next Steps**:
- [ ] Get detailed requirements from Siddhartha
- [ ] Understand typical booking flow message sequences
- [ ] Define validation rules for multi-file scenarios
- [ ] Design UI for multi-file upload and review

---

### 5. Semantic Value Comparison in XML

**Stakeholder**: Siddhartha Baidya (@Siddhartha BAIDYA)
**Date Reported**: October 14, 2025
**Priority**: TBD
**Context**: Conversation with Chetan during demo

**Description**:
Ability to compare values as well as structure in the XML. Tool should be intelligent enough to auto-detect and know the semantic meaning of the values. For example, if the baggageAllowance has different values for measuring weight (kg/lbs), then the Identify API should be able to convert and verify this value.

**Questions Needing Clarification**:
- What types of semantic comparisons are needed?
  - Unit conversions (kg ↔ lbs, km ↔ miles)?
  - Date/time format variations?
  - Currency conversions?
  - Code mappings (airport codes, airline codes)?
  - Other domain-specific conversions?
- Should the tool maintain a master list of conversion rules?
- How should ambiguous values be handled?
- Should the tool learn conversions from patterns or use predefined rules?

**Information Needed from Siddhartha**:
- [ ] **Consolidated list of standard value types** that require semantic comparison
- [ ] Conversion rules for each value type
- [ ] Priority order (which conversions are most critical)
- [ ] Example XML snippets showing variations

**Common Scenarios to Address**:
```
Examples:
1. Weight: 23KG vs 50LBS
2. Distance: 1000KM vs 621MI
3. Dates: 2025-10-15 vs 15OCT25 vs 10/15/2025
4. Currencies: USD100 vs EUR92 vs ¥15000
5. Time: 14:30 vs 2:30PM vs 1430
```

**Next Steps**:
- [ ] Obtain comprehensive list of value types from Siddhartha
- [ ] Research standard NDC value formats
- [ ] Design semantic comparison engine
- [ ] Create conversion rule repository

---

## Summary

**Total Items Pending Clarification**: 5

| Item | Stakeholder | Priority | Status |
|------|-------------|----------|--------|
| Multi-pattern comparison | Sukumar | TBD | Awaiting details |
| Benchmark values | Chetan | TBD | Awaiting consolidated list |
| Missing XML tags | Harsha | TBD | Awaiting examples |
| Multi-file booking test | Siddhartha | TBD | Awaiting flow definition |
| Semantic value comparison | Siddhartha | TBD | **CRITICAL: Need standard values list** |

---

## Action Items

### For Stakeholders:
1. **Sukumar**: Provide specific use cases for multi-pattern comparison
2. **Chetan**: Confirm benchmark value types and validation rules
3. **Harsha**: Share sample malformed XML files and expected behavior
4. **Siddhartha**:
   - Define complete booking flow requirements
   - **URGENT**: Provide consolidated list of standard value types for semantic comparison

### For Development Team:
1. Schedule follow-up meetings with each stakeholder
2. Create technical specifications once requirements are clarified
3. Prioritize based on business impact after clarification

---

**Document Maintained By**: AssistedDiscovery Development Team
**Last Updated**: October 15, 2025
