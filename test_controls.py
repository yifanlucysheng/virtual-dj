"""
Tests for controls.py. Run with:  python3 test_controls.py

No camera and no window. Each test builds dictionaries and pretends to pinch.
"""

from controls import (
    makeButton,
    makeSlider,
    pointInside,
    sliderHandle,
    updateControls,
)


def close(a, b):
    return abs(a - b) < 0.000001


def testPointInside():
    """The edges count as inside. A point just past an edge does not."""
    assert pointInside(10, 20, 10, 20, 30, 40) is True
    assert pointInside(40, 60, 10, 20, 30, 40) is True
    assert pointInside(9, 20, 10, 20, 30, 40) is False
    assert pointInside(41, 20, 10, 20, 30, 40) is False
    assert pointInside(10, 61, 10, 20, 30, 40) is False
    print('pass: pointInside')


def testButtonFiresOncePerPinch():
    """Holding the pinch on a button counts as one press, not one per frame."""
    button = makeButton('play', 0, 0, 100, 40)
    controls = [button]

    updateControls(controls, False, True, 10, 10)
    assert button['presses'] == 1
    assert button['held'] is True

    updateControls(controls, True, True, 10, 10)
    updateControls(controls, True, True, 80, 30)
    assert button['presses'] == 1

    updateControls(controls, True, False, 80, 30)
    assert button['held'] is False
    assert button['presses'] == 1

    updateControls(controls, False, True, 10, 10)
    assert button['presses'] == 2

    # A pinch that starts outside the button does not press it.
    updateControls(controls, True, False, 0, 0)
    updateControls(controls, False, True, 200, 200)
    assert button['presses'] == 2
    print('pass: button fires once per pinch')


def testSliderFollowsTheCursorWhileGrabbed():
    """Pinch the handle, then the value follows x and stays between 0 and 1."""
    slider = makeSlider('volume', 100, 50, 200, 10, value=0)
    controls = [slider]
    handleLeft, handleTop, handleWidth, handleHeight = sliderHandle(slider)
    startX = handleLeft + handleWidth / 2
    startY = handleTop + handleHeight / 2

    updateControls(controls, False, True, startX, startY)
    assert slider['grabbed'] is True

    updateControls(controls, True, True, 200, startY)
    assert close(slider['value'], 0.5)

    updateControls(controls, True, True, 1000, startY)
    assert slider['value'] == 1

    updateControls(controls, True, True, -50, startY)
    assert slider['value'] == 0
    print('pass: slider follows the cursor and clamps')


def testSliderStaysGrabbedUntilRelease():
    """Leaving the handle does not drop the slider. Ending the pinch does."""
    slider = makeSlider('crossfader', 0, 0, 100, 10, value=0.5)
    controls = [slider]
    handleLeft, handleTop, handleWidth, handleHeight = sliderHandle(slider)
    x = handleLeft + handleWidth / 2
    y = handleTop + handleHeight / 2

    updateControls(controls, False, True, x, y)
    # Cursor is far above the track, and the value still follows.
    updateControls(controls, True, True, 25, 500)
    assert slider['grabbed'] is True
    assert close(slider['value'], 0.25)

    updateControls(controls, True, False, 25, 500)
    assert slider['grabbed'] is False
    assert close(slider['value'], 0.25)

    # A pinch on the track, but not on the handle, does not grab.
    updateControls(controls, False, True, 10, 5)
    assert slider['grabbed'] is False
    assert close(slider['value'], 0.25)
    print('pass: slider stays grabbed until the pinch ends')


if __name__ == '__main__':
    testPointInside()
    testButtonFiresOncePerPinch()
    testSliderFollowsTheCursorWhileGrabbed()
    testSliderStaysGrabbedUntilRelease()
    print('4 tests passed')