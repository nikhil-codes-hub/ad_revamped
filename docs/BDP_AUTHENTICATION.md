# BDP (Azure AD) Authentication Guide

## Overview

AssistedDiscovery now supports **two authentication methods** for Azure OpenAI:

1. **API Key Authentication** (legacy/testing) - Using Azure OpenAI API keys
2. **BDP (Azure AD) Authentication** (production) - Using Azure Active Directory credentials

This guide explains how to configure and use BDP authentication for corporate Azure OpenAI endpoints.

---

## What is BDP Authentication?

BDP (Azure AD) authentication uses **ClientSecretCredential** to authenticate with Azure OpenAI instead of API keys. This method is required by many corporate environments for enhanced security and compliance.

### Key Differences

| Feature | API Key Auth | BDP Auth |
|---------|-------------|----------|
| Authentication | Static API key | Dynamic Azure AD tokens |
| Security | Key can be shared | Client credentials managed by Azure AD |
| Token Refresh | Manual rotation | Automatic token refresh |
| Corporate Policy | May not be compliant | Meets corporate standards |
| Setup Complexity | Simple | Requires Azure AD app registration |

---

## Prerequisites

Before using BDP authentication, you need:

1. **Azure AD Tenant ID**: Your organization's Azure AD tenant identifier
2. **Azure AD Application**:
   - Registered application in Azure AD
   - Client ID of the application
   - Client secret for the application
3. **Azure OpenAI Permissions**: The application must have permissions to access Cognitive Services

### Getting Azure AD Credentials

Contact your Azure administrator to:
1. Register an application in Azure AD for AssistedDiscovery
2. Grant the application access to Azure Cognitive Services
3. Obtain the following credentials:
   - Tenant ID
   - Client ID
   - Client Secret

---

## Configuration

### Step 1: Update `.env` File

Edit your `.env` file to use BDP authentication:

```bash
# LLM Configuration - Azure OpenAI
# Set auth method to 'bdp'
AZURE_AUTH_METHOD=bdp

# Option 1: API Key Authentication (comment out when using BDP)
# AZURE_OPENAI_KEY=your-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_API_VERSION=2025-01-01-preview
MODEL_DEPLOYMENT_NAME=gpt-4o

# Option 2: BDP (Azure AD) Authentication
AZURE_TENANT_ID=your-tenant-id-here
AZURE_CLIENT_ID=your-client-id-here
AZURE_CLIENT_SECRET=your-client-secret-here
```

### Step 2: Verify Configuration

The system will automatically detect BDP authentication when:
- `AZURE_AUTH_METHOD=bdp` is set
- All three BDP credentials are provided (tenant_id, client_id, client_secret)

### Step 3: Install Dependencies

Ensure the `azure-identity` package is installed:

```bash
pip install azure-identity
```

---

## Switching Between Authentication Methods

You can easily switch between API key and BDP authentication by changing the `AZURE_AUTH_METHOD` setting:

### Use API Key (for testing)

```bash
AZURE_AUTH_METHOD=api_key
AZURE_OPENAI_KEY=your-api-key
```

### Use BDP (for production)

```bash
AZURE_AUTH_METHOD=bdp
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
```

**Note**: You can keep both sets of credentials in your `.env` file. The system will use the appropriate one based on `AZURE_AUTH_METHOD`.

---

## Logging and Verification

When the application starts, check the logs to verify authentication:

### Successful BDP Authentication

```
INFO  - Initializing Azure OpenAI client with BDP authentication...
INFO  -   Endpoint: https://your-endpoint.openai.azure.com/
INFO  -   API Version: 2025-01-01-preview
INFO  -   Model Deployment: gpt-4o
INFO  -   Auth Method: BDP (Azure AD)
INFO  - ✅ BDP authenticator initialized successfully
INFO  -   Tenant ID: 12345678-1234-1234-1234-123456789012
INFO  -   Client ID: abcdef12...
INFO  - ✅ Async Azure OpenAI client created with BDP authentication
INFO  - ✅ LLM extractor initialized successfully with Azure OpenAI (BDP): gpt-4o
```

### Successful API Key Authentication

```
INFO  - Initializing Azure OpenAI client with API Key...
INFO  -   Endpoint: https://your-endpoint.openai.azure.com/
INFO  -   API Version: 2025-01-01-preview
INFO  -   Model Deployment: gpt-4o
INFO  -   Auth Method: API Key
INFO  - ✅ LLM extractor initialized successfully with Azure OpenAI (API Key): gpt-4o
```

---

## Troubleshooting

### Environment Variables Not Loading on Another Machine

**Problem**: You've copied the .env file to another machine but credentials aren't being loaded.

**Symptoms**:
- Error: "BDP authentication requires AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET"
- Even though these values are in your .env file

**Common Causes & Solutions**:

