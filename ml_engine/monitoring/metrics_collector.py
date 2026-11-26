"""
ml_engine/monitoring/metrics_collector.py

In-memory inference monitoring, latency profiling, and error rate tracking.
Tracks operational health across all machine learning prediction tasks.
"""

from collections import deque
import logging
import threading
import time
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class InferenceMetricsCollector:
    """Thread-safe collector for model latency, error rates, and usage telemetry."""

    _INSTANCE = None
    _LOCK = threading.Lock()

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self._latencies: Dict[str, deque] = {}
        self._counts: Dict[str, int] = {}
        self._errors: Dict[str, int] = {}
        self._unsupported: Dict[str, int] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "InferenceMetricsCollector":
        """Singleton accessor."""
        with cls._LOCK:
            if cls._INSTANCE is None:
                cls._INSTANCE = cls()
            return cls._INSTANCE

    def record_inference(
        self,
        task_name: str,
        latency_ms: float,
        is_success: bool,
        is_unsupported: bool = False,
    ) -> None:
        """Records latency and outcome for a single inference call."""
        with self._lock:
            if task_name not in self._latencies:
                self._latencies[task_name] = deque(maxlen=self.max_samples)
                self._counts[task_name] = 0
                self._errors[task_name] = 0
                self._unsupported[task_name] = 0

            self._latencies[task_name].append(latency_ms)
            self._counts[task_name] += 1
            if not is_success and not is_unsupported:
                self._errors[task_name] += 1
            elif is_unsupported:
                self._unsupported[task_name] += 1

    def get_task_metrics(self, task_name: str) -> Dict[str, Any]:
        """Returns statistical distribution of latency and error rates for a task."""
        with self._lock:
            total = self._counts.get(task_name, 0)
            errors = self._errors.get(task_name, 0)
            unsupported = self._unsupported.get(task_name, 0)
            latencies = list(self._latencies.get(task_name, []))

        if not latencies:
            return {
                "task_name": task_name,
                "total_calls": total,
                "error_rate_pct": 0.0,
                "unsupported_rate_pct": 0.0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "latency_p99_ms": 0.0,
                "latency_mean_ms": 0.0,
            }

        arr = np.array(latencies)
        err_rate = (errors / max(1, total)) * 100.0
        unsup_rate = (unsupported / max(1, total)) * 100.0

        return {
            "task_name": task_name,
            "total_calls": total,
            "error_rate_pct": round(err_rate, 2),
            "unsupported_rate_pct": round(unsup_rate, 2),
            "latency_p50_ms": round(float(np.percentile(arr, 50)), 2),
            "latency_p95_ms": round(float(np.percentile(arr, 95)), 2),
            "latency_p99_ms": round(float(np.percentile(arr, 99)), 2),
            "latency_mean_ms": round(float(np.mean(arr)), 2),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Returns aggregate operational health across all model tasks."""
        with self._lock:
            tasks = list(self._counts.keys())
        return {task: self.get_task_metrics(task) for task in tasks}
