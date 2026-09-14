import io
import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agents.orchestrator import WeeklyEditor
from app.agents.specialists import classify, summarize, verify
from app.domain.models import Category, Claim
from app.ingestion.arxiv import deduplicate_papers, exact_week_window, fetch_quant_ph_papers
from app.providers.aws import DynamoRepository, S3ObjectStorage
from app.providers.tts import MockTTS, PollyTTS
from app.publishing.rss import build_feed
from app.repositories.local import LocalRepository
from app.web.server import application
from scripts.run_digest import load_fixture


def fixture_papers():
    return load_fixture("test")


def test_exact_week_is_half_open_utc():
    start, end = exact_week_window(datetime(2026, 9, 10, 22, tzinfo=UTC))
    assert start.isoformat() == "2026-09-07T00:00:00+00:00"
    assert end.isoformat() == "2026-09-14T00:00:00+00:00"


def atom(entries, total):
    body = "".join(
        f"""<entry><id>https://arxiv.org/abs/{i}</id><updated>2026-09-08T00:00:00Z</updated><published>2026-09-08T00:00:00Z</published><title>Quantum algorithm {i}</title><summary>We propose an algorithm.</summary><author><name>A</name></author><category term="quant-ph"/><arxiv:primary_category term="quant-ph"/><link type="application/pdf" href="https://arxiv.org/pdf/{i}"/></entry>"""
        for i in entries
    )
    return f"""<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><opensearch:totalResults>{total}</opensearch:totalResults>{body}</feed>""".encode()


def test_pagination_rate_limit_and_window():
    pages = [atom(["2609.10001v1"], 2), atom(["2609.10002v1"], 2)]
    sleeps = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    papers = fetch_quant_ph_papers(
        datetime(2026, 9, 7, tzinfo=UTC),
        datetime(2026, 9, 14, tzinfo=UTC),
        "r",
        page_size=1,
        opener=lambda *a, **k: Response(pages.pop(0)),
        sleep=sleeps.append,
    )
    assert len(papers) == 2 and sleeps == [3]


def test_version_dedup_preserves_latest():
    paper = fixture_papers()[0]
    assert deduplicate_papers([paper, paper.model_copy(update={"version": 3})])[0].version == 3


def test_every_category_and_summary_is_grounded():
    processed = [classify(p) for p in fixture_papers()]
    assert {p.quantumlistener_primary_category for p in processed} == set(Category)
    summaries = [summarize(p) for p in processed]
    assert len(summaries) == len(processed)
    assert all(not verify(s, p) for s, p in zip(summaries, processed, strict=True))
    assert all(s.main_result.lower().startswith("the authors report") for s in summaries)


def test_schema_rejects_unattributed_author_claim():
    with pytest.raises(ValidationError):
        Claim(text="A speedup exists.", label="Author-reported claim", evidence=["abstract"])


def test_unsupported_claim_is_rejected():
    p = classify(fixture_papers()[0])
    s = summarize(p)
    s.claims.append(
        Claim(
            text="QuantumListener inference: peer reviewed benchmark.",
            label="QuantumListener inference",
            evidence=["abstract"],
        )
    )
    assert "unsupported claim" in verify(s, p)[0]


def test_orchestrator_tools_retry_and_end_to_end(tmp_path, monkeypatch):
    import app.agents.orchestrator as module

    calls = {"n": 0}
    real = module.summarize

    def flaky(p):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ValueError("temporary")
        return real(p)

    monkeypatch.setattr(module, "summarize", flaky)
    repo = LocalRepository(tmp_path)
    start, end = exact_week_window(datetime(2026, 9, 10, tzinfo=UTC))
    report = WeeklyEditor(repo).run(fixture_papers(), start, end, approve=True)
    assert report["papers_summarized"] == 5 and any(
        x["status"] == "retrying" for x in report["tool_calls"]
    )
    assert (tmp_path / "media/2026-W37/episode.mp3").read_bytes()[:4] in (b"RIFF", b"ID3\x04") or (
        tmp_path / "media/2026-W37/episode.mp3"
    ).stat().st_size > 100


def test_local_atomic_publication_preserves_previous(tmp_path):
    repo = LocalRepository(tmp_path)
    old = {"week": "2026-W36", "status": "published"}
    repo.publish_atomic(old)
    with pytest.raises(ValueError):
        repo.publish_atomic({"week": "2026-W37", "status": "draft"})
    assert repo.current() == old