1. **.env file location**:
   ```bash
   # .env MUST be in one of these locations:
   backend/.env                    # ✅ Recommended
   ad/.env                         # ✅ Works (project root)
   ad/backend/.env                 # ✅ Works (backend dir)
   ```

2. **File encoding issues**:
   - Save .env file with UTF-8 encoding
   - No BOM (Byte Order Mark)
   - Unix-style line endings (LF, not CRLF)

3. **Hidden characters**:
   ```bash
   # BAD - has quotes
   AZURE_TENANT_ID="12345-67890"  ❌

   # GOOD - no quotes
   AZURE_TENANT_ID=12345-67890   ✅
   ```

4. **Spaces around equals sign**:
   ```bash
   # BAD - has spaces
   AZURE_TENANT_ID = 12345   ❌

   # GOOD - no spaces
   AZURE_TENANT_ID=12345     ✅
   ```

5. **Virtual environment not activated**:
   ```bash
   # Activate the virtual environment first
   cd ad
   source assisted_discovery_env/bin/activate  # Mac/Linux
   # OR
   assisted_discovery_env\Scripts\activate     # Windows
   ```

**Diagnostic Steps**:

1. **Run the diagnostic script** (see Testing section below):
   ```bash
   cd backend
   python test_env_loading.py
   ```
   This will show exactly which variables are loaded and which are missing.

2. **Check file permissions**:
   ```bash
   ls -la .env
   # Should be readable (at least -rw-r--r--)
   ```

3. **Verify file content**:
   ```bash
   cat .env | grep AZURE_
   # Should show your BDP credentials
   ```

4. **Check if Python can read the file**:
   ```python
   from pathlib import Path
   print(Path(".env").exists())  # Should print True
   print(Path(".env").read_text())  # Should show your .env content
   ```

### Error: "Azure AD authentication requires AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET"

**Solution**: Ensure all three BDP credentials are set in your `.env` file.

```bash
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
```

### Error: "Failed to get BDP token"

**Possible causes**:
1. Incorrect tenant ID, client ID, or client secret
2. Application not granted access to Cognitive Services
3. Client secret expired

**Solution**:
- Verify credentials with your Azure administrator
- Check if the Azure AD application has permissions for Cognitive Services
- Regenerate client secret if expired

### Error: "Azure authentication not configured"

**Solution**: Set `AZURE_AUTH_METHOD` to either `api_key` or `bdp`:

```bash
AZURE_AUTH_METHOD=bdp  # or api_key
```

---

## Security Best Practices

1. **Never commit credentials to version control**
   - Keep `.env` in `.gitignore`
   - Use environment variables or secret management systems in production

2. **Rotate client secrets regularly**
   - Follow your organization's security policies for credential rotation

3. **Use BDP in production**
   - API keys are easier for development/testing
   - BDP provides better security and compliance for production

4. **Disable SSL verification only in development**
   - The authenticator disables SSL verification by default for corporate proxies
   - Enable SSL verification in production if possible

---

## Architecture

### BDP Authenticator Class

The `BdpAuthenticator` class (`backend/app/services/bdp_authenticator.py`) provides:

```python
from app.services.bdp_authenticator import get_bdp_authenticator

# Create authenticator
bdp_auth = get_bdp_authenticator()

# Create async client
async_client = bdp_auth.create_async_client(
    azure_endpoint="https://your-endpoint.openai.azure.com/",
    api_version="2025-01-01-preview"
)

# Create sync client
sync_client = bdp_auth.create_sync_client(
    azure_endpoint="https://your-endpoint.openai.azure.com/",
    api_version="2025-01-01-preview"
)
```

### Token Provider

The authenticator creates a token provider function that:
1. Requests a token from Azure AD using ClientSecretCredential
2. Returns the token for the Cognitive Services scope
3. Automatically refreshes tokens when they expire

---

## Testing

### Diagnostic Script

**NEW**: Use the diagnostic script to verify environment variable loading:

```bash
cd backend
python test_env_loading.py
```

This script will:
- Check for `.env` file in all possible locations
- Verify that settings are loading correctly
- Show which BDP credentials are set/missing
- Test BDP authenticator initialization

**Expected output when configured correctly:**
```
✅ All BDP credentials are configured correctly!
   You can now use BDP authentication.
```

### Test with API Key

```bash
# .env
AZURE_AUTH_METHOD=api_key
AZURE_OPENAI_KEY=your-test-key
```

Run the application and verify it works.

### Test with BDP

```bash
# .env
AZURE_AUTH_METHOD=bdp
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
```

Run the application and verify:
1. BDP authentication logs appear
2. Token acquisition succeeds
3. LLM calls work correctly

---

## Support

For issues with:
- **BDP credentials**: Contact your Azure administrator
- **Application setup**: See Azure AD app registration docs
- **Code issues**: Check logs and verify configuration

---

**Last Updated**: 2025-11-10
**Version**: 1.0
