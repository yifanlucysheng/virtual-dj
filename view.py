"""Drawing only. This file does not change the model."""

import math

from cmu_graphics import *
import pygame

from controls import pointInside, sliderHandle


NIGHT = rgb(14, 14, 16)
GLASS = rgb(32, 34, 38)
GLASS_EDGE = rgb(214, 214, 210)
TRACK = rgb(18, 18, 20)
TEXT = rgb(236, 234, 228)
MUTED = rgb(156, 154, 148)
BUTTON_OFF = rgb(58, 60, 64)
HOVER_FILL = rgb(78, 80, 84)
DECK1 = rgb(186, 154, 112)
DECK2 = rgb(78, 108, 128)
PRESSED = rgb(244, 242, 236)
WARN = rgb(176, 122, 72)
VINYL = rgb(20, 20, 22)
GROOVE = rgb(62, 62, 66)
LABEL_A = rgb(214, 196, 168)
LABEL_B = rgb(168, 186, 196)
THUMB = rgb(196, 122, 72)
INDEX = rgb(120, 156, 176)
HANDLE = rgb(232, 230, 224)

PANEL_RADIUS = 12
BUTTON_RADIUS = 6
BAR_RADIUS = 4
BAR_HEIGHT = 4
CURSOR_RADIUS = 8
HEADER_HEIGHT = 36
PANEL_PAD_X = 16
PANEL_PAD_TOP = 40
PANEL_PAD_BOTTOM = 14
VINYL_RADIUS = 102
TITLE_SIZE = 14
LABEL_SIZE = 11
# 33 1/3 rpm, in degrees per second.
RECORD_DEGREES_PER_SECOND = 200
HINT = 'pinch the song name    a / b: next song    space / enter: play    arrows: crossfader    q: quit'


def drawRoundedRect(left, top, width, height, radius, fill, border=None, borderWidth=0, opacity=100):
    # CMU Graphics has no rounded rect, and it rejects a piece whose width or height is 0.
    if width <= 0 or height <= 0:
        return
    if border and borderWidth > 0:
        drawRoundedRect(
            left - borderWidth,
            top - borderWidth,
            width + 2 * borderWidth,
            height + 2 * borderWidth,
            radius + borderWidth,
            border,
            opacity=opacity,
        )
    radius = min(radius, width / 2, height / 2)
    if radius < 1:
        drawRect(left, top, width, height, fill=fill, opacity=opacity)
        return
    middleHeight = height - 2 * radius
    if middleHeight > 0:
        drawRect(left, top + radius, width, middleHeight, fill=fill, opacity=opacity)
    capWidth = width - 2 * radius
    if capWidth > 0:
        drawRect(left + radius, top, capWidth, radius, fill=fill, opacity=opacity)
        drawRect(left + radius, top + height - radius, capWidth, radius, fill=fill, opacity=opacity)
    drawCircle(left + radius, top + radius, radius, fill=fill, opacity=opacity)
    drawCircle(left + width - radius, top + radius, radius, fill=fill, opacity=opacity)
    if middleHeight > 0:
        drawCircle(left + radius, top + height - radius, radius, fill=fill, opacity=opacity)
        drawCircle(left + width - radius, top + height - radius, radius, fill=fill, opacity=opacity)


def formatTime(samples, sampleRate):
    if sampleRate <= 0:
        wholeSeconds = 0
    else:
        wholeSeconds = int(samples / sampleRate)
    if wholeSeconds < 0:
        wholeSeconds = 0
    minutes = wholeSeconds // 60
    seconds = wholeSeconds % 60
    return f'{minutes:02d}:{seconds:02d}'


def accentFor(index):
    if index == 1:
        return DECK2
    return DECK1


def hoverPointers(app):
    visible = [pointer for pointer in app.pointers if pointer['x'] is not None]
    if visible:
        return visible
    try:
        if pygame.display.get_surface() is None:
            raise RuntimeError('no window')
        mouseX, mouseY = pygame.mouse.get_pos()
    except Exception:
        return []
    return [{'x': mouseX, 'y': mouseY, 'pinching': False}]


