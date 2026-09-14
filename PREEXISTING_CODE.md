# Pre-existing code disclosure

QuantumListener is a new repository and product. Its initial working tree was copied from the creator's earlier **QubitReel** project; its Git history was not imported. Before this migration, that tree contained a Python/Flask quantum newsroom and film pipeline, arXiv/research ingestion, evidence and claim models, orchestration/approval patterns, captions/audio publication, local and Google storage abstractions, a web experience, tests, fixtures, and Google Compute Engine/Cloud Run deployment material.

## Adapted concepts

The migration retained and substantially adapted these general implementation patterns:

- provider-neutral Python domain models and repository boundaries;
- exact research-source metadata normalization and newest-version deduplication;
- evidence-linked claims and fail-closed editorial checks;
- bounded retry, human approval, atomic current-publication pointer, and run-status patterns;
- FFmpeg-oriented deterministic media assembly, transcript sidecars, and a Flask/static-web split.

All production code now present was rewritten and renamed for a podcast-first QuantumListener domain. The former cinematic storyboards, citation graph interface, video/Imagen/Veo paths, Bell/IBM/MarQov execution, Google ADK/Gemini runtime, Firestore, Cloud Storage, Cloud Tasks, Cloud TTS, and Google deployment scripts were removed. No QubitReel secret, credential, generated film, or Git history is incorporated.

The repository remains licensed under the existing Apache License 2.0. Fixture authors and records are fictional and marked as deterministic demonstration metadata.
