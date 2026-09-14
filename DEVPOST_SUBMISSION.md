# QuantumListener — Devpost submission draft

## Elevator pitch
QuantumListener is an autonomous weekly listening agent that turns every new or substantially updated arXiv `quant-ph` record into one evidence-grounded, five-chapter podcast while leaving scientific judgment to humans.

## Inspiration
Quantum researchers, students, and educators face more papers than they can inspect each week. Reading feeds, sorting topics, checking claims, and creating listening material are repetitive tasks suited to an agent; deciding whether science is convincing is not.

## What it does
A Weekly Editor retrieves an exact interval, resolves versions, classifies every paper into five categories, delegates grounded summaries, rejects unsupported claims, writes complete show notes and a coherent script, pauses for approval, creates narrated chapter audio, and atomically publishes an accessible site and podcast RSS feed. Large weeks can disclose an All Papers Rapid Review appendix.

## How it was built
Python, Flask, the Strands Agents SDK, configurable Amazon Bedrock, DynamoDB, S3, Polly, SQS, EventBridge Scheduler, Secrets Manager, CloudWatch/OpenTelemetry, EC2 Docker Compose, Nginx, and FFmpeg. Provider interfaces keep the credential-free fixture path aligned with AWS production adapters.

## Challenges
Exact version-aware ingestion, claim attribution without overstating abstracts, atomic media publication, and a useful offline demo all required explicit domain boundaries and fail-closed gates.

## Accomplishments
A deterministic end-to-end fixture produces classifications, evidence records, a complete weekly script, audio, transcript, show notes, local records, website playback, activity metrics, and a valid RSS feed without credentials.

## What we learned
Agent activity is most useful when exposed as tools, evidence, warnings, and outcomes—not hidden reasoning. Human review is a feature for scientific communication, not a limitation.

## What is next
Verify AgentCore packaging in an AWS account, add richer pronunciation lexicons and a flagged second voice, add full OpenTelemetry export, load-test very large weeks, and deploy an HTTPS public demo after budget approval.

## Built with
`Strands Agents SDK` `Amazon Bedrock` `Amazon EC2` `Amazon DynamoDB` `Amazon S3` `Amazon Polly` `Amazon SQS` `Amazon EventBridge Scheduler` `AWS Secrets Manager` `Amazon CloudWatch` `OpenTelemetry` `Python` `Flask` `FFmpeg` `Docker` `Nginx`

## Testing
Run `pip install -e '.[dev]'`, `make demo`, `pytest -q`, and `ruff check app tests scripts`.

## Pre-existing work disclosure
The initial tree contained reusable QubitReel code. Provider boundaries, ingestion/evidence ideas, approval/orchestration patterns, audio/caption publication concepts, and Flask web patterns were adapted and rewritten. Film, Google, Gemini, ADK, quantum-execution, and cinematic UI code was removed. See `PREEXISTING_CODE.md`.
