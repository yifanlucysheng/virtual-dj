"""Pinch and cursor math. No camera and no drawing.

Landmarks used: 0 wrist, 4 thumb tip, 8 index tip, 9 middle knuckle.
"""

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
