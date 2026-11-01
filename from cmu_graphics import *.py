from cmu_graphics import *
import math

def onAppStart(app):
    app.r = 20
    app.paddleTop = 155
    app.paddleHeight = 90
    app.cx = 200
    app.cy = 200
    app.dx = -8
    app.dy = 0

def redrawAll(app):
    drawRect(0, app.paddleTop, 10, app.paddleHeight, fill='blue')
    drawCircle(app.cx, app.cy, app.r, fill='blue')

def main():
    runApp()

main()
