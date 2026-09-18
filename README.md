# DroppedNeedle Metadata Doctor

A DroppedNeedle Plugin API v1 plugin for diagnosing suspicious album metadata and ranking likely MusicBrainz releases.

## Why this exists

DroppedNeedle's native identification pipeline is capable, but difficult libraries can still end up attached to the wrong edition or release. Metadata Doctor is designed to reason about an album as a whole instead of trusting one weak clue.

The first milestone is deliberately safe:

- inspect album-level evidence
- query MusicBrainz for candidate releases
- penalize obvious edition mismatches such as track-count differences
- return ranked candidates through a DroppedNeedle plugin route
- never silently overwrite first-party identity metadata

## Current limitation

DroppedNeedle Plugin API v1 exposes `metadata_provider` as a gap-filling enrichment surface only. It does **not** expose a supported plugin capability for replacing release/recording identity metadata.

Accordingly, v0.1 is diagnosis-only. It does not touch DroppedNeedle's SQLite database and does not write tags behind DroppedNeedle's back.

A future DroppedNeedle host capability should expose an explicit identity-repair/apply path.

## Installation

In DroppedNeedle:

1. Go to **Settings > Plugins**.
2. Install:

   `https://github.com/rnicholls/droppedneedle-metadata-doctor`

3. Enable the plugin.
4. Configure the MusicBrainz User-Agent if desired.

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
