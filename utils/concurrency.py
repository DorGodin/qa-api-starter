"""Fire several calls at the same instant.

A thread pool on its own starts calls one after another, and the first often
finishes before the last has started - a race test that way races nothing. Each
call here waits at a barrier until every thread is ready, and they all go
together.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")


def at_once(calls: list[Callable[[], T]], timeout: float = 30) -> list[T]:
    """Run every call concurrently, released together. Results in input order."""
    if not calls:
        return []
    barrier = threading.Barrier(len(calls))

    def run(call: Callable[[], T]) -> T:
        barrier.wait(timeout=timeout)
        return call()

    # One worker per call, or the barrier would wait forever for a thread the
    # pool never started.
    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(run, calls))
