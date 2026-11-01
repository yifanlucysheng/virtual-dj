# Air DJ Mini — design

No code in this step. This is the map for a first-year CMU Graphics app that uses MVC.

Air DJ Mini shows two decks and a crossfader. A webcam watches one hand. The index fingertip moves a cursor. Pinching the thumb and index finger together acts like a mouse click. Holding that pinch and moving acts like a drag, which is how the volume sliders and the crossfader move. Each song is two local audio files: one vocals file and one instrumental file.

The mouse does the same jobs as the hand. Build and test with the mouse first. Add the camera last.

## Words used in this design

- **Model**: the app variables. Everything the program remembers lives here.
- **View**: the drawing. It reads the model and draws shapes. It does not change the model.
- **Controller**: the events. It updates the model when the timer ticks or when the user clicks, drags, or pinches.
- **Deck**: one player, left or right. It has its own song, buttons, and volume.
- **Stem**: one part of a song. This app has two stems per song: vocals and instrumental.
- **Cue**: put that deck back at the start and stop it. The next Play starts at the beginning.
- **Crossfader**: one horizontal slider between the decks. Far left is only the left deck. Far right is only the right deck. The middle is both decks at equal loudness.

CMU Graphics calls `redrawAll` for you after every event and every timer step. Your code should not call `redrawAll`.

---

## 1. MVC

### Model (the app variables)

Set these once when the app starts.

| Variable | Meaning |
| --- | --- |
| `app.leftDeck` | The dictionary of data for the left deck. Fields are listed in section 3. |
| `app.rightDeck` | The same kind of dictionary for the right deck. |
| `app.crossfader` | A number from 0 to 1. Start at `0.5`. `0` is full left. `1` is full right. |
| `app.pointerX`, `app.pointerY` | Where the cursor is, in window pixels. |
| `app.pinching` | `True` when the thumb and index finger are together on this frame. |
| `app.wasPinching` | The value of `app.pinching` from the previous frame. A new click is "pinching now, and not pinching last frame." |
| `app.dragTarget` | `None`, or one of `'leftVolume'`, `'rightVolume'`, `'crossfader'`. This is set while a slider is being dragged. |
| `app.cameraOn` | `True` when the webcam opened. |
| `app.handSeen` | `True` when this frame found a hand. |
| `app.message` | A short status string, such as `"Use the mouse, or pinch to click."` |
| `app.stepsPerSecond` | `30`. CMU Graphics will call the step function about 30 times a second. |

Button positions are not stored in the model. One layout function returns those boxes from the window size. Drawing uses that function. Click tests use that same function. The box numbers then exist in one place.

### View (what gets drawn)

`redrawAll` draws in this order, back to front:

1. A dark background filling the window.
2. The title `Air DJ Mini` and `app.message` along the top.
3. The left deck panel, then the right deck panel.
4. The crossfader between the panels.
5. The cursor: a circle at `(app.pointerX, app.pointerY)`. Fill it while `app.pinching` is true. Draw it as a ring otherwise. Skip the circle when `app.handSeen` is false and the pointer has never moved.

Each deck panel draws, top to bottom:

- The song name (`deck['name']`).
- A Play/Pause button. The label is `Play` when status is `paused` or `stopped`. The label is `Pause` when status is `playing`.
- A Cue button labeled `Cue`.
- A VOCALS toggle. Fill the box when `deck['vocalsOn']` is true. Draw only the outline when it is false.
- An INSTR toggle, using `deck['instrOn']` the same way.
- A volume slider: a horizontal track and a round knob. The knob's x position comes from `deck['volume']`.
- If `deck['loadError']` is set, draw that error string inside the panel.

The crossfader is a horizontal track with a knob. The knob's x position comes from `app.crossfader`.

Suggested window: 1000 by 640. Left panel on the left, right panel on the right, crossfader in the gap. Keep a margin of about 20 pixels. Exact pixels live in the layout function, so hit-testing and drawing stay matched.

### Controller (start, each step, and events)

**When the app starts**

1. Set `app.stepsPerSecond` to 30.
2. Build `app.leftDeck`, `app.rightDeck`, the crossfader, and the cursor variables.
3. Start pygame's mixer so two sounds can play at the same time.
4. Load both decks' audio files.
5. Try to open the webcam. On failure, set `app.cameraOn` to false and set `app.message` to `"Camera off. Use the mouse."`

**Each timer step**

1. If the camera is on, read one frame and update `app.pointerX`, `app.pointerY`, `app.pinching`, and `app.handSeen`.
2. If a pinch just started (`app.pinching` and not `app.wasPinching`), run the same press action as a mouse click at the pointer.
3. If a pinch is held and `app.dragTarget` is set, run the same drag action as the mouse, using the pointer.
4. If a pinch just ended, clear `app.dragTarget`.
5. Set the loudness of all four sounds from the deck volumes, the stem toggles, and the crossfader.
6. Copy `app.pinching` into `app.wasPinching`.

**On mouse move**

