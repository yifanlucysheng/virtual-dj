"""
Tests for flower.py. Run with:  python3 test_flower.py

Every landmark list is made up. Nothing here opens a camera or a window.
"""

import math

import numpy as np

from audio_engine import AudioEngine
from flower import (
    FIST_RATIO,
    OPEN_RATIO,
    bloomAmount,
    handAngle,
    openness,
    palmCenter,
    petalShapes,
    smoothOpen,
    stepPetals,
    updateFlower,
)


def blank():
    """21 landmarks piled on the origin. Tests overwrite the ones they care about."""
    return [(0, 0)] * 21


def close(a, b):
    return abs(a - b) < 0.000001


def openHand(scale):
    """Flat hand, fingertips far from the palm. Wrist is below the knuckles."""
    points = blank()
    points[0] = (0, 100 * scale)
    points[5] = (-30 * scale, 40 * scale)
    points[9] = (0, 30 * scale)
    points[13] = (20 * scale, 40 * scale)
    points[17] = (40 * scale, 55 * scale)
    points[4] = (-50 * scale, 20 * scale)
    points[8] = (-40 * scale, -40 * scale)
    points[12] = (0, -50 * scale)
    points[16] = (30 * scale, -30 * scale)
    points[20] = (55 * scale, 0)
    return points


def fist(scale):
    """Same palm as openHand, with the fingertips curled in close."""
    points = openHand(scale)
    points[4] = (-5 * scale, 80 * scale)
    points[8] = (-20 * scale, 50 * scale)
    points[12] = (0, 45 * scale)
    points[16] = (15 * scale, 50 * scale)
    points[20] = (25 * scale, 60 * scale)
    return points


def freshApp():
    """The few app fields updateFlower writes. No CMU window."""
    app = type('App', (), {})()
    app.petals = []
    app.petalCredit = 0
    app.flowerOpen = None
    app.flowerX = None
    app.stepsPerSecond = 30
    app.height = 600
    return app


def testPalmCenterAveragesFiveLandmarks():
    """The center is the mean of 0, 5, 9, 13, and 17. Other points do not count."""
    points = blank()
    points[0] = (0, 0)
    points[5] = (10, 0)
    points[9] = (10, 10)
    points[13] = (0, 10)
    points[17] = (5, 5)
    points[8] = (99, 99)
    center = palmCenter(points)
    assert close(center[0], 5)
    assert close(center[1], 5)
    print('pass: palm center')


def testUpwardHandPointsNegativeHalfPi():
    """Knuckle straight above the wrist. Screen y grows downward, so the angle is -pi/2."""
    points = blank()
    points[0] = (0, 10)
    points[9] = (0, 0)
    assert close(handAngle(points), -math.pi / 2)
    print('pass: hand angle')


def testOpenHandBloomsAndScaleDoesNotMatter():
    """A fist is under the bud line. An open hand is well above it. Scale cancels."""
    small = openness(openHand(1))
    big = openness(openHand(4))
    closed = openness(fist(1))
    assert small > 1.0
    assert closed < FIST_RATIO
    assert close(small, big)
    assert bloomAmount(closed) == 0
    assert bloomAmount(small) > 0.5
    assert bloomAmount(FIST_RATIO) == 0
    assert bloomAmount(OPEN_RATIO) == 1
    print('pass: openness')


def testSmoothingTakesAQuarterStep():
    """The first sample is kept. The next one moves 25% of the way."""
    assert smoothOpen(None, 1.2) == 1.2
    assert close(smoothOpen(0.4, 1.2), 0.25 * 1.2 + 0.75 * 0.4)
    print('pass: smooth openness')


def testPetalOvalFollowsTheRay():
    """Pointing right puts a petal on +x at 90 degrees. Pointing up puts it on -y at 0."""
    right = petalShapes(0, 0, 0, 100, 1)[0]
    assert right[0] > 0
    assert abs(right[1]) < 0.001
    assert close(right[4], 90)
    up = petalShapes(0, 0, -math.pi / 2, 100, 1)[0]
    assert abs(up[0]) < 0.001
    assert up[1] < 0
    assert close(up[4], 0)
    print('pass: petal ovals')


