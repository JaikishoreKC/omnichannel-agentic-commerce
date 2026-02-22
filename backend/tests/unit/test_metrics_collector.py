from app.infrastructure.observability import MetricsCollector


def test_metrics_collector_renders_core_series() -> None:
    collector = MetricsCollector()
    collector.record_http(method="GET", path_group="products", status_code=200, duration_ms=84.2)
    collector.record_http(method="POST", path_group="orders", status_code=500, duration_ms=320.4)
    collector.record_checkout(success=False)

    rendered = collector.render_prometheus()

    assert "commerce_http_requests_total" in rendered
    assert 'path_group="products"' in rendered
    assert "commerce_http_errors_total" in rendered
    assert "commerce_http_request_duration_ms_bucket" in rendered
    assert "commerce_checkout_total" in rendered
