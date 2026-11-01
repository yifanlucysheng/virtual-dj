"""
Model: app.decks, app.songs, app.crossfader, two pointers, and the controls.
View: redrawAll only reads those and draws.
Controller: onStep, the mouse, and the keyboard.

Keys: a and b pick the next song, space plays deck 1, enter plays deck 2,
left and right move the crossfader, q quits.
"""

import os
import sys

# These four have to be set before cmu_graphics and MediaPipe are imported.
os.environ['CI'] = '1'
os.environ['SDL_MAC_BACKGROUND_APP'] = '0'  # a Terminal process otherwise only bounces the Dock
os.environ['MPLBACKEND'] = 'Agg'  # matplotlib must not open its own Mac window
os.environ['MEDIAPIPE_DISABLE_GPU'] = '1'


def relaunchWithPythonw():
    if sys.platform != 'darwin':
        return
    if os.environ.get('AIR_DJ_FOREGROUND') == '1':
        return
    folder = os.path.dirname(sys.executable)
    candidates = [
        os.path.join(folder, 'pythonw'),
        os.path.join(folder, 'pythonw3.12'),
        '/Library/Frameworks/Python.framework/Versions/3.12/bin/pythonw',
    ]
    for pythonw in candidates:
        if os.path.isfile(pythonw) and os.access(pythonw, os.X_OK):
            print('Opening through pythonw so macOS will show the window.')
            os.environ['AIR_DJ_FOREGROUND'] = '1'
            os.execv(pythonw, [pythonw, *sys.argv])
            return


relaunchWithPythonw()

import math
import random
import time

try:
    import numpy as np
    import sounddevice as sd
    import soundfile as sf
except Exception as error:
    np = None
    sd = None
    sf = None
    audioImportError = error
else:
    audioImportError = None

from cmu_graphics import *
import pygame

from cmu_graphics.shape_logic import activeDrawing


# Pinch and cursor math.

# On below a quarter of the hand. Off only after the gap grows past 0.35.
PINCH_ON_BELOW = 0.25
PINCH_OFF_ABOVE = 0.35
# 0.4 means 40% of the new spot and 60% of where the cursor already was.
CURSOR_NEW_WEIGHT = 0.4

WRIST = 0
THUMB_TIP = 4
INDEX_TIP = 8
MIDDLE_KNUCKLE = 9


def xy(landmark):
    if hasattr(landmark, 'x'):
        return (landmark.x, landmark.y)
    return (landmark[0], landmark[1])


def distance(pointA, pointB):
    ax, ay = pointA
    bx, by = pointB
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def pinchDistance(landmarks):
    gap = distance(xy(landmarks[THUMB_TIP]), xy(landmarks[INDEX_TIP]))
    handSize = distance(xy(landmarks[WRIST]), xy(landmarks[MIDDLE_KNUCKLE]))
    if handSize == 0:
        return None
    return gap / handSize


def nextPinch(wasPinching, landmarks):
    # Between 0.25 and 0.35, keep the previous answer so a wobble does not flicker.
    ratio = pinchDistance(landmarks)
    if ratio is None:
        return False
    if wasPinching:
        return ratio <= PINCH_OFF_ABOVE
    return ratio < PINCH_ON_BELOW


def fingertipMidpoint(landmarks):
    thumbX, thumbY = xy(landmarks[THUMB_TIP])
    indexX, indexY = xy(landmarks[INDEX_TIP])
    return ((thumbX + indexX) / 2, (thumbY + indexY) / 2)


def pairHands(previous, newcomers):
    # Each pointer keeps the hand closest to where it already was.
    assigned = [None] * len(previous)
    usedHands = set()

    pairs = []
    for pointerIndex, old in enumerate(previous):
        if old is None:
            continue
        for handIndex, new in enumerate(newcomers):
            pairs.append((distance(old, new), pointerIndex, handIndex))
    pairs.sort()
    for gap, pointerIndex, handIndex in pairs:
        if assigned[pointerIndex] is not None or handIndex in usedHands:
            continue
        assigned[pointerIndex] = handIndex
        usedHands.add(handIndex)

    leftovers = sorted(
        [handIndex for handIndex in range(len(newcomers)) if handIndex not in usedHands],
        key=lambda handIndex: newcomers[handIndex][0],
    )
    for handIndex in leftovers:
        for pointerIndex in range(len(assigned)):
            if assigned[pointerIndex] is None:
                assigned[pointerIndex] = handIndex
                break
    return assigned


