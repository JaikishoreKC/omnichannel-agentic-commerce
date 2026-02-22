from app.infrastructure.rate_limiter import SlidingWindowRateLimiter


def test_sliding_window_rate_limiter_blocks_after_limit() -> None:
    limiter = SlidingWindowRateLimiter()
    key = "scope:subject"

    first = limiter.check(key=key, limit=2, window_seconds=60)
    second = limiter.check(key=key, limit=2, window_seconds=60)
    third = limiter.check(key=key, limit=2, window_seconds=60)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.remaining == 0
