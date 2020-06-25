#!/usr/bin/env python3
"""
Creates a fadein/fadeout slideshow using ffmpeg.
The codec settings can be changed at the bottom of the script.
At the moment it just encodes to libx264 with...
(-preset veryfast, -tune stillimage, -crf 15)

The resulting video will be 720p.

Usage: <script> <display time in seconds> <outputfile>

The filter_complex chain comes from...
https://superuser.com/questions/833232/create-video-with-5-images-with-fadein-out-effect-in-ffmpeg/834035#834035
"""
import os
import sys
import subprocess as sp

FFMPEGPATH = 'ffmpeg'


def main():
    displaySec = sys.argv[1]
    outputFile = sys.argv[2]
    images = []
    for f in os.listdir('.'):
        if 'JPG' in f or 'jpg' in f:
            images.append(f)

    FFmpegCmd(images, displaySec, outputFile)


def FFmpegCmd(images, displaySec, output):
    cmd = [FFMPEGPATH]

    # Get Input images.
    for img in images:
        cmd += [
            '-framerate', '30000/1001', '-loop', '1', '-t', displaySec, '-i',
            img
        ]

    cmd += ['-filter_complex']

    filterStr = ''

    # Build filter_complex string.
    for x in range(0, len(images)):
        filterStr += '[' + str(
            x) + ':v]fade=t=in:st=0:d=1,fade=t=out:st=4:d=1[v' + str(x) + ']; '

    for x in range(0, len(images)):
        filterStr += '[v' + str(x) + ']'
    filterStr += 'concat=n=' + str(len(images))
    filterStr += ':v=1:a=0,format=yuv420p,scale=-1:720[v]'

    cmd.append(filterStr)

    # Output file format.
    cmd += [
        '-map', '[v]', '-vcodec', 'libx264', '-preset', 'veryfast', '-tune',
        'stillimage', '-crf', '15', output
    ]

    # Print ffmpeg command to stdout.
    for x in cmd:
        print(x, end=' ')
    print()

    # Begin encode.
    p = sp.Popen(cmd)
    p.communicate()


if __name__ == "__main__":
    main()
