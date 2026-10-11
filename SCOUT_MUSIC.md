# Optional soundtracks

FTB Scout's **Music track** selector offers six locally bundled tracks:

- **NBA on NBC · 8-bit**: an instrumental cover of John Tesh's *Roundball Rock*, with pulse lead, triangle bass, and quantized percussion. The sequence comes from [BitMidi's nba-nbc.mid](https://bitmidi.com/nba-nbc-mid), retained in `scripts/music/nba-nbc.mid`. The source page does not identify the MIDI uploader/arranger. The render contains no samples of the broadcast recording. Duration: 77.184 seconds.
- **Battle! May–Brendan · RSE**: the supplied Pokémon Ruby/Sapphire/Emerald MIDI, rendered with 15 SF2 instruments from the user's `H:\Ableton Exports\PKMN RSE` library. Matching May–Brendan variants supply the synth parts; other parts use shared RSE instruments. The collection credits Exabyte U for ripping/sorting and Pokemon Rater and theIpatix for MIDI names. Duration: 64.898 seconds.
- **Battle! Gym Leader · RSE**: 19 RSE soundfonts, including matching Gym Leader synth variants. Duration: 75.918 seconds.
- **Mt. Pyre Peak · RSE**: 13 RSE soundfonts, including its matching synth and NES percussion variants. Duration: 82.353 seconds.
- **Surfing · RSE**: 17 RSE soundfonts, including its matching piano, harp, pad, and lead variants. Duration: 71.341 seconds.
- **Diving · RSE**: 11 RSE soundfonts, including its matching glockenspiel, bubbles, bowed glass, and NES percussion variants. Duration: 86.512 seconds.

All five RSE tracks are rendered from the supplied MIDI files using that local soundfont collection. Shared RSE instruments fill the remaining parts. The RSE drumkit selected for Mt. Pyre Peak and Diving covers every percussion note those MIDI files use.

Click **MUSIC** to start looping the selected track. The same audio element continues across Picks, Matchup, Live PbP, Parlay, and Data. Switching tracks during playback starts the new track from its beginning; switching while paused stays silent. Selecting the already selected track preserves its position. Each full arrangement repeats, including its intro; the RSE MIDI's internal loop markers are recorded in the source manifest but do not change playback boundaries.

The last track selection and volume are saved in this browser when storage is available. Volume defaults to 18%. A reload starts silent and requires another click. Browser or operating-system media suspension can interrupt playback.

All MP3s have content-versioned URLs. `preload="none"` defers audio loading until requested, and playback makes no third-party requests. Adding tracks does not preload the entire collection. The source credit link for the NBA track opens BitMidi; it does not imply a license grant or endorsement. The supplied RSE MIDI files and raw soundfonts remain local; neither is published in the repository or website.

## Rebuilding audio

Install `numpy`, `mido`, and `imageio-ffmpeg` in a development environment. These are asset-generation dependencies; collection and publication do not need them.

For the NBA cover, run `python scripts/render_scout_music.py`. `nba ftb shi/scout_music_source.json` records its source and rendered audio SHA-256 hashes. The MP3 is about 1.24 MB.

For an RSE track, use an official [FluidSynth shared-library build](https://github.com/FluidSynth/fluidsynth/releases), then supply its MIDI, soundfont mapping, output, and manifest explicitly. For example, from the repository root:

```powershell
python scripts/render_rse_music.py --source 'H:\Ableton Exports\PKMN RSE\[PKMN RSE]\Battle! Gym Leader.mid' --soundfonts 'H:\Ableton Exports\PKMN RSE' --library '<path to libfluidsynth-3.dll>' --mapping scripts/music/gym-leader-soundfonts.json --output 'nba ftb shi/gym-leader-rse.mp3' --manifest 'nba ftb shi/gym-leader-rse-source.json'
```

Each `scripts/music/<track>-soundfonts.json` maps MIDI programs to relative soundfont paths. Track names are `may-brendan`, `gym-leader`, `mt-pyre-peak`, `surfing`, and `diving`. The renderer preserves program changes, note velocities, tempo, volume, panning, modulation, and pitch bends. It renders stereo 44.1 kHz audio using FluidSynth, normalizes the peak, applies an 8 ms endpoint fade, and encodes a 128 kbps MP3. It rejects unmapped programs, failed synthesis, and silent or non-finite audio.

`nba ftb shi/rse_music_source.json` records provenance for May–Brendan. The other RSE tracks use `<track>-rse-source.json` beside their `<track>-rse.mp3` files. Every manifest records the MIDI/audio hashes, all selected soundfont hashes, renderer version, source loop markers, and note count. Keep rendered audio and its hash manifest together. Individual RSE MP3s are approximately 1.04–1.39 MB.

Verification on October 11, 2026:

- Twenty music checks cover silent startup, repeat configuration, pause/resume, external media pause, blocked playback, pending-play cancellation, saved/clamped volume, unavailable storage, error recovery, cleanup, audio/source hashes, switching and silently restoring all six tracks, invalid selections, rapid switching, and controller remounts with immutable source URLs. The new RSE provenance check verifies all four audio hashes, source MIDI hashes, instrument maps, note counts, and loop-marker boundaries.
- The allowlisted static build publishes all six MP3s and the versioned player script; all ten publishing checks passed. The original two-track release also passed all nine existing JavaScript suites and 50 Python tests.
- Browser checks confirmed switching between both tracks during playback, selecting a different track while paused, and restoring the selected RSE track on a silent reload. Each page uses one audio element.
- After more than 75 seconds of RSE playback, the 64.898-second track was still playing at approximately 13 seconds with no media error, confirming a natural repeat. Switching analysis tabs retained playback.
- At a 390-pixel mobile viewport, the track selector fits beside playback and volume controls, and the Parlay page has no horizontal overflow.
- Browser playback checks loaded each of the four new, versioned MP3s successfully, with the expected duration, native looping, one audio element, and no media errors.

No scoring, statistical data, candidate ranking, or research settings change as part of this soundtrack feature.
