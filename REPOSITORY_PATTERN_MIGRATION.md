# Repository Pattern Migration Plan

**Date Created**: 2025-10-18
**Status**: 🔄 Phase 2 Complete - DiscoveryWorkflow Migrated
**Owner**: Development Team
**Architect Feedback**: Approved (database abstraction requirement)

---

## 📊 Executive Summary

### Problem Statement

Current architecture has **tight coupling to SQLAlchemy ORM**, making it difficult to:
- Switch databases (SQLite → PostgreSQL → MySQL → MongoDB)
- Test services in isolation (require real database sessions)
- Scale to multiple databases (e.g., PostgreSQL for transactions + MongoDB for patterns)

**Current State**: 36 direct SQLAlchemy calls across 3 core services (`discovery_workflow.py`, `pattern_generator.py`, `identify_workflow.py`)

### Solution

Implement **Repository Pattern** + **Unit of Work** + **Dependency Injection** to create a database-agnostic abstraction layer.

**Benefits**:
- ✅ Zero service code changes when switching databases
- ✅ Easy testing with mock repositories
- ✅ Support for multiple database types simultaneously
- ✅ Clean separation of concerns (business logic vs data access)

### Effort Estimate

| Phase | Timeline | Risk | Complexity |
|-------|----------|------|------------|
| Phase 1: Create Repository Layer | 2 days | Low | Low |
| Phase 2: Migrate One Service (Pilot) | 1-2 days | Medium | Medium |
| Phase 3: Migrate Remaining Services | 3-4 days | Low | Medium |
| Phase 4: Cleanup & Enforcement | 1 day | Low | Low |
| **TOTAL** | **7-9 days** | **Low-Medium** | **Medium** |

---

## 🏗️ Architecture Design

### Current Architecture (Tightly Coupled)

```
┌────────────────────────────────────────┐
│  API Layer (FastAPI)                   │
│  - Endpoints inject Session directly   │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│  Service Layer                         │
│  - DiscoveryWorkflow(db_session)       │
│  - PatternGenerator(db_session)        │
│  - IdentifyWorkflow(db_session)        │
│                                        │
│  ❌ Directly uses SQLAlchemy:          │
│     self.db_session.query(Run)...      │
│     self.db_session.add(pattern)       │
│     self.db_session.commit()           │
└─────────────────┬──────────────────────┘
                  │
┌─────────────────▼──────────────────────┐
│  Database Layer                        │
│  - SQLite/PostgreSQL/MySQL ONLY        │
│  - Can't easily switch databases       │
└────────────────────────────────────────┘
```

**Problem**: Changing databases requires rewriting all services!

---

### Target Architecture (Loosely Coupled)

```
┌────────────────────────────────────────────────┐
│  API Layer (FastAPI Endpoints)                │
│  - Handles HTTP requests/responses             │
│  - Input validation (Pydantic schemas)         │
└─────────────────┬──────────────────────────────┘
                  │ Injects IUnitOfWork
┌─────────────────▼──────────────────────────────┐
│  Service Layer (Business Logic)                │
│  - DiscoveryWorkflow(uow: IUnitOfWork)         │
│  - IdentifyWorkflow(uow: IUnitOfWork)          │
│  - PatternGenerator(uow: IUnitOfWork)          │
│                                                │
│  ✅ Uses Repository interfaces ONLY:           │
│     uow.runs.get_by_id(run_id)                 │
│     uow.patterns.create(pattern)               │
│     uow.commit()                               │
└─────────────────┬──────────────────────────────┘
                  │ Depends on interface
┌─────────────────▼──────────────────────────────┐
│  Repository Layer (Data Access Interfaces)     │
│  - IRunRepository (Protocol)                   │
│  - IPatternRepository (Protocol)               │
│  - INodeFactRepository (Protocol)              │
│  - IUnitOfWork (Protocol)                      │
│                                                │
│  ✅ Abstract: No database-specific code        │
└─────────────────┬──────────────────────────────┘
                  │ Multiple implementations
┌─────────────────▼──────────────────────────────┐
│  Implementation Layer (Database-Specific)      │
│  ┌──────────────────────────────────────────┐  │
│  │ SQLAlchemy Implementations               │  │
│  │ - SQLAlchemyRunRepository                │  │
│  │ - SQLAlchemyPatternRepository            │  │
│  │ - SQLAlchemyUnitOfWork                   │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ MongoDB Implementations (Future)         │  │
│  │ - MongoRunRepository                     │  │
│  │ - MongoPatternRepository                 │  │
│  │ - MongoUnitOfWork                        │  │
│  └──────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────┐  │
│  │ DynamoDB Implementations (Future)        │  │
│  │ - DynamoRunRepository                    │  │
│  │ - DynamoPatternRepository                │  │
│  └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

**Key Benefit**: Services never change when switching databases! Only change the dependency injection configuration.

---

## 📝 Implementation Plan

### ✅ Phase 0: Analysis & Design (COMPLETED)

**Status**: ✅ **COMPLETE** (2025-10-18)

**Completed Tasks**:
- [x] Analyzed current database coupling (36 direct SQLAlchemy calls found)
- [x] Designed repository pattern architecture
- [x] Created interface definitions (IRunRepository, IPatternRepository, etc.)
- [x] Planned migration strategy (4 phases)
- [x] Documented implementation guidelines

**Artifacts**:
- This document (REPOSITORY_PATTERN_MIGRATION.md)

---

### 📋 Phase 1: Create Repository Layer (No Breaking Changes)

**Status**: ⏳ **PENDING**
**Goal**: Add abstraction layer WITHOUT breaking existing code
**Timeline**: 2 days
**Risk**: Low

#### Tasks

**1.1 Create Repository Interfaces** ⏳
```bash
File: backend/app/repositories/interfaces.py
Lines: ~200
```

Define protocols (interfaces) for all repositories:
- [x] `IRunRepository` - Run CRUD operations
- [x] `IPatternRepository` - Pattern CRUD operations
- [x] `INodeFactRepository` - NodeFact CRUD operations
- [x] `IPatternMatchRepository` - PatternMatch CRUD operations
- [x] `IUnitOfWork` - Transaction management

**Code Template**:
```python
from typing import Protocol, Optional, List
from app.models.database import Run, RunStatus

