#!/bin/bash

# Run all database migrations for AssistedDiscovery
# Usage: ./run_all_migrations.sh [mysql_user] [mysql_password] [database_name]
#
# Default values:
#   mysql_user: assisted_discovery
#   mysql_password: assisted_discovery_2025_secure
#   database_name: assisted_discovery

set -e  # Exit on error

# Configuration
MYSQL_USER="${1:-assisted_discovery}"
MYSQL_PASSWORD="${2:-assisted_discovery_2025_secure}"
DATABASE="${3:-assisted_discovery}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=========================================="
echo "AssistedDiscovery Database Migrations"
echo "=========================================="
echo "Database: $DATABASE"
echo "User: $MYSQL_USER"
echo "=========================================="
echo ""

# Array of migration files in order
MIGRATIONS=(
    "001_initial_schema.sql"
    "002_add_airline_columns.sql"
    "003_add_airline_to_patterns.sql"
    "004_add_node_configurations.sql"
    "005_add_pattern_description.sql"
)

# Run each migration
for migration in "${MIGRATIONS[@]}"; do
    echo "Running migration: $migration"

    # Run migration and capture exit code
    mysql -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$DATABASE" < "$SCRIPT_DIR/$migration" 2>&1
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ $migration - SUCCESS"
    else
        echo "❌ $migration - FAILED (exit code: $EXIT_CODE)"
        exit 1
    fi
    echo ""
done

echo "=========================================="
echo "All migrations completed successfully!"
echo "=========================================="
echo ""

# Verify tables
echo "Verifying database tables..."
mysql -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$DATABASE" -e "SHOW TABLES;" 2>&1

echo ""
echo "Expected tables:"
echo "  ✓ ndc_target_paths"
echo "  ✓ ndc_path_aliases"
echo "  ✓ runs"
echo "  ✓ node_facts"
echo "  ✓ association_facts"
echo "  ✓ patterns"
echo "  ✓ pattern_matches"
echo "  ✓ node_configurations"
