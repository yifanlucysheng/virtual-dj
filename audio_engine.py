"""Four tracks, one speaker callback.

Deck 1 vocals, deck 1 instrumental, deck 2 vocals, deck 2 instrumental.
"""

import math
import numpy as np
import sounddevice as sd
import soundfile as sf


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
        if frames > 0:
            self.loudness = float(np.mean(np.abs(mix)))
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
        if stream is not None and stream.active:
            return self.loudness
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
