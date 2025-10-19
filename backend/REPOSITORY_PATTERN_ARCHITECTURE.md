# Repository Pattern Architecture

## Overview

This document describes the Repository Pattern implementation in the AssistedDiscovery backend. The repository pattern provides a clean separation between the business logic layer (services) and the data access layer (database operations).

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                      │
│                  app/api/v1/endpoints/                       │
│                    - runs.py                                 │
│                    - patterns.py                             │
│                    - node_configs.py                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ├──────────────────────────┐
                         ▼                          ▼
┌──────────────────────────────────┐  ┌──────────────────────────┐
│      Service Layer                │  │   Dependency Injection   │
│   app/services/                   │  │   app/api/dependencies.py│
│   - DiscoveryWorkflow            │  │   - get_unit_of_work()   │
│   - IdentifyWorkflow              │  └──────────────────────────┘
│   - PatternGenerator              │
│   - RelationshipAnalyzer          │
└────────────┬─────────────────────┘
             │
             │ Uses IUnitOfWork
             ▼
┌─────────────────────────────────────────────────────────────┐
│              Repository Layer (Interfaces)                   │
│           app/repositories/interfaces.py                     │
│   - IUnitOfWork (Protocol)                                  │
│   - IRunRepository (Protocol)                               │
│   - IPatternRepository (Protocol)                           │
│   - INodeFactRepository (Protocol)                          │
│   - IPatternMatchRepository (Protocol)                      │
│   - INodeRelationshipRepository (Protocol)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Implemented by
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         Repository Implementations (SQLAlchemy)              │
│        app/repositories/sqlalchemy/                          │
│   - SQLAlchemyUnitOfWork                                    │
│   - SQLAlchemyRunRepository                                 │
│   - SQLAlchemyPatternRepository                             │
│   - SQLAlchemyNodeFactRepository                            │
│   - SQLAlchemyPatternMatchRepository                        │
│   - SQLAlchemyNodeRelationshipRepository                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Uses
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Models                           │
│              app/models/database.py                          │
│   - Run, NodeFact, Pattern, PatternMatch                   │
│   - NodeRelationship, NodeConfiguration                     │
└─────────────────────────────────────────────────────────────┘
```

## Core Concepts

### 1. Repository Pattern

The repository pattern abstracts database operations behind well-defined interfaces. This provides several benefits:

- **Database Independence**: Business logic doesn't depend on specific database implementation
- **Testability**: Easy to mock repositories for unit testing
- **Maintainability**: Centralized data access logic
- **Flexibility**: Can swap database implementations without changing business logic

### 2. Unit of Work Pattern

The Unit of Work pattern manages database transactions and coordinates multiple repositories:

- **Transaction Management**: Commit/rollback operations across multiple repositories
- **Session Management**: Single database session shared across all repositories
- **Atomicity**: Ensures all-or-nothing execution for complex operations

### 3. Protocol-Based Interfaces

We use Python's `typing.Protocol` for structural subtyping:

```python
from typing import Protocol

class IUnitOfWork(Protocol):
    """Unit of Work interface for managing database transactions."""

    @property
    def runs(self) -> 'IRunRepository': ...

    @property
    def patterns(self) -> 'IPatternRepository': ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
```

**Benefits**:
- No inheritance required
- Duck typing support
- Better IDE support with type hints
- Clearer interface contracts

## Implementation Details

### Repository Interfaces

Each repository interface defines domain-specific operations:

#### IRunRepository
```python
class IRunRepository(Protocol):
    def create(self, run: Run) -> Run: ...
    def get_by_id(self, run_id: str) -> Optional[Run]: ...
    def update(self, run: Run) -> Run: ...
    def list_all(self, limit: int = 100) -> List[Run]: ...
```

#### IPatternRepository
```python
class IPatternRepository(Protocol):
    def create(self, pattern: Pattern) -> Pattern: ...
    def get_by_id(self, pattern_id: int) -> Optional[Pattern]: ...
    def find_by_signature(self, spec_version: str, message_root: str,
                         airline_code: Optional[str],
                         signature_hash: str) -> Optional[Pattern]: ...
    def list_by_version(self, spec_version: str, message_root: str,
                       airline_code: Optional[str] = None) -> List[Pattern]: ...
