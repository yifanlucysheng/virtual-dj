"""Deck values. Pinches write these dictionaries. The audio engine reads them."""

import os

from controls import clamp01

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
    from controls import makeButton, makeSlider

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
