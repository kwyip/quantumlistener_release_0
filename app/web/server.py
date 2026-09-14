from __future__ import annotations

import os
from datetime import UTC, datetime

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from app.agents.orchestrator import WeeklyEditor
from app.ingestion.arxiv import exact_week_window
from app.repositories.local import LocalRepository
from scripts.run_digest import load_fixture

repo = LocalRepository()
application = Flask(__name__, static_folder="static")


@application.get("/")
def home():
    return application.send_static_file("index.html")


@application.get("/episodes")
def episodes_page():
    return application.send_static_file("index.html")


@application.get("/episodes/<week>")
def episode_page(week):
    return application.send_static_file("index.html")


@application.get("/papers")
def papers_page():
    return application.send_static_file("index.html")


@application.get("/papers/<path:arxiv_id>")
def paper_page(arxiv_id):
    return application.send_static_file("index.html")


@application.get("/api/v1/episodes/current")
def current():
    return jsonify(repo.current() or {})


@application.get("/api/v1/episodes")
def episode_list():
    return jsonify(repo.episodes())


@application.get("/api/v1/episodes/<week>")
def episode(week):
    value = next((e for e in repo.episodes() if e["week"] == week), None)
    return jsonify(value) if value else abort(404)


@application.get("/api/v1/papers")
def papers():
    category = request.args.get("category")
    values = repo.papers()
    return jsonify(
        [p for p in values if not category or p.get("quantumlistener_primary_category") == category]
    )


@application.get("/api/v1/papers/<path:arxiv_id>")
def paper(arxiv_id):
    value = next((p for p in repo.papers() if p["arxiv_id"] == arxiv_id), None)
    return jsonify(value) if value else abort(404)


@application.get("/api/v1/runs/<run_id>")
def run(run_id):
    value = repo.run(run_id)
    return jsonify(value) if value else abort(404)


@application.get("/feed.xml")
def feed():
    path = repo.root / "feed.xml"
    return Response(
        path.read_bytes()
        if path.exists()
        else b'<?xml version="1.0"?><rss version="2.0"><channel><title>QuantumListener</title></channel></rss>',
        mimetype="application/rss+xml",
    )


@application.get("/media/<week>/<path:name>")
def media(week, name):
    if name not in {"episode.mp3", "transcript.txt", "show-notes.md"}:
        abort(404)
    return send_from_directory(repo.root / "media" / week, name)


def authorized():
    return (
        request.headers.get("Authorization")
        == f"Bearer {os.getenv('ADMIN_TOKEN', 'local-demo-only')}"
    )


@application.post("/api/v1/admin/digests/run")
def manual_run():
    if not authorized():
        abort(401)
    body = request.get_json(silent=True) or {}
    start, end = exact_week_window(datetime.now(UTC))
    report = WeeklyEditor(repo).run(
        load_fixture("manual-fixture"),
        start,
        end,
        approve=bool(body.get("approve")),
        dry_run=bool(body.get("dry_run")),
        resume_from=body.get("resume_from"),
    )
    return jsonify(report), 202


@application.post("/api/v1/admin/episodes/<week>/approve")
def approve(week):
    if not authorized():
        abort(401)
    return jsonify(repo.approve(week))


@application.post("/api/v1/admin/episodes/<week>/publish")
def publish(week):
    if not authorized():
        abort(401)
    episode = repo.approve(week)
    audio = repo.root / "media" / week / "episode.mp3"
    if not audio.exists() or audio.stat().st_size < 100:
        return jsonify({"error": "validated audio asset is required"}), 409
    episode.update(
        status="published",
        published_at=datetime.now(UTC).isoformat(),
        audio_bytes=audio.stat().st_size,
    )
    repo.publish_atomic(episode)
    return jsonify(episode)


def main():
    application.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


if __name__ == "__main__":
    main()
