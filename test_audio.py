"""
Play one song for 5 seconds.

    python3 test_audio.py
    python3 test_audio.py songs/track1_vocals.wav songs/track1_instr.wav

No arguments: write a 5 second tone (440 Hz vocals, 220 Hz instrumental)
and play it on deck 1. The first part checks the crossfade without speakers.
"""

import math
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_engine import AudioEngine

RATE = 44100
SECONDS = 5


def writeTone(path, frequency):
    times = np.arange(RATE * SECONDS, dtype=np.float32) / RATE
    wave = (0.2 * np.sin(2 * math.pi * frequency * times)).astype(np.float32)
    sf.write(path, wave, RATE)


def checkMix():
    """0 is deck 1, 1 is deck 2, and the middle is cos and sin of the same angle."""
    folder = Path(tempfile.mkdtemp())
    loud = np.full(RATE, 0.5, dtype=np.float32)
    quiet = np.full(RATE, 0.25, dtype=np.float32)
    sf.write(folder / 'loud.wav', loud, RATE)
    sf.write(folder / 'quiet.wav', quiet, RATE)

    engine = AudioEngine(RATE)
    engine.load(0, folder / 'loud.wav', folder / 'quiet.wav')
    engine.load(1, folder / 'quiet.wav', folder / 'loud.wav')
    for deck in engine.decks:
        deck.volume = 1
        deck.instrumentalOn = False
        deck.playing = True

    engine.crossfader = 0
    assert np.allclose(engine.render(64), 0.5)
    # Deck 2 is silent here, and its playhead still moves.
    assert engine.decks[1].position == 64
    engine.crossfader = 1
    assert np.allclose(engine.render(64), 0.25)
    engine.crossfader = 0.5
    half = math.cos(math.pi / 4)
    assert np.allclose(engine.render(64), 0.5 * half + 0.25 * half)
    print('pass: equal-power crossfade')


def main():
    checkMix()
    if len(sys.argv) == 3:
        vocals, instrumental = sys.argv[1], sys.argv[2]
    else:
        folder = Path(tempfile.mkdtemp())
        vocals = folder / 'vocals.wav'
        instrumental = folder / 'instrumental.wav'
        writeTone(vocals, 440)
        writeTone(instrumental, 220)
        print('no song path given, playing a 5 second tone on deck 1')

    engine = AudioEngine(RATE)
    engine.load(0, vocals, instrumental)
    engine.load(1, vocals, instrumental)
    engine.crossfader = 0
    engine.decks[0].playing = True
    try:
        engine.start()
    except Exception as error:
        print('mix check passed, but no speakers are available:', error)
        return
    time.sleep(SECONDS)
    engine.stop()
    print('played 5 seconds')


if __name__ == '__main__':
    main()