def smoothCursor(oldCursor, newCursor, weight=CURSOR_NEW_WEIGHT):
    if oldCursor is None:
        return newCursor
    oldX, oldY = oldCursor
    newX, newY = newCursor
    x = weight * newX + (1 - weight) * oldX
    y = weight * newY + (1 - weight) * oldY
    return (x, y)

# Buttons and sliders. Releasing one hand does not drop the other hand.

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

# Deck values, song list, and keyboard.

# Used only when the songs folder has no vocals/instrumental pair.
SONG_PATHS = [
    ('songs/track1_vocals.wav', 'songs/track1_instr.wav'),
    ('songs/track2_vocals.wav', 'songs/track2_instr.wav'),
]

AUDIO_SUFFIXES = ('.wav', '.aiff', '.aif', '.flac', '.ogg')
CROSSFADER_STEP = 0.05

BUTTONS = {
    'deck1-play': ('play', 0),
    'deck1-vocals': ('vocalsOn', 0),
    'deck1-instr': ('instrumentalOn', 0),
    'deck1-song': ('song', 0),
    'deck2-play': ('play', 1),
    'deck2-vocals': ('vocalsOn', 1),
    'deck2-instr': ('instrumentalOn', 1),
    'deck2-song': ('song', 1),
}


def makeDeck(name):
    return {
        'name': name,
        'playing': False,
        'volume': 0.8,
        'vocalsOn': True,
        'instrumentalOn': True,
        'loadError': None,
        'heardPlaying': False,
        # songIndex is the row we want. loadedIndex is the row already in the engine.
        'songIndex': 0,
        'songName': 'No song',
        'loadedIndex': -1,
    }


def makeControls(width, height):
    deckWidth = 316
    margin = 28
    songHeight = 32
    playHeight = 40
    volumeHeight = 26
    crossHeight = 32
    # The fader cap hangs 18 pixels past the track. Leave room for that.
    crossTop = height - 16 - 18 - crossHeight
    volumeTop = crossTop - 44 - volumeHeight
    playTop = volumeTop - 16 - playHeight
    songTop = playTop - 18 - songHeight
    left = margin
    right = width - margin - deckWidth
    return [
        makeButton('deck1-song', left, songTop, deckWidth, songHeight),
        makeButton('deck1-play', left, playTop, 104, playHeight),
        makeButton('deck1-vocals', left + 112, playTop, 98, playHeight),
        makeButton('deck1-instr', left + 218, playTop, 98, playHeight),
        makeSlider('deck1-volume', left, volumeTop, deckWidth, volumeHeight, 0.8),
        makeButton('deck2-song', right, songTop, deckWidth, songHeight),
        makeButton('deck2-play', right, playTop, 104, playHeight),
        makeButton('deck2-vocals', right + 112, playTop, 98, playHeight),
        makeButton('deck2-instr', right + 218, playTop, 98, playHeight),
        makeSlider('deck2-volume', right, volumeTop, deckWidth, volumeHeight, 0.8),
        makeSlider('crossfader', 80, crossTop, width - 160, crossHeight, 0.5),
    ]


def songFileKind(filename):
    stem = os.path.splitext(filename)[0].lower()
    if 'vocal' in stem:
        return 'vocals'
    if 'instr' in stem:
        return 'instrumental'
    return None


def songGroupKey(filename):
    stem = os.path.splitext(filename)[0].lower()
    for word in ('instrumental', 'vocals', 'vocal', 'instr'):
        stem = stem.replace(word, '')
    return stem.strip(' _-.')


def songDisplayName(folder, dirpath, key):
    if os.path.abspath(dirpath) != os.path.abspath(folder) and os.path.basename(dirpath):
        return os.path.basename(dirpath)
    if key:
        return key.replace('_', ' ').replace('-', ' ').strip()
    return 'Song'


