"""Lightweight Prometheus metrics without external dependencies."""
import time
import threading
from collections import defaultdict
from typing import Any
from fastapi import Response


class SimpleCounter:
    def __init__(self, name: str, help_text: str):
        self.name = name
        self.help = help_text
        self._values: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, labels: dict[str, str] | None = None, value: float = 1.0):
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] += value

    def _labels_key(self, labels: dict | None) -> str:
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))

    def collect(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        with self._lock:
            for key, val in self._values.items():
                label_str = f"{{{key}}}" if key else ""
                lines.append(f"{self.name}{label_str} {val}")
        return "\n".join(lines)


class SimpleHistogram:
    def __init__(self, name: str, help_text: str, buckets: list[float] | None = None):
        self.name = name
        self.help = help_text
        self.buckets = buckets or [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._observations: list[float] = []
        self._lock = threading.Lock()

    def observe(self, value: float):
        with self._lock:
            self._observations.append(value)

    def collect(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        with self._lock:
            obs = sorted(self._observations)
        total = len(obs)
        total_sum = sum(obs)
        for b in self.buckets:
            count = sum(1 for o in obs if o <= b)
            lines.append(f'{self.name}_bucket{{le="{b}"}} {count}')
        lines.append(f'{self.name}_bucket{{le="+Inf"}} {total}')
        lines.append(f"{self.name}_sum {total_sum}")
        lines.append(f"{self.name}_count {total}")
        return "\n".join(lines)


# Global metrics instances
REQUEST_COUNT = SimpleCounter("copilot_requests_total", "Total API requests")
REQUEST_DURATION = SimpleHistogram("copilot_request_duration_seconds", "Request duration in seconds")
CACHE_HITS = SimpleCounter("copilot_cache_hits_total", "Semantic cache hits")
CACHE_MISSES = SimpleCounter("copilot_cache_misses_total", "Semantic cache misses")
RAG_RETRIEVAL_COUNT = SimpleCounter("copilot_rag_retrievals_total", "RAG retrieval operations")
LLM_ERRORS = SimpleCounter("copilot_llm_errors_total", "LLM API errors")


def collect_all_metrics() -> str:
    """Collect all metrics in Prometheus text exposition format."""
    sections = [
        REQUEST_COUNT.collect(),
        REQUEST_DURATION.collect(),
        CACHE_HITS.collect(),
        CACHE_MISSES.collect(),
        RAG_RETRIEVAL_COUNT.collect(),
        LLM_ERRORS.collect(),
    ]
    return "\n\n".join(sections) + "\n"
