import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from core.common.logging_manager import get_logger


@dataclass
class DefaultPattern:
    """Data class representing a default pattern"""
    pattern_id: str
    name: str
    description: str
    prompt: str
    example: str
    xpath: str
    category: str = "default"
    api: Optional[str] = None
    api_version: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_active: bool = True


class DefaultPatternsManager:
    """Manager for default patterns with filesystem and database storage"""
    
    def __init__(self, db_path: str = None, patterns_dir: str = None):
        self.logger = get_logger("default_patterns_manager")
        
        # Set up file paths
        self.base_dir = Path(__file__).parent.parent
        self.db_path = db_path or str(self.base_dir / "database" / "data" / "default_patterns.db")
        self.patterns_dir = patterns_dir or str(self.base_dir / "database" / "data" / "default_patterns")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.patterns_dir, exist_ok=True)
        
        self._initialize_database()
        self._load_default_patterns()
    
    def _initialize_database(self):
        """Initialize the default patterns database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create default_patterns table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS default_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        prompt TEXT NOT NULL,
                        example TEXT,
                        xpath TEXT,
                        category TEXT DEFAULT 'default',
                        api TEXT,
                        api_version TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1
                    )
                """)
                
                # Create index for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_category_active 
                    ON default_patterns (category, is_active)
                """)
                
                # Migration: Add new columns if they don't exist
                self._migrate_database(cursor)
                
                conn.commit()
                self.logger.info(f"Database initialized at {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def _migrate_database(self, cursor):
        """Migrate database to add new columns if they don't exist"""
        try:
            # Check if api column exists
            cursor.execute("PRAGMA table_info(default_patterns)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'api' not in columns:
                cursor.execute("ALTER TABLE default_patterns ADD COLUMN api TEXT")
                self.logger.info("Added 'api' column to default_patterns table")
            
            if 'api_version' not in columns:
                cursor.execute("ALTER TABLE default_patterns ADD COLUMN api_version TEXT")
                self.logger.info("Added 'api_version' column to default_patterns table")
                
        except Exception as e:
            self.logger.error(f"Failed to migrate database: {e}")
            # Don't raise here as this is a migration, we want the app to continue
    
    def _load_default_patterns(self):
        """Check default patterns status without auto-creating any"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if there are ANY patterns in the database (active or inactive)
                cursor.execute("SELECT COUNT(*) FROM default_patterns")
                total_count = cursor.fetchone()[0]
                
                if total_count == 0:
                    self.logger.info("Default patterns database is empty - ready for user-created patterns")
                else:
                    # Check active patterns for logging purposes
                    cursor.execute("SELECT COUNT(*) FROM default_patterns WHERE is_active = 1")
                    active_count = cursor.fetchone()[0]
                    self.logger.info(f"Found {active_count} active patterns out of {total_count} total patterns")
                    
        except Exception as e:
            self.logger.error(f"Failed to check default patterns: {e}")
    
    def _create_initial_patterns(self):
        """Create initial default patterns"""
        default_patterns = [
            DefaultPattern(
                pattern_id="flight_segment_basic",
                name="Basic Flight Segment",
                description="Extract basic flight segment information including departure and arrival details",
                prompt="Extract flight segment data including departure airport, arrival airport, flight number, and departure time from the provided XML element.",
                example="<FlightSegment><DepartureAirport>NYC</DepartureAirport><ArrivalAirport>LAX</ArrivalAirport></FlightSegment>",
                xpath="//FlightSegment | //Segment | //Flight",
                category="flight"
            ),
            DefaultPattern(
                pattern_id="passenger_info_basic",
                name="Basic Passenger Information",
                description="Extract passenger details including name, contact information, and preferences",
                prompt="Extract passenger information including first name, last name, email, phone number, and any special service requests from the provided XML element.",
                example="<Passenger><Name><First>John</First><Last>Doe</Last></Name><Email>john@example.com</Email></Passenger>",
                xpath="//Passenger | //PassengerInfo | //Traveler",
                category="passenger"
            ),
            DefaultPattern(
                pattern_id="fare_info_basic",
                name="Basic Fare Information",
                description="Extract fare and pricing details from booking elements",
                prompt="Extract fare information including fare basis code, fare amount, currency, taxes, and total price from the provided XML element.",
                example="<Fare><BaseFare Currency='USD'>299.00</BaseFare><Taxes>45.60</Taxes></Fare>",
                xpath="//Fare | //FareInfo | //Pricing",
                category="fare"
            ),
            DefaultPattern(
                pattern_id="booking_reference_basic",
                name="Basic Booking Reference",
                description="Extract booking and reservation reference information",
                prompt="Extract booking reference details including PNR, confirmation number, booking status, and creation date from the provided XML element.",
                example="<BookingReference><PNR>ABC123</PNR><ConfirmationNumber>XYZ789</ConfirmationNumber></BookingReference>",
                xpath="//BookingReference | //Reservation | //PNR",
                category="booking"
            ),
            DefaultPattern(
                pattern_id="airline_info_basic",
                name="Basic Airline Information",
                description="Extract airline and carrier information from travel elements",
                prompt="Extract airline information including airline code, airline name, operating carrier, and marketing carrier from the provided XML element.",
                example="<Airline><Code>AA</Code><Name>American Airlines</Name></Airline>",
                xpath="//Airline | //Carrier | //AirlineInfo",
                category="airline"
            )
        ]
        
        for pattern in default_patterns:
            self.save_pattern(pattern)
        
        self.logger.info(f"Created {len(default_patterns)} initial default patterns")
    
    def get_all_patterns(self, category: str = None, active_only: bool = True) -> List[DefaultPattern]:
        """Get all default patterns, optionally filtered by category"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM default_patterns"
                params = []
                
                conditions = []
                if active_only:
                    conditions.append("is_active = ?")
                    params.append(1)
                
                if category:
                    conditions.append("category = ?")
                    params.append(category)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY category, name"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                patterns = []
                for row in rows:
                    # Handle cases where api/api_version columns might not exist in older records
                    api = row[10] if len(row) > 10 else None
                    api_version = row[11] if len(row) > 11 else None
                    
                    pattern = DefaultPattern(
                        pattern_id=row[0], name=row[1], description=row[2],
                        prompt=row[3], example=row[4], xpath=row[5],
                        category=row[6], created_at=row[7], updated_at=row[8],
                        is_active=bool(row[9]), api=api, api_version=api_version
                    )
                    patterns.append(pattern)
                
                return patterns
                
        except Exception as e:
            self.logger.error(f"Failed to get patterns: {e}")
            return []
    
    def get_pattern_by_id(self, pattern_id: str) -> Optional[DefaultPattern]:
        """Get a specific pattern by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM default_patterns WHERE pattern_id = ? AND is_active = 1",
                    (pattern_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    # Handle cases where api/api_version columns might not exist in older records
                    api = row[10] if len(row) > 10 else None
                    api_version = row[11] if len(row) > 11 else None
                    
                    return DefaultPattern(
                        pattern_id=row[0], name=row[1], description=row[2],
                        prompt=row[3], example=row[4], xpath=row[5],
                        category=row[6], created_at=row[7], updated_at=row[8],
                        is_active=bool(row[9]), api=api, api_version=api_version
                    )
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get pattern {pattern_id}: {e}")
            return None
    
    def save_pattern(self, pattern: DefaultPattern) -> bool:
        """Save a pattern to both database and filesystem"""
        try:
            # Set timestamps
            now = datetime.now().isoformat()
            if not pattern.created_at:
                pattern.created_at = now
            pattern.updated_at = now
            
            # Save to database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO default_patterns 
                    (pattern_id, name, description, prompt, example, xpath, category, api, api_version, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pattern.pattern_id, pattern.name, pattern.description,
                    pattern.prompt, pattern.example, pattern.xpath,
                    pattern.category, pattern.api, pattern.api_version,
                    pattern.created_at, pattern.updated_at, pattern.is_active
                ))
                conn.commit()
            
            # Save to filesystem as JSON
            pattern_file = os.path.join(self.patterns_dir, f"{pattern.pattern_id}.json")
            with open(pattern_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(pattern), f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved pattern {pattern.pattern_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save pattern {pattern.pattern_id}: {e}")
            return False
    
    def delete_pattern(self, pattern_id: str) -> bool:
        """Soft delete a pattern (mark as inactive)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE default_patterns SET is_active = 0, updated_at = ? WHERE pattern_id = ?",
                    (datetime.now().isoformat(), pattern_id)
                )
                
                if cursor.rowcount > 0:
                    conn.commit()
                    self.logger.info(f"Deleted pattern {pattern_id}")
                    return True
                else:
                    self.logger.warning(f"Pattern {pattern_id} not found for deletion")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to delete pattern {pattern_id}: {e}")
            return False
    
    def get_patterns_by_category(self, category: str) -> List[DefaultPattern]:
        """Get patterns filtered by category"""
        return self.get_all_patterns(category=category)
    
    def search_patterns(self, query: str) -> List[DefaultPattern]:
        """Search patterns by name, description, or xpath"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM default_patterns 
                    WHERE is_active = 1 AND (
                        name LIKE ? OR 
                        description LIKE ? OR 
                        xpath LIKE ? OR
                        category LIKE ?
                    )
                    ORDER BY 
                        CASE 
                            WHEN name LIKE ? THEN 1
                            WHEN description LIKE ? THEN 2
                            ELSE 3
                        END,
                        name
                """, [f"%{query}%" for _ in range(6)])
                
                rows = cursor.fetchall()
                patterns = []
                
                for row in rows:
                    # Handle cases where api/api_version columns might not exist in older records
                    api = row[10] if len(row) > 10 else None
                    api_version = row[11] if len(row) > 11 else None
                    
                    pattern = DefaultPattern(
                        pattern_id=row[0], name=row[1], description=row[2],
                        prompt=row[3], example=row[4], xpath=row[5],
                        category=row[6], created_at=row[7], updated_at=row[8],
                        is_active=bool(row[9]), api=api, api_version=api_version
                    )
                    patterns.append(pattern)
                
                return patterns
                
        except Exception as e:
            self.logger.error(f"Failed to search patterns: {e}")
            return []
    
    def export_patterns(self, file_path: str = None, category: str = None) -> str:
        """Export patterns to JSON file"""
        try:
            patterns = self.get_all_patterns(category=category)
            patterns_dict = [asdict(pattern) for pattern in patterns]
            
            if not file_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = os.path.join(self.patterns_dir, f"patterns_export_{timestamp}.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(patterns_dict, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Exported {len(patterns)} patterns to {file_path}")
            return file_path
            
        except Exception as e:
            self.logger.error(f"Failed to export patterns: {e}")
            raise
    
    def import_patterns(self, file_path: str) -> int:
        """Import patterns from JSON file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                patterns_data = json.load(f)
            
            imported_count = 0
            for pattern_dict in patterns_data:
                pattern = DefaultPattern(**pattern_dict)
                if self.save_pattern(pattern):
                    imported_count += 1
            
            self.logger.info(f"Imported {imported_count} patterns from {file_path}")
            return imported_count
            
        except Exception as e:
            self.logger.error(f"Failed to import patterns from {file_path}: {e}")
            raise
    
    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT category FROM default_patterns WHERE is_active = 1 ORDER BY category")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
                
        except Exception as e:
            self.logger.error(f"Failed to get categories: {e}")
            return []
    
    def backup_database(self, backup_path: str = None) -> str:
        """Create a backup of the patterns database"""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{self.db_path}.backup_{timestamp}"
            
            # Copy database file
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            self.logger.info(f"Database backed up to {backup_path}")
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Failed to backup database: {e}")
            raise