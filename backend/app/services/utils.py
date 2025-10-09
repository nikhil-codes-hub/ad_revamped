"""
Utility functions for AssistedDiscovery services.

Common helper functions used across different service modules.
"""

import logging

logger = logging.getLogger(__name__)


def normalize_iata_prefix(path: str, message_root: str) -> str:
    """
    Remove IATA_ prefix from message root in section paths.

    NDC 19.2+ uses IATA_ prefix (e.g., IATA_OrderViewRS), while
    NDC 17.2 and earlier use plain names (e.g., OrderViewRS).
    This function normalizes both formats to the plain name for
    consistent pattern matching.

    Args:
        path: Section path that may contain IATA-prefixed message root
              Examples: "IATA_OrderViewRS/Response/DataLists"
                       "/IATA_AirShoppingRS/Response/Offers"
        message_root: Detected message root (without IATA_ prefix)
                     Examples: "OrderViewRS", "AirShoppingRS", "OfferPriceRS"

    Returns:
        Normalized path with IATA_ prefix removed from message root only.
        Other IATA_ prefixed elements (like IATA_LocationCode) are preserved.

    Examples:
        >>> normalize_iata_prefix("IATA_OrderViewRS/Response", "OrderViewRS")
        'OrderViewRS/Response'

        >>> normalize_iata_prefix("/IATA_AirShoppingRS/Response/Offers", "AirShoppingRS")
        '/AirShoppingRS/Response/Offers'

        >>> normalize_iata_prefix("OrderViewRS/Response", "OrderViewRS")
        'OrderViewRS/Response'  # No change if already normalized

        >>> normalize_iata_prefix("IATA_OrderViewRS/Response/IATA_LocationCode", "OrderViewRS")
        'OrderViewRS/Response/IATA_LocationCode'  # Only message root normalized
    """
    if not message_root or not path:
        return path

    iata_variant = f"IATA_{message_root}"

    # Replace with slashes (most common case)
    # This handles: IATA_OrderViewRS/ → OrderViewRS/
    path = path.replace(f'{iata_variant}/', f'{message_root}/')

    # This handles: /IATA_OrderViewRS/ → /OrderViewRS/
    path = path.replace(f'/{iata_variant}/', f'/{message_root}/')

    # Handle case where message root is at end of path (no trailing slash)
    # This handles: IATA_OrderViewRS → OrderViewRS
    if path.endswith(iata_variant):
        path = path[:-len(iata_variant)] + message_root

    # Handle case where message root is at start of path (no leading slash)
    # This handles: IATA_OrderViewRS → OrderViewRS (when path == iata_variant)
    if path == iata_variant:
        path = message_root

    return path
