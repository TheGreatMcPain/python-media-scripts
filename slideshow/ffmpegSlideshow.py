#!/usr/bin/env python3
"""
Creates a fadein/fadeout slideshow using ffmpeg.
The codec settings can be changed at the bottom of the script.
At the moment it just encodes to libx264 with...
(-preset veryfast, -tune stillimage, -crf 15)

Usage: <script> <width> <height> <display time in seconds> <outputfile>

The filter_complex chain comes from...
https://superuser.com/questions/833232/create-video-with-5-images-with-fadein-out-effect-in-ffmpeg/834035#834035
"""
import os
import sys
import subprocess as sp

FFMPEGPATH = 'ffmpeg'


def main():
    width = sys.argv[1]
    height = sys.argv[2]
    displaySec = sys.argv[3]
    outputFile = sys.argv[4]
    images = []
    for f in os.listdir('.'):
        if 'jpg' in f.lower() or 'jpeg' in f.lower():
            images.append(f)

    FFmpegCmd(images, width, height, displaySec, outputFile)


def FFmpegCmd(images, width, height, displaySec, output):
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
        filterStr += '[' + str(x) + ':v]scale=' + str(width) + ':' + str(
            height) + ':'
        filterStr += 'force_original_aspect_ratio=decrease,pad='
        filterStr += str(width) + ':' + str(height) + ':(ow-iw)/2:(oh-ih)/2'
        filterStr += ',setsar=1,'
        filterStr += 'fade=t=in:st=0:d=1,fade=t=out:st=' + str(
            int(displaySec) - 1)
        filterStr += ':d=1[v' + str(x) + ']; '

    for x in range(0, len(images)):
        filterStr += '[v' + str(x) + ']'
    filterStr += 'concat=n=' + str(len(images))
    filterStr += ':v=1:a=0,format=yuv420p[v]'

    cmd.append(filterStr)

    # Output file format.
    cmd += [
        '-map', '[v]', '-vcodec', 'libx264', '-preset', 'veryfast', '-crf',
        '15', '-x264-params', 'qcomp=0.8', output
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
