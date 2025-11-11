"""
Diagnostic script to test .env file loading for BDP authentication.

Run this script to verify that environment variables are being loaded correctly:
    python test_env_loading.py
"""

import os
import sys
from pathlib import Path

print("=" * 80)
print("BDP Authentication Environment Variable Diagnostic")
print("=" * 80)
print()

# Check current working directory
print(f"1. Current working directory: {os.getcwd()}")
print()

# Check for .env file in various locations
env_locations = [
    ".env",
    "../.env",
    "../../.env",
    "../../../.env"
]

print("2. Checking for .env file in possible locations:")
for loc in env_locations:
    env_path = Path(loc)
    exists = env_path.exists()
    print(f"   {'✅' if exists else '❌'} {env_path.absolute()} {'(FOUND)' if exists else '(NOT FOUND)'}")
print()

# Try to import settings
print("3. Attempting to load settings from config.py:")
try:
    from app.core.config import settings
    print("   ✅ Settings loaded successfully")
    print()

    # Check BDP credentials
    print("4. Checking BDP credentials from settings:")
    print(f"   AZURE_AUTH_METHOD: {settings.AZURE_AUTH_METHOD}")
    print(f"   AZURE_TENANT_ID: {'✅ SET' if settings.AZURE_TENANT_ID else '❌ NOT SET'}")
    print(f"   AZURE_CLIENT_ID: {'✅ SET' if settings.AZURE_CLIENT_ID else '❌ NOT SET'}")
    print(f"   AZURE_CLIENT_SECRET: {'✅ SET' if settings.AZURE_CLIENT_SECRET else '❌ NOT SET'}")

    # Show first few characters if set
    if settings.AZURE_TENANT_ID:
        print(f"   Tenant ID preview: {settings.AZURE_TENANT_ID[:8]}...")
    if settings.AZURE_CLIENT_ID:
        print(f"   Client ID preview: {settings.AZURE_CLIENT_ID[:8]}...")
    if settings.AZURE_CLIENT_SECRET:
        print(f"   Client Secret preview: {settings.AZURE_CLIENT_SECRET[:8]}...")
    print()

    # Check Azure OpenAI settings
    print("5. Checking Azure OpenAI settings:")
    print(f"   AZURE_OPENAI_ENDPOINT: {settings.AZURE_OPENAI_ENDPOINT}")
    print(f"   AZURE_API_VERSION: {settings.AZURE_API_VERSION}")
    print(f"   MODEL_DEPLOYMENT_NAME: {settings.MODEL_DEPLOYMENT_NAME}")
    print(f"   LLM_PROVIDER: {settings.LLM_PROVIDER}")
    print()

    # Try to initialize BDP authenticator if method is bdp
    if settings.AZURE_AUTH_METHOD == "bdp":
        print("6. Testing BDP Authenticator initialization:")
        try:
            from app.services.bdp_authenticator import get_bdp_authenticator
            bdp_auth = get_bdp_authenticator()
            print("   ✅ BDP Authenticator initialized successfully!")
            print()
        except Exception as e:
            print(f"   ❌ BDP Authenticator initialization failed:")
            print(f"   Error: {e}")
            print()
    else:
        print(f"6. Skipping BDP test (AZURE_AUTH_METHOD={settings.AZURE_AUTH_METHOD}, not 'bdp')")
        print()

    # Summary
    print("=" * 80)
    print("Summary:")
    print("=" * 80)

    if settings.AZURE_AUTH_METHOD == "bdp":
        all_set = all([
            settings.AZURE_TENANT_ID,
            settings.AZURE_CLIENT_ID,
            settings.AZURE_CLIENT_SECRET
        ])

        if all_set:
            print("✅ All BDP credentials are configured correctly!")
            print("   You can now use BDP authentication.")
        else:
            print("❌ BDP credentials are incomplete!")
            print("   Please update your .env file with:")
            if not settings.AZURE_TENANT_ID:
                print("   - AZURE_TENANT_ID=your-tenant-id")
            if not settings.AZURE_CLIENT_ID:
                print("   - AZURE_CLIENT_ID=your-client-id")
            if not settings.AZURE_CLIENT_SECRET:
                print("   - AZURE_CLIENT_SECRET=your-client-secret")
    else:
        print(f"ℹ️  Currently using {settings.AZURE_AUTH_METHOD} authentication")
        print("   To use BDP, set AZURE_AUTH_METHOD=bdp in .env")

except ImportError as e:
    print(f"   ❌ Failed to import settings: {e}")
    print(f"   Make sure you're running this from the backend directory:")
    print(f"      cd backend && python test_env_loading.py")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 80)