def isHovering(control, pointers):
    if control['held'] or not pointers:
        return False
    for pointer in pointers:
        if pointer['pinching'] or pointer['x'] is None:
            continue
        if pointInside(
            pointer['x'], pointer['y'],
            control['left'], control['top'], control['width'], control['height'],
        ):
            return True
    return False


def buttonColors(on, hovering, held, accent):
    if held:
        return PRESSED, NIGHT
    if on:
        text = TEXT if accent == DECK2 else NIGHT
        return accent, text
    if hovering:
        return HOVER_FILL, TEXT
    return BUTTON_OFF, MUTED


def controlBox(controls, names, padTop=PANEL_PAD_TOP, padBottom=PANEL_PAD_BOTTOM):
    chosen = [c for c in controls if c['name'] in names]
    left = min(c['left'] for c in chosen) - PANEL_PAD_X
    top = min(c['top'] for c in chosen) - padTop
    right = max(c['left'] + c['width'] for c in chosen) + PANEL_PAD_X
    bottom = max(c['top'] + c['height'] for c in chosen) + padBottom
    return left, top, right - left, bottom - top


def songReadout(engine, index):
    if engine is None:
        return 0, 0, 1
    audio = engine.decks[index]
    length = min(len(audio.vocals), len(audio.instrumental))
    return audio.position, length, engine.samplerate


def drawHeader(app):
    drawRect(0, 0, app.width, HEADER_HEIGHT, fill=NIGHT, opacity=72)
    drawRect(0, HEADER_HEIGHT - 1, app.width, 1, fill=GLASS_EDGE, opacity=35)
    drawLabel('Air DJ', 20, HEADER_HEIGHT / 2, size=TITLE_SIZE, fill=TEXT, align='left', bold=True)
    drawLabel(app.status, app.width / 2, HEADER_HEIGHT / 2, size=LABEL_SIZE, fill=MUTED)
    drawLabel(f'{app.fps:.0f} fps', app.width - 20, HEADER_HEIGHT / 2, size=LABEL_SIZE, fill=MUTED, align='right')


def drawGlass(left, top, width, height):
    drawRoundedRect(left, top + 3, width, height, PANEL_RADIUS, rgb(0, 0, 0), opacity=22)
    drawRoundedRect(left, top, width, height, PANEL_RADIUS, GLASS_EDGE, opacity=36)
    if width > 2 and height > 2:
        drawRoundedRect(
            left + 1, top + 1, width - 2, height - 2,
            max(1, PANEL_RADIUS - 1), GLASS, opacity=74,
        )
    sheen = width - 28
    if sheen > 0:
        drawRect(left + 14, top + 1, sheen, 1, fill=rgb(255, 255, 255), opacity=50)


def recordDegrees(position, sampleRate):
    # Read from the playhead. A paused song stays still, and nothing is stored on app.
    if sampleRate <= 0:
        return 0
    seconds = position / sampleRate
    return (seconds * RECORD_DEGREES_PER_SECOND) % 360


def drawVinyl(centerX, centerY, radius, degrees, labelFill):
    drawCircle(centerX, centerY + 5, radius + 6, fill=rgb(0, 0, 0), opacity=28)
    drawCircle(centerX, centerY, radius, fill=VINYL)
    for fraction in (0.9, 0.76, 0.62, 0.5):
        drawCircle(centerX, centerY, radius * fraction, fill=None, border=GROOVE, borderWidth=1)
    labelRadius = radius * 0.34
    drawCircle(centerX, centerY, labelRadius, fill=labelFill)
    radians = math.radians(degrees)
    inner = labelRadius * 0.35
    outer = labelRadius * 0.78
    drawLine(
        centerX + math.cos(radians) * inner,
        centerY + math.sin(radians) * inner,
        centerX + math.cos(radians) * outer,
        centerY + math.sin(radians) * outer,
        fill=NIGHT,
        lineWidth=2,
    )
    drawCircle(centerX, centerY, 4, fill=NIGHT)


