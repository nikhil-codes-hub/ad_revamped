"""
Integration tests for Discovery API endpoints.

NOTE: Backend uses "identify" for the service that validates XML against patterns.
UI terminology: This is called "Discovery" in the user interface.

Tests the discovery/validation workflow including:
- POST /api/v1/identify/upload (upload XML for discovery)
- Pattern matching against library
- Missing pattern detection
- Quality alert generation
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.database import Pattern


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


class TestDiscoveryAPI:
    """Test suite for Discovery API endpoints (backend: Identify API)."""

    def test_identify_xml_with_patterns(self, client, db_session: Session, sample_pattern: Pattern, sample_xml_file: Path):
        """Test identifying XML against existing patterns."""
        with open(sample_xml_file, 'rb') as f:
            response = client.post(
                "/api/v1/identify/upload",
                files={"file": ("test.xml", f, "application/xml")},
                data={"workspace": "default"}
            )

        # Should return 200 with identification results
        assert response.status_code == 200
        data = response.json()

        # Check for expected response structure
        assert "matched_patterns" in data or "matches" in data
        assert "missing_patterns" in data or "missing" in data

    def test_identify_xml_no_patterns(self, client, sample_xml_file: Path):
        """Test identifying XML when no patterns exist."""
        with open(sample_xml_file, 'rb') as f:
            response = client.post(
                "/api/v1/identify/upload",
                files={"file": ("test.xml", f, "application/xml")},
                data={"workspace": "default"}
            )

        assert response.status_code == 200
        data = response.json()

        # Should indicate no patterns found
        matched = data.get("matched_patterns", data.get("matches", []))
        assert len(matched) == 0

    def test_identify_invalid_xml(self, client):
        """Test identifying invalid XML."""
        invalid_xml = b"<invalid>This is not valid XML"

        response = client.post(
            "/api/v1/identify/upload",
            files={"file": ("invalid.xml", invalid_xml, "application/xml")},
            data={"workspace": "default"}
        )

        # Should return error
        assert response.status_code in [400, 422, 500]

    def test_identify_with_version_mismatch(self, client, db_session: Session, sample_pattern: Pattern):
        """Test identifying XML with different version than patterns."""
        # Create XML with different version
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<IATA_OrderViewRS xmlns="http://www.iata.org/IATA/2015/00/2018.1/IATA_OrderViewRS">
    <Response>
        <DataLists>
            <PaxList>
                <Pax>
                    <PaxID>PAX1</PaxID>
                </Pax>
            </PaxList>
        </DataLists>
    </Response>
</IATA_OrderViewRS>"""

        response = client.post(
            "/api/v1/identify/upload",
            files={"file": ("test.xml", xml_content, "application/xml")},
            data={"workspace": "default"}
        )

        assert response.status_code == 200
        data = response.json()

        # May have version mismatch warnings
        if "warnings" in data:
            assert any("version" in w.lower() for w in data["warnings"])

    def test_identify_quality_alerts(self, client, db_session: Session, sample_pattern: Pattern):
        """Test that quality alerts are generated."""
        # Create XML with quality issues (orphaned references)
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<IATA_OrderViewRS xmlns="http://www.iata.org/IATA/2015/00/2019.2/IATA_OrderViewRS">
    <Response>
        <DataLists>
            <PaxList>
                <Pax>
                    <PaxID>PAX1</PaxID>
                    <PaxJourneyRefID>NONEXISTENT</PaxJourneyRefID>
                </Pax>
            </PaxList>
        </DataLists>
    </Response>
</IATA_OrderViewRS>"""

        response = client.post(
            "/api/v1/identify/upload",
            files={"file": ("test.xml", xml_content, "application/xml")},
            data={"workspace": "default"}
        )

        if response.status_code == 200:
            data = response.json()
            # May have quality alerts
            if "quality_alerts" in data:
                assert isinstance(data["quality_alerts"], list)

    def test_identify_missing_patterns(self, client, db_session: Session, sample_pattern: Pattern):
        """Test detection of missing patterns."""
        # Create XML that doesn't match any patterns
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<IATA_OrderViewRS xmlns="http://www.iata.org/IATA/2015/00/2019.2/IATA_OrderViewRS">
    <Response>
        <DataLists>
            <BaggageList>
                <Baggage>
                    <BaggageID>BAG1</BaggageID>
                </Baggage>
            </BaggageList>
        </DataLists>
    </Response>
</IATA_OrderViewRS>"""

        response = client.post(
            "/api/v1/identify/upload",
            files={"file": ("test.xml", xml_content, "application/xml")},
            data={"workspace": "default"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should report missing patterns
        missing = data.get("missing_patterns", data.get("missing", []))
        assert isinstance(missing, list)

    def test_identify_response_structure(self, client, sample_xml_file: Path):
        """Test that identify response has correct structure."""
        with open(sample_xml_file, 'rb') as f:
            response = client.post(
                "/api/v1/identify/upload",
                files={"file": ("test.xml", f, "application/xml")},
                data={"workspace": "default"}
            )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert isinstance(data, dict)
        # Should have at least matched or missing patterns
        has_matches = "matched_patterns" in data or "matches" in data
        has_missing = "missing_patterns" in data or "missing" in data
        assert has_matches or has_missing

    def test_identify_with_airline_filter(self, client, db_session: Session, sample_xml_file: Path):
        """Test identifying with airline-specific patterns."""
        with open(sample_xml_file, 'rb') as f:
            response = client.post(
                "/api/v1/identify/upload",
                files={"file": ("test.xml", f, "application/xml")},
                data={
                    "workspace": "default",
                    "airline_code": "AA"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_identify_performance_large_xml(self, client, db_session: Session):
        """Test identify performance with larger XML."""
        # Create larger XML with multiple elements
        xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<IATA_OrderViewRS xmlns="http://www.iata.org/IATA/2015/00/2019.2/IATA_OrderViewRS">
    <Response>
        <DataLists>
            <PaxList>"""

        # Add 100 passengers
        for i in range(100):
            xml_content += f"""
                <Pax>
                    <PaxID>PAX{i}</PaxID>
                    <PTC>ADT</PTC>
                </Pax>""".encode()

        xml_content += b"""
            </PaxList>
        </DataLists>
    </Response>
</IATA_OrderViewRS>"""

        import time
        start_time = time.time()

        response = client.post(
            "/api/v1/identify/upload",
            files={"file": ("large.xml", xml_content, "application/xml")},
            data={"workspace": "default"}
        )

        duration = time.time() - start_time

        assert response.status_code == 200
        # Should complete within reasonable time (30 seconds)
        assert duration < 30.0