```

#### INodeFactRepository
```python
class INodeFactRepository(Protocol):
    def create(self, node_fact: NodeFact) -> NodeFact: ...
    def create_batch(self, node_facts: List[NodeFact]) -> List[NodeFact]: ...
    def list_by_run(self, run_id: str) -> List[NodeFact]: ...
    def get_by_id(self, node_fact_id: int) -> Optional[NodeFact]: ...
```

#### IPatternMatchRepository
```python
class IPatternMatchRepository(Protocol):
    def create(self, pattern_match: PatternMatch) -> PatternMatch: ...
    def list_by_run(self, run_id: str) -> List[PatternMatch]: ...
```

#### INodeRelationshipRepository
```python
class INodeRelationshipRepository(Protocol):
    def create(self, relationship: NodeRelationship) -> NodeRelationship: ...
    def create_batch(self, relationships: List[NodeRelationship]) -> List[NodeRelationship]: ...
    def list_broken_for_node(self, node_fact_id: int) -> List[NodeRelationship]: ...
```

### Unit of Work Implementation

The `SQLAlchemyUnitOfWork` class coordinates all repositories:

```python
class SQLAlchemyUnitOfWork:
    """SQLAlchemy implementation of Unit of Work pattern."""

    def __init__(self, session: Session):
        self._session = session
        self._runs = SQLAlchemyRunRepository(session)
        self._patterns = SQLAlchemyPatternRepository(session)
        self._node_facts = SQLAlchemyNodeFactRepository(session)
        self._pattern_matches = SQLAlchemyPatternMatchRepository(session)
        self._node_relationships = SQLAlchemyNodeRelationshipRepository(session)

    @property
    def runs(self) -> IRunRepository:
        return self._runs

    @property
    def patterns(self) -> IPatternRepository:
        return self._patterns

    # ... other repositories ...

    def commit(self) -> None:
        """Commit the current transaction."""
        self._session.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._session.rollback()
```

## Service Layer Integration

### Before Migration (Direct SQLAlchemy)

```python
class PatternGenerator:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def find_pattern(self, signature_hash: str) -> Optional[Pattern]:
        return self.db_session.query(Pattern).filter(
            Pattern.signature_hash == signature_hash
        ).first()

    def save_pattern(self, pattern: Pattern):
        self.db_session.add(pattern)
        self.db_session.commit()
```

**Issues**:
- Tightly coupled to SQLAlchemy
- Hard to test (requires database)
- Cannot swap database implementation
- Transaction management scattered

### After Migration (Repository Pattern)

```python
class PatternGenerator:
    def __init__(self, unit_of_work: IUnitOfWork):
        self.uow = unit_of_work

    def find_pattern(self, signature_hash: str) -> Optional[Pattern]:
        return self.uow.patterns.find_by_signature(
            spec_version="21.3",
            message_root="OrderViewRS",
            airline_code="AA",
            signature_hash=signature_hash
        )

    def save_pattern(self, pattern: Pattern):
        self.uow.patterns.create(pattern)
        self.uow.commit()
```

**Benefits**:
- Decoupled from database implementation
- Easy to mock for testing
- Clear transaction boundaries
- Database-agnostic business logic

## FastAPI Integration

### Dependency Injection

We use FastAPI's dependency injection to provide the UnitOfWork:

```python
# app/api/dependencies.py
from fastapi import Depends
from sqlalchemy.orm import Session
from app.services.workspace_db import get_workspace_db
from app.repositories.sqlalchemy.unit_of_work import SQLAlchemyUnitOfWork
from app.repositories.interfaces import IUnitOfWork

def get_unit_of_work(
    workspace: str = "default",
    db: Session = Depends(get_workspace_db)
) -> IUnitOfWork:
    """Get Unit of Work for the specified workspace."""
    return SQLAlchemyUnitOfWork(db)
```

### API Endpoint Usage

```python
# app/api/v1/endpoints/runs.py
@router.post("/", response_model=RunResponse)
async def create_run(
    kind: str = Query(...),
    file: UploadFile = File(...),
    workspace: str = Query("default")
):
    # Get workspace database session
    db_generator = get_workspace_db(workspace)
    db = next(db_generator)

    try:
        # Create Unit of Work from database session
        uow = SQLAlchemyUnitOfWork(db)

        # Run appropriate workflow based on kind
        if kind == "discovery":
            workflow = create_discovery_workflow(uow)
            results = workflow.run_discovery(temp_file_path)
        elif kind == "identify":
            workflow = create_identify_workflow(uow)
            results = workflow.run_identify(temp_file_path)

        return RunResponse(**results)
    finally:
        # Cleanup...
        pass
