from app.infrastructure.observability import MetricsCollector


def test_metrics_collector_renders_core_series() -> None:
    collector = MetricsCollector()
    collector.record_http(method="GET", path_group="products", status_code=200, duration_ms=84.2)
    collector.record_http(method="POST", path_group="orders", status_code=500, duration_ms=320.4)
    collector.record_checkout(success=False)
    collector.record_security_event(event_type="rate_limit", severity="warning")
    collector.record_intent_event(intent_name="checkout", source="hybrid")
    collector.record_intent_confidence(intent_name="checkout", confidence=0.82)
    collector.record_action_truncation(intent_name="multi_status", truncated_count=2)
    collector.record_planner_step_event(event_type="failed", intent_name="multi_status", step_index=2)

    rendered = collector.render_prometheus()

    assert "commerce_http_requests_total" in rendered
    assert 'path_group="products"' in rendered
    assert "commerce_http_errors_total" in rendered
    assert "commerce_http_request_duration_ms_bucket" in rendered
    assert "commerce_checkout_total" in rendered
    assert "commerce_security_events_total" in rendered
    assert "commerce_intent_events_total" in rendered
    assert 'intent="checkout"' in rendered
    assert "commerce_intent_confidence_bucket_total" in rendered
    assert "commerce_action_truncation_total" in rendered
    assert "commerce_planner_step_events_total" in rendered
