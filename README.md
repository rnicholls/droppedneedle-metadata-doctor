# DroppedNeedle Metadata Doctor

A DroppedNeedle Plugin API v1 plugin for diagnosing suspicious album metadata and ranking likely MusicBrainz releases.

## Why this exists

DroppedNeedle's native identification pipeline is capable, but difficult libraries can still end up attached to the wrong edition or release. Metadata Doctor is designed to reason about an album as a whole instead of trusting one weak clue.

The plugin now has two deliberately separate paths:

- **Diagnose** — read-only MusicBrainz search and candidate ranking.
- **Identify exact** — an admin supplies an exact MusicBrainz release MBID and the plugin applies that release directly through DroppedNeedle's existing native identity store.

The exact path exists for the simple case where the administrator already knows:

> "This is the album. Make it so."

It deliberately does not wait for DroppedNeedle's normal evidence/edition decision to agree.

## Identify exact

Admin-only:

`POST /api/v1/plugins/ext/droppedneedle-metadata-doctor/identify-exact`

Example:

```json
{
  "album_id": "cbbe4ba2-9a36-56a4-811e-fb8155e8cb49",
  "release_mbid": "04ebe4ba-9969-403e-9356-97929d4a7270"
}
```

The plugin resolves the supplied release through DroppedNeedle's existing MusicBrainz candidate service, requires a complete disc/track position mapping, writes the album and per-track identities as manual identities, and schedules the normal identified-album management/reconciliation work.

If the release cannot be mapped one-to-one, nothing is changed and the route returns a 409.

This is intentionally an album identity repair path; it does not rewrite audio tags and does not depend on beets.

## Installation

In DroppedNeedle:

1. Go to **Settings > Plugins**.
2. Install:

   `https://github.com/rnicholls/droppedneedle-metadata-doctor`

3. Enable the plugin.
4. Configure the MusicBrainz User-Agent if desired.

To install the exact-identity work currently under development, use:

`https://github.com/rnicholls/droppedneedle-metadata-doctor/tree/exact-identify`

Under Docker, make sure `/app/plugins` is persisted or installed plugins disappear when the container is recreated.

## Diagnose route

Admin-only:

`POST /api/v1/plugins/ext/droppedneedle-metadata-doctor/diagnose`

Example body:

```json
{
  "artist": "Example Artist",
  "album": "Example Album",
  "tracks": [
    {
      "title": "Track One",
      "recording_mbid": "..."
    }
  ]
}
```

The response returns ranked MusicBrainz release candidates plus mismatch warnings.

## Planned roadmap

- fetch complete MusicBrainz release media/tracklists
- compare recording MBIDs per track
- compare disc and track positions
- compare durations
- optional Chromaprint/AcoustID evidence for ambiguous tracks
- explicit ambiguity thresholds
- repair preview UI
- supported DroppedNeedle apply workflow once the host exposes an identity-repair capability

## Safety rule

Metadata Doctor should prefer **ambiguous** over **wrong**. Low-confidence cases stay manual.