def testSilenceSpawnsNothingAndLoudnessSpawnsMore():
    """Loudness 0 stays empty. A louder value, over the same steps, drops more petals."""
    def count(loudness):
        petals = []
        credit = 0
        for _ in range(30):
            petals, credit = stepPetals(petals, credit, loudness, 30, 10, 10, 600)
        return len(petals)

    assert count(0) == 0
    assert count(1) > count(0.25) > 0
    print('pass: spawn rate')


def testPetalListNeverPassesForty():
    """A long loud stretch fills the list and then stops at 40."""
    petals = []
    credit = 0
    # A tall window, so petals pile up instead of falling off before the cap.
    for _ in range(400):
        petals, credit = stepPetals(petals, credit, 1, 30, 10, 10, 10000)
    assert len(petals) == 40
    assert credit <= 1
    print('pass: petal cap')


def testPetalsFallOffTheWindow():
    """Each step adds speed to y. Past the window, the petal is dropped."""
    petal = {
        'x': 5, 'y': 10, 'speed': 5, 'drift': 0, 'spin': 0,
        'angle': 0, 'size': 12, 'tint': 0,
    }
    petals, credit = stepPetals([petal], 0, 0, 30, None, None, 600)
    assert len(petals) == 1
    assert close(petals[0]['y'], 15)
    petals[0]['y'] = 590
    petals[0]['speed'] = 50
    petals, credit = stepPetals(petals, credit, 1, 30, None, None, 600)
    assert petals == []
    assert credit == 0
    print('pass: petals fall')


def testUpdateFlowerHidesWhenTheHandLeaves():
    """A hand stores a center. The next call with no points clears it and keeps old petals falling."""
    app = freshApp()
    updateFlower(app, openHand(1), 0)
    assert app.flowerX is not None
    assert app.flowerBloom > 0.5
    app.petals.append({
        'x': 5, 'y': 10, 'speed': 4, 'drift': 0, 'spin': 1,
        'angle': 0, 'size': 12, 'tint': 1,
    })
    updateFlower(app, None, 1)
    assert app.flowerX is None
    assert len(app.petals) == 1
    assert close(app.petals[0]['y'], 14)
    print('pass: update flower')


def testKnobLoudnessWhenSpeakersAreOff():
    """render stores the mix. With no stream, loudnessNow uses the deck knobs instead."""
    engine = AudioEngine(44100, blocksize=64)
    # Longer than one block, so render does not reach the end and stop the deck.
    tone = np.full(1000, 0.5, dtype=np.float32)
    deck = engine.decks[0]
    deck.vocals = tone
    deck.instrumental = np.zeros(1000, dtype=np.float32)
    deck.volume = 1
    deck.vocalsOn = True
    deck.instrumentalOn = True
    deck.playing = True
    engine.crossfader = 0
    engine.render(64)
    assert close(engine.loudness, 0.5)
    # Two stems at volume 1, crossfader all the way to this deck: knob level 1.
    # The mix itself is only 0.5, because the instrumental buffer is silent.
    assert close(engine.loudnessNow(), 1)
    deck.playing = False
    assert engine.loudnessNow() == 0
    print('pass: loudness')


if __name__ == '__main__':
    testPalmCenterAveragesFiveLandmarks()
    testUpwardHandPointsNegativeHalfPi()
    testOpenHandBloomsAndScaleDoesNotMatter()
    testSmoothingTakesAQuarterStep()
    testPetalOvalFollowsTheRay()
    testSilenceSpawnsNothingAndLoudnessSpawnsMore()
    testPetalListNeverPassesForty()
    testPetalsFallOffTheWindow()
    testUpdateFlowerHidesWhenTheHandLeaves()
    testKnobLoudnessWhenSpeakersAreOff()
    print('all flower tests passed')