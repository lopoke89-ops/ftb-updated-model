# Optional soundtracks

FTB Scout's **Music track** selector offers two locally bundled tracks:

- **NBA on NBC · 8-bit**: an instrumental cover of John Tesh's *Roundball Rock*, with pulse lead, triangle bass, and quantized percussion. The sequence comes from [BitMidi's nba-nbc.mid](https://bitmidi.com/nba-nbc-mid), retained in `scripts/music/nba-nbc.mid`. The source page does not identify the MIDI uploader/arranger. The render contains no samples of the broadcast recording. Duration: 77.184 seconds.
- **Battle! May–Brendan · RSE**: the supplied Pokémon Ruby/Sapphire/Emerald MIDI, rendered with 15 SF2 instruments from the user's `H:\Ableton Exports\PKMN RSE` library. Matching May–Brendan variants supply the synth parts; other parts use shared RSE instruments. The collection credits Exabyte U for ripping/sorting and Pokemon Rater and theIpatix for MIDI names. Duration: 64.898 seconds.

Click **MUSIC** to start looping the selected track. The same audio element continues across Picks, Matchup, Live PbP, Parlay, and Data. Switching tracks during playback starts the new track from its beginning; switching while paused stays silent. Selecting the already selected track preserves its position. Each full arrangement repeats, including its intro; the RSE MIDI's internal loop markers are recorded in the source manifest but do not change playback boundaries.

The last track selection and volume are saved in this browser when storage is available. Volume defaults to 18%. A reload starts silent and requires another click. Browser or operating-system media suspension can interrupt playback.

Both MP3s have content-versioned URLs. `preload="none"` defers audio loading until requested, and playback makes no third-party requests. The source credit link for the NBA track opens BitMidi; it does not imply a license grant or endorsement. The supplied RSE MIDI and raw soundfonts remain local; neither is published in the repository or website.

## Rebuilding audio

Install `numpy`, `mido`, and `imageio-ffmpeg` in a development environment. These are asset-generation dependencies; collection and publication do not need them.

For the NBA cover, run `python scripts/render_scout_music.py`. `nba ftb shi/scout_music_source.json` records its source and rendered audio SHA-256 hashes. The MP3 is about 1.24 MB.

For the RSE track, use an official [FluidSynth shared-library build](https://github.com/FluidSynth/fluidsynth/releases), then run:

```powershell
python scripts/render_rse_music.py --source 'H:\Ableton Exports\PKMN RSE\[PKMN RSE]\Battle! May-Brendan.mid' --soundfonts 'H:\Ableton Exports\PKMN RSE' --library '<path to libfluidsynth-3.dll>'
```

`scripts/music/may-brendan-soundfonts.json` maps each MIDI program to a relative soundfont path. The renderer preserves program changes, note velocities, tempo, volume, panning, modulation, and pitch bends. It renders stereo 44.1 kHz audio using FluidSynth, normalizes the peak, applies an 8 ms endpoint fade, and encodes a 128 kbps MP3. `nba ftb shi/rse_music_source.json` records the MIDI/audio hashes, all 15 soundfont hashes, renderer version, source loop markers, and note count. Keep rendered audio and its hash manifest together. The RSE MP3 is about 1.04 MB.

Verification on October 11, 2026:

- Eighteen music checks cover silent startup, repeat configuration, pause/resume, external media pause, blocked playback, pending-play cancellation, saved/clamped volume, unavailable storage, error recovery, cleanup, both audio/source hashes, track switching, saved selection, invalid selections, rapid switching, and controller remounts with immutable source URLs.
- All nine existing JavaScript suites and 50 Python tests passed; the allowlisted static build publishes both MP3s and the versioned player script.
- Browser checks confirmed switching between both tracks during playback, selecting a different track while paused, and restoring the selected RSE track on a silent reload. Each page uses one audio element.
- After more than 75 seconds of RSE playback, the 64.898-second track was still playing at approximately 13 seconds with no media error, confirming a natural repeat. Switching analysis tabs retained playback.
- At a 390-pixel mobile viewport, the track selector fits beside playback and volume controls, and the Parlay page has no horizontal overflow.

No scoring, statistical data, candidate ranking, or research settings change as part of this soundtrack feature.