def drawProgress(left, top, width, position, length, sampleRate, accent):
    drawRoundedRect(left, top, width, BAR_HEIGHT, BAR_RADIUS, TRACK)
    if length > 0:
        filled = width * position / length
        if filled > width:
            filled = width
        if filled > 1:
            drawRoundedRect(left, top, filled, BAR_HEIGHT, BAR_RADIUS, accent)
    clock = f'{formatTime(position, sampleRate)} / {formatTime(length, sampleRate)}'
    drawLabel(clock, left + width, top - 14, size=LABEL_SIZE, fill=MUTED, align='right')


def drawPad(control, label, on, hovering, accent):
    fill, textFill = buttonColors(on, hovering, control['held'], accent)
    drawRoundedRect(
        control['left'], control['top'], control['width'], control['height'],
        BUTTON_RADIUS, fill,
    )
    drawLabel(
        label,
        control['left'] + control['width'] / 2,
        control['top'] + control['height'] / 2,
        size=LABEL_SIZE, fill=textFill, bold=True,
    )


def shortTitle(name, limit=24):
    if len(name) <= limit:
        return name
    return name[:limit - 1].rstrip() + '…'


def drawSongButton(control, name, broken, hovering, accent):
    hasSong = name != 'No song' and not broken
    fill, textFill = buttonColors(hasSong, hovering, control['held'], accent)
    if broken and not control['held']:
        textFill = WARN
    drawRoundedRect(
        control['left'], control['top'], control['width'], control['height'],
        BUTTON_RADIUS, fill,
    )
    midY = control['top'] + control['height'] / 2
    drawLabel(
        shortTitle(name),
        control['left'] + 12,
        midY,
        size=LABEL_SIZE, fill=textFill, align='left', bold=True,
    )
    drawLabel(
        'next',
        control['left'] + control['width'] - 12,
        midY,
        size=LABEL_SIZE, fill=textFill, align='right',
    )


def drawPlayButton(control, playing, hovering, accent):
    drawPad(control, 'Pause' if playing else 'Play', playing, hovering, accent)


def drawSlider(control, accent, pointers):
    left = control['left']
    top = control['top']
    width = control['width']
    height = control['height']
    drawRoundedRect(left, top, width, height, height / 2, TRACK)
    if control['name'] == 'crossfader':
        tick = height - 12
        if tick > 0:
            drawRect(left + width / 2 - 1, top + 6, 2, tick, fill=GLASS_EDGE, opacity=45)
        drawLabel('A', left, top - 12, size=LABEL_SIZE, fill=DECK1, align='left')
        drawLabel('B', left + width, top - 12, size=LABEL_SIZE, fill=DECK2, align='right')
    else:
        filled = width * control['value']
        if filled > 1:
            drawRoundedRect(left, top, filled, height, height / 2, accent, opacity=80)
        drawLabel('Volume', left, top - 12, size=LABEL_SIZE, fill=MUTED, align='left')
    handleLeft, handleTop, handleWidth, handleHeight = sliderHandle(control)
    hovering = False
    if not control['grabbed']:
        for pointer in pointers:
            if pointer['x'] is None or pointer['pinching']:
                continue
            onHandle = pointInside(pointer['x'], pointer['y'], handleLeft, handleTop, handleWidth, handleHeight)
            onTrack = pointInside(pointer['x'], pointer['y'], left, top, width, height)
            if onHandle or onTrack:
                hovering = True
    cap = HANDLE if not control['grabbed'] else PRESSED
    if hovering and not control['grabbed']:
        cap = rgb(255, 255, 255)
    drawRoundedRect(handleLeft, handleTop, handleWidth, handleHeight, handleWidth / 2, cap)
    notchTop = handleTop + handleHeight / 2 - 6
    drawRect(handleLeft + handleWidth / 2 - 1, notchTop, 2, 12, fill=NIGHT, opacity=40)


