from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.infrastructure.superu_client import SuperUClient
from app.services.notification_service import NotificationService
from app.services.support_service import SupportService
from app.store.in_memory import InMemoryStore


class VoiceRecoveryService:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        settings: Settings,
        superu_client: SuperUClient,
        support_service: SupportService,
        notification_service: NotificationService,
    ) -> None:
        self.store = store
        self.settings = settings
        self.superu_client = superu_client
        self.support_service = support_service
        self.notification_service = notification_service
        self._ensure_defaults()

    def process_due_work(self) -> dict[str, Any]:
        now = self.store.utc_now()
        enqueued = self._enqueue_abandoned_cart_jobs(now=now)
        processed = self._process_due_jobs(now=now)
        polled = self._poll_provider_updates(now=now)
        generated_alerts = self._evaluate_alerts(now=now)
        return {
            "enqueued": enqueued,
            "processed": processed,
            "polled": polled,
            "alertsGenerated": generated_alerts,
            "settingsEnabled": bool(self.get_settings().get("enabled", False)),
        }

    def get_settings(self) -> dict[str, Any]:
        with self.store.lock:
            settings = deepcopy(self.store.voice_settings)
        return settings

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            current = deepcopy(self.store.voice_settings)
            merged = {**current, **updates}
            merged["abandonmentMinutes"] = max(1, int(merged.get("abandonmentMinutes", 30)))
            merged["maxAttemptsPerCart"] = max(1, int(merged.get("maxAttemptsPerCart", 3)))
            merged["maxCallsPerUserPerDay"] = max(1, int(merged.get("maxCallsPerUserPerDay", 2)))
            merged["maxCallsPerDay"] = max(1, int(merged.get("maxCallsPerDay", 300)))
            merged["dailyBudgetUsd"] = max(0.0, float(merged.get("dailyBudgetUsd", 300.0)))
            merged["estimatedCostPerCallUsd"] = max(
                0.0, float(merged.get("estimatedCostPerCallUsd", 0.7))
            )
            merged["quietHoursStart"] = max(0, min(23, int(merged.get("quietHoursStart", 21))))
            merged["quietHoursEnd"] = max(0, min(23, int(merged.get("quietHoursEnd", 8))))
            merged["retryBackoffSeconds"] = self._normalize_backoff_list(
                merged.get("retryBackoffSeconds")
            )
            merged["scriptVersion"] = str(merged.get("scriptVersion", "v1")).strip() or "v1"
            merged["scriptTemplate"] = str(
                merged.get("scriptTemplate", self.settings.voice_script_template)
            ).strip()
            merged["assistantId"] = str(merged.get("assistantId", "")).strip()
            merged["fromPhoneNumber"] = str(merged.get("fromPhoneNumber", "")).strip()
            merged["defaultTimezone"] = str(merged.get("defaultTimezone", "UTC")).strip() or "UTC"
            merged["alertBacklogThreshold"] = max(
                1, int(merged.get("alertBacklogThreshold", 50))
            )
            merged["alertFailureRatioThreshold"] = max(
                0.01, min(1.0, float(merged.get("alertFailureRatioThreshold", 0.35)))
            )
            merged["enabled"] = bool(merged.get("enabled", False))
            merged["killSwitch"] = bool(merged.get("killSwitch", False))
            self.store.voice_settings = merged
            return deepcopy(merged)

    def list_calls(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self.store.lock:
            rows = list(self.store.voice_calls_by_id.values())
        if status:
            rows = [row for row in rows if str(row.get("status", "")) == status]
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return [deepcopy(row) for row in rows[:safe_limit]]

    def list_jobs(self, *, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 500))
        with self.store.lock:
            rows = list(self.store.voice_jobs_by_id.values())
        if status:
            rows = [row for row in rows if str(row.get("status", "")) == status]
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return [deepcopy(row) for row in rows[:safe_limit]]

    def suppress_user(self, *, user_id: str, reason: str) -> dict[str, Any]:
        payload = {
            "userId": user_id,
            "reason": reason.strip() or "manual_suppression",
            "createdAt": self.store.iso_now(),
        }
        with self.store.lock:
            self.store.voice_suppressions_by_user[user_id] = deepcopy(payload)
        return payload

    def unsuppress_user(self, *, user_id: str) -> None:
        with self.store.lock:
            self.store.voice_suppressions_by_user.pop(user_id, None)

    def list_suppressions(self) -> list[dict[str, Any]]:
        with self.store.lock:
            rows = list(self.store.voice_suppressions_by_user.values())
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return [deepcopy(row) for row in rows]

    def list_alerts(self, *, limit: int = 50, severity: str | None = None) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 200))
        with self.store.lock:
            rows = list(self.store.voice_alerts)
        if severity:
            rows = [row for row in rows if str(row.get("severity", "")) == severity]
        rows.sort(key=lambda row: str(row.get("createdAt", "")), reverse=True)
        return [deepcopy(row) for row in rows[:safe_limit]]

    def stats(self) -> dict[str, Any]:
        today = self.store.utc_now().date().isoformat()
        settings = self.get_settings()
        with self.store.lock:
            calls = list(self.store.voice_calls_by_id.values())
            jobs = list(self.store.voice_jobs_by_id.values())
        calls_today = [row for row in calls if str(row.get("createdAt", "")).startswith(today)]
        completed_today = [row for row in calls_today if str(row.get("status", "")) == "completed"]
        failed_today = [row for row in calls_today if str(row.get("status", "")) == "failed"]
        suppressed_today = [
            row for row in calls_today if str(row.get("status", "")) in {"suppressed", "skipped"}
        ]
        pending_jobs = [row for row in jobs if str(row.get("status", "")) in {"queued", "retrying"}]
        retrying_jobs = [row for row in jobs if str(row.get("status", "")) == "retrying"]
        estimated_spend = round(
            len(calls_today) * float(settings.get("estimatedCostPerCallUsd", 0.0)),
            2,
        )
        return {
            "enabled": bool(settings.get("enabled", False)),
            "totalCalls": len(calls),
            "callsToday": len(calls_today),
            "completedToday": len(completed_today),
            "failedToday": len(failed_today),
            "suppressedToday": len(suppressed_today),
            "pendingJobs": len(pending_jobs),
            "retryingJobs": len(retrying_jobs),
            "estimatedSpendToday": estimated_spend,
            "dailyBudgetUsd": float(settings.get("dailyBudgetUsd", 0.0)),
            "maxCallsPerDay": int(settings.get("maxCallsPerDay", 0)),
            "alertsOpen": len(self.list_alerts(limit=200)),
        }

    def _ensure_defaults(self) -> None:
        with self.store.lock:
            if not isinstance(self.store.voice_settings, dict):
                self.store.voice_settings = {}
            default_settings = {
                "enabled": bool(self.settings.superu_enabled),
                "killSwitch": bool(self.settings.voice_global_kill_switch),
                "abandonmentMinutes": int(self.settings.voice_abandonment_minutes),
                "maxAttemptsPerCart": int(self.settings.voice_max_attempts_per_cart),
                "maxCallsPerUserPerDay": int(self.settings.voice_max_calls_per_user_per_day),
                "maxCallsPerDay": int(self.settings.voice_max_calls_per_day),
                "dailyBudgetUsd": float(self.settings.voice_daily_budget_usd),
                "estimatedCostPerCallUsd": float(self.settings.voice_estimated_cost_per_call_usd),
                "quietHoursStart": int(self.settings.voice_quiet_hours_start),
                "quietHoursEnd": int(self.settings.voice_quiet_hours_end),
                "retryBackoffSeconds": self._normalize_backoff_list(
                    self.settings.voice_retry_backoff_seconds_csv
                ),
                "scriptVersion": self.settings.voice_script_version,
                "scriptTemplate": self.settings.voice_script_template,
                "assistantId": self.settings.superu_assistant_id,
                "fromPhoneNumber": self.settings.superu_from_phone_number,
                "defaultTimezone": self.settings.voice_default_timezone,
                "alertBacklogThreshold": int(self.settings.voice_alert_backlog_threshold),
                "alertFailureRatioThreshold": float(self.settings.voice_alert_failure_ratio_threshold),
            }
            for key, value in default_settings.items():
                self.store.voice_settings.setdefault(key, value)

    def _enqueue_abandoned_cart_jobs(self, *, now: datetime) -> int:
        settings = self.get_settings()
        if not bool(settings.get("enabled", False)):
            return 0
        cutoff = now - timedelta(minutes=int(settings.get("abandonmentMinutes", 30)))
        enqueued = 0
        with self.store.lock:
            carts = list(self.store.carts_by_id.values())
            existing_jobs = list(self.store.voice_jobs_by_id.values())
        existing_keys = {
            str(job.get("recoveryKey", ""))
            for job in existing_jobs
            if str(job.get("status", ""))
            in {"queued", "retrying", "processing", "completed", "cancelled", "dead_letter"}
        }

        for cart in carts:
            user_id = str(cart.get("userId", "")).strip()
            if not user_id:
                continue
            if int(cart.get("itemCount", 0)) <= 0:
                continue
            updated_at = self._parse_iso(cart.get("updatedAt"))
            if updated_at is None or updated_at > cutoff:
                continue
            if self._has_newer_order(user_id=user_id, since=updated_at):
                continue
            recovery_key = f"{cart['id']}::{cart['updatedAt']}"
            with self.store.lock:
                if recovery_key in self.store.voice_call_idempotency:
                    continue
            if recovery_key in existing_keys:
                continue
            job = {
                "id": f"vjob_{self.store.next_id('item')}",
                "status": "queued",
                "userId": user_id,
                "sessionId": str(cart.get("sessionId", "")),
                "cartId": str(cart["id"]),
                "recoveryKey": recovery_key,
                "attempt": 0,
                "nextRunAt": now.isoformat(),
                "lastError": None,
                "createdAt": self.store.iso_now(),
                "updatedAt": self.store.iso_now(),
            }
            with self.store.lock:
                self.store.voice_jobs_by_id[job["id"]] = deepcopy(job)
            enqueued += 1
            existing_keys.add(recovery_key)
        return enqueued

    def _process_due_jobs(self, *, now: datetime) -> dict[str, int]:
        with self.store.lock:
            jobs = [
                deepcopy(job)
                for job in self.store.voice_jobs_by_id.values()
                if str(job.get("status", "")) in {"queued", "retrying"}
                and self._parse_iso(job.get("nextRunAt")) is not None
                and self._parse_iso(job.get("nextRunAt")) <= now
            ]
        jobs.sort(key=lambda row: str(row.get("nextRunAt", "")))
        counters = {"completed": 0, "retried": 0, "deadLetter": 0, "cancelled": 0}
        for job in jobs:
            result = self._process_single_job(job=job, now=now)
            counters[result] = counters.get(result, 0) + 1
        return counters

    def _process_single_job(self, *, job: dict[str, Any], now: datetime) -> str:
        settings = self.get_settings()
        if bool(settings.get("killSwitch", False)):
            self._complete_job(job_id=str(job["id"]), status="cancelled", error="kill_switch")
            self._append_alert(
                code="VOICE_KILL_SWITCH_ACTIVE",
                message="Voice recovery kill switch is active; jobs are being cancelled.",
                severity="warning",
            )
            return "cancelled"

        user = self._get_user(job.get("userId"))
        cart = self._get_cart(job.get("cartId"))
        if not user or not cart or int(cart.get("itemCount", 0)) <= 0:
            self._complete_job(job_id=str(job["id"]), status="cancelled", error="cart_or_user_missing")
            self._record_call_event(
                job=job,
                cart=cart,
                user=user,
                status="skipped",
                error="cart_or_user_missing",
            )
            return "cancelled"

        user_id = str(user.get("id", "")).strip()
        if user_id in self._suppressed_users():
            self._complete_job(job_id=str(job["id"]), status="cancelled", error="suppressed_user")
            self._record_call_event(job=job, cart=cart, user=user, status="suppressed", error="suppressed_user")
            return "cancelled"

        phone = str(user.get("phone", "")).strip()
        if not phone:
            self._complete_job(job_id=str(job["id"]), status="cancelled", error="missing_phone")
            self._record_call_event(job=job, cart=cart, user=user, status="skipped", error="missing_phone")
            return "cancelled"

        if self._in_quiet_hours(user=user, now=now, settings=settings):
            next_run = self._next_non_quiet_time(user=user, now=now, settings=settings)
            self._reschedule_job(job_id=str(job["id"]), attempt=int(job.get("attempt", 0)), next_run=next_run)
            return "retried"

        budget_decision = self._budget_and_cap_guardrails(user_id=user_id, settings=settings, now=now)
        if budget_decision != "ok":
            self._complete_job(job_id=str(job["id"]), status="cancelled", error=budget_decision)
            self._record_call_event(job=job, cart=cart, user=user, status="skipped", error=budget_decision)
            self._append_alert(
                code="VOICE_GUARDRAIL_TRIGGERED",
                message=f"Voice call blocked by guardrail: {budget_decision}",
                severity="warning",
                details={"userId": user_id, "jobId": str(job["id"])},
            )
            return "cancelled"

        campaign = self._campaign_payload(user=user, cart=cart, settings=settings)
        assistant_id = str(settings.get("assistantId", "")).strip() or None
        from_phone_number = str(settings.get("fromPhoneNumber", "")).strip() or None
        attempt_number = int(job.get("attempt", 0)) + 1

        if not self.superu_client.enabled:
            self._complete_job(job_id=str(job["id"]), status="cancelled", error="provider_not_configured")
            self._record_call_event(
                job=job,
                cart=cart,
                user=user,
                status="skipped",
                error="provider_not_configured",
                request_payload=campaign,
            )
            self._append_alert(
                code="VOICE_PROVIDER_NOT_CONFIGURED",
                message="Voice recovery is enabled but SuperU credentials are missing.",
                severity="critical",
            )
            return "cancelled"
        if not assistant_id or not from_phone_number:
            self._complete_job(job_id=str(job["id"]), status="cancelled", error="provider_not_configured")
            self._record_call_event(
                job=job,
                cart=cart,
                user=user,
                status="skipped",
                error="provider_not_configured",
                request_payload=campaign,
            )
            self._append_alert(
                code="VOICE_PROVIDER_NOT_CONFIGURED",
                message="Voice settings require assistantId and fromPhoneNumber.",
                severity="critical",
            )
            return "cancelled"

        try:
            response = self.superu_client.start_outbound_call(
                to_phone_number=phone,
                assistant_id=assistant_id,
                from_phone_number=from_phone_number,
                metadata={
                    "campaign": campaign,
                    "jobId": str(job.get("id", "")),
                    "cartId": str(cart.get("id", "")),
                    "userId": user_id,
                },
            )
            provider_call_id = self._extract_provider_call_id(response)
            self._complete_job(job_id=str(job["id"]), status="completed", error=None)
            self._record_call_event(
                job=job,
                cart=cart,
                user=user,
                status="initiated",
                error=None,
                request_payload=campaign,
                response_payload=response,
                provider_call_id=provider_call_id,
                attempt_number=attempt_number,
            )
            with self.store.lock:
                self.store.voice_call_idempotency[str(job.get("recoveryKey", ""))] = provider_call_id or str(
                    job["id"]
                )
            return "completed"
        except Exception as exc:
            error = str(exc)
            max_attempts = max(1, int(settings.get("maxAttemptsPerCart", 3)))
            if attempt_number >= max_attempts:
                self._complete_job(job_id=str(job["id"]), status="dead_letter", error=error)
                self._record_call_event(
                    job=job,
                    cart=cart,
                    user=user,
                    status="failed",
                    error=error,
                    request_payload=campaign,
                    attempt_number=attempt_number,
                )
                self._append_alert(
                    code="VOICE_DEAD_LETTER",
                    message="Voice call job moved to dead-letter after max retries.",
                    severity="critical",
                    details={"jobId": str(job["id"]), "error": error},
                )
                return "deadLetter"

            backoffs = self._normalize_backoff_list(settings.get("retryBackoffSeconds"))
            delay = backoffs[min(attempt_number - 1, len(backoffs) - 1)]
            next_run = now + timedelta(seconds=delay)
            self._reschedule_job(job_id=str(job["id"]), attempt=attempt_number, next_run=next_run, error=error)
            self._record_call_event(
                job=job,
                cart=cart,
                user=user,
                status="retrying",
                error=error,
                request_payload=campaign,
                attempt_number=attempt_number,
                next_retry_at=next_run.isoformat(),
            )
            return "retried"

    def _poll_provider_updates(self, *, now: datetime) -> int:
        if not self.superu_client.enabled:
            return 0
        with self.store.lock:
            active_calls = [
                deepcopy(call)
                for call in self.store.voice_calls_by_id.values()
                if str(call.get("status", "")) in {"initiated", "ringing", "in_progress"}
                and str(call.get("providerCallId", "")).strip()
            ]
        updates = 0
        for call in active_calls:
            provider_call_id = str(call.get("providerCallId", "")).strip()
            if not provider_call_id:
                continue
            try:
                rows = self.superu_client.fetch_call_logs(call_id=provider_call_id, limit=1)
            except Exception as exc:
                self._append_alert(
                    code="VOICE_POLL_FAILED",
                    message=f"Failed to poll SuperU call logs: {exc}",
                    severity="warning",
                    details={"callId": call.get("id"), "providerCallId": provider_call_id},
                )
                continue
            if not rows:
                continue
            latest = rows[-1]
            normalized_status = self._normalize_provider_status(latest)
            outcome = self._extract_outcome(latest)
            if normalized_status in {"completed", "failed"}:
                self._update_call_terminal(
                    call_id=str(call["id"]),
                    status=normalized_status,
                    outcome=outcome,
                    payload=latest,
                )
                updates += 1
            elif normalized_status in {"ringing", "in_progress"}:
                self._update_call_progress(
                    call_id=str(call["id"]),
                    status=normalized_status,
                    payload=latest,
                )
                updates += 1
        return updates

    def _evaluate_alerts(self, *, now: datetime) -> int:
        generated = 0
        settings = self.get_settings()
        backlog_threshold = int(settings.get("alertBacklogThreshold", 50))
        failure_ratio_threshold = float(settings.get("alertFailureRatioThreshold", 0.35))
        pending = len(self.list_jobs(limit=1000, status="queued")) + len(
            self.list_jobs(limit=1000, status="retrying")
        )
        if pending > backlog_threshold:
            self._append_alert(
                code="VOICE_BACKLOG_HIGH",
                message=f"Voice job backlog is high ({pending}).",
                severity="warning",
                details={"pendingJobs": pending},
            )
            generated += 1

        today = now.date().isoformat()
        calls_today = [row for row in self.list_calls(limit=2000) if str(row.get("createdAt", "")).startswith(today)]
        terminal = [
            row
            for row in calls_today
            if str(row.get("status", "")) in {"completed", "failed", "suppressed", "skipped"}
        ]
        failed = [row for row in terminal if str(row.get("status", "")) == "failed"]
        if terminal:
            ratio = len(failed) / len(terminal)
            if ratio > failure_ratio_threshold:
                self._append_alert(
                    code="VOICE_FAILURE_RATIO_HIGH",
                    message=f"Voice failure ratio today is {ratio:.2f}, above threshold.",
                    severity="critical",
                    details={"terminalCalls": len(terminal), "failedCalls": len(failed), "ratio": ratio},
                )
                generated += 1
        return generated

    def _record_call_event(
        self,
        *,
        job: dict[str, Any],
        cart: dict[str, Any] | None,
        user: dict[str, Any] | None,
        status: str,
        error: str | None,
        request_payload: dict[str, Any] | None = None,
        response_payload: dict[str, Any] | None = None,
        provider_call_id: str | None = None,
        attempt_number: int | None = None,
        next_retry_at: str | None = None,
    ) -> None:
        call = self._get_or_create_call(job=job, cart=cart, user=user)
        attempt_index = attempt_number if attempt_number is not None else int(job.get("attempt", 0))
        event = {
            "attempt": max(1, attempt_index),
            "timestamp": self.store.iso_now(),
            "status": status,
            "error": error,
            "request": request_payload or {},
            "response": response_payload or {},
        }
        call.setdefault("attempts", []).append(event)
        call["attemptCount"] = len(call["attempts"])
        call["status"] = status
        call["updatedAt"] = self.store.iso_now()
        call["lastError"] = error
        call["nextRetryAt"] = next_retry_at
        if provider_call_id:
            call["providerCallId"] = provider_call_id
        with self.store.lock:
            self.store.voice_calls_by_id[str(call["id"])] = deepcopy(call)

    def _get_or_create_call(
        self,
        *,
        job: dict[str, Any],
        cart: dict[str, Any] | None,
        user: dict[str, Any] | None,
    ) -> dict[str, Any]:
        recovery_key = str(job.get("recoveryKey", "")).strip()
        with self.store.lock:
            for existing in self.store.voice_calls_by_id.values():
                if str(existing.get("recoveryKey", "")) == recovery_key:
                    return deepcopy(existing)

        settings = self.get_settings()
        cart_total = float((cart or {}).get("total", 0.0))
        item_count = int((cart or {}).get("itemCount", 0))
        payload = {
            "id": f"vcall_{self.store.next_id('item')}",
            "recoveryKey": recovery_key,
            "userId": str((user or {}).get("id", "")),
            "sessionId": str(job.get("sessionId", "")),
            "cartId": str(job.get("cartId", "")),
            "status": "queued",
            "attemptCount": 0,
            "attempts": [],
            "provider": "superu",
            "providerCallId": None,
            "scriptVersion": str(settings.get("scriptVersion", "v1")),
            "campaign": {
                "itemCount": item_count,
                "cartTotal": cart_total,
                "template": str(settings.get("scriptTemplate", "")),
            },
            "outcome": "",
            "followupApplied": False,
            "estimatedCostUsd": float(settings.get("estimatedCostPerCallUsd", 0.0)),
            "createdAt": self.store.iso_now(),
            "updatedAt": self.store.iso_now(),
            "nextRetryAt": None,
            "lastError": None,
        }
        with self.store.lock:
            self.store.voice_calls_by_id[payload["id"]] = deepcopy(payload)
        return payload

    def _update_call_progress(self, *, call_id: str, status: str, payload: dict[str, Any]) -> None:
        with self.store.lock:
            call = deepcopy(self.store.voice_calls_by_id.get(call_id))
        if not call:
            return
        call["status"] = status
        call["updatedAt"] = self.store.iso_now()
        call["providerPayload"] = payload
        with self.store.lock:
            self.store.voice_calls_by_id[call_id] = deepcopy(call)

    def _update_call_terminal(
        self,
        *,
        call_id: str,
        status: str,
        outcome: str,
        payload: dict[str, Any],
    ) -> None:
        with self.store.lock:
            call = deepcopy(self.store.voice_calls_by_id.get(call_id))
        if not call:
            return
        call["status"] = status
        call["outcome"] = outcome
        call["providerPayload"] = payload
        call["updatedAt"] = self.store.iso_now()
        with self.store.lock:
            self.store.voice_calls_by_id[call_id] = deepcopy(call)
        if not bool(call.get("followupApplied", False)):
            self._apply_outcome_actions(call=call)
            with self.store.lock:
                latest = self.store.voice_calls_by_id.get(call_id)
                if latest is not None:
                    latest["followupApplied"] = True
                    latest["updatedAt"] = self.store.iso_now()
                    self.store.voice_calls_by_id[call_id] = deepcopy(latest)

    def _apply_outcome_actions(self, *, call: dict[str, Any]) -> None:
        user_id = str(call.get("userId", "")).strip()
        session_id = str(call.get("sessionId", "")).strip() or "voice-session"
        if not user_id:
            return

        outcome = str(call.get("outcome", "")).strip().lower()
        status = str(call.get("status", "")).strip().lower()

        if outcome in {"do_not_call", "opt_out", "dnc"}:
            self.suppress_user(user_id=user_id, reason="voice_opt_out")
            return

        if outcome in {"requested_callback", "needs_help", "agent_handoff"}:
            self.support_service.create_ticket(
                user_id=user_id,
                session_id=session_id,
                issue=f"Voice recovery callback requested for cart {call.get('cartId', '')}",
                priority="normal",
            )
            self.notification_service.send_voice_recovery_followup(
                user_id=user_id,
                call_id=str(call.get("id", "")),
                message="We received your callback request and a support agent will reach out.",
                disposition="callback_requested",
            )
            return

        if outcome in {"converted", "checkout_intent", "interested"}:
            self.notification_service.send_voice_recovery_followup(
                user_id=user_id,
                call_id=str(call.get("id", "")),
                message="Your cart is still available. Continue checkout when ready.",
                disposition="conversion_intent",
            )
            return

        if status == "failed":
            self.notification_service.send_voice_recovery_followup(
                user_id=user_id,
                call_id=str(call.get("id", "")),
                message="We could not complete your call. Your cart remains available.",
                disposition="call_failed",
            )

    def _campaign_payload(
        self,
        *,
        user: dict[str, Any],
        cart: dict[str, Any],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        name = str(user.get("name", "")).strip() or "there"
        item_count = int(cart.get("itemCount", 0))
        cart_total = float(cart.get("total", 0.0))
        template = str(settings.get("scriptTemplate", "")).strip() or self.settings.voice_script_template
        try:
            script = template.format(name=name, item_count=item_count, cart_total=cart_total)
        except Exception:
            script = (
                f"Hi {name}, you still have {item_count} item(s) in your cart worth "
                f"${cart_total:.2f}. Would you like help checking out?"
            )
        items = []
        for row in cart.get("items", []):
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "itemId": str(row.get("itemId", "")),
                    "productId": str(row.get("productId", "")),
                    "variantId": str(row.get("variantId", "")),
                    "name": str(row.get("name", "")),
                    "quantity": int(row.get("quantity", 0)),
                }
            )
        return {
            "scriptVersion": str(settings.get("scriptVersion", "v1")),
            "scriptText": script,
            "cart": {
                "id": str(cart.get("id", "")),
                "itemCount": item_count,
                "total": round(cart_total, 2),
                "currency": str(cart.get("currency", "USD")),
                "items": items,
            },
            "customer": {
                "id": str(user.get("id", "")),
                "name": name,
                "email": str(user.get("email", "")),
                "timezone": str(user.get("timezone", "")).strip()
                or str(settings.get("defaultTimezone", "UTC")),
            },
        }

    def _budget_and_cap_guardrails(
        self,
        *,
        user_id: str,
        settings: dict[str, Any],
        now: datetime,
    ) -> str:
        today = now.date().isoformat()
        with self.store.lock:
            calls = list(self.store.voice_calls_by_id.values())

        calls_today = [row for row in calls if str(row.get("createdAt", "")).startswith(today)]
        if len(calls_today) >= int(settings.get("maxCallsPerDay", 0)):
            return "max_calls_per_day_reached"

        user_calls_today = [row for row in calls_today if str(row.get("userId", "")) == user_id]
        if len(user_calls_today) >= int(settings.get("maxCallsPerUserPerDay", 0)):
            return "max_calls_per_user_per_day_reached"

        spend_today = len(calls_today) * float(settings.get("estimatedCostPerCallUsd", 0.0))
        if spend_today + float(settings.get("estimatedCostPerCallUsd", 0.0)) > float(
            settings.get("dailyBudgetUsd", 0.0)
        ):
            return "daily_budget_exceeded"
        return "ok"

    def _in_quiet_hours(
        self,
        *,
        user: dict[str, Any],
        now: datetime,
        settings: dict[str, Any],
    ) -> bool:
        tz_name = str(user.get("timezone", "")).strip() or str(settings.get("defaultTimezone", "UTC")).strip()
        try:
            zone = ZoneInfo(tz_name)
        except Exception:
            zone = timezone.utc
        local_now = now.astimezone(zone)
        hour = local_now.hour
        start = int(settings.get("quietHoursStart", 21))
        end = int(settings.get("quietHoursEnd", 8))
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def _next_non_quiet_time(
        self,
        *,
        user: dict[str, Any],
        now: datetime,
        settings: dict[str, Any],
    ) -> datetime:
        tz_name = str(user.get("timezone", "")).strip() or str(settings.get("defaultTimezone", "UTC")).strip()
        try:
            zone = ZoneInfo(tz_name)
        except Exception:
            zone = timezone.utc
        local_now = now.astimezone(zone)
        start = int(settings.get("quietHoursStart", 21))
        end = int(settings.get("quietHoursEnd", 8))
        if start == end:
            return now + timedelta(minutes=1)

        local_target = local_now.replace(hour=end, minute=0, second=0, microsecond=0)
        if start < end:
            if local_now.hour >= end:
                local_target = local_target + timedelta(days=1)
        else:
            if local_now.hour >= start:
                local_target = local_target + timedelta(days=1)
            elif local_now.hour < end and local_target <= local_now:
                local_target = local_target + timedelta(days=1)

        if local_target <= local_now:
            local_target = local_target + timedelta(minutes=1)
        return local_target.astimezone(timezone.utc)

    def _reschedule_job(
        self,
        *,
        job_id: str,
        attempt: int,
        next_run: datetime,
        error: str | None = None,
    ) -> None:
        with self.store.lock:
            current = self.store.voice_jobs_by_id.get(job_id)
            if current is None:
                return
            updated = deepcopy(current)
            updated["status"] = "retrying"
            updated["attempt"] = max(0, int(attempt))
            updated["nextRunAt"] = next_run.isoformat()
            updated["lastError"] = error
            updated["updatedAt"] = self.store.iso_now()
            self.store.voice_jobs_by_id[job_id] = deepcopy(updated)

    def _complete_job(self, *, job_id: str, status: str, error: str | None) -> None:
        with self.store.lock:
            current = self.store.voice_jobs_by_id.get(job_id)
            if current is None:
                return
            updated = deepcopy(current)
            updated["status"] = status
            updated["lastError"] = error
            updated["updatedAt"] = self.store.iso_now()
            if status in {"completed", "cancelled", "dead_letter"}:
                updated["nextRunAt"] = None
            self.store.voice_jobs_by_id[job_id] = deepcopy(updated)

    def _append_alert(
        self,
        *,
        code: str,
        message: str,
        severity: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        alert = {
            "id": f"valert_{self.store.next_id('item')}",
            "code": code,
            "message": message,
            "severity": severity,
            "details": details or {},
            "createdAt": self.store.iso_now(),
        }
        with self.store.lock:
            self.store.voice_alerts.append(deepcopy(alert))
            if len(self.store.voice_alerts) > 500:
                self.store.voice_alerts = self.store.voice_alerts[-500:]

    def _suppressed_users(self) -> set[str]:
        with self.store.lock:
            return {str(user_id) for user_id in self.store.voice_suppressions_by_user.keys()}

    def _get_user(self, user_id: Any) -> dict[str, Any] | None:
        key = str(user_id or "").strip()
        if not key:
            return None
        with self.store.lock:
            payload = self.store.users_by_id.get(key)
            return deepcopy(payload) if payload is not None else None

    def _get_cart(self, cart_id: Any) -> dict[str, Any] | None:
        key = str(cart_id or "").strip()
        if not key:
            return None
        with self.store.lock:
            payload = self.store.carts_by_id.get(key)
            return deepcopy(payload) if payload is not None else None

    def _has_newer_order(self, *, user_id: str, since: datetime) -> bool:
        with self.store.lock:
            orders = list(self.store.orders_by_id.values())
        for order in orders:
            if str(order.get("userId", "")) != user_id:
                continue
            created_at = self._parse_iso(order.get("createdAt"))
            if created_at and created_at > since:
                return True
        return False

    def _extract_provider_call_id(self, payload: dict[str, Any]) -> str | None:
        direct_keys = ("call_id", "callId", "id", "uuid")
        for key in direct_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data = payload.get("data")
        if isinstance(data, dict):
            for key in direct_keys:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _normalize_provider_status(self, payload: dict[str, Any]) -> str:
        raw = (
            payload.get("status")
            or payload.get("call_status")
            or payload.get("state")
            or payload.get("event")
            or ""
        )
        value = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
        if value in {"queued", "dialing", "ringing"}:
            return "ringing"
        if value in {"connected", "answered", "in_progress", "active"}:
            return "in_progress"
        if value in {"completed", "success", "ended", "done"}:
            return "completed"
        if value in {
            "failed",
            "error",
            "busy",
            "cancelled",
            "canceled",
            "no_answer",
            "voicemail",
            "dropped",
            "timeout",
        }:
            return "failed"
        return "in_progress"

    def _extract_outcome(self, payload: dict[str, Any]) -> str:
        for key in ("outcome", "disposition", "result", "intent"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower().replace("-", "_").replace(" ", "_")
        return self._normalize_provider_status(payload)

    def _parse_iso(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _normalize_backoff_list(self, raw: Any) -> list[int]:
        values: list[int] = []
        if isinstance(raw, list):
            source = raw
        elif isinstance(raw, str):
            source = [part.strip() for part in raw.split(",")]
        elif raw is None:
            source = []
        else:
            source = [raw]
        for value in source:
            try:
                parsed = int(float(value))
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                values.append(parsed)
        if not values:
            return [60, 300, 900]
        return values
