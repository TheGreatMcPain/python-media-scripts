#!/usr/bin/env python3
"""
This program is designed to batch convert a directory of
DSD audio files (.dsf) to 192Khz 24bit PCM flac files.

This is for people who purchase music from NativeDSD, but want
to play their music on devices that either don't support the DSD format,
or just can't handle higher bitrates like 256DSD.

For example my Samsung S8 will play DSD files, but can't reliably play 256DSD,
and even though it says it supports DSD the phone actually will resample it to
192Khz anyway.  So until I get a proper portable DAC/AMP for my phone I'll just
convert them to 192Khz flac.
"""
import os
import sys
import getopt
import subprocess as sp
import time
import json
from pathlib import Path
from shutil import copy2


def main():
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], "hs:b:i:o:",
            ["help", "samplerate=", "bitdepth=", "input=", "output="])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(1)

    if len(sys.argv) == 1:
        usage()
        sys.exit(1)

    dsdDir = None
    flacDir = None
    sampleRate = "192000"
    bitdepth = "24"

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-s", "--samplerate"):
            sampleRate = a
        elif o in ("-b", "--bitdepth"):
            bitdepth = a
        elif o in ("-i", "--input"):
            dsdDir = a
        elif o in ("-o", "--output"):
            flacDir = a
        else:
            usage()
            sys.exit(1)

    if dsdDir is None:
        print("Input DSD directory missing! (--input <dsd directory>)")
        sys.exit(1)

    if flacDir is None:
        print("Output FLAC directory missing! (--output <flac directory>)")
        sys.exit(1)

    if bitdepth not in ("24", "16"):
        print("Bitdepth must be '24', or '16'! (--bitdepth 24,16)")
        sys.exit(1)

    listDir, listDsf, listNotDsf = getFilesAndDirectories(dsdDir)

    print("Creating output folders")
    createOutputFolders(listDir, flacDir)

    listFlac = outputFlacList(listDsf, dsdDir, flacDir)
    print("Copying non-DSD files")
    copyNonDsfFiles(listNotDsf, dsdDir, flacDir)

    print("Converting DSD files to FLAC")
    transcodeDSDtoFLAC(listDsf, listFlac, sampleRate, bitdepth)


def usage():
    print(sys.argv[0],
          "'options' --input <dsd directory> --output <flac directory>")
    print()
    print("-h,--help    'Print this message.'")
    print()
    print("-s,--samplerate <output sameple-rate>")
    print("             'Specify FLAC sample-rate. (Default 192000)'")
    print()
    print("-b,--bitdepth <output bitdepth>")
    print("             'Specify FLAC bitdepth (16 or 24). (Default 24)'")
    print()
    print("-i,--input <dsd input directory>")
    print("             'Input directory containing DSD files.'")
    print()
    print("-o,--output <flac output directory>")
    print("             'Output directory which will contain FLAC files.'")
    print()


# from: https://github.com/Tatsh/ffmpeg-progress/blob/master/ffmpeg_progress.py
def ffprobe(in_file):
    """ffprobe font-end."""
    return dict(
        json.loads(
            sp.check_output(('ffprobe', '-v', 'quiet', '-print_format', 'json',
                             '-show_format', '-show_streams', in_file),
                            encoding='utf-8')))


def ffmpegConvert(cmd, inFile):
    print("Total Duration : ", end='')
    tags = ffprobe(inFile)['streams'][0]
    if 'duration' in tags:
        durationSec = int(tags['duration'].split('.')[0])
        durationMili = tags['duration'].split('.')[1]
        duration = time.strftime('%H:%M:%S', time.gmtime(durationSec))
        duration += '.' + durationMili
        print(duration)
    else:
        print(tags['DURATION-eng'])
    for x in cmd:
        print(x, end=' ')
    print()
    p = sp.Popen(cmd,
                 stderr=sp.STDOUT,
                 stdout=sp.PIPE,
                 universal_newlines=True)
    for line in p.stdout:
        line = line.rstrip()
        if 'size=' in line:
            print(f'{line}\r', end='')
    print()


def transcodeDSDtoFLAC(listDsf, listFlac, sampleRate, bitdepth):
    if bitdepth in "24":
        depth = "s32"
    if bitdepth in "16":
        depth = "s16"

    for i in range(0, len(listDsf)):
        print()
        print(i, "out of", len(listDsf), "done.")

        ffmpegCmd = [
            "ffmpeg", "-i", listDsf[i], "-sample_fmt", depth, "-ar",
            sampleRate, listFlac[i]
        ]

        ffmpegConvert(ffmpegCmd, listDsf[i])


# Collects Lists of files, and directories.
def getFilesAndDirectories(dsdDir):
    osListDir = [
        os.path.join(dp, f)
        for dp, dn, fn in os.walk(os.path.expanduser(dsdDir)) for f in fn
    ]

    listDsf = []
    listNotDsf = []
    listDir = []

    # Split file list into a list of dsf files, directory names,
    # and files that are not dsf.
    for f in osListDir:
        dirName = os.path.dirname(f)
        if len(listDir) > 0:
            if listDir[-1] != dirName:
                listDir.append(dirName)
        else:
            listDir.append(dirName)

        extension = f.split('.')[-1]
        if "dsf" == extension.lower():
            listDsf.append(f)
        else:
            listNotDsf.append(f)

    # Remove 'dsdDir' from 'listDir' items.
    for i in range(0, len(listDir)):
        newDir = listDir[i].replace(dsdDir, "")
        # Remove first '/' if it exists.
        if newDir[0] == '/':
            newDir = newDir[1:]
        listDir[i] = newDir

    return listDir, listDsf, listNotDsf


# Same as str.replace, but start from the end of the string.
def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)


# Creates a output List
def outputFlacList(listDsf, dsdDir, flacDir):
    listFlac = []

    for f in listDsf:
        newPath = f.replace(dsdDir, "")
        if newPath[0] == '/':
            newPath = newPath[1:]
        newPath = rreplace(newPath, ".dsf", ".flac", 1)
        listFlac.append(os.path.join(flacDir, newPath))

    return listFlac


# Creates the output directory tree.
def createOutputFolders(listDir, flacDir):
    for f in listDir:
        outputPath = os.path.join(flacDir, f)
        Path(outputPath).mkdir(parents=True, exist_ok=True)


# Copies non-dsf files to new directories.
def copyNonDsfFiles(listNotDsf, dsdDir, flacDir):
    for f in listNotDsf:
        newPath = f.replace(dsdDir, "")
        if newPath[0] == '/':
            newPath = newPath[1:]
        newPath = os.path.join(flacDir, newPath)

        copy2(f, newPath)


if __name__ == "__main__":
    main()
