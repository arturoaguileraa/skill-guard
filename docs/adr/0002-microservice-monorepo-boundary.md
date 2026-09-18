# 0002 — Isolate Jev in a Python microservice with a TS↔Jev boundary

**Status:** Accepted

## Context

The validated scoring engine (question bank, extraction, scoring, calibration work) is Python, built on the `typesafe-sdk`. The product UI is a TypeScript stack (React/Vite, better-t-stack: Hono + oRPC). The Jev API needs a secret key that must never reach the browser, and we want the ability to swap the model vendor without touching the app.

## Decision

A Bun + Turborepo monorepo with three apps:
- `apps/jev` (Python/FastAPI) wraps the existing engine and is the **only** process that holds the Jev key and knows the question bank exists.
- `apps/server` (Hono/oRPC) is a typed BFF that forwards to the Jev service.
- `apps/web` (React) calls the server.

`packages/api/src/jev.ts` is the single point where the TS side knows Jev exists.

## Consequences

- **Positive:** Key stays server-side. The tested Python engine is reused as-is (no rewrite, no re-validation of calibration). Vendor swap or model change is a one-app change behind a stable HTTP contract. Apps are independently runnable and disjoint (Bun vs uv — no lockfile races).
- **Negative:** Two runtimes to install (`bun install` + `uv sync`) and one extra network hop (~10ms locally, measured as noise). A polyglot repo is slightly more to reason about.
- **Rejected:** Rewriting the engine in TS with the Jev JS SDK — would have discarded the validated bank/scoring/calibration for no boundary benefit.