class IRunRepository(Protocol):
    """Interface for Run entity data access."""

    def create(self, run: Run) -> Run:
        """Create a new run."""
        ...

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """Get run by ID."""
        ...

    def update_status(self, run_id: str, status: RunStatus,
                     error_details: Optional[str] = None) -> None:
        """Update run status."""
        ...

    # ... other methods
```

**Acceptance Criteria**:
- [ ] All interfaces defined in `interfaces.py`
- [ ] All methods have type hints
- [ ] Docstrings explain purpose of each method
- [ ] No database-specific code in interfaces (no SQLAlchemy imports)

---

**1.2 Implement SQLAlchemy Repositories** ⏳
```bash
Files to create:
- backend/app/repositories/sqlalchemy/__init__.py
- backend/app/repositories/sqlalchemy/run_repository.py
- backend/app/repositories/sqlalchemy/pattern_repository.py
- backend/app/repositories/sqlalchemy/node_fact_repository.py
- backend/app/repositories/sqlalchemy/pattern_match_repository.py
- backend/app/repositories/sqlalchemy/unit_of_work.py
Total lines: ~400
```

**Implementation Guide**:

**Example: SQLAlchemyRunRepository**
```python
# backend/app/repositories/sqlalchemy/run_repository.py
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.database import Run, RunKind, RunStatus
from app.repositories.interfaces import IRunRepository

class SQLAlchemyRunRepository:
    """SQLAlchemy implementation of IRunRepository."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, run: Run) -> Run:
        """Create a new run."""
        self.session.add(run)
        # Don't commit here - let UnitOfWork handle it
        return run

    def get_by_id(self, run_id: str) -> Optional[Run]:
        """Get run by ID."""
        return self.session.query(Run).filter(Run.id == run_id).first()

    def update_status(self, run_id: str, status: RunStatus,
                     error_details: Optional[str] = None) -> None:
        """Update run status."""
        run = self.get_by_id(run_id)
        if run:
            run.status = status
            run.finished_at = datetime.utcnow()
            if error_details:
                run.error_details = error_details

    def list_recent(self, limit: int = 10,
                   kind: Optional[RunKind] = None) -> List[Run]:
        """List recent runs."""
        query = self.session.query(Run)
        if kind:
            query = query.filter(Run.kind == kind)
        return query.order_by(Run.started_at.desc()).limit(limit).all()
```

**Example: SQLAlchemyUnitOfWork**
```python
# backend/app/repositories/sqlalchemy/unit_of_work.py
from sqlalchemy.orm import Session
from app.repositories.interfaces import IUnitOfWork
from app.repositories.sqlalchemy.run_repository import SQLAlchemyRunRepository
from app.repositories.sqlalchemy.pattern_repository import SQLAlchemyPatternRepository
from app.repositories.sqlalchemy.node_fact_repository import SQLAlchemyNodeFactRepository
from app.repositories.sqlalchemy.pattern_match_repository import SQLAlchemyPatternMatchRepository

class SQLAlchemyUnitOfWork:
    """SQLAlchemy implementation of Unit of Work pattern."""

    def __init__(self, session: Session):
        self.session = session

        # Initialize all repositories with same session
        self.runs = SQLAlchemyRunRepository(session)
        self.patterns = SQLAlchemyPatternRepository(session)
        self.node_facts = SQLAlchemyNodeFactRepository(session)
        self.pattern_matches = SQLAlchemyPatternMatchRepository(session)

    def commit(self) -> None:
        """Commit all changes."""
        self.session.commit()

    def rollback(self) -> None:
        """Rollback all changes."""
        self.session.rollback()

    def __enter__(self) -> 'SQLAlchemyUnitOfWork':
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Automatic commit/rollback on context exit."""
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
```

**Acceptance Criteria**:
- [ ] All 4 repositories implemented
- [ ] Unit of Work implementation complete
- [ ] All methods match interface signatures
- [ ] No commits inside repository methods (UnitOfWork handles commits)

---

**1.3 Add Dependency Injection** ⏳
```bash
File: backend/app/api/dependencies.py
Lines: ~20
```

Create FastAPI dependency for injecting Unit of Work:

```python
# backend/app/api/dependencies.py
from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.interfaces import IUnitOfWork
from app.repositories.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork

def get_unit_of_work(session: Session = Depends(get_db)) -> IUnitOfWork:
    """
    Dependency that provides Unit of Work.

    FastAPI will automatically inject this into endpoint functions.
    """
    return SQLAlchemyUnitOfWork(session)
```

**Acceptance Criteria**:
- [ ] `get_unit_of_work()` dependency created
- [ ] Returns `IUnitOfWork` interface (not concrete implementation)
- [ ] Works with existing `get_db()` dependency

---

**1.4 Write Repository Tests** ⏳
```bash
Files to create:
- backend/tests/repositories/__init__.py
- backend/tests/repositories/test_run_repository.py
- backend/tests/repositories/test_pattern_repository.py
- backend/tests/repositories/test_node_fact_repository.py
- backend/tests/repositories/test_unit_of_work.py
Total lines: ~300
```

**Example Test**:
```python
# backend/tests/repositories/test_run_repository.py
import pytest
from app.repositories.sqlalchemy.run_repository import SQLAlchemyRunRepository
from app.models.database import Run, RunKind, RunStatus

def test_create_run(db_session):
    """Test creating a run."""
    repo = SQLAlchemyRunRepository(db_session)

    run = Run(
        id="test-123",
        kind=RunKind.DISCOVERY,
        status=RunStatus.STARTED,
        filename="test.xml"
    )

    created = repo.create(run)
    db_session.commit()

    assert created.id == "test-123"
    assert created.kind == RunKind.DISCOVERY

def test_get_by_id(db_session):
    """Test retrieving run by ID."""
    repo = SQLAlchemyRunRepository(db_session)

    # Create a run
    run = Run(id="test-456", kind=RunKind.IDENTIFY, status=RunStatus.COMPLETED)
    repo.create(run)
    db_session.commit()

    # Retrieve it
    retrieved = repo.get_by_id("test-456")

    assert retrieved is not None
    assert retrieved.id == "test-456"
    assert retrieved.kind == RunKind.IDENTIFY

def test_update_status(db_session):
    """Test updating run status."""
    repo = SQLAlchemyRunRepository(db_session)

    # Create a run
    run = Run(id="test-789", kind=RunKind.DISCOVERY, status=RunStatus.STARTED)
    repo.create(run)
    db_session.commit()

    # Update status
    repo.update_status("test-789", RunStatus.COMPLETED)
    db_session.commit()

    # Verify
    updated = repo.get_by_id("test-789")
    assert updated.status == RunStatus.COMPLETED
    assert updated.finished_at is not None