def findSongs(folder='songs'):
    # A pair is two files in one folder whose names match once "vocal" and "instr" are removed.
    if not os.path.isdir(folder):
        return []
    grouped = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        for name in sorted(filenames):
            if name.startswith('.'):
                continue
            if not name.lower().endswith(AUDIO_SUFFIXES):
                continue
            kind = songFileKind(name)
            if kind is None:
                continue
            key = songGroupKey(name)
            slot = grouped.setdefault((dirpath, key), {})
            slot[kind] = os.path.join(dirpath, name)
    songs = []
    for (dirpath, key), slot in grouped.items():
        if 'vocals' in slot and 'instrumental' in slot:
            songs.append({
                'name': songDisplayName(folder, dirpath, key),
                'vocals': slot['vocals'],
                'instrumental': slot['instrumental'],
            })
    byFolder = {}
    for (dirpath, key), slot in grouped.items():
        byFolder.setdefault(dirpath, []).append(slot)
    already = {(song['vocals'], song['instrumental']) for song in songs}
    for dirpath, slots in byFolder.items():
        vocals = [slot['vocals'] for slot in slots if 'vocals' in slot and 'instrumental' not in slot]
        instrumental = [
            slot['instrumental'] for slot in slots
            if 'instrumental' in slot and 'vocals' not in slot
        ]
        if len(vocals) == 1 and len(instrumental) == 1:
            pair = (vocals[0], instrumental[0])
            if pair not in already:
                songs.append({
                    'name': songDisplayName(folder, dirpath, ''),
                    'vocals': vocals[0],
                    'instrumental': instrumental[0],
                })
    songs.sort(key=lambda song: song['name'].lower())
    return songs


def assignSongs(decks, songs):
    if not songs:
        return
    for index, deck in enumerate(decks):
        choice = index if index < len(songs) else 0
        deck['songIndex'] = choice
        deck['songName'] = songs[choice]['name']


def chooseNextSong(deck, songs):
    if not songs:
        print(f"{deck['name']}: no songs found in the songs folder.")
        return
    deck['songIndex'] = (deck['songIndex'] + 1) % len(songs)
    deck['songName'] = songs[deck['songIndex']]['name']
    print(f"{deck['name']}: {deck['songName']}")


def loadSelectedSongs(engine, decks, songs):
    if engine is None or not songs:
        return
    for index, deck in enumerate(decks):
        if deck['loadedIndex'] == deck['songIndex']:
            continue
        song = songs[deck['songIndex'] % len(songs)]
        previous = deck['loadedIndex']
        try:
            engine.load(index, song['vocals'], song['instrumental'])
        except Exception as error:
            print(f"{deck['name']}: could not open {song['name']} ({error}).")
            if previous >= 0:
                deck['songIndex'] = previous
                deck['songName'] = songs[previous]['name']
                print(f"{deck['name']}: staying on {deck['songName']}.")
            else:
                deck['loadError'] = 'No song file'
                deck['songName'] = song['name']
                deck['loadedIndex'] = deck['songIndex']
            continue
        deck['loadError'] = None
        deck['playing'] = False
        deck['heardPlaying'] = False
        deck['loadedIndex'] = deck['songIndex']
        deck['songName'] = song['name']
        print(f"{deck['name']}: loaded {song['name']}.")


def togglePlay(deck):
    if deck['loadError'] is not None:
        print(f"{deck['name']}: no song file, so play does nothing.")
        return
    deck['playing'] = not deck['playing']


def applyControls(decks, crossfader, controls, songs=None):
    for control in controls:
        name = control['name']
        if control['kind'] == 'slider':
            if name == 'deck1-volume':
                decks[0]['volume'] = control['value']
            elif name == 'deck2-volume':
                decks[1]['volume'] = control['value']
            elif name == 'crossfader':
                crossfader = control['value']
        elif control['kind'] == 'button':
            # presses goes up once per pinch. seenPresses skips a pinch we already applied.
            if control['presses'] == control['seenPresses']:
                continue
            control['seenPresses'] = control['presses']
            action, index = BUTTONS[name]
            if action == 'song':
                chooseNextSong(decks[index], songs or [])
            elif action == 'play':
                togglePlay(decks[index])
            else:
                decks[index][action] = not decks[index][action]
    return crossfader


