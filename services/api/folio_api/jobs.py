"""Durable, tenant-scoped jobs with fenced leases and conservative token budgets.

All transitions take a database-backed scheduler lock, including across worker
processes. This intentionally favours simple correctness over queue throughput.
No process-local lock or SQLite-only SQL is used in the production path.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError

metadata = MetaData()
scheduler = Table(
    "folio_job_scheduler",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("revision", Integer, nullable=False),
)
jobs = Table(
    "folio_jobs",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("workspace_id", String(160), nullable=False, index=True),
    Column("operation_id", String(160), nullable=False),
    Column("request_hash", String(64), nullable=False),
    Column("question", Text, nullable=False),
    Column("scope", String(40), nullable=False),
    Column("expected_version", Integer, nullable=False),
    Column("status", String(24), nullable=False),
    Column("created_at", Float, nullable=False),
    Column("updated_at", Float, nullable=False),
    Column("quota_day", Integer, nullable=False),
    Column("reservation", Integer, nullable=False),
    Column("charged_tokens", Integer, nullable=False, default=0),
    Column("prompt_tokens", Integer, nullable=False, default=0),
    Column("completion_tokens", Integer, nullable=False, default=0),
    Column("open_model_calls", Integer, nullable=False, default=0),
    Column("usage_uncertain", Boolean, nullable=False, default=False),
    Column("cancel_requested", Boolean, nullable=False, default=False),
    Column("attempt", Integer, nullable=False, default=0),
    Column("worker_id", String(160)),
    Column("lease_token", String(64)),
    Column("lease_until", Float),
    Column("result", Text),
    Column("finish_hash", String(64)),
    UniqueConstraint("workspace_id", "operation_id"),
)
events = Table(
    "folio_job_events",
    metadata,
    Column("run_id", String(64), primary_key=True),
    Column("sequence", Integer, primary_key=True),
    Column("source_key", String(160), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("payload", Text, nullable=False),
    UniqueConstraint("run_id", "source_key"),
)
TERMINAL = frozenset({"completed", "failed", "cancelled", "partial", "needs_input"})


class JobError(RuntimeError):
    def __init__(self, message: str, status: int = 409):
        self.status = status
        super().__init__(message)


class LeaseLost(JobError):
    """An expired or superseded worker must stop without publishing anything."""


@dataclass(frozen=True)
class JobPolicy:
    reservation_tokens: int = 64_000
    workspace_daily_tokens: int = 256_000
    max_active_runs: int = 4
    lease_seconds: float = 60
    max_attempts: int = 2

    def __post_init__(self):
        if (
            any(
                type(value) is not int or value < 1
                for value in (
                    self.reservation_tokens,
                    self.workspace_daily_tokens,
                    self.max_active_runs,
                    self.max_attempts,
                )
            )
            or not 1 <= self.lease_seconds <= 3600
        ):
            raise ValueError("Job policy bounds must be positive")


@dataclass(frozen=True)
class JobLease:
    run_id: str
    workspace_id: str
    question: str
    scope: str
    expected_version: int
    lease_token: str
    attempt: int


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


class JobQueue:
    def __init__(self, engine, *, policy: JobPolicy | None = None, clock=time.time):
        self.engine = engine
        self.policy = policy or JobPolicy()
        self.clock = clock

    def migrate(self):
        metadata.create_all(self.engine)
        # Safe when migration is invoked twice or two startup processes race.
        try:
            with self.engine.begin() as con:
                con.execute(scheduler.insert().values(id=1, revision=0))
        except IntegrityError:
            pass

    @contextmanager
    def _transaction(self):
        with self.engine.begin() as con:
            changed = con.execute(
                update(scheduler)
                .where(scheduler.c.id == 1)
                .values(revision=scheduler.c.revision + 1)
            )
            if changed.rowcount != 1:
                raise RuntimeError("Run database migrations before using the job queue")
            yield con

    def _row(self, con, workspace_id, run_id):
        row = (
            con.execute(
                select(jobs).where(jobs.c.run_id == run_id, jobs.c.workspace_id == workspace_id)
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise JobError("Run not found", 404)
        return row

    def _leased(self, con, lease):
        row = self._row(con, lease.workspace_id, lease.run_id)
        if (
            row["status"] != "running"
            or row["lease_token"] != lease.lease_token
            or row["lease_until"] <= self.clock()
        ):
            raise LeaseLost("Worker lease expired or was replaced")
        return row

    def _event(self, con, row, source_key, payload):
        clean = {k: v for k, v in payload.items() if k not in {"runId", "sequence"}}
        fingerprint = _hash(clean)
        prior = (
            con.execute(
                select(events).where(
                    events.c.run_id == row["run_id"], events.c.source_key == source_key
                )
            )
            .mappings()
            .one_or_none()
        )
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise JobError("Event ID was already used for different data")
            return False
        sequence = (
            con.execute(
                select(events.c.sequence)
                .where(events.c.run_id == row["run_id"])
                .order_by(events.c.sequence.desc())
                .limit(1)
            ).scalar_one_or_none()
            or 0
        )
        clean.update(runId=row["run_id"], sequence=sequence + 1)
        con.execute(
            events.insert().values(
                run_id=row["run_id"],
                sequence=sequence + 1,
                source_key=source_key,
                fingerprint=fingerprint,
                payload=_json(clean),
            )
        )
        return True

    def _snapshot(self, con, row, after_sequence=0):
        return {
            "runId": row["run_id"],
            "operationId": row["operation_id"],
            "status": row["status"],
            "scope": row["scope"],
            "question": row["question"],
            "expectedVersion": row["expected_version"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "cancelRequested": row["cancel_requested"],
            "attempt": row["attempt"],
            "usage": {
                "promptTokens": row["prompt_tokens"],
                "completionTokens": row["completion_tokens"],
                "totalTokens": row["prompt_tokens"] + row["completion_tokens"],
            },
            "usageUncertain": row["usage_uncertain"],
            "quotaChargedTokens": row["charged_tokens"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "events": [
                json.loads(value)
                for value in con.execute(
                    select(events.c.payload)
                    .where(events.c.run_id == row["run_id"], events.c.sequence > after_sequence)
                    .order_by(events.c.sequence)
                ).scalars()
            ],
        }

    def enqueue(self, *, workspace_id, operation_id, question, scope, expected_version):
        if any(
            not isinstance(value, str) or not 1 <= len(value) <= 160
            for value in (workspace_id, operation_id)
        ):
            raise JobError("Invalid operation or workspace identifier", 422)
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise JobError("Question must contain 1–2000 characters", 422)
        if scope not in {"personal", "business", "everything"}:
            raise JobError("Invalid scope", 422)
        if type(expected_version) is not int or expected_version < 1:
            raise JobError("Invalid workspace version", 422)
        fingerprint = _hash([question, scope, expected_version])
        now = self.clock()
        with self._transaction() as con:
            prior = (
                con.execute(
                    select(jobs).where(
                        jobs.c.workspace_id == workspace_id, jobs.c.operation_id == operation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if prior:
                if prior["request_hash"] != fingerprint:
                    raise JobError("Operation ID was already used for different data")
                return self._snapshot(con, prior)
            rows = con.execute(
                select(jobs).where(
                    jobs.c.workspace_id == workspace_id,
                    ((jobs.c.quota_day == int(now // 86400)) | jobs.c.status.not_in(TERMINAL)),
                )
            ).mappings()
            committed = sum(
                r["charged_tokens"] if r["status"] in TERMINAL else r["reservation"] for r in rows
            )
            if committed + self.policy.reservation_tokens > self.policy.workspace_daily_tokens:
                raise JobError("Daily workspace token budget is reserved or exhausted", 429)
            run_id = secrets.token_hex(16)
            con.execute(
                jobs.insert().values(
                    run_id=run_id,
                    workspace_id=workspace_id,
                    operation_id=operation_id,
                    request_hash=fingerprint,
                    question=question,
                    scope=scope,
                    expected_version=expected_version,
                    status="queued",
                    created_at=now,
                    updated_at=now,
                    quota_day=int(now // 86400),
                    reservation=self.policy.reservation_tokens,
                )
            )
            row = self._row(con, workspace_id, run_id)
            self._event(con, row, "queued", {"type": "run.queued"})
            return self._snapshot(con, row)

    def get(self, workspace_id, run_id, after_sequence=0):
        if type(after_sequence) is not int or after_sequence < 0:
            raise JobError("Invalid event cursor", 422)
        with self.engine.connect() as con:
            return self._snapshot(con, self._row(con, workspace_id, run_id), after_sequence)

    def list(self, workspace_id, limit=20):
        """Recover recent runs using authenticated workspace identity, never client identity."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise JobError("History limit must be between 1 and 100", 422)
        with self.engine.connect() as con:
            rows = con.execute(
                select(jobs)
                .where(jobs.c.workspace_id == workspace_id)
                .order_by(jobs.c.created_at.desc(), jobs.c.run_id.desc())
                .limit(limit)
            ).mappings()
            return [self._snapshot(con, row) for row in rows]

    def claim(self, worker_id):
        if not isinstance(worker_id, str) or not 1 <= len(worker_id) <= 160:
            raise ValueError("Worker requires a bounded identifier")
        with self._transaction() as con:
            now = self.clock()
            expired = list(
                con.execute(
                    select(jobs).where(jobs.c.status == "running", jobs.c.lease_until <= now)
                ).mappings()
            )
            for row in expired:
                # A crashed process may have sent a request without persisting its receipt.
                con.execute(
                    update(jobs)
                    .where(jobs.c.run_id == row["run_id"])
                    .values(
                        usage_uncertain=True,
                    )
                )
                row = self._row(con, row["workspace_id"], row["run_id"])
                if row["cancel_requested"] or row["attempt"] >= self.policy.max_attempts:
                    self._finish(
                        con,
                        row,
                        {
                            "status": "cancelled" if row["cancel_requested"] else "failed",
                            "text": "Worker stopped before completion could be verified.",
                        },
                    )
                else:
                    con.execute(
                        update(jobs)
                        .where(jobs.c.run_id == row["run_id"])
                        .values(
                            status="queued",
                            lease_token=None,
                            lease_until=None,
                        )
                    )
            active = len(
                list(con.execute(select(jobs.c.run_id).where(jobs.c.status == "running")).scalars())
            )
            if active >= self.policy.max_active_runs:
                return None
            row = (
                con.execute(
                    select(jobs)
                    .where(jobs.c.status == "queued")
                    .order_by(jobs.c.created_at, jobs.c.run_id)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            token = secrets.token_hex(24)
            attempt = row["attempt"] + 1
            con.execute(
                update(jobs)
                .where(jobs.c.run_id == row["run_id"])
                .values(
                    status="running",
                    worker_id=worker_id,
                    lease_token=token,
                    lease_until=now + self.policy.lease_seconds,
                    attempt=attempt,
                    updated_at=now,
                )
            )
            return JobLease(
                row["run_id"],
                row["workspace_id"],
                row["question"],
                row["scope"],
                row["expected_version"],
                token,
                attempt,
            )

    def renew(self, lease):
        with self._transaction() as con:
            row = self._leased(con, lease)
            con.execute(
                update(jobs)
                .where(jobs.c.run_id == lease.run_id)
                .values(
                    lease_until=self.clock() + self.policy.lease_seconds,
                )
            )
            return row["cancel_requested"]

    def append_event(self, lease, event):
        if not isinstance(event, dict) or type(event.get("sequence")) is not int:
            raise JobError("Event requires a source sequence", 422)
        if event["sequence"] < 1 or not isinstance(event.get("type"), str):
            raise JobError("Event requires a type and positive sequence", 422)
        if len(_json(event)) > 64_000:
            raise JobError("Event exceeds its size bound", 422)
        with self._transaction() as con:
            row = self._leased(con, lease)
            if not self._event(con, row, f"{lease.lease_token}:{event['sequence']}", event):
                return
            changes: dict[str, Any] = {"updated_at": self.clock()}
            if event["type"] == "model.started":
                changes["open_model_calls"] = row["open_model_calls"] + 1
            elif event["type"] == "model.completed":
                usage = event.get("usage", {})
                prompt, completion = usage.get("promptTokens"), usage.get("completionTokens")
                if any(type(value) is not int or value < 0 for value in (prompt, completion)):
                    raise JobError("Model usage must contain non-negative token counts", 422)
                changes.update(
                    prompt_tokens=row["prompt_tokens"] + prompt,
                    completion_tokens=row["completion_tokens"] + completion,
                    open_model_calls=max(0, row["open_model_calls"] - 1),
                )
            con.execute(update(jobs).where(jobs.c.run_id == lease.run_id).values(**changes))

    def _finish(self, con, row, result):
        uncertain = row["usage_uncertain"] or row["open_model_calls"] > 0
        charged = row["prompt_tokens"] + row["completion_tokens"]
        if uncertain:
            charged = max(charged, row["reservation"])
        clean = dict(result)
        # Persisted provider receipts are authoritative even if a later tool failed.
        recorded = [
            json.loads(payload)
            for payload in con.execute(
                select(events.c.payload).where(events.c.run_id == row["run_id"])
            ).scalars()
        ]
        clean["actualInference"] = any(e["type"] == "model.completed" for e in recorded)
        clean["usage"] = {
            "promptTokens": row["prompt_tokens"],
            "completionTokens": row["completion_tokens"],
            "totalTokens": row["prompt_tokens"] + row["completion_tokens"],
        }
        clean["usageUncertain"] = uncertain
        clean.setdefault("toolResults", [])
        if row["cancel_requested"]:
            clean.update(status="cancelled", text="Stopped. Any committed work is preserved.")
        con.execute(
            update(jobs)
            .where(jobs.c.run_id == row["run_id"])
            .values(
                status=clean["status"],
                result=_json(clean),
                charged_tokens=charged,
                quota_day=int(self.clock() // 86400),
                finish_hash=_hash(result),
                usage_uncertain=uncertain,
                updated_at=self.clock(),
                lease_until=None,
            )
        )
        self._event(con, row, "terminal", {**clean, "type": f"run.{clean['status']}"})

    def finish(self, lease, result):
        if not isinstance(result, dict) or result.get("status") not in TERMINAL:
            raise JobError("Result requires a terminal status", 422)
        with self._transaction() as con:
            row = self._row(con, lease.workspace_id, lease.run_id)
            if row["status"] in TERMINAL and row["lease_token"] == lease.lease_token:
                if row["finish_hash"] != _hash(result):
                    raise JobError("Result was already completed with different data")
                return self._snapshot(con, row)
            row = self._leased(con, lease)
            self._finish(con, row, result)
            return self._snapshot(con, self._row(con, lease.workspace_id, lease.run_id))

    def cancel(self, workspace_id, run_id):
        with self._transaction() as con:
            row = self._row(con, workspace_id, run_id)
            if row["status"] in TERMINAL or row["cancel_requested"]:
                return self._snapshot(con, row)
            con.execute(
                update(jobs)
                .where(jobs.c.run_id == run_id)
                .values(
                    cancel_requested=True,
                    updated_at=self.clock(),
                )
            )
            row = self._row(con, workspace_id, run_id)
            if row["status"] == "queued":
                self._finish(con, row, {"status": "cancelled", "text": "Stopped before starting."})
            else:
                self._event(con, row, "cancel", {"type": "run.cancel_requested"})
            return self._snapshot(con, self._row(con, workspace_id, run_id))