Store the mouse position in `app.pointerX` and `app.pointerY` when `app.handSeen` is false. While a hand is visible, the hand owns the pointer.

**On mouse press, and on a new pinch**

Find which box contains the point. Then:

- Play/Pause on a deck: if status is `playing`, pause that deck. Otherwise play that deck.
- Cue on a deck: cue that deck.
- VOCALS on a deck: flip `deck['vocalsOn']`.
- INSTR on a deck: flip `deck['instrOn']`.
- Volume track or knob: set `app.dragTarget` to that deck's volume and set the volume from the x position.
- Crossfader track or knob: set `app.dragTarget` to `'crossfader'` and set `app.crossfader` from the x position.
- Anywhere else: clear `app.dragTarget`.

**On mouse drag, and while a pinch is held**

- If `app.dragTarget` is a volume, set that deck's `volume` from the x position.
- If `app.dragTarget` is `'crossfader'`, set `app.crossfader` from the x position.

Turn an x position into a 0-to-1 value with:

```text
value = (x - trackLeft) / trackWidth
```

If `value` is below 0, use 0. If `value` is above 1, use 1.

**On mouse release, and when a pinch ends**

Set `app.dragTarget` to `None`.

### Loudness rule

The controller applies this at the end of every step, and also right after a toggle, so a mute is heard immediately.

```text
leftGain = 1 - app.crossfader
rightGain = app.crossfader

vocalsLoudness = deck.volume * gain * (1 if deck.vocalsOn else 0)
instrLoudness  = deck.volume * gain * (1 if deck.instrOn else 0)
```

`gain` is `leftGain` for the left deck and `rightGain` for the right deck.

Stem toggles, the volume slider, and the crossfader change loudness only. They do not stop or restart a sound. The vocals and the instrumental of one song stay on the same moment in the song.

### Play, pause, and cue

Each deck's `status` is one of three words:

| Status | Meaning | Play does this | Cue does this |
| --- | --- | --- | --- |
| `stopped` | Sitting at the start. This is how a deck begins. | Start vocals and instrumental together. Status becomes `playing`. | Stay `stopped`. |
| `playing` | Both stems are advancing together. | Pause both stems at this moment. Status becomes `paused`. | Stop both stems. Status becomes `stopped`. |
| `paused` | Both stems are holding their place. | Continue both stems from that place. Status becomes `playing`. | Stop both stems. Status becomes `stopped`. |

If `deck['loadError']` is set, Play, Pause, and Cue do nothing.

A Sound is the audio file loaded into memory. A Channel is the live playback of that Sound. Pause and loudness talk to the Channel. After a cue, forget the old channels. The next Play starts both files from the beginning again.

---

## 2. File layout

Six small Python files, plus a folder of audio. No other code files.

| File | What it does |
| --- | --- |
| `main.py` | Opens the CMU Graphics window and connects each event (`onAppStart`, `onStep`, `onMousePress`, `onMouseDrag`, `onMouseRelease`, `onMouseMove`, `redrawAll`) to one function in the controller or the view. |
| `model.py` | Creates the starting app variables: two deck dictionaries, the crossfader, the cursor, and the status message. |
| `view.py` | Draws the window from the app variables and returns the button and slider boxes so clicks can use the same rectangles. |
| `controller.py` | Updates the app variables on each timer step and on each press, drag, and release, including a pinch that just started. |
| `deck_audio.py` | Loads one deck's vocals and instrumental files and plays, pauses, cues, and sets loudness on those two sounds. |
| `hand_input.py` | Opens the webcam, reads one frame, and reports the fingertip position plus whether the thumb and index finger are pinched. |

Audio files live in `songs/`, not in a code file:

```text
songs/track1_vocals.wav
songs/track1_instr.wav
songs/track2_vocals.wav
songs/track2_instr.wav
```

Use `.wav` files. Pygame's mixer opens those without an extra decoder.

Functions to write, each doing one job:

- `main.py`: `onAppStart`, `onStep`, `onMousePress`, `onMouseDrag`, `onMouseRelease`, `onMouseMove`, `redrawAll`, `main`
- `model.py`: `initApp(app)`
- `view.py`: `redrawAll(app)`, `layout(app)`, `drawDeck(app, deck, boxes)`, `drawCrossfader(app, box)`, `drawCursor(app)`
- `controller.py`: `onAppStart(app)`, `onStep(app)`, `pressAt(app, x, y)`, `dragAt(app, x, y)`, `releaseAt(app, x, y)`, `pointInside(x, y, box)`, `sliderValue(x, trackLeft, trackWidth)`
- `deck_audio.py`: `loadDeck(deck)`, `togglePlay(deck)`, `cueDeck(deck)`, `applyLoudness(deck, gain)`
- `hand_input.py`: `openCamera()`, `readHand(camera, width, height)`, `closeCamera(camera)`

