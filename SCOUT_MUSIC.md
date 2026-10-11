# Optional 8-bit soundtrack

FTB Scout includes an instrumental 8-bit-style cover of John Tesh's **Roundball Rock**, the NBA on NBC theme. The sequence comes from [BitMidi's nba-nbc.mid](https://bitmidi.com/nba-nbc-mid); the original sequence is retained in `scripts/music/nba-nbc.mid`. The MIDI uploader/arranger is not identified by that source page. Composition credit remains John Tesh. This is an unofficial synthesized cover, with pulse lead, triangle bass, and quantized percussion; it contains no samples of the broadcast recording.

Click **8-BIT MUSIC** to start the 77.184-second loop. The same audio element continues across Picks, Matchup, Live PbP, Parlay, and Data. The button pauses/resumes it. Volume defaults to 18% and is saved in this browser when storage is available. A reload starts silent and requires another click. Browser or operating-system media suspension can still interrupt playback.

The soundtrack is bundled with the website, with a content-versioned URL. There is no streaming service, iframe, or third-party request for playback. `preload="none"` defers loading until requested. Track/source credit links to BitMidi; it does not imply a license grant or endorsement.

`nba ftb shi/scout_music_source.json` records the source and rendered audio SHA-256 hashes. To rebuild the asset, install `numpy`, `mido`, and `imageio-ffmpeg` in a development environment and run `python scripts/render_scout_music.py`. These are asset-generation dependencies; collection and publication do not need them. The checked-in MP3 is about 1.24 MB. Keep the updated audio and hash manifest together.

Verification on October 11, 2026:

- Ten playback checks cover silent startup, repeat configuration, pause/resume, external media pause, blocked playback, pending-play cancellation, saved/clamped volume, unavailable storage, error recovery, cleanup, and audio/source hashes.
- All nine existing JavaScript suites and 50 Python tests passed; the allowlisted static build publishes the versioned script and MP3.
- In the browser, after 91 seconds of playback, the 77.184-second track was playing at approximately 14 seconds with no media error, confirming a natural repeat. Tab navigation retained one audio element and continued playback.
- At a 390-pixel mobile viewport, player controls fit and page content had no horizontal overflow. A changed volume was retained on reload, which returned to silent startup.

No scoring, statistical data, candidate ranking, or research settings change as part of this soundtrack feature.
