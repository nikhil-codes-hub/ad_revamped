# IATA Prefix Normalization - Analysis & Solution

## Current Problem

The system has **hardcoded** normalization for only `IATA_OrderViewRS`:

```python
# Current code (HARDCODED):
normalized = normalized.replace('IATA_OrderViewRS/', 'OrderViewRS/')
normalized = normalized.replace('/IATA_OrderViewRS/', '/OrderViewRS/')
```

This means:
- ✅ Works for `IATA_OrderViewRS` → `OrderViewRS`
- ❌ Fails for `IATA_AirShoppingRS` → stays as `IATA_AirShoppingRS`
- ❌ Fails for `IATA_OfferPriceRS` → stays as `IATA_OfferPriceRS`
- ❌ Fails for `IATA_OrderReshopRS` → stays as `IATA_OrderReshopRS`

## Analysis of Alaska XMLs

Found the following IATA-prefixed message roots:

| File | Root Element | Should Normalize To |
|------|--------------|---------------------|
| AirShoppingRS.xml | `IATA_AirShoppingRS` | `AirShoppingRS` |
| OfferPriceRS.xml | `IATA_OfferPriceRS` | `OfferPriceRS` |
| OrderReshopRS.xml | `IATA_OrderReshopRS` | `OrderReshopRS` |
| OrderViewRS.xml | `IATA_OrderViewRS` | `OrderViewRS` |

Additional IATA-prefixed elements found:
- `IATA_LocationCode` (attribute/element in all files)
- `IATA_AircraftType`, `IATA_AircraftTypeCode` (in OfferPriceRS)
- `IATA_OffersAndOrdersMessage` (namespace)
- `IATA_OffersAndOrdersCommonTypes` (namespace)

## Why IATA_ Prefix Exists

Based on NDC specification:
- **NDC 17.2 and earlier**: Used simple names like `OrderViewRS`
- **NDC 19.2 and later**: Added `IATA_` prefix to message roots for XML namespace clarity
- Airlines may use either format depending on their NDC version

## Proposed Solution

### Approach 1: **Generic Message Root Normalization** (RECOMMENDED)

**Strategy**: Dynamically detect the message root from XML, then normalize ALL occurrences of `IATA_{MessageRoot}` to `{MessageRoot}`.

**Advantages**:
- ✅ Works for ANY NDC message type (OrderViewRS, AirShoppingRS, etc.)
- ✅ Future-proof for new message types
- ✅ No hardcoding needed
- ✅ Works for both paths and element names

**Implementation**:

```python
def normalize_iata_prefix(path: str, message_root: str) -> str:
    """
    Remove IATA_ prefix from message root in paths.

    Args:
        path: Section path (e.g., "IATA_AirShoppingRS/Response/DataLists")
        message_root: Detected message root (e.g., "AirShoppingRS")

    Returns:
        Normalized path with IATA_ prefix removed

    Examples:
        normalize_iata_prefix("IATA_OrderViewRS/Response", "OrderViewRS")
        → "OrderViewRS/Response"

        normalize_iata_prefix("/IATA_AirShoppingRS/Response/Offers", "AirShoppingRS")
        → "/AirShoppingRS/Response/Offers"
    """
    if not message_root:
        return path

    # Create both prefixed and non-prefixed versions
    iata_variant = f"IATA_{message_root}"

    # Replace both with and without leading slash
    path = path.replace(f'{iata_variant}/', f'{message_root}/')
    path = path.replace(f'/{iata_variant}/', f'/{message_root}/')
    path = path.replace(f'{iata_variant}', f'{message_root}')  # Handle end of path

    return path
```

**Where to Apply**:

1. **`discovery_workflow.py`** - Lines 121-122, 150-157:
   ```python
   # OLD (hardcoded):
   normalized_path = section_path.replace('IATA_OrderViewRS/', 'OrderViewRS/')

   # NEW (dynamic):
   normalized_path = normalize_iata_prefix(section_path, self.message_root)
   ```

2. **`pattern_generator.py`** - Lines 36-37:
   ```python
   # OLD (hardcoded):
   normalized = normalized.replace('/IATA_OrderViewRS/', '/OrderViewRS/')

   # NEW (dynamic):
   normalized = normalize_iata_prefix(normalized, message_root)
   ```

