"""
Four tests for pinch.py. Run with:  python3 test_pinch.py

Every landmark list is made up. Nothing here opens a camera or draws a window.
"""

from pinch import (
    CURSOR_NEW_WEIGHT,
    fingertipMidpoint,
    nextPinch,
    pinchDistance,
    smoothCursor,
)


def makeLandmarks(scale, gap, shift=(0, 0)):
    """A 10-point hand. Hand size is `scale`. Fingertip gap is `gap * scale`.

    The pinch ratio is `gap` at every scale. `shift` slides the whole hand.
    """
    points = [(0, 0)] * 10
    sx, sy = shift
    points[0] = (sx, sy)
    points[9] = (sx + scale, sy)
    points[4] = (sx, sy)
    points[8] = (sx, sy + gap * scale)
    return points


def close(a, b):
    return abs(a - b) < 0.000001


def testSamePinchWhenHandIsScaled():
    """A bigger copy of the same shape has the same pinch distance."""
    small = pinchDistance(makeLandmarks(scale=1, gap=0.2))
    big = pinchDistance(makeLandmarks(scale=7, gap=0.2))
    slid = pinchDistance(makeLandmarks(scale=7, gap=0.2, shift=(30, -12)))
    assert close(small, 0.2)
    assert close(big, small)
    assert close(slid, small)
    print('pass: scaling the hand does not change pinchDistance')


def testPinchTurnsOnBelow025():
    """Fingers closer than 0.25 of the hand turn the pinch on."""
    closed = makeLandmarks(scale=3, gap=0.2)
    barelyOpen = makeLandmarks(scale=3, gap=0.25)
    assert nextPinch(False, closed) is True
    assert nextPinch(False, barelyOpen) is False
    # Same gaps, different size: the on/off answer stays the same.
    assert nextPinch(False, makeLandmarks(scale=10, gap=0.2)) is True
    assert nextPinch(False, makeLandmarks(scale=10, gap=0.25)) is False
    print('pass: pinch turns on below 0.25')


def testPinchDoesNotFlickerInTheMiddle():
    """Between 0.25 and 0.35 the pinch stays whatever it already was."""
    middle = makeLandmarks(scale=2, gap=0.30)
    closed = makeLandmarks(scale=2, gap=0.20)
    wide = makeLandmarks(scale=4, gap=0.36)
    atOffLine = makeLandmarks(scale=4, gap=0.35)

    assert nextPinch(False, middle) is False
    assert nextPinch(False, closed) is True
    assert nextPinch(True, middle) is True
    assert nextPinch(True, atOffLine) is True
    assert nextPinch(True, wide) is False
    print('pass: pinch does not flicker between 0.25 and 0.35')


def testCursorFollowsTheMidpointPartway():
    """The cursor is the fingertip midpoint, pulled only partway each frame."""
    landmarks = [(0, 0)] * 10
    landmarks[0] = (0, 0)
    landmarks[9] = (10, 0)
    landmarks[4] = (2, 4)
    landmarks[8] = (8, 10)
    midpoint = fingertipMidpoint(landmarks)
    assert midpoint == (5, 7)

    # A hand twice as big has the same pinch ratio, and a midpoint twice as far.
    doubled = [(x * 2, y * 2) for x, y in landmarks]
    assert close(pinchDistance(landmarks), pinchDistance(doubled))
    assert fingertipMidpoint(doubled) == (10, 14)

    smoothed = smoothCursor((0, 0), midpoint)
    assert close(smoothed[0], CURSOR_NEW_WEIGHT * 5)
    assert close(smoothed[1], CURSOR_NEW_WEIGHT * 7)
    assert smoothed != midpoint
    assert smoothCursor(None, midpoint) == midpoint
    print('pass: cursor is a smoothed midpoint')


if __name__ == '__main__':
    testSamePinchWhenHandIsScaled()
    testPinchTurnsOnBelow025()
    testPinchDoesNotFlickerInTheMiddle()
    testCursorFollowsTheMidpointPartway()
    print('4 tests passed')