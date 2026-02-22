from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from typing import Iterable


_LATENCY_BUCKETS_MS = (50, 100, 250, 500, 1000, 2500, 5000)


@dataclass(frozen=True)
class RequestTimer:
    started_at: float

    @staticmethod
    def start() -> "RequestTimer":
        return RequestTimer(started_at=perf_counter())

    def elapsed_ms(self) -> float:
        return max(0.0, (perf_counter() - self.started_at) * 1000.0)


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = Lock()
        self._http_requests_total: dict[tuple[str, str, str], int] = {}
        self._http_errors_total: dict[str, int] = {}
        self._http_latency_sum_ms: dict[tuple[str, str], float] = {}
        self._http_latency_count: dict[tuple[str, str], int] = {}
        self._http_latency_bucket_count: dict[tuple[str, str, str], int] = {}
        self._checkout_total: dict[str, int] = {"success": 0, "failed": 0}

    def record_http(
        self,
        *,
        method: str,
        path_group: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        method_label = method.upper()
        status_label = str(status_code)
        base_key = (method_label, path_group)
        request_key = (method_label, path_group, status_label)

        with self._lock:
            self._http_requests_total[request_key] = self._http_requests_total.get(request_key, 0) + 1
            if status_code >= 400:
                self._http_errors_total[path_group] = self._http_errors_total.get(path_group, 0) + 1

            self._http_latency_sum_ms[base_key] = self._http_latency_sum_ms.get(base_key, 0.0) + duration_ms
            self._http_latency_count[base_key] = self._http_latency_count.get(base_key, 0) + 1

            for bucket_label in self._bucket_labels(duration_ms):
                bucket_key = (method_label, path_group, bucket_label)
                self._http_latency_bucket_count[bucket_key] = (
                    self._http_latency_bucket_count.get(bucket_key, 0) + 1
                )

    def record_checkout(self, *, success: bool) -> None:
        with self._lock:
            key = "success" if success else "failed"
            self._checkout_total[key] = self._checkout_total.get(key, 0) + 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines: list[str] = []
            lines.append("# HELP commerce_http_requests_total Total HTTP requests by method/path/status.")
            lines.append("# TYPE commerce_http_requests_total counter")
            for (method, path_group, status), count in sorted(self._http_requests_total.items()):
                lines.append(
                    f'commerce_http_requests_total{{method="{method}",path_group="{path_group}",status="{status}"}} {count}'
                )

            lines.append("# HELP commerce_http_errors_total Total HTTP error responses by path group.")
            lines.append("# TYPE commerce_http_errors_total counter")
            for path_group, count in sorted(self._http_errors_total.items()):
                lines.append(f'commerce_http_errors_total{{path_group="{path_group}"}} {count}')

            lines.append("# HELP commerce_http_request_duration_ms HTTP request latency histogram in milliseconds.")
            lines.append("# TYPE commerce_http_request_duration_ms histogram")
            base_keys = set(self._http_latency_count.keys())
            for method, path_group in sorted(base_keys):
                for bucket in list(_LATENCY_BUCKETS_MS) + ["+Inf"]:
                    bucket_label = str(bucket)
                    bucket_count = self._http_latency_bucket_count.get((method, path_group, bucket_label), 0)
                    lines.append(
                        f'commerce_http_request_duration_ms_bucket{{method="{method}",path_group="{path_group}",le="{bucket_label}"}} {bucket_count}'
                    )

                sum_value = self._http_latency_sum_ms.get((method, path_group), 0.0)
                count_value = self._http_latency_count.get((method, path_group), 0)
                lines.append(
                    f'commerce_http_request_duration_ms_sum{{method="{method}",path_group="{path_group}"}} {sum_value:.4f}'
                )
                lines.append(
                    f'commerce_http_request_duration_ms_count{{method="{method}",path_group="{path_group}"}} {count_value}'
                )

            lines.append("# HELP commerce_checkout_total Checkout attempts by outcome.")
            lines.append("# TYPE commerce_checkout_total counter")
            for result, count in sorted(self._checkout_total.items()):
                lines.append(f'commerce_checkout_total{{result="{result}"}} {count}')

            return "\n".join(lines) + "\n"

    def _bucket_labels(self, duration_ms: float) -> Iterable[str]:
        labels: list[str] = []
        for bucket in _LATENCY_BUCKETS_MS:
            if duration_ms <= bucket:
                labels.append(str(bucket))
        labels.append("+Inf")
        return labels
