"""
Workers package — FastStream async task consumers.

This module is the FastStream application entry point.  
It will be populated in Phase 2 with actual consumer handlers.

Usage:
    faststream run apps.workers.src.runner:app
"""

from faststream import FastStream

app = FastStream(title="saas-workers")
