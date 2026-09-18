"""Small MusicBrainz client using DroppedNeedle's shared HTTP client."""

from __future__ import annotations

from urllib.parse import quote


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
        return value or "DroppedNeedle-Metadata-Doctor/0.1.0"

    async def search_releases(self, *, artist: str, album: str, limit: int = 10) -> list[dict]:
        query = f'artist:"{artist}" AND release:"{album}"'
        url = f"{self.base_url}/release/?query={quote(query)}&fmt=json&limit={max(1, min(limit, 25))}"
        response = await self.ctx.http.get(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()

        releases: list[dict] = []
        for release in payload.get("releases", []):
            media = release.get("media") or []
            track_count = sum(int(m.get("track-count") or 0) for m in media)
            releases.append(
                {
                    "release_mbid": release.get("id"),
                    "title": release.get("title"),
                    "date": release.get("date"),
                    "country": release.get("country"),
                    "status": release.get("status"),
                    "track_count": track_count or int(release.get("track-count") or 0),
                    "score": int(release.get("score") or 0),
                    "release_group_mbid": (release.get("release-group") or {}).get("id"),
                }
            )
        return releases