3. **`xml_parser.py`** - When extracting section paths:
   ```python
   # Apply normalization during path extraction
   section_path = normalize_iata_prefix(raw_path, self.version_info.message_root)
   ```

### Approach 2: **Regex-Based Universal Prefix Removal**

**Strategy**: Use regex to remove `IATA_` prefix from any element that matches `IATA_[A-Z]`.

```python
import re

def normalize_iata_prefix_regex(path: str) -> str:
    """Remove IATA_ prefix from all elements using regex."""
    # Match IATA_ followed by uppercase letter (message root pattern)
    return re.sub(r'IATA_([A-Z][A-Za-z]+)', r'\1', path)
```

**Advantages**:
- ✅ Universal - works on all IATA_ prefixed elements
- ✅ No need to know message root

**Disadvantages**:
- ⚠️ May remove IATA_ from elements where it should stay (e.g., `IATA_LocationCode`)
- ⚠️ Less precise than Approach 1

### Approach 3: **Whitelist-Based Normalization**

**Strategy**: Maintain a list of known message roots to normalize.

```python
MESSAGE_ROOTS = [
    'OrderViewRS', 'OrderCreateRQ', 'OrderChangeRQ',
    'AirShoppingRS', 'AirShoppingRQ',
    'OfferPriceRS', 'OfferPriceRQ',
    'OrderReshopRS', 'OrderReshopRQ',
    'ServiceListRS', 'ServiceListRQ',
    'SeatAvailabilityRS', 'SeatAvailabilityRQ'
]

def normalize_iata_prefix_whitelist(path: str) -> str:
    """Remove IATA_ prefix for known message roots."""
    for root in MESSAGE_ROOTS:
        iata_variant = f'IATA_{root}'
        path = path.replace(f'{iata_variant}/', f'{root}/')
        path = path.replace(f'/{iata_variant}/', f'/{root}/')
    return path
```

**Advantages**:
- ✅ Precise - only normalizes known message types
- ✅ Safe - won't accidentally normalize other IATA_ elements

**Disadvantages**:
- ❌ Requires maintaining list
- ❌ Not future-proof for new message types

## Recommendation

**Use Approach 1 (Generic Message Root Normalization)**

**Reasoning**:
1. **Dynamic**: Works automatically for any NDC message type
2. **Future-proof**: No maintenance needed when new messages are added
3. **Precise**: Only normalizes the message root, not other IATA_ elements
4. **Clean**: Message root is already detected by `xml_parser.py`

## Implementation Plan

### Step 1: Create Utility Function

**File**: `backend/app/services/utils.py` (new file)

```python
"""Utility functions for AssistedDiscovery."""

def normalize_iata_prefix(path: str, message_root: str) -> str:
    """
    Remove IATA_ prefix from message root in section paths.

    NDC 19.2+ uses IATA_ prefix (e.g., IATA_OrderViewRS), while
    NDC 17.2 and earlier use plain names (e.g., OrderViewRS).
    This function normalizes both formats to the plain name.

    Args:
        path: Section path that may contain IATA-prefixed message root
        message_root: Detected message root (without IATA_ prefix)

    Returns:
        Normalized path with IATA_ prefix removed from message root only

    Examples:
        >>> normalize_iata_prefix("IATA_OrderViewRS/Response", "OrderViewRS")
        'OrderViewRS/Response'

        >>> normalize_iata_prefix("/IATA_AirShoppingRS/Response/Offers", "AirShoppingRS")
        '/AirShoppingRS/Response/Offers'

        >>> normalize_iata_prefix("OrderViewRS/Response", "OrderViewRS")
        'OrderViewRS/Response'  # No change if already normalized
    """
    if not message_root:
        return path

    iata_variant = f"IATA_{message_root}"

    # Replace with and without slashes
    path = path.replace(f'{iata_variant}/', f'{message_root}/')
    path = path.replace(f'/{iata_variant}/', f'/{message_root}/')

    # Handle case where message root is at end of path
    if path.endswith(iata_variant):
        path = path[:-len(iata_variant)] + message_root

    return path
```

