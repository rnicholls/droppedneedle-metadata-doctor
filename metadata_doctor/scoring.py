"""Album-level candidate scoring.

This intentionally starts conservative: exact track-count agreement matters a lot,
while MusicBrainz text-search confidence is treated as supporting evidence only.
"""

from __future__ import annotations

from typing import Any


def score_release(candidate: dict[str, Any], tracks: list[dict[str, Any]]) -> dict[str, Any]:
    expected = int(candidate.get("track_count") or 0)
    observed = len(tracks)
    mb_search_score = max(0, min(100, int(candidate.get("score") or 0))) / 100.0

    track_count_score = 0.0
    if expected and observed:
        delta = abs(expected - observed)
        if delta == 0:
            track_count_score = 1.0
        elif delta == 1:
            track_count_score = 0.65
        elif delta <= 3:
            track_count_score = 0.30

    recording_ids = [
        str(track.get("recording_mbid") or "").strip()
        for track in tracks
        if isinstance(track, dict)
    ]
    embedded_recording_ratio = (
        sum(1 for mbid in recording_ids if mbid) / observed if observed else 0.0
    )

    # Conservative starter weights. Future versions can add actual recording,
    # position, duration, disc-layout and AcoustID agreement.
    total = (
        track_count_score * 0.60
        + mb_search_score * 0.25
        + embedded_recording_ratio * 0.15
    )

    warnings: list[str] = []
    if expected and observed and expected != observed:
        warnings.append(f"track_count_mismatch:{observed}_vs_{expected}")
    if observed and embedded_recording_ratio < 0.5:
        warnings.append("weak_embedded_recording_evidence")

    return {
        "score": round(total, 4),
        "track_count_score": round(track_count_score, 4),
        "musicbrainz_search_score": round(mb_search_score, 4),
        "embedded_recording_ratio": round(embedded_recording_ratio, 4),
        "warnings": warnings,
    }