def drawDeck(app, index, pointers, engine):
    prefix = 'deck1' if index == 0 else 'deck2'
    names = (
        f'{prefix}-song', f'{prefix}-play', f'{prefix}-vocals',
        f'{prefix}-instr', f'{prefix}-volume',
    )
    left, top, width, height = controlBox(app.controls, names)
    accent = accentFor(index)
    deck = app.decks[index]
    position, length, sampleRate = songReadout(engine, index)
    labelFill = LABEL_B if index == 1 else LABEL_A
    drawVinyl(
        left + width / 2,
        top - VINYL_RADIUS - 12,
        VINYL_RADIUS,
        recordDegrees(position, sampleRate),
        labelFill,
    )
    drawGlass(left, top, width, height)

    songButton = None
    for control in app.controls:
        if control['name'] == f'{prefix}-song':
            songButton = control
    barLeft = left + PANEL_PAD_X
    barWidth = width - 2 * PANEL_PAD_X
    barTop = songButton['top'] - 12
    titleColor = WARN if deck['loadError'] else TEXT
    drawLabel(deck['name'], barLeft, barTop - 14, size=LABEL_SIZE, fill=titleColor, align='left', bold=True)
    drawProgress(barLeft, barTop, barWidth, position, length, sampleRate, accent)

    for control in app.controls:
        if not control['name'].startswith(prefix):
            continue
        if control['kind'] == 'slider':
            drawSlider(control, accent, pointers)
            continue
        hovering = isHovering(control, pointers)
        if control['name'].endswith('song'):
            drawSongButton(control, deck['songName'], deck['loadError'] is not None, hovering, accent)
        elif control['name'].endswith('play'):
            drawPlayButton(control, deck['playing'], hovering, accent)
        elif control['name'].endswith('vocals'):
            drawPad(control, 'Vocals', deck['vocalsOn'], hovering, accent)
        elif control['name'].endswith('instr'):
            drawPad(control, 'Inst', deck['instrumentalOn'], hovering, accent)


def drawCrossfader(app, pointers):
    for control in app.controls:
        if control['name'] == 'crossfader':
            drawSlider(control, PRESSED, pointers)


def drawPointers(app):
    for index, pointer in enumerate(app.pointers):
        if pointer['thumbX'] is not None:
            drawCircle(pointer['thumbX'], pointer['thumbY'], 12, fill=THUMB, opacity=30)
            drawCircle(pointer['thumbX'], pointer['thumbY'], 8, fill=THUMB, border=TEXT, borderWidth=2)
        if pointer['indexX'] is not None:
            drawCircle(pointer['indexX'], pointer['indexY'], 12, fill=INDEX, opacity=30)
            drawCircle(pointer['indexX'], pointer['indexY'], 8, fill=INDEX, border=TEXT, borderWidth=2)
        if pointer['x'] is None:
            continue
        color = accentFor(index)
        drawCircle(pointer['x'], pointer['y'], CURSOR_RADIUS + 10, fill=color, opacity=16)
        drawCircle(pointer['x'], pointer['y'], CURSOR_RADIUS + 5, fill=color, opacity=32)
        if pointer['pinching']:
            drawCircle(pointer['x'], pointer['y'], CURSOR_RADIUS, fill=color, border=PRESSED, borderWidth=2)
        else:
            drawCircle(pointer['x'], pointer['y'], CURSOR_RADIUS, fill=None, border=color, borderWidth=2)


def drawAll(app, cameraPicture, engine):
    drawRect(0, 0, app.width, app.height, fill=NIGHT)
    if app.showCameraImage and cameraPicture is not None:
        drawImage(
            cameraPicture,
            app.pictureLeft,
            app.pictureTop,
            width=app.pictureWidth,
            height=app.pictureHeight,
        )

    drawHeader(app)
    drawLabel(HINT, app.width / 2, HEADER_HEIGHT + 14, size=LABEL_SIZE, fill=MUTED)
    pointers = hoverPointers(app)
    drawDeck(app, 0, pointers, engine)
    drawDeck(app, 1, pointers, engine)
    drawCrossfader(app, pointers)
    drawPointers(app)