### Step 2: Update `discovery_workflow.py`

```python
from app.services.utils import normalize_iata_prefix

class DiscoveryWorkflow:
    def _get_target_paths_from_configs(self, node_configs: Dict[str, Dict]) -> List[Dict]:
        # ... existing code ...

        for section_path, config in node_configs.items():
            # Remove IATA_ prefix using message root
            normalized_path = normalize_iata_prefix(section_path, self.message_root)

            target_paths.append({
                'path_local': f"/{normalized_path}",
                # ... rest of config ...
            })

    def _should_extract_node(self, section_path: str, node_configs: Dict[str, Dict]) -> bool:
        # Normalize the section_path using message root
        normalized_section = normalize_iata_prefix(section_path, self.message_root)

        for config_path, config in node_configs.items():
            normalized_config = normalize_iata_prefix(config_path, self.message_root)
            # ... rest of logic ...
```

### Step 3: Update `pattern_generator.py`

```python
from app.services.utils import normalize_iata_prefix

class PatternGenerator:
    def _normalize_path(self, path: str, message_root: str) -> str:
        """Normalize section path for consistent matching."""
        normalized = path.strip('/')

        # Remove IATA_ prefix dynamically based on message root
        normalized = normalize_iata_prefix(normalized, message_root)

        return normalized
```

### Step 4: Test with All Message Types

**Test Cases**:
```python
# Test OrderViewRS (existing)
assert normalize_iata_prefix("IATA_OrderViewRS/Response", "OrderViewRS") == "OrderViewRS/Response"

# Test AirShoppingRS (new)
assert normalize_iata_prefix("IATA_AirShoppingRS/Response/Offers", "AirShoppingRS") == "AirShoppingRS/Response/Offers"

# Test OfferPriceRS (new)
assert normalize_iata_prefix("/IATA_OfferPriceRS/Response", "OfferPriceRS") == "/OfferPriceRS/Response"

# Test OrderReshopRS (new)
assert normalize_iata_prefix("IATA_OrderReshopRS/Response", "OrderReshopRS") == "OrderReshopRS/Response"

# Test already normalized (should not change)
assert normalize_iata_prefix("AirShoppingRS/Response", "AirShoppingRS") == "AirShoppingRS/Response"

# Test nested IATA_ (should only normalize message root)
assert normalize_iata_prefix("IATA_OrderViewRS/Response/IATA_LocationCode", "OrderViewRS") == "OrderViewRS/Response/IATA_LocationCode"
```

## Edge Cases to Handle

1. **Multiple IATA_ elements in path**:
   - `IATA_OrderViewRS/Response/IATA_LocationCode`
   - Should normalize to: `OrderViewRS/Response/IATA_LocationCode`
   - ✅ Handled by only replacing message root

2. **Message root at end of path**:
   - `IATA_OrderViewRS`
   - Should normalize to: `OrderViewRS`
   - ✅ Handled by endswith check

3. **Already normalized paths**:
   - `OrderViewRS/Response`
   - Should stay as: `OrderViewRS/Response`
   - ✅ Handled by checking for IATA_ prefix

4. **Empty or None message_root**:
   - Should return path unchanged
   - ✅ Handled by early return

## Testing Checklist

Before deploying:
- [ ] Test with IATA_OrderViewRS XML (existing)
- [ ] Test with IATA_AirShoppingRS XML (new)
- [ ] Test with IATA_OfferPriceRS XML (new)
- [ ] Test with IATA_OrderReshopRS XML (new)
- [ ] Test with non-IATA OrderViewRS XML (backward compatibility)
- [ ] Verify IATA_LocationCode is NOT normalized
- [ ] Verify pattern matching works across both formats

## Estimated Effort

- **Implementation**: 30 minutes
- **Testing**: 30 minutes
- **Total**: 1 hour

## Benefits

1. **User Testing Ready**: Users can test ANY NDC message type
2. **Future-Proof**: Works with new message types automatically
3. **No Maintenance**: No hardcoded lists to update
4. **Backward Compatible**: Works with both IATA_ and non-IATA_ formats

---

**Recommendation**: Implement Approach 1 immediately before user testing to ensure compatibility with all NDC message types.
