"""
Pytest configuration and shared fixtures for AssistedDiscovery tests.
"""
import pytest
import os
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Dict, Any

from app.models.database import Base, Run, NodeFact, Pattern, NodeConfiguration, ReferenceType
from app.core.config import settings


@pytest.fixture(scope="session")
def test_db_engine():
    """Create a test database engine."""
    # Use in-memory SQLite for tests
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_db_engine) -> Generator[Session, None, None]:
    """Create a new database session for a test."""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_run(db_session: Session) -> Run:
    """Create a sample Run for testing with unique ID."""
    import uuid
    run = Run(
        id=f"test-run-{uuid.uuid4().hex[:8]}",
        kind="discovery",
        spec_version="21.3",
        message_root="OrderViewRS",
        airline_code="AA",
        filename="test_order.xml",
        status="completed"
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


@pytest.fixture
def sample_node_fact(db_session: Session, sample_run: Run) -> NodeFact:
    """Create a sample NodeFact for testing."""
    fact = NodeFact(
        run_id=sample_run.id,
        spec_version="21.3",
        message_root="OrderViewRS",
        section_path="Response/DataLists/PaxList",
        node_type="Pax",
        node_ordinal=0,
        fact_json={
            "node_type": "Pax",
            "attributes": {
                "PaxID": "PAX1"
            },
            "children": [
                {
                    "node_type": "Individual",
                    "attributes": {"GivenName": "John", "Surname": "Doe"}
                }
            ],
            "references": {}
        }
    )
    db_session.add(fact)
    db_session.commit()
    db_session.refresh(fact)
    return fact


@pytest.fixture
def sample_pattern(db_session: Session) -> Pattern:
    """Create a sample Pattern for testing with unique hash."""
    import uuid
    pattern = Pattern(
        spec_version="21.3",
        message_root="OrderViewRS",
        airline_code="AA",
        section_path="Response/DataLists/PaxList",
        selector_xpath="./Pax",
        decision_rule={
            "node_type": "Pax",
            "must_have_attributes": ["PaxID"],
            "optional_attributes": [],
            "child_structure": {
                "has_children": True,
                "child_types": ["Individual"]
            }
        },
        signature_hash=f"hash-{uuid.uuid4().hex[:16]}",
        times_seen=1,
        created_by_model="gpt-4"
    )
    db_session.add(pattern)
    db_session.commit()
    db_session.refresh(pattern)
    return pattern


@pytest.fixture
def sample_node_config(db_session: Session) -> NodeConfiguration:
    """Create a sample NodeConfiguration for testing."""
    config = NodeConfiguration(
        spec_version="21.3",
        message_root="OrderViewRS",
        airline_code="AA",
        node_type="PaxList",
        section_path="Response/DataLists/PaxList",
        enabled=True
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


@pytest.fixture
def sample_reference_type(db_session: Session) -> ReferenceType:
    """Create a sample ReferenceType for testing."""
    ref_type = ReferenceType(
        reference_type="pax_journey",
        display_name="Passenger Journey Reference",
        description="Reference from journey to passenger",
        example="PaxJourneyRefID -> PaxID",
        category="passenger"
    )
    db_session.add(ref_type)
    db_session.commit()
    db_session.refresh(ref_type)
    return ref_type


@pytest.fixture
def sample_xml_file() -> Generator[Path, None, None]:
    """Create a temporary XML file for testing."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<IATA_OrderViewRS xmlns="http://www.iata.org/IATA/2015/00/2019.2/IATA_OrderViewRS">
    <Response>
        <DataLists>
            <PaxList>
                <Pax>
                    <PaxID>PAX1</PaxID>
                    <PTC>ADT</PTC>
                    <Individual>
                        <GivenName>John</GivenName>
                        <Surname>Doe</Surname>
                    </Individual>
                </Pax>
                <Pax>
                    <PaxID>PAX2</PaxID>
                    <PTC>ADT</PTC>
                    <Individual>
                        <GivenName>Jane</GivenName>
                        <Surname>Smith</Surname>
                    </Individual>
                </Pax>
            </PaxList>
        </DataLists>
    </Response>
    <PayloadAttributes>
        <CorrelationID>test-123</CorrelationID>
        <VersionNumber>21.3</VersionNumber>
    </PayloadAttributes>
</IATA_OrderViewRS>"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
        f.write(xml_content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def mock_llm_response() -> Dict[str, Any]:
    """Mock LLM response for testing."""
    return {
        "node_type": "Pax",
        "attributes": {
            "PaxID": "PAX1",
            "PTC": "ADT"
        },
        "children": [
            {
                "node_type": "Individual",
                "attributes": {
                    "GivenName": "John",
                    "Surname": "Doe"
                }
            }
        ],
        "references": {
            "PaxJourneyRefID": ["PJ1"]
        },
        "relationships": [],
        "business_intelligence": {
            "passenger_counts": {"ADT": 1},
            "has_contact_info": False
        }
    }
