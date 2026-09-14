# Five-minute demo script

**0:00–0:30 — Problem and users.** Quantum scientists, students, educators, and technical professionals cannot manually triage every weekly `quant-ph` update. QuantumListener automates collection and communication—not scientific judgment.

**0:30–0:55 — Why it matters.** Show the evidence disclosure. Explain that metadata facts, author-reported claims, and QuantumListener inferences stay distinct.

**0:55–1:25 — Live run.** Run `make demo`. Point out the exact half-open weekly interval, deterministic offline fixture, version deduplication, and no AWS credentials.

**1:25–2:00 — Strands activity.** Open the agent status panel: papers found/classified/summarized, evidence warnings, audio segments, and publication. Explain Weekly Editor delegation, bounded retries, missing-evidence gate, budget limits, and default human pause. Do not show private reasoning.

**2:00–2:35 — Five categories.** Filter Algorithms, Error Correction, Hardware, Measurement and Sensing, and Simulation. Open an arXiv source and identify explicit author attribution.

**2:35–3:15 — Generated podcast.** Play the MP3, click category chapter seek buttons, and show that every paper is covered. Open transcript and complete show notes.

**3:15–3:45 — Website and RSS.** Demonstrate native non-autoplay audio, responsive layout, previous episodes, `/feed.xml`, and the AI-summary disclosure.

**3:45–4:25 — AWS architecture.** Show `docs/architecture.svg`: EventBridge to SQS/DLQ to EC2/AgentCore Strands loop, Bedrock and arXiv tools, Polly/FFmpeg, private S3, DynamoDB atomic pointer, CloudWatch/OpenTelemetry.

**4:25–5:00 — Safeguards and close.** Explain human approval, conditional lock, per-paper retry, Bedrock/Polly ceilings, instance roles, private drafts, and atomic publication preserving the previous episode. Close with the Pro Agents thesis: repetitive research-listening work delegated, consequential scientific judgment retained by people.