def test_drafts_are_private(tmp_path):
    repo = LocalRepository(tmp_path)
    repo.save_draft({"week": "2026-W37", "status": "draft"})
    assert repo.current() is None and repo.episodes() == []


def test_rss_is_valid_and_ignores_drafts():
    episode = {
        "week": "2026-W37",
        "title": "Weekly",
        "description": "All papers",
        "status": "published",
        "published_at": "2026-09-14T00:00:00+00:00",
        "audio_url": "https://example.org/e.mp3",
        "transcript_url": "https://example.org/t.txt",
        "duration_seconds": 60,
        "audio_bytes": 12,
    }
    root = ET.fromstring(
        build_feed(
            [episode, {**episode, "week": "draft", "status": "draft"}],
            site_url="https://example.org",
            owner_email="owner@example.org",
            cover_url="https://example.org/c.webp",
        )
    )
    assert (
        root.tag == "rss"
        and len(root.findall("./channel/item")) == 1
        and root.find("./channel/item/enclosure").attrib["type"] == "audio/mpeg"
    )


def test_mock_and_polly_adapters(tmp_path):
    assert MockTTS().synthesize("hello", tmp_path / "a.mp3").stat().st_size > 100
    stream = io.BytesIO(b"ID3audio")
    client = SimpleNamespace(synthesize_speech=lambda **kwargs: {"AudioStream": stream})
    assert (
        PollyTTS(client=client).synthesize("hello", tmp_path / "p.mp3").read_bytes() == b"ID3audio"
    )


def test_s3_private_draft_rule(tmp_path):
    source = tmp_path / "x"
    source.write_text("x")
    calls = []
    client = SimpleNamespace(upload_file=lambda *a, **k: calls.append((a, k)))
    store = S3ObjectStorage(bucket="bucket", client=client)
    with pytest.raises(ValueError):
        store.upload("episodes/2026-W37/episode.mp3", source)
    assert store.upload("episodes/2026-W37/episode.mp3", source, public=True).startswith("https://")


def test_dynamo_lock_condition_and_atomic_publish():
    class Table:
        name = "q"
        meta = SimpleNamespace(
            client=SimpleNamespace(transact_write_items=lambda **k: setattr(table, "tx", k))
        )

        def put_item(self, **kwargs):
            self.put = kwargs

    table = Table()
    repo = DynamoRepository(table=table)
    repo.acquire_lock("w", "r", 99)
    assert "attribute_not_exists" in table.put["ConditionExpression"]
    repo.publish_atomic({"week": "w", "status": "published"})
    assert len(table.tx["TransactItems"]) == 2


def test_homepage_accessibility_audio_and_chapter_seek(tmp_path, monkeypatch):
    html = Path("app/web/static/index.html").read_text()
    js = Path("app/web/static/app.js").read_text()
    assert '<audio id="player" controls preload="metadata">' in html and "autoplay" not in html
    assert 'aria-label="Episode chapters"' in html and "player.currentTime" in js
    assert '<html lang="en">' in html and "<label>" in html


def test_required_public_routes_do_not_expose_drafts(tmp_path, monkeypatch):
    import app.web.server as server

    monkeypatch.setattr(server, "repo", LocalRepository(tmp_path))
    client = application.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/api/v1/episodes/current").json == {}
    assert client.post("/api/v1/admin/digests/run").status_code == 401


def test_runtime_iam_policy_uses_valid_authorization_actions():
    policy = json.loads(Path("deployment/iam/runtime-policy.json").read_text())
    actions = {
        action
        for statement in policy["Statement"]
        for action in (
            statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        )
    }
    assert "dynamodb:TransactWriteItems" not in actions
    assert "s3:HeadObject" not in actions
    assert {
        "dynamodb:ConditionCheckItem",
        "dynamodb:PutItem",
        "s3:GetObject",
    } <= actions


def test_compose_wrapper_supports_v2_and_legacy_fallback():
    wrapper = Path("scripts/compose.sh").read_text()
    assert 'docker compose version' in wrapper
    assert 'command -v docker-compose' in wrapper
    assert 'exec docker compose "$@"' in wrapper
    assert 'exec docker-compose "$@"' in wrapper