def nudgeCrossfader(controls, step):
    for control in controls:
        if control['name'] == 'crossfader':
            control['value'] = clamp01(control['value'] + step)
            return control['value']
    return None


def handleKey(decks, controls, key, songs=None):
    if key == 'space':
        togglePlay(decks[0])
    elif key == 'enter':
        togglePlay(decks[1])
    elif key == 'left':
        nudgeCrossfader(controls, -CROSSFADER_STEP)
    elif key == 'right':
        nudgeCrossfader(controls, CROSSFADER_STEP)
    elif key == 'a':
        chooseNextSong(decks[0], songs or [])
    elif key == 'b':
        chooseNextSong(decks[1], songs or [])
    elif key == 'q':
        return True
    return False


def loadDeckFiles(engine, decks, paths):
    for index, deck in enumerate(decks):
        vocalsPath, instrumentalPath = paths[index]
        missing = [
            path for path in (vocalsPath, instrumentalPath) if not os.path.isfile(path)
        ]
        if missing:
            names = ', '.join(missing)
            print(f"{deck['name']}: could not find {names}. This deck stays quiet.")
            deck['loadError'] = 'No song file'
            continue
        try:
            engine.load(index, vocalsPath, instrumentalPath)
            print(f"{deck['name']}: loaded {vocalsPath} and {instrumentalPath}.")
        except Exception as error:
            print(f"{deck['name']}: could not open the song ({error}). This deck stays quiet.")
            deck['loadError'] = 'No song file'


def syncEngine(engine, decks, crossfader):
    if engine is None:
        return
    engine.crossfader = crossfader
    for index, deck in enumerate(decks):
        audio = engine.decks[index]
        length = min(len(audio.vocals), len(audio.instrumental))
        wasPlaying = deck['heardPlaying']
        # The callback clears playing at the last sample. Put the button back to Play.
        songEnded = (
            wasPlaying
            and not audio.playing
            and length > 0
            and audio.position >= length
        )
        if songEnded:
            deck['playing'] = False
        if deck['playing'] and not wasPlaying and audio.position >= length:
            audio.position = 0
        playing = deck['playing'] and deck['loadError'] is None and length > 0
        audio.playing = playing
        audio.volume = deck['volume']
        audio.vocalsOn = deck['vocalsOn']
        audio.instrumentalOn = deck['instrumentalOn']
        deck['heardPlaying'] = playing

# Four tracks and the speaker callback.

def toMono(samples):
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    return np.ascontiguousarray(samples)


class Deck:
    def __init__(self):
        self.playing = False
        self.position = 0
        self.volume = 0.8
        self.vocalsOn = True
        self.instrumentalOn = True
        self.vocals = np.zeros(0, dtype=np.float32)
        self.instrumental = np.zeros(0, dtype=np.float32)


