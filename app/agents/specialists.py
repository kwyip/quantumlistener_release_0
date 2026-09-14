from __future__ import annotations

import re

from app.domain.models import Category, Claim, Paper, PaperSummary

RULES = {
    Category.ERROR_CORRECTION: ("error correction", "fault toler", "surface code", "decoder"),
    Category.HARDWARE: ("qubit device", "superconduct", "ion trap", "hardware", "fabricat"),
    Category.MEASUREMENT: ("sensor", "sensing", "metrolog", "measurement", "magnetometr"),
    Category.SIMULATION: ("simulation", "chemistry", "many-body", "materials", "open quantum"),
    Category.ALGORITHMS: ("algorithm", "optimization", "annealing", "complexity", "search"),
}


def classify(paper: Paper) -> Paper:
    text = f"{paper.title} {paper.abstract}".lower()
    scores = {category: sum(term in text for term in terms) for category, terms in RULES.items()}
    primary = max(
        Category, key=lambda category: (scores[category], -list(Category).index(category))
    )
    secondaries = [
        category for category in Category if category != primary and scores[category] > 0
    ]
    total = sum(scores.values()) or 1
    return paper.model_copy(
        update={
            "quantumlistener_primary_category": primary,
            "quantumlistener_secondary_categories": secondaries,
            "classification_confidence": min(0.98, 0.55 + scores[primary] / total * 0.4),
            "classification_explanation": f"Matched abstract/title terminology associated with {primary.value}.",
        }
    )


def summarize(paper: Paper) -> PaperSummary:
    sentences = re.split(r"(?<=[.!?])\s+", paper.abstract.strip())
    first = sentences[0] if sentences and sentences[0] else "The abstract provides limited detail."
    attributed = f"The authors report that {first[0].lower() + first[1:] if len(first) > 1 else first.lower()}"
    claims = [
        Claim(
            text=f"Metadata fact: {paper.title} is arXiv {paper.arxiv_id}v{paper.version}.",
            label="Metadata fact",
            evidence=["title", "arxiv_id", "version"],
        ),
        Claim(text=attributed, label="Author-reported claim", evidence=["abstract:sentence:1"]),
        Claim(
            text=f"QuantumListener inference: this paper is most relevant to {paper.quantumlistener_primary_category.value} listeners.",
            label="QuantumListener inference",
            evidence=["title", "abstract", "classification"],
        ),
    ]
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z-]{3,}", paper.title)][:3]
    keywords = (words + ["quantum", "research", "methods"])[:3]
    return PaperSummary(
        arxiv_id=paper.arxiv_id,
        takeaway=attributed,
        accessible_summary=f"In accessible terms, the paper studies {paper.title.lower()}. {attributed}",
        technical_summary=f"Based only on the abstract, {attributed[0].lower() + attributed[1:]}",
        methods=["Methods described in the arXiv abstract"],
        main_result=attributed,
        claimed_advancement=f"The paper proposes an advance concerning {paper.title.lower()}.",
        limitations="Only metadata and the abstract were evaluated; independent verification and full-text limitations are unavailable.",
        keywords=keywords,
        audience="researcher",
        source_url=paper.abstract_url,
        claims=claims,
    )


def verify(summary: PaperSummary, paper: Paper) -> list[str]:
    warnings = []
    evidence_fields = {
        "title",
        "arxiv_id",
        "version",
        "abstract:sentence:1",
        "abstract",
        "classification",
    }
    for claim in summary.claims:
        if not claim.evidence or any(ref not in evidence_fields for ref in claim.evidence):
            warnings.append(f"{paper.arxiv_id}: unsupported evidence reference")
    forbidden = ("peer reviewed", "quantum advantage", "affiliation", "benchmark")
    for claim in summary.claims:
        unsupported = [
            term
            for term in forbidden
            if term in claim.text.lower() and term not in paper.abstract.lower()
        ]
        if unsupported:
            warnings.append(f"{paper.arxiv_id}: unsupported claim ({unsupported[0]})")
    return warnings
