from __future__ import annotations

from datetime import datetime
from email.utils import format_datetime
from xml.etree import ElementTree as ET

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
PODCAST = "https://podcastindex.org/namespace/1.0"
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("podcast", PODCAST)


def build_feed(episodes: list[dict], *, site_url: str, owner_email: str, cover_url: str) -> bytes:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    for tag, value in (
        ("title", "QuantumListener"),
        ("description", "A weekly evidence-grounded quant-ph research digest."),
        ("link", site_url),
        ("language", "en-US"),
    ):
        ET.SubElement(channel, tag).text = value
    ET.SubElement(channel, f"{{{ITUNES}}}explicit").text = "false"
    ET.SubElement(channel, f"{{{ITUNES}}}image", {"href": cover_url})
    owner = ET.SubElement(channel, f"{{{ITUNES}}}owner")
    ET.SubElement(owner, f"{{{ITUNES}}}name").text = "QuantumListener"
    ET.SubElement(owner, f"{{{ITUNES}}}email").text = owner_email
    for episode in sorted(episodes, key=lambda e: e.get("published_at") or "", reverse=True):
        if episode.get("status") != "published":
            continue
        item = ET.SubElement(channel, "item")
        for tag, value in (
            ("guid", f"quantumlistener:{episode['week']}"),
            ("title", episode["title"]),
            ("description", episode["description"]),
            ("link", f"{site_url}/episodes/{episode['week']}"),
        ):
            ET.SubElement(item, tag).text = value
        published = datetime.fromisoformat(episode["published_at"])
        ET.SubElement(item, "pubDate").text = format_datetime(published)
        ET.SubElement(
            item,
            "enclosure",
            {
                "url": episode["audio_url"],
                "length": str(episode.get("audio_bytes", 0)),
                "type": "audio/mpeg",
            },
        )
        ET.SubElement(item, f"{{{ITUNES}}}duration").text = str(episode["duration_seconds"])
        ET.SubElement(item, f"{{{ITUNES}}}explicit").text = "false"
        ET.SubElement(
            item,
            f"{{{PODCAST}}}transcript",
            {"url": episode["transcript_url"], "type": "text/plain"},
        )
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)
