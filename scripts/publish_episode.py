#!/usr/bin/env python3
import argparse
import json
from datetime import UTC, datetime

from app.publishing.rss import build_feed
from app.repositories.local import LocalRepository

parser = argparse.ArgumentParser()
parser.add_argument("week")
args = parser.parse_args()
repo = LocalRepository()
episode = repo.approve(args.week)
media = repo.root / "media" / args.week / "episode.mp3"
if not media.exists():
    raise SystemExit("audio asset missing; run an approved digest first")
episode.update(
    status="published", published_at=datetime.now(UTC).isoformat(), audio_bytes=media.stat().st_size
)
repo.publish_atomic(episode)
site = __import__("os").getenv("PUBLIC_SITE_URL", "http://localhost:8080")
(repo.root / "feed.xml").write_bytes(
    build_feed(
        repo.episodes(),
        site_url=site,
        owner_email=__import__("os").getenv("PODCAST_OWNER_EMAIL", "podcast@example.invalid"),
        cover_url=f"{site}/static/cover.svg",
    )
)
print(json.dumps({"status": "published", "week": args.week}))