class AudioEngine:
    def __init__(self, samplerate=44100, blocksize=1024):
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.decks = [Deck(), Deck()]
        self.crossfader = 0.5
        self.loudness = 0.0
        # Reused every callback so the audio thread does not build a new array.
        self._mix = np.zeros(blocksize, dtype=np.float32)
        self._stream = None

    def load(self, index, vocalsPath, instrumentalPath):
        deck = self.decks[index]
        deck.playing = False
        vocals, vocalsRate = sf.read(vocalsPath, dtype='float32')
        instrumental, instrumentalRate = sf.read(instrumentalPath, dtype='float32')
        if vocalsRate != self.samplerate or instrumentalRate != self.samplerate:
            raise ValueError('wav sample rate must match the engine')
        deck.vocals = toMono(vocals)
        deck.instrumental = toMono(instrumental)
        deck.position = 0

    def gains(self):
        # Equal power: cos^2 + sin^2 is 1, so the middle is not louder than the ends.
        faded = self.crossfader
        if faded < 0.0:
            faded = 0.0
        elif faded > 1.0:
            faded = 1.0
        angle = faded * (math.pi / 2)
        return math.cos(angle), math.sin(angle)

    def render(self, frames):
        mix = self._mix[:frames]
        mix.fill(0.0)
        deck1Gain, deck2Gain = self.gains()
        self._addDeck(self.decks[0], deck1Gain, frames)
        self._addDeck(self.decks[1], deck2Gain, frames)
        np.clip(mix, -1.0, 1.0, out=mix)
        
        return mix

    def _addDeck(self, deck, gain, frames):
        if not deck.playing:
            return
        start = deck.position
        length = min(len(deck.vocals), len(deck.instrumental))
        count = min(frames, length - start)
        if count <= 0:
            deck.playing = False
            return
        # A faded-out deck still moves forward, so the song does not pause.
        if gain != 0.0:
            level = deck.volume * gain
            if deck.vocalsOn:
                self._mix[:count] += deck.vocals[start:start + count] * level
            if deck.instrumentalOn:
                self._mix[:count] += deck.instrumental[start:start + count] * level
        deck.position = start + count
        if deck.position >= length:
            deck.playing = False

    def _callback(self, outdata, frames, timeInfo, status):
        if frames > len(self._mix):
            outdata.fill(0.0)
            return
        mix = self.render(frames)
        outdata[:, 0] = mix
        outdata[:, 1] = mix

    def loudnessNow(self):
        stream = self._stream
        return self.knobLoudness()

    def knobLoudness(self):
        deck1Gain, deck2Gain = self.gains()
        level = 0.0
        for deck, gain in ((self.decks[0], deck1Gain), (self.decks[1], deck2Gain)):
            if not deck.playing:
                continue
            stems = int(deck.vocalsOn) + int(deck.instrumentalOn)
            level += deck.volume * gain * stems * 0.5
        if level > 1.0:
            return 1.0
        if level < 0.0:
            return 0.0
        return level

    def start(self):
        self._stream = sd.OutputStream(
            samplerate=self.samplerate,
            channels=2,
            dtype='float32',
            blocksize=self.blocksize,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


# Drawing only.

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

# Window, camera, and timer.

OPENCV_PIN = '4.12.0.88'
TARGET_FPS = 30
MAX_FRAME_WIDTH = 640
DOT_STATUS = 'One pointer on each hand. Pinch thumb to index.'

# Not app variables: hashing a camera frame or the samples every redraw is too slow,
# and the speaker thread writes the samples.
camera = None
hands = None
cameraPicture = None
engine = None
cv2 = None
mp = None
pilImage = None
windowShown = False
cameraReady = False


def onAppStart(app):
    app.stepsPerSecond = TARGET_FPS
    app.background = 'black'
    app.title = 'Air DJ Mini'

    # Pointer 0 is brass, pointer 1 is slate. None means that hand is gone.
    app.pointers = [blankPointer(), blankPointer()]

    app.pictureLeft = 0
    app.pictureTop = 0
    app.pictureWidth = app.width
    app.pictureHeight = app.height

    app.decks = [makeDeck('Deck 1'), makeDeck('Deck 2')]
    app.songs = findSongs('songs')
    assignSongs(app.decks, app.songs)
    if app.songs:
        print(f"Found {len(app.songs)} song(s) in the songs folder.")
    else:
        print('No song pairs in the songs folder. Trying the two default tracks.')
    app.crossfader = 0.5
    app.controls = makeControls(app.width, app.height)
    app.saidNoHand = False
    # 0 draws the window. 1 loads speakers and the camera after that paint.
    app.startupStep = 0

    app.fps = 0
    app.stepsThisSecond = 0
    app.secondStarted = time.time()
    app.cameraErrorPrinted = False
    app.cameraOk = False
    app.showCameraImage = True
    app.status = 'Opening the window...'
    print(f'Python {sys.version.split()[0]} ({sys.platform}).')
    print('Any Python 3.12 uses the same library builds. 3.12.10 matches this project.')
    if sys.version_info[:2] != (3, 12):
        print('This project was set up for Python 3.12. Run it with python3.12 main.py.')
    print('Starting the Air DJ Mini window.')
    becomeMacForegroundApp()


def becomeMacForegroundApp():
    if sys.platform != 'darwin':
        return
    try:
        import ctypes
        services = ctypes.cdll.LoadLibrary(
            '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices'
        )

        class ProcessSerialNumber(ctypes.Structure):
            _fields_ = [
                ('highLongOfPSN', ctypes.c_ulong),
                ('lowLongOfPSN', ctypes.c_ulong),
            ]

        # 2 is "this process." 1 is "become a normal foreground app."
        psn = ProcessSerialNumber(0, 2)
        services.TransformProcessType.argtypes = [
            ctypes.POINTER(ProcessSerialNumber),
            ctypes.c_uint32,
        ]
        services.TransformProcessType.restype = ctypes.c_int32
        services.TransformProcessType(ctypes.byref(psn), 1)
    except Exception as error:
        print('Could not mark this as a Mac app with a window.')
        print(error)


def bringWindowForward():
    global windowShown
    if windowShown:
        return
    windowShown = True
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            window = pygame.Window.from_display_module()
        window.title = 'Air DJ Mini'
        window.show()
    except Exception:
        pass
    print('Air DJ Mini window is open. Look for that title, not the Terminal.')


def installedVersion(distName):
    import importlib.metadata as metadata
    try:
        return metadata.version(distName)
    except metadata.PackageNotFoundError:
        return None


def packageContainsSdl(packageName):
    import importlib.util
    spec = importlib.util.find_spec(packageName)
    if spec is None or not spec.submodule_search_locations:
        return False
    root = spec.submodule_search_locations[0]
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            if 'sdl' in name.lower():
                return True
    return False


def cameraLibrariesAreSafe():
    # OpenCV 5 ships a second SDL, which fights pygame and the window never stays open.
    opencv = installedVersion('opencv-python')
    contrib = installedVersion('opencv-contrib-python')
    if opencv != OPENCV_PIN or contrib != OPENCV_PIN:
        print(f'Found opencv-python {opencv}, opencv-contrib-python {contrib}.')
        return False
    if packageContainsSdl('cv2'):
        print('The installed cv2 folder contains its own SDL library.')
        return False
    return True


def ensureCamera(app):
    global camera, hands, cameraReady, cv2, mp
    if cameraReady:
        return
    cameraReady = True

    if not cameraLibrariesAreSafe():
        app.showCameraImage = False
        app.cameraOk = False
        app.status = 'Camera library would hide this window. See the terminal.'
        print('OpenCV must be 4.12.0.88, with no SDL of its own.')
        print('From the air-dj-mini folder, run:')
        print('python3.12 -m pip install -r requirements.txt')
        return

    import cv2 as cv2Module
    import mediapipe as mpModule
    cv2 = cv2Module
    mp = mpModule

    if not hasattr(mp, 'solutions'):
        app.showCameraImage = False
        app.status = 'Install mediapipe 0.10.14 (it has mp.solutions.hands).'
        return

    camera = openCamera()
    app.cameraOk = camera is not None
    if not app.cameraOk:
        app.showCameraImage = False
        app.status = 'No webcam found. Plug one in, then run the file again.'
        print('No webcam found. You can still play with the keyboard.')
        return

    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    app.status = DOT_STATUS
    hands = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    print('Camera is on.')


def onStep(app):
    bringWindowForward()
    if app.startupStep == 0:
        app.startupStep = 1
        app.status = 'Window is open.'
        updateFps(app, time.time())
        return
    if app.startupStep == 1:
        app.startupStep = 2
        print('Window is up. Loading speakers and camera next.')
        print('No speakers, or no camera, still leaves this window open.')
        try:
            openAudio(app)
        except Exception as error:
            print('Speakers could not start. The window stays open.')
            print(error)
        try:
            ensureCamera(app)
        except Exception as error:
            app.showCameraImage = False
            app.cameraOk = False
            app.status = 'Camera did not start. Keyboard still works.'
            print('Camera did not start. The window stays open.')
            print(error)
        updateFps(app, time.time())
        return
    rgb = readOneFrame(app)
    found = []
    if rgb is None:
        forgetCameraPicture()
    else:
        rememberPictureRect(app, rgb)
        try:
            found = findHands(rgb)
        except Exception as error:
            found = []
            if not app.saidNoHand:
                print('Could not read a hand from this frame. The app will keep running.')
                print(error)
                app.saidNoHand = True
        if not found and not app.saidNoHand:
            print('No hand in view. Pinch when a hand shows up, or use the keyboard.')
            app.saidNoHand = True
        if app.showCameraImage:
            storeCameraPicture(rgb)
        else:
            forgetCameraPicture()
    updatePointers(app, found)
    sendModelToSpeakers(app)
    updateFps(app, time.time())


def onMousePress(app, mouseX, mouseY):
    pointer = app.pointers[0]
    wasPinching = pointer['pinching']
    pointer['x'] = mouseX
    pointer['y'] = mouseY
    pointer['pinching'] = True
    updateControls(app.controls, wasPinching, True, mouseX, mouseY, owner=0)
    sendModelToSpeakers(app)


def onMouseDrag(app, mouseX, mouseY):
    pointer = app.pointers[0]
    pointer['x'] = mouseX
    pointer['y'] = mouseY
    pointer['pinching'] = True
    updateControls(app.controls, True, True, mouseX, mouseY, owner=0)
    sendModelToSpeakers(app)


def onMouseRelease(app, mouseX, mouseY):
    pointer = app.pointers[0]
    pointer['x'] = mouseX
    pointer['y'] = mouseY
    wasPinching = pointer['pinching']
    pointer['pinching'] = False
    updateControls(app.controls, wasPinching, False, mouseX, mouseY, owner=0)
    sendModelToSpeakers(app)


def onKeyPress(app, key):
    if handleKey(app.decks, app.controls, key, app.songs):
        app.quit()
        return
    sendModelToSpeakers(app)


def openAudio(app):
    global engine
    if audioImportError is not None:
        print('Speakers could not be loaded. The window stays open.')
        print(audioImportError)
        engine = None
        return
    engine = AudioEngine()
    if app.songs:
        loadSelectedSongs(engine, app.decks, app.songs)
    else:
        loadDeckFiles(engine, app.decks, SONG_PATHS)
    try:
        engine.start()
        print('Speakers are on.')
    except Exception as error:
        print('No speakers found. The window stays open, and the decks stay quiet.')
        print(error)


def sendModelToSpeakers(app):
    global engine
    app.crossfader = applyControls(app.decks, app.crossfader, app.controls, app.songs)
    loadSelectedSongs(engine, app.decks, app.songs)
    syncEngine(engine, app.decks, app.crossfader)


def fitInside(frameWidth, frameHeight, windowWidth, windowHeight):
    if frameWidth == 0 or frameHeight == 0:
        return 0, 0, windowWidth, windowHeight
    scale = min(windowWidth / frameWidth, windowHeight / frameHeight)
    drawWidth = frameWidth * scale
    drawHeight = frameHeight * scale
    left = (windowWidth - drawWidth) / 2
    top = (windowHeight - drawHeight) / 2
    return left, top, drawWidth, drawHeight


def rememberPictureRect(app, rgb):
    frameHeight, frameWidth = rgb.shape[:2]
    left, top, width, height = fitInside(
        frameWidth, frameHeight, app.width, app.height
    )
    app.pictureLeft = left
    app.pictureTop = top
    app.pictureWidth = width
    app.pictureHeight = height


def openCamera():
    if sys.platform == 'darwin':
        for index in (0, 1):
            cam = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
            if cam.isOpened():
                return cam
            cam.release()
    cam = cv2.VideoCapture(0)
    if cam.isOpened():
        return cam
    cam.release()
    return None


def shrinkFrame(frame):
    height, width = frame.shape[:2]
    if width <= MAX_FRAME_WIDTH:
        return frame
    newHeight = max(1, int(height * (MAX_FRAME_WIDTH / width)))
    return cv2.resize(frame, (MAX_FRAME_WIDTH, newHeight))


def readOneFrame(app):
    if cv2 is None or not app.cameraOk or camera is None:
        return None

    try:
        ok, frame = camera.read()
    except Exception as error:
        if not app.cameraErrorPrinted:
            print('The camera stopped sending frames. The app will keep running.')
            print(error)
            app.cameraErrorPrinted = True
        return None
    if not ok or frame is None:
        return None

    # Flip before MediaPipe, or the dots land on the wrong side of the hand.
    frame = cv2.flip(frame, 1)
    frame = shrinkFrame(frame)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def blankPointer():
    return {
        'x': None,
        'y': None,
        'pinching': False,
        'thumbX': None,
        'thumbY': None,
        'indexX': None,
        'indexY': None,
    }


def clearPointer(pointer):
    pointer['x'] = None
    pointer['y'] = None
    pointer['pinching'] = False
    pointer['thumbX'] = None
    pointer['thumbY'] = None
    pointer['indexX'] = None
    pointer['indexY'] = None


def findHands(rgb):
    if hands is None:
        return []

    rgb.flags.writeable = False
    results = hands.process(rgb)
    rgb.flags.writeable = True

    if not results.multi_hand_landmarks:
        return []
    return [hand.landmark for hand in results.multi_hand_landmarks][:2]


def landmarkToPixel(app, landmark):
    # Landmark x and y are fractions from 0 to 1, placed inside the camera rectangle.
    fractionX, fractionY = xy(landmark)
    x = app.pictureLeft + fractionX * app.pictureWidth
    y = app.pictureTop + fractionY * app.pictureHeight
    return x, y


def updatePointers(app, handList):
    spots = []
    for landmarks in handList:
        fractionX, fractionY = fingertipMidpoint(landmarks)
        spots.append((
            app.pictureLeft + fractionX * app.pictureWidth,
            app.pictureTop + fractionY * app.pictureHeight,
            landmarks,
        ))
    previous = []
    for pointer in app.pointers:
        if pointer['x'] is None:
            previous.append(None)
        else:
            previous.append((pointer['x'], pointer['y']))
    assignment = pairHands(previous, [(x, y) for x, y, landmarks in spots])

    for index, pointer in enumerate(app.pointers):
        handIndex = assignment[index]
        if handIndex is None:
            if pointer['pinching']:
                updateControls(
                    app.controls, True, False,
                    pointer['x'] or 0, pointer['y'] or 0, owner=index,
                )
            clearPointer(pointer)
            continue

        pixelX, pixelY, landmarks = spots[handIndex]
        oldCursor = None
        if pointer['x'] is not None:
            oldCursor = (pointer['x'], pointer['y'])
        pointer['x'], pointer['y'] = smoothCursor(oldCursor, (pixelX, pixelY))
        pointer['thumbX'], pointer['thumbY'] = landmarkToPixel(app, landmarks[THUMB_TIP])
        pointer['indexX'], pointer['indexY'] = landmarkToPixel(app, landmarks[INDEX_TIP])

        pinching = nextPinch(pointer['pinching'], landmarks)
        updateControls(
            app.controls, pointer['pinching'], pinching,
            pointer['x'], pointer['y'], owner=index,
        )
        pointer['pinching'] = pinching


def storeCameraPicture(rgbFrame):
    global cameraPicture, pilImage
    forgetCameraPicture()
    if pilImage is None:
        from PIL import Image
        pilImage = Image
    cameraPicture = CMUImage(pilImage.fromarray(rgbFrame))


def forgetCameraPicture():
    global cameraPicture
    if cameraPicture is None:
        return
    # drawImage keeps every picture forever. Drop the previous frame or FPS falls.
    activeDrawing.images.pop(cameraPicture.uuid, None)
    cameraPicture = None


def updateFps(app, now):
    app.stepsThisSecond += 1
    elapsed = now - app.secondStarted
    if elapsed < 1:
        return

    app.fps = app.stepsThisSecond / elapsed
    print(f'FPS: {app.fps:.1f}')
    app.stepsThisSecond = 0
    app.secondStarted = now


def onAppStop(app):
    if engine is not None:
        engine.stop()
    if camera is not None:
        camera.release()
    if hands is not None:
        hands.close()


def redrawAll(app):
    drawAll(app, cameraPicture, engine)


def showWindowAsSoonAsItExists():
    # Paint as soon as pygame creates the window, before the camera libraries load.
    import cmu_graphics.cmu_graphics as graphics
    original = graphics.App.updateScreen

    def updateScreen(self, newScreen):
        original(self, newScreen)
        if not newScreen:
            return
        pygame.display.set_caption('Air DJ Mini')
        pygame.event.pump()
        pygame.display.flip()

    graphics.App.updateScreen = updateScreen


def main():
    showWindowAsSoonAsItExists()
    runApp(width=960, height=600)


if __name__ == '__main__':
    main()
