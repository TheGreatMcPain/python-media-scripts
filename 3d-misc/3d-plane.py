#!/usr/bin/env python3
"""
This is some code ported to python from the program BD3D2MK3D
which is written in 'TCL'.

The code simply takes in a 3D Planes file, and then returns it's stats.

This is simply some pratice code as I might port some of functionality
from BD3D2MK3D to C, or Python. If I want to port to C I'll need to figure
out how to read the 3D-Planes file.
"""
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage:", sys.argv[0], "<3d-planes.ofs>")
        exit(1)
    with open(sys.argv[1], 'rb') as f:
        plane = f.read()

    if plane[0:7] == b"\x89OFS\r\n\x1a":
        plane = plane[41:]

    numframes = len(plane)
    framerate = 23.976
    get3DPlanesData(plane, framerate, numframes)


def get3DPlanesData(data, framerate, numframes):
    minval = 128
    maxval = -128
    total = 0
    undefined = 0
    firstframe = -1
    lastframe = -1
    tenth = numframes / 10
    p = 0
    progress = 0
    lastval = ""
    cuts = 0

    for i in range(0, numframes):
        p += 1
        if p == tenth:
            progress += 10
            p = 0

        byte = data[i]
        if byte != lastval:
            cuts += 1
            lastval = byte

        if byte == 128:
            undefined += 1
            continue
        else:
            lastframe = i
            if firstframe == -1:
                firstframe = i

        # If the value is bigger than 128.
        # Negate the value.
        if byte > 128:
            byte = 128 - byte

        if byte < minval:
            minval = byte
        if byte > maxval:
            maxval = byte

        total += byte

    print("NumFrames:", numframes)
    print("Minimum depth:", minval)
    print("Maximum depth:", maxval)
    print(
        "Average depth:",
        round((float(total) / (float(numframes) - float(undefined))) * 100.0) /
        100.0)
    print("Number of changes of depth value:", cuts)
    print("First frame with a defined depth:", firstframe)
    print("Last frame with a defined depth:", lastframe)
    print("Undefined:", undefined)
    if minval == maxval:
        print("*** Warning This 3D-Plane has a fixed depth of minval! ***")


if __name__ == "__main__":
    main()
