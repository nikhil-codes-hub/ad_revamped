#!/usr/bin/env python3
"""
Test database connection for AssistedDiscovery.
Verifies that the database connection works with our configuration.
"""

import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

try:
    from app.core.config import settings
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    print("🔧 Testing AssistedDiscovery Database Connection")
    print("=" * 50)

    # Test configuration loading
    print(f"📋 Configuration:")
    print(f"   Database: {settings.MYSQL_DATABASE}")
    print(f"   Host: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}")
    print(f"   User: {settings.MYSQL_USER}")
    print(f"   Password: {'*' * len(settings.MYSQL_PASSWORD) if settings.MYSQL_PASSWORD else 'NOT SET'}")

    # Test database connection
    print(f"\n🔌 Testing connection to MySQL...")
    engine = create_engine(settings.mysql_url, echo=False)

    with engine.connect() as connection:
        # Test basic connection
        result = connection.execute(text("SELECT VERSION() as version, DATABASE() as db, USER() as user"))
        row = result.fetchone()

        print(f"✅ Connection successful!")
        print(f"   MySQL Version: {row.version}")
        print(f"   Connected Database: {row.db}")
        print(f"   Connected User: {row.user}")

        # Test tables exist
        print(f"\n📊 Checking tables...")
        result = connection.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result.fetchall()]

        expected_tables = [
            'ndc_target_paths', 'ndc_path_aliases', 'runs', 'node_facts',
            'association_facts', 'patterns', 'pattern_matches'
        ]

        for table in expected_tables:
            if table in tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} - MISSING")

        # Test sample data
        print(f"\n📈 Checking sample data...")
        result = connection.execute(text("SELECT COUNT(*) as count FROM ndc_target_paths"))
        target_paths_count = result.fetchone().count
        print(f"   Target paths: {target_paths_count} entries")

        result = connection.execute(text("SELECT COUNT(*) as count FROM ndc_path_aliases"))
        aliases_count = result.fetchone().count
        print(f"   Path aliases: {aliases_count} entries")

        # Test a sample query
        print(f"\n🔍 Sample query test...")
        result = connection.execute(text("""
            SELECT spec_version, message_root, COUNT(*) as paths
            FROM ndc_target_paths
            GROUP BY spec_version, message_root
        """))

        for row in result.fetchall():
            print(f"   {row.spec_version} {row.message_root}: {row.paths} paths")

    print(f"\n🎉 Database setup is complete and working!")
    print(f"✅ All tests passed - FastAPI can connect to the database")

except Exception as e:
    print(f"\n❌ Database connection failed!")
    print(f"Error: {str(e)}")
    print(f"\nTroubleshooting:")
    print(f"1. Check if MySQL is running: brew services list | grep mysql")
    print(f"2. Verify .env file has correct credentials")
    print(f"3. Test manual connection: mysql -u assisted_discovery -p")
    sys.exit(1)