`readHand` returns `(x, y, pinching)` when a hand is visible, and `None` when it is not. The distance check is yours: MediaPipe point 4 is the thumb tip, point 8 is the index tip. If the distance between those two points is under about 40 pixels, `pinching` is true. You will tune that number once you can see the cursor fill in. Flip the camera frame left-right before reading x, so moving your hand to the right moves the cursor to the right.

`layout(app)` returns a dictionary of boxes. Each box is `(left, top, width, height)`. Suggested keys: `leftPlay`, `leftCue`, `leftVocals`, `leftInstr`, `leftVolume`, `rightPlay`, `rightCue`, `rightVocals`, `rightInstr`, `rightVolume`, `crossfader`.

Libraries, and the line of work that belongs to you around each one:

- `cmu-graphics` draws the window and delivers mouse and timer events.
- `pygame` (only `pygame.mixer`) plays the wav files and sets channel volume.
- `opencv-python` reads webcam frames.
- `mediapipe` returns the hand points. Your line is the distance check between point 4 and point 8.

---

## 3. Data each deck stores

Both `app.leftDeck` and `app.rightDeck` are dictionaries with these keys.

| Key | Type | Role |
| --- | --- | --- |
| `name` | string | Label drawn at the top of the panel, such as `"Track 1"`. |
| `vocalsPath` | string | Path to the vocals wav file. |
| `instrPath` | string | Path to the instrumental wav file. |
| `vocalsSound` | Sound or `None` | The loaded vocals file. `None` until load succeeds. |
| `instrSound` | Sound or `None` | The loaded instrumental file. |
| `vocalsChannel` | Channel or `None` | Live vocals playback. `None` while status is `stopped`. |
| `instrChannel` | Channel or `None` | Live instrumental playback. `None` while status is `stopped`. |
| `status` | string | `'stopped'`, `'playing'`, or `'paused'`. Start as `'stopped'`. |
| `volume` | float | Slider value from 0 to 1. Start at `0.8`. |
| `vocalsOn` | bool | VOCALS toggle. Start as `True`. |
| `instrOn` | bool | INSTR toggle. Start as `True`. |
| `loadError` | string or `None` | `None` after a good load. Otherwise a short reason, such as `"Missing vocals file"`. |

The left deck and the right deck use the same keys. Only the name and the two paths differ.

---

## 4. Build order

Finish each step and check the "you should see" line before starting the next one. Use the mouse through step 7. Leave `hand_input.py` as a stub that returns `None` until step 8.

**Step 1. Window and model.**  
Write `main.py`, `model.py`, and a `redrawAll` that draws the title plus two empty panels.  
You should see a window with two labeled boxes and the message about using the mouse.

**Step 2. Layout and buttons, no sound.**  
Add `layout(app)` and draw Play, Cue, VOCALS, INSTR, both volume sliders, and the crossfader from the starting model values.  
You should see every control in the right place. Knobs sit at volume 0.8 and crossfader 0.5. Toggles look on.

**Step 3. Clicks change labels.**  
Add `pressAt`. Play/Pause flips `status` between `playing` and `paused` without audio. Cue sets `status` to `stopped`. Each toggle flips its bool.  
You should see the Play label become Pause, Cue return it to Play, and a toggle box fill or empty when clicked.

**Step 4. Drags move knobs.**  
Add `dragAt`, `releaseAt`, and `sliderValue`.  
You should see the volume knobs and the crossfader knob follow the mouse, stay inside the track, and keep their new values after release.

**Step 5. One deck of real audio.**  
Fill in `deck_audio.py` for the left deck only: load, play, pause, cue. Put both wav files in `songs/`.  
You should hear vocals and instrumental together. Pause holds the place. Play continues from that place. Cue goes back to the start. The right deck still only changes labels.

**Step 6. Stem toggles.**  
Call `applyLoudness` after every toggle and at the end of each step.  
You should hear the vocal disappear when VOCALS is off and come back when it is on, with the instrumental still in time. Same for INSTR.

**Step 7. Second deck and the crossfader.**  
Load the right deck. Use `leftGain` and `rightGain` inside `applyLoudness`. If a file is missing, set `loadError` and draw it.  
You should hear the crossfader blend the two songs. A bad path shows a message in that panel, and that panel's Play does nothing.

**Step 8. Fingertip cursor.**  
Fill in `hand_input.py` so `readHand` returns the index fingertip mapped into the window. Flip the frame left-right. On camera failure, keep `app.cameraOn` false.  
You should see the ring follow your index finger. Mouse clicks still work when no hand is in view. Covering the camera leaves the DJ usable with the mouse.

**Step 9. Pinch is a click and a drag.**  
Add `app.pinching` and `app.wasPinching`. A new pinch calls `pressAt`. A held pinch calls `dragAt`. Pinch end calls `releaseAt`. Fill the cursor circle while pinched.  
You should click Play by pinching over the button, and move a slider by pinching and sliding. Releasing the pinch leaves the knob where it is.

Tune the pinch distance in step 9 only. If pinches never register, raise the pixel threshold. If the cursor stays filled all the time, lower it.