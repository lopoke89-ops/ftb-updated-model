"""Render the bundled Roundball Rock MIDI as an 8-bit-style instrumental.

One-time asset tool, separate from collection and publication. Install numpy,
mido and imageio-ffmpeg to rebuild; publication uses the checked-in MP3.
"""
import argparse
import hashlib
import json
import subprocess
import wave
from pathlib import Path

import mido
import numpy as np
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
RATE = 44100


def render(source, output):
    midi = mido.MidiFile(source)
    now, active, notes = 0.0, {}, []
    for event in midi:
        now += event.time
        if event.type == 'note_on' and event.velocity:
            active.setdefault((event.channel, event.note), []).append((now, event.velocity))
        elif event.type == 'note_off' or event.type == 'note_on':
            stack = active.get((event.channel, event.note), [])
            if stack:
                start, velocity = stack.pop(0)
                notes.append((start, now, event.channel, event.note, velocity))
    if active and any(active.values()):
        raise ValueError('Source has unclosed notes')
    # Preserve the complete sequence, including its final resolving chord.
    duration = midi.length
    mix = np.zeros(round(duration * RATE), dtype=np.float64)
    rng = np.random.default_rng(89)
    for start, end, channel, pitch, velocity in notes:
        if channel == 9:
            length = .19 if pitch in (35, 36, 38, 40) else .075
        else:
            length = max(.015, end - start)
        offset = round(start * RATE)
        count = min(round(length * RATE), len(mix) - offset)
        if count <= 0:
            continue
        t = np.arange(count) / RATE
        freq = 440 * 2 ** ((pitch - 69) / 12)
        if channel == 9:
            noise = rng.choice((-1., 1.), count)
            if pitch in (35, 36):
                signal = np.sin(2 * np.pi * (48 * t + 2.6 * (1 - np.exp(-30 * t))))
                signal *= np.exp(-24 * t)
                gain = .32
            elif pitch in (38, 40):
                signal = (.8 * noise + .2 * np.sign(np.sin(2 * np.pi * 180 * t))) * np.exp(-27 * t)
                gain = .18
            elif pitch in (41, 43, 45, 47, 48, 50):
                tom = {41: 65, 43: 82, 45: 98, 47: 123, 48: 147, 50: 175}[pitch]
                signal = np.sign(np.sin(2 * np.pi * tom * t)) * np.exp(-30 * t)
                gain = .12
            else:
                signal = (noise - np.roll(noise, 1)) * .5 * np.exp(-55 * t)
                gain = .065
        elif channel == 7:
            signal = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * freq * t))
            gain = .32
        else:
            # Band-limited pulse lead: retain retro harmonics without aliasing.
            signal = sum(np.sin(2 * np.pi * freq * k * t) / k
                         for k in (1, 3, 5, 7, 9) if freq * k < RATE / 2)
            signal *= 4 / np.pi
            gain = .17
        envelope = np.minimum(1, t / .003) * np.minimum(1, (count / RATE - t) / .018)
        mix[offset:offset + count] += signal * envelope * gain * velocity / 127
    peak = float(np.max(np.abs(mix)))
    mix *= .78 / peak
    mix = np.round(mix * 127) / 127  # 8-bit amplitude steps in a modern container.
    # Quiet endpoints prevent a click as the audio element repeats the phrase.
    fade = round(.008 * RATE)
    mix[:fade] *= np.linspace(0, 1, fade)
    mix[-fade:] *= np.linspace(1, 0, fade)
    output.parent.mkdir(parents=True, exist_ok=True)
    wav = output.with_suffix('.render.wav')
    try:
        with wave.open(str(wav), 'wb') as stream:
            stream.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            stream.writeframes((mix * 32767).astype('<i2').tobytes())
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(wav),
                        '-codec:a', 'libmp3lame', '-b:a', '128k', '-map_metadata', '-1',
                        '-metadata', 'title=Roundball Rock - 8-bit cover',
                        '-metadata', 'composer=John Tesh', str(output)], check=True)
    finally:
        wav.unlink(missing_ok=True)
    result = {'title': 'Roundball Rock — 8-bit cover', 'composer': 'John Tesh',
              'sourcePage': 'https://bitmidi.com/nba-nbc-mid',
              'sourceDownload': 'https://bitmidi.com/uploads/79568.mid',
              'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'audioSha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'seconds': duration, 'sampleRate': RATE, 'notes': len(notes),
              'arrangement': 'Pulse lead, triangle bass, quantized noise percussion; no sampled recording.'}
    (output.parent / 'scout_music_source.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'scripts/music/nba-nbc.mid')
    parser.add_argument('--output', type=Path, default=ROOT / 'nba ftb shi/roundball-rock-8bit.mp3')
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.output), indent=2))
