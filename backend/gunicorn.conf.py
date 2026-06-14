"""Gunicorn config.

gevent worker is chosen because SSE streaming holds long-lived connections that
spend most of their time waiting on the LLM upstream (I/O bound). sync/thread
workers would be tied up for the duration of each stream and exhaust the pool
(PLAN §2 "Production worker"). Worker count defaults to 2*CPU+1.
"""
from __future__ import annotations

import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
worker_class = "gevent"
workers = int(os.getenv("WEB_CONCURRENCY", str(2 * multiprocessing.cpu_count() + 1)))
worker_connections = 1000
timeout = 120          # allow long streaming responses
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()