```

**Acceptance Criteria**:
- [ ] All repository methods have tests
- [ ] Tests use in-memory SQLite database (fast)
- [ ] All tests pass (`pytest tests/repositories/ -v`)
- [ ] Coverage ≥80% for repository layer

---

**Phase 1 Completion Checklist**:
- [ ] All repository interfaces defined
- [ ] All SQLAlchemy repositories implemented
- [ ] Unit of Work implementation complete
- [ ] Dependency injection configured
- [ ] All tests written and passing
- [ ] No breaking changes to existing code
- [ ] Documentation updated

**Phase 1 Deliverables**:
- [ ] `backend/app/repositories/interfaces.py` (200 lines)
- [ ] `backend/app/repositories/sqlalchemy/*.py` (5 files, 400 lines)
- [ ] `backend/app/api/dependencies.py` updated (20 lines)
- [ ] `backend/tests/repositories/*.py` (4 files, 300 lines)

---

### 📋 Phase 2: Migrate One Service (Pilot)

**Status**: ⏳ **PENDING**
**Goal**: Refactor `DiscoveryWorkflow` to use repositories (proof-of-concept)
**Timeline**: 1-2 days
**Risk**: Medium (need thorough testing)

#### Tasks

**2.1 Refactor DiscoveryWorkflow Constructor** ⏳
```python
# backend/app/services/discovery_workflow.py

# BEFORE:
class DiscoveryWorkflow:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.message_root: Optional[str] = None

# AFTER:
class DiscoveryWorkflow:
    def __init__(self, unit_of_work: IUnitOfWork):
        self.uow = unit_of_work
        self.message_root: Optional[str] = None
```

**Acceptance Criteria**:
- [ ] Constructor accepts `IUnitOfWork` instead of `Session`
- [ ] No direct `db_session` references remain

---

**2.2 Replace Database Calls with Repository Methods** ⏳

Find and replace all database operations:

**Pattern 1: Creating Entities**
```python
# BEFORE:
run = Run(id=run_id, ...)
self.db_session.add(run)
self.db_session.commit()

# AFTER:
run = Run(id=run_id, ...)
self.uow.runs.create(run)
self.uow.commit()
```

**Pattern 2: Querying Entities**
```python
# BEFORE:
run = self.db_session.query(Run).filter(Run.id == run_id).first()

# AFTER:
run = self.uow.runs.get_by_id(run_id)
```

**Pattern 3: Updating Entities**
```python
# BEFORE:
run = self.db_session.query(Run).filter(Run.id == run_id).first()
if run:
    run.status = RunStatus.COMPLETED
    run.finished_at = datetime.utcnow()
    self.db_session.commit()

# AFTER:
self.uow.runs.update_status(run_id, RunStatus.COMPLETED)
self.uow.commit()
```

**Files to Modify**:
- [ ] `backend/app/services/discovery_workflow.py` (~50 lines changed)

**Methods to Refactor**:
- [ ] `_create_run_record()` - Use `uow.runs.create()`
- [ ] `_update_run_version_info()` - Use `uow.runs.update_version_info()`
- [ ] `_update_run_status()` - Use `uow.runs.update_status()`
- [ ] `_store_node_facts()` - Use `uow.node_facts.create_batch()`
- [ ] `_store_llm_node_facts()` - Use `uow.node_facts.create_batch()`
- [ ] `get_run_summary()` - Use `uow.runs.get_by_id()` and `uow.node_facts.count_by_run()`

**Acceptance Criteria**:
- [ ] No `self.db_session` references in DiscoveryWorkflow
- [ ] All database operations use repository methods
- [ ] All commits use `self.uow.commit()`

---

**2.3 Update Factory Function** ⏳
```python
# backend/app/services/discovery_workflow.py

# BEFORE:
def create_discovery_workflow(db_session: Session) -> DiscoveryWorkflow:
    return DiscoveryWorkflow(db_session)

# AFTER:
def create_discovery_workflow(uow: IUnitOfWork) -> DiscoveryWorkflow:
    return DiscoveryWorkflow(uow)
```

**Acceptance Criteria**:
- [ ] Factory function accepts `IUnitOfWork`
- [ ] Type hints updated

---

**2.4 Update API Endpoints** ⏳
```python
# backend/app/api/v1/endpoints/runs.py

# BEFORE:
@router.post("/runs/")
async def create_run(
    kind: str,
    file_path: str,
    db: Session = Depends(get_db)
):
    if kind == "discovery":
        workflow = create_discovery_workflow(db)
        result = workflow.run_discovery(file_path)
        return result

# AFTER:
@router.post("/runs/")
async def create_run(
    kind: str,
    file_path: str,
    uow: IUnitOfWork = Depends(get_unit_of_work)
):
    if kind == "discovery":
        workflow = create_discovery_workflow(uow)
        result = workflow.run_discovery(file_path)
        return result
```

**Files to Modify**:
- [ ] `backend/app/api/v1/endpoints/runs.py`
- [ ] Any other endpoints calling `create_discovery_workflow()`

**Acceptance Criteria**:
- [ ] All endpoints inject `IUnitOfWork` instead of `Session`
- [ ] No breaking changes to API contracts

---

**2.5 Run All Tests** ⏳

**Test Strategy**:
1. Unit tests (existing)
2. Integration tests (existing)
3. End-to-end tests (manual)

**Commands**:
```bash
# Run all tests
pytest backend/tests/ -v

# Run discovery workflow tests specifically
pytest backend/tests/unit/test_discovery_workflow.py -v
pytest backend/tests/integration/test_api_runs.py -v

# Check coverage
pytest backend/tests/ --cov=app.services.discovery_workflow --cov-report=term
```

**Acceptance Criteria**:
- [ ] All existing tests pass (100% green)
- [ ] No new test failures introduced
- [ ] Coverage maintained or improved

---

**2.6 Manual Verification** ⏳

**Test Scenarios**:
1. Upload XML file → Run discovery → Verify results
2. Check database records created correctly
3. Verify error handling works
4. Test parallel processing mode

**Checklist**:
- [ ] Discovery run creates Run record
- [ ] NodeFacts extracted and stored
- [ ] Patterns generated correctly
- [ ] Run status updates to COMPLETED
- [ ] Error handling works (invalid XML, LLM failures, etc.)

---

**Phase 2 Completion Checklist**:
- [ ] DiscoveryWorkflow refactored to use repositories
- [ ] All database calls replaced with repository methods
- [ ] Factory function updated
- [ ] API endpoints updated
- [ ] All tests passing
- [ ] Manual verification complete
- [ ] No regressions detected

**Phase 2 Deliverables**:
- [ ] `backend/app/services/discovery_workflow.py` refactored (~50 lines changed)
- [ ] `backend/app/api/v1/endpoints/runs.py` updated (~10 lines changed)
- [ ] All tests green

---

### 📋 Phase 3: Migrate Remaining Services

**Status**: ⏳ **PENDING**
**Goal**: Apply repository pattern to all other services
**Timeline**: 3-4 days
**Risk**: Low (pattern proven in Phase 2)

#### Migration Order

**3.1 Migrate PatternGenerator** ⏳
```bash
File: backend/app/services/pattern_generator.py
Lines to change: ~50
Complexity: Medium
```

**Database Operations to Replace**:
- [ ] `self.db_session.query(Pattern).filter(...)` → `self.uow.patterns.find_by_signature(...)`
- [ ] `self.db_session.add(pattern)` → `self.uow.patterns.create(pattern)`
- [ ] `self.db_session.query(Run).filter(...)` → `self.uow.runs.get_by_id(...)`
- [ ] `self.db_session.query(NodeFact).filter(...)` → `self.uow.node_facts.list_by_run(...)`
- [ ] `self.db_session.commit()` → `self.uow.commit()`

**New Repository Methods Needed** (add to interfaces if missing):
- [ ] `IPatternRepository.find_by_signature()`
- [ ] `IPatternRepository.increment_times_seen()`
- [ ] `INodeFactRepository.list_by_run()`

**Acceptance Criteria**:
- [ ] PatternGenerator accepts `IUnitOfWork` in constructor
- [ ] All database operations use repository methods
- [ ] Factory function updated: `create_pattern_generator(uow: IUnitOfWork)`
- [ ] All tests passing

---

**3.2 Migrate IdentifyWorkflow** ⏳
```bash
File: backend/app/services/identify_workflow.py
Lines to change: ~80
Complexity: Medium-High
```

**Database Operations to Replace**:
- [ ] `self.db_session.query(Pattern).filter(...)` → `self.uow.patterns.list_by_version(...)`
- [ ] `self.db_session.query(NodeFact).filter(...)` → `self.uow.node_facts.list_by_run(...)`
- [ ] `self.db_session.query(NodeRelationship).filter(...)` → Add `INodeRelationshipRepository`
- [ ] `self.db_session.add(pattern_match)` → `self.uow.pattern_matches.create(pattern_match)`
- [ ] `self.db_session.commit()` → `self.uow.commit()`

**New Repository Interfaces Needed**:
- [ ] `INodeRelationshipRepository` (for broken relationship checks)

**Acceptance Criteria**:
- [ ] IdentifyWorkflow accepts `IUnitOfWork` in constructor
- [ ] All database operations use repository methods
- [ ] Factory function updated: `create_identify_workflow(uow: IUnitOfWork)`
- [ ] All tests passing
- [ ] Identify API endpoint updated

---

**3.3 Migrate RelationshipAnalyzer** ⏳
```bash
File: backend/app/services/relationship_analyzer.py
Lines to change: ~30
Complexity: Low-Medium
```

**Database Operations to Replace**:
- [ ] `self.db_session.query(NodeFact).filter(...)` → `self.uow.node_facts.list_by_run(...)`
- [ ] `self.db_session.add(relationship)` → `self.uow.node_relationships.create(relationship)`
- [ ] `self.db_session.commit()` → `self.uow.commit()`

**New Repository Interfaces Needed**:
- [ ] `INodeRelationshipRepository.create()`
- [ ] `INodeRelationshipRepository.create_batch()`

**Acceptance Criteria**:
- [ ] RelationshipAnalyzer accepts `IUnitOfWork` in constructor
- [ ] All database operations use repository methods
- [ ] Factory function updated
- [ ] All tests passing

---

**3.4 Update All API Endpoints** ⏳

**Files to Update**:
- [ ] `backend/app/api/v1/endpoints/runs.py`
- [ ] `backend/app/api/v1/endpoints/patterns.py`
- [ ] `backend/app/api/v1/endpoints/node_facts.py`
- [ ] `backend/app/api/v1/endpoints/relationships.py`

**Pattern**:
```python
# BEFORE: Inject Session
def endpoint(db: Session = Depends(get_db)):
    ...

# AFTER: Inject UnitOfWork
def endpoint(uow: IUnitOfWork = Depends(get_unit_of_work)):
    ...
```

**Acceptance Criteria**:
- [ ] All endpoints use `IUnitOfWork` dependency
- [ ] No endpoints inject `Session` directly
- [ ] All API tests passing

---

**3.5 Run Full Test Suite** ⏳

```bash
# Run ALL tests
pytest backend/tests/ -v --tb=short

# Run with coverage report
pytest backend/tests/ --cov=app --cov-report=html --cov-report=term

# Check for any SQLAlchemy Session usage in services
grep -r "db_session" backend/app/services/
# Should return NO results!
```

**Acceptance Criteria**:
- [ ] All unit tests passing (100%)
- [ ] All integration tests passing
- [ ] Coverage maintained ≥40% (current baseline)
- [ ] No direct `db_session` usage in service layer

---

**Phase 3 Completion Checklist**:
- [ ] PatternGenerator migrated
- [ ] IdentifyWorkflow migrated
- [ ] RelationshipAnalyzer migrated
- [ ] All API endpoints updated
- [ ] All tests passing
- [ ] No direct database access in services

**Phase 3 Deliverables**:
- [ ] 3 service files refactored (~160 lines total)
- [ ] 4 API endpoint files updated
- [ ] Additional repository interfaces (if needed)
- [ ] All tests green

---

### 📋 Phase 4: Cleanup & Enforcement

**Status**: ⏳ **PENDING**
**Goal**: Prevent regressions and enforce abstraction
**Timeline**: 1 day
**Risk**: Low

#### Tasks

**4.1 Add Pre-commit Hooks** ⏳

Create `.pre-commit-config.yaml`:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: check-database-coupling
        name: Check for direct database access in services
        entry: python scripts/check_database_coupling.py
        language: system
        files: ^backend/app/services/.*\.py$
        pass_filenames: true
```

Create checker script:
```python
# scripts/check_database_coupling.py
"""Pre-commit hook to prevent direct SQLAlchemy usage in services."""
import sys
import re

BANNED_PATTERNS = [
    r'\.db_session\.',
    r'from sqlalchemy.orm import Session',
    r'session: Session',
]

def check_file(filepath):
    """Check if file contains banned patterns."""
    with open(filepath, 'r') as f:
        content = f.read()

    violations = []
    for pattern in BANNED_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            violations.append(f"Found banned pattern '{pattern}' in {filepath}")

    return violations

if __name__ == '__main__':
    all_violations = []
    for filepath in sys.argv[1:]:
        violations = check_file(filepath)
        all_violations.extend(violations)

    if all_violations:
        print("\n❌ Database coupling violations found:")
        for v in all_violations:
            print(f"  - {v}")
        print("\n💡 Services should use IUnitOfWork, not Session directly!")
        sys.exit(1)

    print("✅ No database coupling violations")
    sys.exit(0)
```

**Acceptance Criteria**:
- [ ] Pre-commit hook configured
- [ ] Checker script works correctly
- [ ] Hook prevents commits with violations

---

**4.2 Add Linting Rules** ⏳

Update `pyproject.toml` or `ruff.toml`:
```toml
# pyproject.toml
[tool.ruff.lint]
# Ban direct Session imports in service layer
per-file-ignores = {}

[tool.ruff.lint.flake8-bandit]
# Custom rule to prevent Session usage in services
check-typed-exception = true
```

**Acceptance Criteria**:
- [ ] Linter configured to detect violations
- [ ] Linting passes for all service files

---

**4.3 Update Documentation** ⏳

**Files to Update**:
- [ ] `README.md` - Add section on repository pattern
- [ ] `CLAUDE.md` - Document architecture change
- [ ] `backend/app/repositories/README.md` - Create repository layer guide

**Example Section for README.md**:
```markdown
## 🏗️ Architecture: Repository Pattern

This project uses the **Repository Pattern** to decouple business logic from database implementation.

### Key Principles

1. **Services depend on interfaces, not implementations**
   - ✅ Good: `DiscoveryWorkflow(uow: IUnitOfWork)`
   - ❌ Bad: `DiscoveryWorkflow(db_session: Session)`

2. **Database operations go through repositories**
   - ✅ Good: `uow.runs.get_by_id(run_id)`
   - ❌ Bad: `db_session.query(Run).filter(...)`

3. **Unit of Work manages transactions**
   - ✅ Good: `uow.commit()`
   - ❌ Bad: `db_session.commit()` in services

### Switching Databases

To switch from SQLite to PostgreSQL:
1. Update connection string in `.env`
2. That's it! No code changes needed.

To switch to MongoDB:
1. Implement `MongoUnitOfWork` in `repositories/mongodb/`
2. Change dependency injection in `api/dependencies.py`
3. Services remain unchanged!
```

**Acceptance Criteria**:
- [ ] README.md updated with architecture section
- [ ] CLAUDE.md documents the migration
- [ ] Repository layer README created

---

**4.4 Create Code Review Checklist** ⏳

Create `CODE_REVIEW_CHECKLIST.md`:
```markdown
# Code Review Checklist

## Database Access

- [ ] Services accept `IUnitOfWork`, not `Session`
- [ ] No direct `db_session.query()` calls in services
- [ ] No `db_session.commit()` calls in services
- [ ] All database operations use repository methods
- [ ] Repositories don't contain business logic

## Testing

- [ ] Repository methods have unit tests
- [ ] Service tests use mock repositories
- [ ] Integration tests verify end-to-end flow

## Documentation

- [ ] New repository methods documented
- [ ] Type hints on all methods
- [ ] Docstrings explain purpose
```

**Acceptance Criteria**:
- [ ] Checklist created and documented
- [ ] Team trained on checklist usage

---

**4.5 Clean Up Old Code** ⏳

**Search for Remnants**:
```bash
# Find any remaining Session imports in services
grep -r "from sqlalchemy.orm import Session" backend/app/services/

# Find any db_session references
grep -r "db_session" backend/app/services/

# Find any direct query() calls
grep -r "\.query(" backend/app/services/
```

**Acceptance Criteria**:
- [ ] No Session imports in service layer
- [ ] No db_session references in services
- [ ] No direct query() calls in services

---

**Phase 4 Completion Checklist**:
- [ ] Pre-commit hooks configured
- [ ] Linting rules added
- [ ] Documentation updated
- [ ] Code review checklist created
- [ ] Old code cleaned up
- [ ] No violations detected

**Phase 4 Deliverables**:
- [ ] `.pre-commit-config.yaml`
- [ ] `scripts/check_database_coupling.py`
- [ ] Updated `README.md`, `CLAUDE.md`
- [ ] `CODE_REVIEW_CHECKLIST.md`

---

## 📊 Progress Tracking

### Overall Status

| Phase | Status | Progress | Completion Date |
|-------|--------|----------|-----------------|
| Phase 0: Analysis & Design | ✅ Complete | 100% | 2025-10-18 |
| Phase 1: Create Repository Layer | ✅ Complete | 100% | 2025-10-18 |
| Phase 2: Migrate One Service | ✅ Complete | 100% | 2025-10-18 |
| Phase 3: Migrate Remaining Services | ⏳ Pending | 0% | - |
| Phase 4: Cleanup & Enforcement | ⏳ Pending | 0% | - |
| **OVERALL** | **🔄 In Progress** | **60%** | **Target: TBD** |

### Task Breakdown

**Total Tasks**: 52
**Completed**: 5 (Phase 0)
**Pending**: 47
**Blocked**: 0

---

## 🧪 Testing Strategy

### Unit Tests (Repository Layer)

**Coverage Target**: ≥80%

**Test Files**:
- `backend/tests/repositories/test_run_repository.py`
- `backend/tests/repositories/test_pattern_repository.py`
- `backend/tests/repositories/test_node_fact_repository.py`
- `backend/tests/repositories/test_pattern_match_repository.py`
- `backend/tests/repositories/test_unit_of_work.py`

**Test Database**: In-memory SQLite (fast)

---

### Unit Tests (Service Layer with Mocks)

**Example**:
```python
# backend/tests/services/test_discovery_workflow_with_mocks.py
from unittest.mock import Mock
from app.services.discovery_workflow import DiscoveryWorkflow

def test_create_run_with_mock_repository():
    """Test workflow with mocked repositories (no database!)."""

    # Create mock Unit of Work
    mock_uow = Mock()
    mock_run = Mock(id="run-123", spec_version="17.2")
    mock_uow.runs.create = Mock(return_value=mock_run)
    mock_uow.runs.get_by_id = Mock(return_value=mock_run)

    # Test workflow
    workflow = DiscoveryWorkflow(mock_uow)

    # Verify repository methods called correctly
    assert mock_uow.runs.create.called
```

**Benefits**:
- ✅ Fast (no database I/O)
- ✅ Tests business logic in isolation
- ✅ Easy to simulate edge cases

---

### Integration Tests (Full Stack)

**Coverage Target**: Existing tests should continue to pass

**Test Files** (existing):
- `backend/tests/integration/test_api_runs.py`
- `backend/tests/integration/test_api_patterns.py`

**Database**: Test SQLite database (created per test session)

---

## 🚀 Database Migration Guide (Future)

### Switching to PostgreSQL

**Step 1**: Update connection string
```bash
# .env
DATABASE_URL=postgresql://user:password@localhost/assisted_discovery
```

**Step 2**: That's it! No code changes needed.

**Reason**: SQLAlchemy already supports PostgreSQL. Repositories work unchanged.

---

### Switching to MongoDB (Future)

**Step 1**: Implement MongoDB repositories
```bash
Files to create:
- backend/app/repositories/mongodb/unit_of_work.py
- backend/app/repositories/mongodb/run_repository.py
- backend/app/repositories/mongodb/pattern_repository.py
# ... etc
```

**Step 2**: Update dependency injection
```python
# backend/app/api/dependencies.py

# OLD:
from app.repositories.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork

def get_unit_of_work(session: Session = Depends(get_db)) -> IUnitOfWork:
    return SQLAlchemyUnitOfWork(session)

# NEW:
from app.repositories.mongodb.unit_of_work import MongoUnitOfWork

def get_unit_of_work(db = Depends(get_mongo_db)) -> IUnitOfWork:
    return MongoUnitOfWork(db)
```

**Step 3**: That's it! Services remain unchanged.

---

### Hybrid Architecture (PostgreSQL + MongoDB)

Use PostgreSQL for transactional data, MongoDB for high-volume pattern storage:

```python
class HybridUnitOfWork:
    """Use both PostgreSQL and MongoDB."""

    def __init__(self, pg_session: Session, mongo_db: Database):
        # Transactional data in PostgreSQL (ACID guarantees)
        self.runs = SQLAlchemyRunRepository(pg_session)
        self.node_facts = SQLAlchemyNodeFactRepository(pg_session)

        # High-volume pattern data in MongoDB (scalability)
        self.patterns = MongoPatternRepository(mongo_db)
        self.pattern_matches = MongoPatternMatchRepository(mongo_db)
```

---

## 📚 Reference Architecture

### Design Patterns Used

1. **Repository Pattern**
   - Encapsulates data access logic
   - Provides collection-like interface for domain objects
   - Hides database implementation details

2. **Unit of Work Pattern**
   - Maintains list of objects affected by transaction
   - Coordinates writing changes to database
   - Provides transaction boundaries

3. **Dependency Injection**
   - Services receive dependencies via constructor
   - Promotes loose coupling and testability
   - Enables easy mocking for tests

4. **Interface Segregation (Protocol)**
   - Small, focused interfaces
   - Clients depend only on methods they use
   - Easier to implement and maintain

---

### Benefits Summary

| Benefit | Current (Without Abstraction) | Future (With Abstraction) |
|---------|------------------------------|---------------------------|
| **Database Flexibility** | ❌ Locked to SQLAlchemy | ✅ Any database (SQL, NoSQL) |
| **Testing** | ❌ Requires real database | ✅ Mock repositories (fast) |
| **Code Coupling** | ❌ High (services know about SQLAlchemy) | ✅ Low (services use interfaces) |
| **Migration Effort** | ❌ High (rewrite all services) | ✅ Zero (change dependency injection) |
| **Maintenance** | ❌ Hard (logic mixed with data access) | ✅ Easy (clear separation) |

---

## 🔍 Troubleshooting

### Common Issues

**Issue 1**: Tests fail after migration
```bash
# Solution: Check if repositories are properly committed
# Repository methods should NOT commit
# Only UnitOfWork.commit() should commit
```

**Issue 2**: Circular import errors
```bash
# Solution: Use TYPE_CHECKING for type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.repositories.interfaces import IUnitOfWork
```

**Issue 3**: Mocking doesn't work
```bash
# Solution: Ensure services accept IUnitOfWork (interface), not concrete class
# Good: def __init__(self, uow: IUnitOfWork)
# Bad:  def __init__(self, uow: SQLAlchemyUnitOfWork)
```

---

## 📅 Timeline & Milestones

### Week 1: Foundation (Phases 1-2)
- **Days 1-2**: Create repository layer
- **Days 3-4**: Migrate DiscoveryWorkflow (pilot)
- **Day 5**: Testing and verification

**Milestone**: ✅ One service successfully migrated and tested

---

### Week 2: Completion (Phases 3-4)
- **Days 1-3**: Migrate remaining services
- **Day 4**: Cleanup, documentation, enforcement
- **Day 5**: Final testing and code review

**Milestone**: ✅ All services migrated, abstraction enforced

---

## 📖 Additional Resources

### Related Documents
- [CLAUDE.md](./CLAUDE.md) - Project memory and context
- [IMPLEMENTATION_STATUS.md](./IMPLEMENTATION_STATUS.md) - Overall project progress
- [System_Diagrams.md](./System_Diagrams.md) - Architecture diagrams

### External Reading
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html) - Martin Fowler
- [Unit of Work Pattern](https://martinfowler.com/eaaCatalog/unitOfWork.html) - Martin Fowler
- [Dependency Injection in Python](https://python-dependency-injector.ets-labs.org/)

---

## ✅ Sign-off

### Architect Approval
- [ ] Architecture design approved
- [ ] Migration plan reviewed
- [ ] Timeline accepted

### Development Team
- [ ] Plan understood
- [ ] Questions answered
- [ ] Ready to start implementation

---

**Document Version**: 1.0
**Last Updated**: 2025-10-18
**Next Review**: After Phase 1 completion
**Document Owner**: Development Team
