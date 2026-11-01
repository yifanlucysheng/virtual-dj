"""
Palm flower for Air DJ Mini.

No camera and no drawing. Pass in pixel points (one per landmark) and get
the flower's center, angle, and how open the hand is.

Landmarks used:

  0, 5, 9, 13, 17   wrist and the four finger knuckles. Their average is the palm.
  0 and 9           wrist to middle knuckle. That arrow rotates the flower,
                    and its length is the hand size.
  4, 8, 12, 16, 20  the five fingertips. Far from the palm means an open hand.
"""

import math
import random

from pinch import distance, xy

# The five landmarks averaged to find the middle of the palm.
PALM = (0, 5, 9, 13, 17)
WRIST = 0
MIDDLE_KNUCKLE = 9
# Thumb, index, middle, ring, and pinky tips.
TIPS = (4, 8, 12, 16, 20)

# A closed fist measures near 0.55. A flat open hand measures near 1.35.
# bloomAmount stretches that range onto 0 (bud) to 1 (fully open petals).
FIST_RATIO = 0.55
OPEN_RATIO = 1.35

# Each step the openness moves this fraction of the way toward the new ratio.
# 0.25 means 25% of the new measurement and 75% of the old one.
OPEN_NEW_WEIGHT = 0.25

# How many petals to drop per second when the music is as loud as it gets.
SPAWN_PER_SECOND = 18
MAX_PETALS = 40
PETAL_COUNT = 5


def palmCenter(points):
    """Average of the wrist and the four knuckles.

    Adding the five x values and dividing by five is the middle in x.
    Same for y. A landmark that is not in PALM is ignored.
    """
    totalX = 0.0
    totalY = 0.0
    for index in PALM:
        x, y = xy(points[index])
        totalX += x
        totalY += y
    count = len(PALM)
    return (totalX / count, totalY / count)


def handAngle(points):
    """Radians of the arrow from the wrist (0) to the middle knuckle (9).

    atan2(dy, dx) turns that arrow into an angle. Pointing right is 0.
    Pointing up the screen is about -pi/2, because y grows downward.
    """
    x0, y0 = xy(points[WRIST])
    x9, y9 = xy(points[MIDDLE_KNUCKLE])
    return math.atan2(y9 - y0, x9 - x0)


def handSize(points):
    """Pixels from the wrist to the middle knuckle. Same size pinch.py uses."""
    return distance(xy(points[WRIST]), xy(points[MIDDLE_KNUCKLE]))


def openness(points):
    """Average fingertip distance from the palm, divided by hand size.

    Dividing cancels scale: a far-away open hand scores the same as a close
    one. A fist keeps the tips near the palm, so the ratio is small.
    Returns None when the hand size is 0, because there is nothing to divide by.
    """
    size = handSize(points)
    if size == 0:
        return None
    center = palmCenter(points)
    total = 0.0
    for index in TIPS:
        total += distance(xy(points[index]), center)
    return (total / len(TIPS)) / size


def smoothOpen(oldOpen, newOpen, weight=OPEN_NEW_WEIGHT):
    """Slide the openness toward the new ratio. The first sample is used as-is."""
    if oldOpen is None or newOpen is None:
        return newOpen
    return weight * newOpen + (1 - weight) * oldOpen


def bloomAmount(ratio):
    """Map a smoothed openness ratio onto 0 (bud) through 1 (bloomed)."""
    if ratio is None:
        return 0.0
    span = OPEN_RATIO - FIST_RATIO
    amount = (ratio - FIST_RATIO) / span
    if amount < 0.0:
        return 0.0
    if amount > 1.0:
        return 1.0
    return amount


def petalShapes(centerX, centerY, angle, handPixels, bloom, count=PETAL_COUNT):
    """One rotated oval per petal.

    Petal i sits on the ray at `angle + i * (a full turn / count)`.
    cos(theta) and sin(theta) are the x and y steps along that ray
    (screen y grows downward, which matches atan2 in handAngle).

    An unrotated CMU oval is taller than it is wide, so its long axis
    points up and down. rotateAngle is degrees(theta) + 90, which lays
    that long axis along the ray: a hand pointing up stays at 0 degrees,
    and a hand pointing right is 90 degrees.
    """
    if handPixels < 1:
        handPixels = 1
    # Short and round when bloom is 0. Long and narrow when bloom is 1.
    length = handPixels * (0.42 + bloom * 0.95)
    width = length * (0.70 - bloom * 0.32)
    if width < 2:
        width = 2
    if length < 2:
        length = 2
    reach = length * 0.42
    step = (2 * math.pi) / count
    shapes = []
    for i in range(count):
        theta = angle + i * step
        x = centerX + math.cos(theta) * reach
        y = centerY + math.sin(theta) * reach
        degrees = math.degrees(theta) + 90
        shapes.append((x, y, width, length, degrees))
    return shapes


def makePetal(x, y):
    """One falling petal. Speeds are pixels per step."""
    return {
        'x': x + random.uniform(-14, 14),
        'y': y + random.uniform(-6, 8),
        'speed': random.uniform(1.5, 3.2),
        'drift': random.uniform(-0.7, 0.7),
        'spin': random.uniform(-4, 4),
        'angle': random.uniform(0, 180),
        'size': random.uniform(10, 18),
        'tint': random.randrange(2),
    }


def stepPetals(petals, credit, loudness, stepsPerSecond, spawnX, spawnY, windowHeight):
    """Move petals down. Spawn more when the music is louder. Never past 40.

    credit is the leftover fraction of a petal from the last step. Loudness 1
    adds SPAWN_PER_SECOND / stepsPerSecond to it. Every time credit reaches 1,
    one petal appears and credit loses 1. No palm (spawnX is None) means the
    ones already falling keep going, and no new ones are added.
    """
    kept = []
    for petal in petals:
        petal['y'] += petal['speed']
        petal['x'] += petal['drift']
        petal['angle'] += petal['spin']
        if petal['y'] < windowHeight + 30:
            kept.append(petal)
    petals = kept

    if spawnX is None:
        return petals, credit

    rate = stepsPerSecond if stepsPerSecond else 30
    credit += loudness * SPAWN_PER_SECOND / rate
    while credit >= 1.0 and len(petals) < MAX_PETALS:
        credit -= 1.0
        petals.append(makePetal(spawnX, spawnY))
    # Drop stored credit once the list is full, so it does not dump a burst later.
    if len(petals) >= MAX_PETALS and credit > 1.0:
        credit = 1.0
    return petals, credit


def updateFlower(app, points, loudness):
    """Write the palm flower onto app, then step the falling petals.

    `points` is a list of (x, y) pixels, or None when no hand is in view.
    Called from onStep. redrawAll only reads what this stored.
    """
    spawnX = None
    spawnY = None
    if points is None:
        app.flowerX = None
    else:
        app.flowerX, app.flowerY = palmCenter(points)
        app.flowerAngle = handAngle(points)
        app.flowerSize = handSize(points)
        app.flowerOpen = smoothOpen(app.flowerOpen, openness(points))
        app.flowerBloom = bloomAmount(app.flowerOpen)
        spawnX = app.flowerX
        spawnY = app.flowerY
    app.petals, app.petalCredit = stepPetals(
        app.petals,
        app.petalCredit,
        loudness,
        app.stepsPerSecond,
        spawnX,
        spawnY,
        app.height,
    )