"""
Main API router for AssistedDiscovery v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import runs, patterns, node_facts, llm_test, identify, node_configs, reference_types

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(patterns.router, prefix="/patterns", tags=["patterns"])
api_router.include_router(node_facts.router, prefix="/node_facts", tags=["node_facts"])
api_router.include_router(identify.router, prefix="/identify", tags=["identify"])
api_router.include_router(node_configs.router, prefix="/node-configs", tags=["node_configs"])
api_router.include_router(reference_types.router, prefix="/reference-types", tags=["reference_types"])
api_router.include_router(llm_test.router, prefix="/llm", tags=["llm_testing"])