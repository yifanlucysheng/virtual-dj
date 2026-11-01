"""Buttons and sliders. A control is a dictionary. No camera and no drawing.

Releasing one hand does not drop a control the other hand is holding.
"""

HANDLE_WIDTH = 44
HANDLE_PAD_Y = 18


def pointInside(x, y, left, top, width, height):
    return (left <= x <= left + width) and (top <= y <= top + height)


def makeButton(name, left, top, width, height):
    return {
        'kind': 'button',
        'name': name,
        'left': left,
        'top': top,
        'width': width,
        'height': height,
        'presses': 0,
        'seenPresses': 0,
        'held': False,
        'owner': None,
    }


def makeSlider(name, left, top, width, height, value=0.5):
    return {
        'kind': 'slider',
        'name': name,
        'left': left,
        'top': top,
        'width': width,
        'height': height,
        'value': value,
        'grabbed': False,
        'owner': None,
    }


def sliderHandle(slider):
    centerX = slider['left'] + slider['value'] * slider['width']
    return (
        centerX - HANDLE_WIDTH / 2,
        slider['top'] - HANDLE_PAD_Y,
        HANDLE_WIDTH,
        slider['height'] + 2 * HANDLE_PAD_Y,
    )


def clamp01(value):
    if value < 0:
        return 0
    if value > 1:
        return 1
    return value


def moveSlider(slider, x):
    if slider['width'] == 0:
        slider['value'] = 0
        return
    slider['value'] = clamp01((x - slider['left']) / slider['width'])


def takenBySomeoneElse(control, owner):
    return control['owner'] is not None and control['owner'] != owner


def beginPinch(controls, x, y, owner):
    for control in controls:
        if takenBySomeoneElse(control, owner):
            continue
        if control['kind'] == 'button':
            if pointInside(x, y, control['left'], control['top'], control['width'], control['height']):
                control['presses'] += 1
                control['held'] = True
                control['owner'] = owner
        elif control['kind'] == 'slider':
            # The cap or the whole track starts a grab. The cap alone was too small.
            handleLeft, handleTop, handleWidth, handleHeight = sliderHandle(control)
            onHandle = pointInside(x, y, handleLeft, handleTop, handleWidth, handleHeight)
            onTrack = pointInside(x, y, control['left'], control['top'], control['width'], control['height'])
            if onHandle or onTrack:
                control['grabbed'] = True
                control['owner'] = owner
                moveSlider(control, x)


def dragPinch(controls, x, owner):
    for control in controls:
        if control['kind'] == 'slider' and control['grabbed'] and control['owner'] == owner:
            moveSlider(control, x)


def releaseControls(controls, owner):
    for control in controls:
        if control['owner'] != owner:
            continue
        if control['kind'] == 'button':
            control['held'] = False
        elif control['kind'] == 'slider':
            control['grabbed'] = False
        control['owner'] = None


def updateControls(controls, wasPinching, pinching, x, y, owner=0):
    # A button counts on the frame the pinch starts, not on every frame it is held.
    if pinching and not wasPinching:
        beginPinch(controls, x, y, owner)
    elif pinching and wasPinching:
        dragPinch(controls, x, owner)
    elif wasPinching and not pinching:
        releaseControls(controls, owner)
