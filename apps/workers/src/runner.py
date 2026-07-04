"""
Workers package — FastStream async task consumers.

This module is the FastStream application entry point.  
It will be populated in Phase 2 with actual consumer handlers.

Usage:
    faststream run apps.workers.src.runner:app
"""

from faststream import FastStream
from apps.workers.src.topology import broker
from apps.workers.src.subscribers.git_consumer import router as git_router
from apps.workers.src.subscribers.margin_consumer import router as margin_router

broker.include_router(git_router)
broker.include_router(margin_router)

app = FastStream(broker, title="saas-workers", version="1.0.0")
