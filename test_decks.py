"""
Tests for decks.py. Run with:  python3 test_decks.py

No window and no speakers. One test uses a tiny wav with the wrong sample rate.
"""

import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_engine import AudioEngine
from controls import makeButton, makeSlider, updateControls
from decks import (
    applyControls,
    handleKey,
    loadDeckFiles,
    makeControls,
    makeDeck,
    syncEngine,
)


def testMissingSongPrintsAndContinues():
    """A missing path sets loadError and does not raise."""
    engine = AudioEngine()
    decks = [makeDeck('Deck 1'), makeDeck('Deck 2')]
    missing = [('songs/no-such-vocals.wav', 'songs/no-such-instr.wav')] * 2
    loadDeckFiles(engine, decks, missing)
    assert decks[0]['loadError'] == 'No song file'
    assert decks[1]['loadError'] == 'No song file'
    assert len(engine.decks[0].vocals) == 0
    print('pass: missing song stays quiet')


def testBadWavStaysQuiet():
    """A wav at the wrong sample rate is a friendly failure, not a crash."""
    engine = AudioEngine()
    decks = [makeDeck('Deck 1'), makeDeck('Deck 2')]
    folder = Path(tempfile.mkdtemp())
    quiet = np.zeros(200, dtype=np.float32)
    vocals = folder / 'vocals.wav'
    instrumental = folder / 'instrumental.wav'
    sf.write(vocals, quiet, 22050)
    sf.write(instrumental, quiet, 22050)
    paths = [(vocals, instrumental), ('missing.wav', 'missing2.wav')]
    loadDeckFiles(engine, decks, paths)
    assert decks[0]['loadError'] == 'No song file'
    assert decks[1]['loadError'] == 'No song file'
    print('pass: bad wav stays quiet')


def testPinchWritesTheModel():
    """One pinch toggles play. Holding it does not toggle again. A slider sets volume."""
    decks = [makeDeck('Deck 1'), makeDeck('Deck 2')]
    controls = makeControls(960, 600)
    play = controls[0]
    updateControls(controls, False, True, play['left'] + 4, play['top'] + 4)
    crossfader = applyControls(decks, 0.5, controls)
    assert decks[0]['playing'] is True

    updateControls(controls, True, True, play['left'] + 4, play['top'] + 4)
    crossfader = applyControls(decks, crossfader, controls)
    assert decks[0]['playing'] is True

    volume = next(c for c in controls if c['name'] == 'deck1-volume')
    volume['value'] = 0.25
    crossfader = applyControls(decks, crossfader, controls)
    assert decks[0]['volume'] == 0.25

    vocals = next(c for c in controls if c['name'] == 'deck1-vocals')
    updateControls(controls, False, True, vocals['left'] + 4, vocals['top'] + 4)
    applyControls(decks, crossfader, controls)
    assert decks[0]['vocalsOn'] is False
    print('pass: pinch writes the deck model')


def testKeysAndSync():
    """Arrows move the crossfader. The engine receives play, volume, and the end of a song."""
    decks = [makeDeck('Deck 1'), makeDeck('Deck 2')]
    controls = [makeSlider('crossfader', 0, 0, 100, 10, 0.5), makeButton('deck1-play', 0, 0, 10, 10)]
    assert handleKey(decks, controls, 'right') is False
    assert abs(controls[0]['value'] - 0.55) < 0.000001
    crossfader = applyControls(decks, 0.5, controls)
    assert abs(crossfader - 0.55) < 0.000001

    assert handleKey(decks, controls, 'space') is False
    assert decks[0]['playing'] is True
    assert handleKey(decks, controls, 'q') is True

    engine = AudioEngine()
    samples = np.ones(100, dtype=np.float32)
    for audio in engine.decks:
        audio.vocals = samples
        audio.instrumental = samples
    decks[0]['volume'] = 0.25
    syncEngine(engine, decks, crossfader)
    assert engine.decks[0].playing is True
    assert engine.decks[0].volume == 0.25
    assert abs(engine.crossfader - 0.55) < 0.000001

    # Pause keeps the playhead. Play again continues from there.
    decks[0]['playing'] = False
    engine.decks[0].position = 40
    syncEngine(engine, decks, crossfader)
    assert engine.decks[0].playing is False
    assert engine.decks[0].position == 40
    decks[0]['playing'] = True
    syncEngine(engine, decks, crossfader)
    assert engine.decks[0].playing is True
    assert engine.decks[0].position == 40

    # The callback reached the last sample. The button returns to Play.
    engine.decks[0].position = 100
    engine.decks[0].playing = False
    syncEngine(engine, decks, crossfader)
    assert decks[0]['playing'] is False
    assert engine.decks[0].playing is False

    # The next play starts over at sample 0.
    decks[0]['playing'] = True
    syncEngine(engine, decks, crossfader)
    assert engine.decks[0].position == 0
    assert engine.decks[0].playing is True
    print('pass: keys and engine sync')


def testBrokenDeckIgnoresPlay():
    decks = [makeDeck('Deck 1'), makeDeck('Deck 2')]
    decks[0]['loadError'] = 'No song file'
    assert handleKey(decks, [], 'space') is False
    assert decks[0]['playing'] is False
    print('pass: play on a missing song does nothing')


if __name__ == '__main__':
    testMissingSongPrintsAndContinues()
    testBadWavStaysQuiet()
    testPinchWritesTheModel()
    testKeysAndSync()
    testBrokenDeckIgnoresPlay()
    print('5 tests passed')