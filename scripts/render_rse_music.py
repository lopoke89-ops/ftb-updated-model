"""Offline render of a supplied MIDI using a per-song map of the user's RSE SF2 files.

Requires numpy, mido, imageio-ffmpeg and a FluidSynth shared library. Only the
rendered MP3 ships to browsers; the original soundfont library stays local.
"""
import argparse
import ctypes as ct
import hashlib
import json
import os
import subprocess
import wave
from pathlib import Path

import imageio_ffmpeg
import mido
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RATE = 44100


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(source, soundfonts, library, output, mapping_path, manifest, title=None):
    mapping = json.loads(mapping_path.read_text())
    title = title or source.stem
    # Retain the DLL directory handle while Windows resolves shared dependencies.
    dll_dir = os.add_dll_directory(str(library.resolve().parent)) if os.name == 'nt' else None
    lib = ct.CDLL(str(library.resolve()))
    def bind(name, result, *args):
        fn = getattr(lib, name)
        fn.restype, fn.argtypes = result, list(args)
        return fn
    ptr, integer = ct.c_void_p, ct.c_int
    renderer_version = bind('fluid_version_str', ct.c_char_p)().decode('ascii')
    new_settings = bind('new_fluid_settings', ptr)
    delete_settings = bind('delete_fluid_settings', None, ptr)
    set_num = bind('fluid_settings_setnum', integer, ptr, ct.c_char_p, ct.c_double)
    set_int = bind('fluid_settings_setint', integer, ptr, ct.c_char_p, integer)
    new_synth = bind('new_fluid_synth', ptr, ptr)
    delete_synth = bind('delete_fluid_synth', None, ptr)
    load = bind('fluid_synth_sfload', integer, ptr, ct.c_char_p, integer)
    select = bind('fluid_synth_program_select', integer, ptr, integer, integer, integer, integer)
    note_on = bind('fluid_synth_noteon', integer, ptr, integer, integer, integer)
    note_off = bind('fluid_synth_noteoff', integer, ptr, integer, integer)
    cc = bind('fluid_synth_cc', integer, ptr, integer, integer, integer)
    bend = bind('fluid_synth_pitch_bend', integer, ptr, integer, integer)
    pressure = bind('fluid_synth_channel_pressure', integer, ptr, integer, integer)
    write = bind('fluid_synth_write_float', integer, ptr, integer, ptr, integer, integer, ptr, integer, integer)
    settings = new_settings()
    set_num(settings, b'synth.sample-rate', RATE)
    set_num(settings, b'synth.gain', .5)
    set_int(settings, b'synth.reverb.active', 0)
    set_int(settings, b'synth.chorus.active', 0)
    synth = new_synth(settings)
    if not synth:
        delete_settings(settings)
        raise RuntimeError('FluidSynth initialization failed')
    fonts, provenance, used, markers = {}, [], set(), {}
    midi = mido.MidiFile(source)
    mix = np.zeros((round(midi.length * RATE), 2), dtype=np.float32)
    now, frame, notes = 0., 0, 0
    try:
        for program, relative in mapping.items():
            path = soundfonts / relative
            font = load(synth, str(path.resolve()).encode('utf-8'), 0)
            if font < 0:
                raise ValueError('Could not load soundfont: ' + relative)
            fonts[int(program)] = font
            provenance.append({'program': int(program), 'file': relative, 'sha256': digest(path)})
        for event in midi:
            now += event.time
            end = min(round(now * RATE), len(mix))
            if end > frame:
                block = np.zeros((end - frame, 2), dtype=np.float32)
                data = block.ctypes.data_as(ptr)
                if write(synth, end - frame, data, 0, 2, data, 1, 2) < 0:
                    raise RuntimeError('Audio synthesis failed')
                mix[frame:end] = block
                frame = end
            result = 0
            if event.type == 'program_change':
                if event.program not in fonts:
                    raise ValueError('Unmapped MIDI program: ' + str(event.program))
                result = select(synth, event.channel, fonts[event.program], 0, event.program)
                used.add(event.program)
            elif event.type == 'note_on':
                if event.velocity:
                    result = note_on(synth, event.channel, event.note, event.velocity)
                else:
                    note_off(synth, event.channel, event.note)
                notes += bool(event.velocity)
            elif event.type == 'note_off':
                # One-shot percussion can finish before its MIDI note-off.
                note_off(synth, event.channel, event.note)
            elif event.type == 'control_change':
                result = cc(synth, event.channel, event.control, event.value)
            elif event.type == 'pitchwheel':
                result = bend(synth, event.channel, event.pitch + 8192)
            elif event.type == 'aftertouch':
                result = pressure(synth, event.channel, event.value)
            elif event.type == 'marker':
                markers[event.text] = round(now, 6)
            if result < 0:
                raise ValueError('MIDI event failed: ' + str(event))
    finally:
        delete_synth(synth)
        delete_settings(settings)
        if dll_dir:
            dll_dir.close()
    if used != set(fonts):
        raise ValueError('Soundfont mapping and MIDI programs differ')
    peak = float(np.max(np.abs(mix)))
    if not np.isfinite(mix).all() or peak <= 0:
        raise ValueError('Invalid or silent synthesized audio')
    mix *= .78 / peak
    fade = round(.008 * RATE)
    mix[:fade] *= np.linspace(0, 1, fade)[:, None]
    mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
    output.parent.mkdir(parents=True, exist_ok=True)
    wav = output.with_suffix('.render.wav')
    try:
        with wave.open(str(wav), 'wb') as stream:
            stream.setparams((2, 2, RATE, 0, 'NONE', 'not compressed'))
            stream.writeframes((mix * 32767).astype('<i2').tobytes())
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y', '-i', str(wav),
                        '-codec:a', 'libmp3lame', '-b:a', '128k', '-map_metadata', '-1',
                        '-metadata', 'title=' + title + ' - Pokemon RSE', str(output)], check=True)
    finally:
        wav.unlink(missing_ok=True)
    report = {'title': title, 'collection': 'Pokémon Ruby/Sapphire/Emerald',
              'sourceFile': source.name, 'sourceSha256': digest(source), 'audioSha256': digest(output),
              'seconds': midi.length, 'sampleRate': RATE, 'channels': 2, 'notes': notes,
              'renderer': 'FluidSynth ' + renderer_version, 'soundfontCollectionCredit': 'Exabyte U; MIDI names: Pokemon Rater and theIpatix',
              'soundfonts': provenance, 'sourceMarkersSeconds': markers,
              'loopPlayback': 'Full rendered arrangement, including intro, repeats.'}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--soundfonts', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--title')
    args = parser.parse_args()
    result = render(args.source, args.soundfonts, args.library, args.output, args.mapping, args.manifest, args.title)
    print(json.dumps({key: value for key, value in result.items() if key != 'soundfonts'}, indent=2))
