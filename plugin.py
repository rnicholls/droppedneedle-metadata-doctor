"""DroppedNeedle Metadata Doctor plugin.

v0.1 focuses on safe diagnosis. It does not silently rewrite identity metadata.
"""

from __future__ import annotations

from typing import Any

from infrastructure.plugins.protocols import PluginRouteResponse

from metadata_doctor.musicbrainz import MusicBrainzClient
from metadata_doctor.scoring import score_release


class MetadataDoctor:
    def __init__(self, context):
        self.ctx = context
        self.mb = MusicBrainzClient(context)

    async def enrich_artist(self, *, artist_name, mbid=None, timeout=30.0):
        return None

    async def enrich_album(self, *, artist_name, album_title, mbid=None, timeout=30.0):
        # Metadata Provider v1 is gap-fill only. Identity repair belongs in the
        # diagnose/apply workflow, so we deliberately do not mutate here.
        return None

    async def handle_route(
        self,
        method: str,
        subpath: str,
        query: dict[str, str],
        body: object,
    ) -> PluginRouteResponse:
        if method != "POST" or subpath != "diagnose":
            return PluginRouteResponse(status=404, body={"error": "not_found"})

        if not isinstance(body, dict):
            return PluginRouteResponse(
                status=400,
                body={"error": "invalid_body", "message": "Expected a JSON object."},
            )

        artist = str(body.get("artist") or "").strip()
        album = str(body.get("album") or "").strip()
        tracks = body.get("tracks") or []

        if not artist or not album:
            return PluginRouteResponse(
                status=400,
                body={"error": "missing_fields", "message": "artist and album are required"},
            )

        if not isinstance(tracks, list):
            return PluginRouteResponse(
                status=400,
                body={"error": "invalid_tracks", "message": "tracks must be an array"},
            )

        candidates = await self.mb.search_releases(
            artist=artist,
            album=album,
            limit=10,
        )

        ranked: list[dict[str, Any]] = []
        for candidate in candidates:
            result = score_release(candidate, tracks)
            ranked.append({**candidate, "diagnosis": result})

        ranked.sort(
            key=lambda item: float(item.get("diagnosis", {}).get("score", 0.0)),
            reverse=True,
        )

        return PluginRouteResponse(
            status=200,
            body={
                "artist": artist,
                "album": album,
                "candidate_count": len(ranked),
                "candidates": ranked,
                "safe_to_apply": False,
                "note": (
                    "DroppedNeedle Plugin API v1 does not expose an identity-write "
                    "capability. This endpoint diagnoses and ranks candidates only."
                ),
            },
        )
