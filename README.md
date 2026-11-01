# Air DJ Mini

A first-year CMU Graphics app. The window shows your hand, two decks, and a crossfader. The plan for the rest of the decks is in `DESIGN.md`.

The window shows your hand in a mirror, at the camera's own proportions, with black bars where the window is a different shape. An orange dot sits on the thumb tip (landmark 4). A blue dot sits on the index fingertip (landmark 8). A yellow cursor sits halfway between them. The program prints the frames per second in the terminal. If a full second after startup is under 20 FPS, the camera picture turns off and the window stays dark, with only the dots left.

Along the bottom, each deck has Play, VOCALS, INSTR, and a volume slider. The crossfader sits in the middle. Pinch a button once to press it. Pinch a slider handle and drag: the value follows your cursor from 0 to 1 until you release. The mouse does the same thing.

Keys: space plays or pauses deck 1, enter does deck 2, left and right move the crossfader, q quits.

A flower sits in the palm (the average of landmarks 0, 5, 9, 13, and 17). It rotates with the line from the wrist to the middle knuckle, opens when the hand opens, and closes into a bud for a fist. Falling petals spawn faster when the music is louder, and the list never grows past 40.

Songs are `songs/track1_vocals.wav`, `songs/track1_instr.wav`, `songs/track2_vocals.wav`, and `songs/track2_instr.wav`, at 44100 Hz. If a file is missing, that deck stays quiet and the terminal says so. No webcam and no speakers do the same: a message, and the window stays open.

## Run it

```bash
pip install -r requirements.txt
python3 main.py