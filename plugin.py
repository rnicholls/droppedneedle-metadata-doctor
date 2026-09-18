"""DroppedNeedle Metadata Doctor plugin.

v0.1 focuses on safe diagnosis. It does not silently rewrite identity metadata.
"""

from __future__ import annotations

from typing import Any

from infrastructure.plugins.protocols import PluginRouteResponse

from urllib.parse import quote


def score_release(candidate: dict[str, Any], tracks: list[dict[str, Any]]) -> dict[str, Any]:
    expected = int(candidate.get("track_count") or 0)
    observed = len(tracks)
    mb_search_score = max(0, min(100, int(candidate.get("score") or 0))) / 100.0
    track_count_score = 0.0
    if expected and observed:
        delta = abs(expected - observed)
        track_count_score = 1.0 if delta == 0 else 0.65 if delta == 1 else 0.30 if delta <= 3 else 0.0
    recording_ids = [str(track.get("recording_mbid") or "").strip() for track in tracks if isinstance(track, dict)]
    embedded_recording_ratio = sum(1 for mbid in recording_ids if mbid) / observed if observed else 0.0
    total = track_count_score * 0.60 + mb_search_score * 0.25 + embedded_recording_ratio * 0.15
    warnings = []
    if expected and observed and expected != observed:
        warnings.append(f"track_count_mismatch:{observed}_vs_{expected}")
    if observed and embedded_recording_ratio < 0.5:
        warnings.append("weak_embedded_recording_evidence")
    return {"score": round(total, 4), "track_count_score": round(track_count_score, 4), "musicbrainz_search_score": round(mb_search_score, 4), "embedded_recording_ratio": round(embedded_recording_ratio, 4), "warnings": warnings}


class MusicBrainzClient:
    def __init__(self, context):
        self.ctx = context

    @property
    def base_url(self) -> str:
        value = str(self.ctx.settings.get("musicbrainz_base_url") or "").strip()
        return value.rstrip("/") or "https://musicbrainz.org/ws/2"

    @property
    def user_agent(self) -> str:
        value = str(self.ctx.settings.get("user_agent") or "").strip()
        return value or "DroppedNeedle-Metadata-Doctor/0.2.1"

    async def search_releases(self, *, artist: str, album: str, limit: int = 10) -> list[dict]:
        query = f'artist:"{artist}" AND release:"{album}"'
        url = f"{self.base_url}/release/?query={quote(query)}&fmt=json&limit={max(1, min(limit, 25))}"
        response = await self.ctx.http.get(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        releases = []
        for release in payload.get("releases", []):
            media = release.get("media") or []
            track_count = sum(int(m.get("track-count") or 0) for m in media)
            releases.append({"release_mbid": release.get("id"), "title": release.get("title"), "date": release.get("date"), "country": release.get("country"), "status": release.get("status"), "track_count": track_count or int(release.get("track-count") or 0), "score": int(release.get("score") or 0), "release_group_mbid": (release.get("release-group") or {}).get("id")})
        return releases


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