```

## Migration Guide

### Migrating a Service

1. **Change constructor signature**:
```python
# Before
def __init__(self, db_session: Session):
    self.db_session = db_session

# After
def __init__(self, unit_of_work: IUnitOfWork):
    self.uow = unit_of_work
```

2. **Replace database queries**:
```python
# Before
existing = self.db_session.query(Pattern).filter(...).first()

# After
existing = self.uow.patterns.find_by_signature(...)
```

3. **Replace create/update operations**:
```python
# Before
self.db_session.add(new_pattern)

# After
self.uow.patterns.create(new_pattern)
```

4. **Replace commit/rollback**:
```python
# Before
self.db_session.commit()
self.db_session.rollback()

# After
self.uow.commit()
self.uow.rollback()
```

5. **Update factory functions**:
```python
# Before
def create_pattern_generator(db_session: Session) -> PatternGenerator:
    return PatternGenerator(db_session)

# After
def create_pattern_generator(unit_of_work: IUnitOfWork) -> PatternGenerator:
    return PatternGenerator(unit_of_work)
```

## Testing

### Mocking Repositories

The repository pattern makes testing much easier:

```python
from unittest.mock import Mock
from app.repositories.interfaces import IUnitOfWork, IPatternRepository

def test_pattern_generation():
    # Create mock UnitOfWork
    mock_uow = Mock(spec=IUnitOfWork)
    mock_pattern_repo = Mock(spec=IPatternRepository)

    # Configure mocks
    mock_uow.patterns = mock_pattern_repo
    mock_pattern_repo.find_by_signature.return_value = None

    # Test service
    generator = PatternGenerator(mock_uow)
    result = generator.find_pattern("hash123")

    # Verify
    assert result is None
    mock_pattern_repo.find_by_signature.assert_called_once()
```

## Future Enhancements

### 1. Additional Database Support

The repository pattern makes it easy to add support for other databases:

```python
class MongoDBUnitOfWork:
    """MongoDB implementation of Unit of Work."""

    def __init__(self, mongo_client):
        self.client = mongo_client
        self._runs = MongoDBRunRepository(mongo_client)
        # ... other repositories
```

### 2. Caching Layer

Add caching without changing business logic:

```python
class CachedPatternRepository:
    """Pattern repository with caching."""

    def __init__(self, base_repo: IPatternRepository, cache: Cache):
        self.base_repo = base_repo
        self.cache = cache

    def get_by_id(self, pattern_id: int) -> Optional[Pattern]:
        cached = self.cache.get(f"pattern:{pattern_id}")
        if cached:
            return cached

        pattern = self.base_repo.get_by_id(pattern_id)
        if pattern:
            self.cache.set(f"pattern:{pattern_id}", pattern)
        return pattern
```

### 3. Event Sourcing

Add event tracking without modifying services:

```python
class EventSourcedUnitOfWork:
    """Unit of Work with event sourcing."""

    def commit(self):
        # Emit events before committing
        for event in self._collect_events():
            self.event_bus.publish(event)

        self._session.commit()
```

## Best Practices

1. **Always use UnitOfWork for transaction boundaries**
   - Let UnitOfWork handle commits and rollbacks
   - Don't mix direct session access with repository usage

2. **Keep repositories focused**
   - Each repository handles one aggregate root
   - Don't create "god repositories" that do everything

3. **Use factory functions for service creation**
   - Provides consistent service instantiation
   - Makes dependency injection easier

4. **Maintain interface contracts**
   - Don't add implementation-specific methods to interfaces
   - Keep interfaces database-agnostic

5. **Test through interfaces**
   - Mock repositories, not database sessions
   - Test business logic independently of database

## Conclusion

The repository pattern implementation provides a solid foundation for:
- **Maintainable Code**: Clear separation of concerns
- **Testable Services**: Easy to mock and test
- **Flexible Architecture**: Can swap implementations
- **Clean Business Logic**: Free from database coupling

This architecture supports the long-term evolution of the AssistedDiscovery platform while maintaining code quality and developer productivity.
