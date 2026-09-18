"""DroppedNeedle Metadata Doctor plugin.

v0.1 focuses on safe diagnosis. It does not silently rewrite identity metadata.
"""

from __future__ import annotations

import time
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


async def _apply_exact_release(*, album_id: str, release_mbid: str) -> dict[str, Any]:
    """Apply an administrator-supplied exact release through native store APIs.

    This deliberately bypasses the explicit-reidentification decision gate.
    The admin has already supplied the exact MusicBrainz release, so we persist
    the same manual identity shapes used by DroppedNeedle's native store.
    """
    from core.dependencies.cache_providers import get_native_library_store
    from core.dependencies.repo_providers import get_musicbrainz_identification_repository
    from core.dependencies.service_providers import _schedule_identified_album_work
    from models.local_catalog import LocalAlbumExternalIdentity, LocalTrackExternalIdentity
    from services.native.album_candidate_service import AlbumCandidateService
    from services.native.identification_revisions import album_input_revisions
    from services.native.local_album_grouping_service import grouping_track_from_row

    store = get_native_library_store()
    context = await store.get_album_identification_context(album_id)
    if context is None:
        return {"status": 404, "body": {"error": "album_not_found", "message": "Library album not found."}}

    indexed_rows = [
        row for row in context.get("tracks", [])
        if row.get("availability") == "indexed"
    ]
    if not indexed_rows:
        return {
            "status": 400,
            "body": {"error": "no_indexed_tracks", "message": "The album has no indexed tracks."},
        }

    candidate_service = AlbumCandidateService(
        get_musicbrainz_identification_repository()
    )
    grouping_tracks = [grouping_track_from_row(row) for row in indexed_rows]
    candidates = await candidate_service.recall(
        grouping_tracks,
        exact_release_mbid=release_mbid,
        explicit=True,
    )
    if not candidates:
        return {
            "status": 404,
            "body": {
                "error": "release_not_found",
                "message": "MusicBrainz did not return that release for this album.",
                "release_mbid": release_mbid,
            },
        }

    candidate = candidates[0]
    release_group_mbid = str(candidate.release_group_mbid or "").strip()
    candidate_release_mbid = str(candidate.release_mbid or release_mbid).strip()
    if not release_group_mbid:
        return {
            "status": 422,
            "body": {
                "error": "release_group_missing",
                "message": "The selected MusicBrainz release has no release-group ID.",
                "release_mbid": release_mbid,
            },
        }

    local_by_position: dict[tuple[int, int], dict[str, Any]] = {}
    for row in indexed_rows:
        position = (int(row.get("disc_number") or 1), int(row.get("track_number") or 0))
        if position[1] < 1 or position in local_by_position:
            local_by_position = {}
            break
        local_by_position[position] = row

    candidate_by_position: dict[tuple[int, int], Any] = {}
    for track in candidate.tracks:
        position = (int(track.disc_number or 1), int(track.position or 0))
        if (
            position[1] < 1
            or not track.recording_mbid
            or not track.release_track_mbid
            or position in candidate_by_position
        ):
            candidate_by_position = {}
            break
        candidate_by_position[position] = track

    if (
        not local_by_position
        or not candidate_by_position
        or set(local_by_position) != set(candidate_by_position)
    ):
        return {
            "status": 400,
            "body": {
                "error": "track_mapping_required",
                "message": (
                    "The exact release was found, but its disc/track positions "
                    "do not map one-to-one onto the indexed album. No identity was changed."
                ),
                "release_mbid": candidate_release_mbid,
                "release_group_mbid": release_group_mbid,
                "local_track_count": len(indexed_rows),
                "release_track_count": len(candidate.tracks),
            },
        }

    now = time.time()
    await store.attach_album_identity(
        LocalAlbumExternalIdentity(
            local_album_id=album_id,
            release_group_mbid=release_group_mbid,
            release_mbid=candidate_release_mbid,
            decision_source="manual",
            selected_at=now,
        ),
        expected_album_revision=int(context["album"]["row_revision"]),
    )

    attached_tracks = 0
    for position, row in local_by_position.items():
        provider_track = candidate_by_position[position]
        await store.attach_track_identity(
            LocalTrackExternalIdentity(
                local_track_id=str(row["id"]),
                recording_mbid=str(provider_track.recording_mbid),
                release_mbid=candidate_release_mbid,
                release_track_mbid=str(provider_track.release_track_mbid),
                medium_position=int(provider_track.disc_number or 1),
                release_track_position=int(provider_track.position),
                decision_source="manual",
                selected_at=now,
            ),
            expected_track_revision=int(row.get("identity_row_revision") or 1),
        )
        attached_tracks += 1

    await _schedule_identified_album_work(
        album_id,
        album_input_revisions(indexed_rows)[2],
    )
    return {
        "status": 200,
        "body": {
            "ok": True,
            "album_id": album_id,
            "release_mbid": candidate_release_mbid,
            "release_group_mbid": release_group_mbid,
            "tracks_updated": attached_tracks,
            "decision_source": "manual",
            "message": "Exact MusicBrainz release applied.",
        },
    }


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
        if method != "POST":
            return PluginRouteResponse(status=404, body={"error": "not_found"})

        if subpath == "identify-exact":
            if not isinstance(body, dict):
                return PluginRouteResponse(
                    status=400,
                    body={"error": "invalid_body", "message": "Expected a JSON object."},
                )
            album_id = str(body.get("album_id") or "").strip()
            release_mbid = str(body.get("release_mbid") or "").strip()
            if not album_id or not release_mbid:
                return PluginRouteResponse(
                    status=400,
                    body={
                        "error": "missing_fields",
                        "message": "album_id and release_mbid are required",
                    },
                )
            result = await _apply_exact_release(
                album_id=album_id,
                release_mbid=release_mbid,
            )
            return PluginRouteResponse(
                status=int(result["status"]),
                body=result["body"],
            )

        if subpath != "diagnose":
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
