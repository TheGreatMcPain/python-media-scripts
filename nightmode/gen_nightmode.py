#!/usr/bin/env python
import subprocess as sp
import json
import sys
import os
import pathlib


def main():
    if len(sys.argv) < 2:
        print("Usage:", sys.argv[0], "<directory of mkvs>")
        exit(1)

    filelist = getFilesList(sys.argv[1])

    filestats = getFileStats(filelist)

    rejectedStats = getRejectedFiles(filestats)

    # Subtract rejected files from filestats
    for rejectedStat in rejectedStats:
        filestats.remove(rejectedStat)

    workDictList = generateWorkDictList(filestats)

    # Write rejected files into a text file
    rejectedFiles = [x['mkv'] for x in rejectedStats]
    with open('rejectedFiles.txt', 'w') as f:
        for line in rejectedFiles:
            f.write(line + "\n")

    # Dump workDictList into a json file
    with open('workDictList.json', 'w') as f:
        json.dump(workDictList, f, indent=2)


# Ask the user which is the surround track which we'll use
# to create nightmode tracks (and it's language).
# We'll also ask which tracks will be kept.
def generateWorkDictList(fileStats):
    reducedStats = getSimilarTracks(fileStats)
    workList = []

    for stats in reducedStats:
        # Print audio metadata and the number of files that have the same
        # type of tracks.
        for info in stats['ffaudio_info']:
            print(" ".join([str(info[x]) for x in info.keys()]))
        print("Number of files with these audio tracks:", len(stats['mkvs']))

        print("Please list tracks that will be kept. (seperated by a comma)")
        keepTracks = input('Ex: (1,2): ')
        while ',' not in keepTracks and len(keepTracks) != 1:
            keepTracks = input('Error: Please seperate numbers with a comma: ')
        keepTracks = keepTracks.split(',')

        # TODO: Add proper input checking.
        print("Now select tracks that the nightmode tracks will be based on: ",
              end='')
        surroundTracks = input("Example: (1:eng,2:jpn): ")
        surroundTracks = [x.split(':') for x in surroundTracks.split(',')]

        codec = None
        while codec not in ['flac', 'aac']:
            if codec:
                print("Invalid input")

            print("Select a codec for the nightmode tracks. (flac or aac): ",
                  end='')
            codec = input()

        trackLists = {}
        trackLists['surroundTracks'] = surroundTracks
        trackLists['keepTracks'] = keepTracks
        trackLists['codec'] = codec

        # Start building the workList
        for mkv in stats['mkvs']:
            workDict = {}
            workDict['sourceFile'] = mkv
            workDict.update(trackLists)
            workList.append(workDict)

    return workList


# Asks the user if they want to process a file for each file in
# fileStats. The function then returns the rejected fileStats.
def getRejectedFiles(fileStats):
    rejected = []

    for fileStat in fileStats:
        # Print the file's stats
        printFilestat(fileStat)
        # Ask for y or n
        selections = ['y', 'n']
        print("Process this file? (y or n):", end=" ", flush=True)
        selection = input().lower()
        print()

        while selection not in selections:
            print("Invalid input")
            print("Process this file? (y or n):", end=" ", flush=True)
            selection = input().lower()

        if selection == 'y':
            print("File added to process list.")
        elif selection == "n":
            rejected.append(fileStat)
            print("File added to rejected list.")

        print()

    return rejected


def getSimilarTracks(fileStats):
    ffaudioInfo = [x['ffaudio_info'] for x in fileStats]

    # Strip ffaudioInfo to only similar items.
    similar = []
    for x in ffaudioInfo:
        if x not in similar:
            similar.append(x)
    ffaudioInfo = similar

    returnStats = []

    for info in ffaudioInfo:
        returnStat = {}
        returnStat['ffaudio_info'] = info
        returnStat['mkvs'] = []

        for fileStat in fileStats:
            if info == fileStat['ffaudio_info']:
                returnStat['mkvs'].append(fileStat['mkv'])

        returnStats.append(returnStat)

    return returnStats


# from: https://github.com/Tatsh/ffmpeg-progress/blob/master/ffmpeg_progress.py
# Basically uses ffprobe to grab mediainfo in a json format.
def ffprobe(in_file):
    """ffprobe font-end."""
    return dict(
        json.loads(
            sp.check_output(('ffprobe', '-v', 'quiet', '-print_format', 'json',
                             '-show_format', '-show_streams', in_file),
                            encoding='utf-8')))


# Recursive find files.
def getFilesList(folder):
    fileList = []
    for path in pathlib.Path(os.path.expanduser(folder)).rglob("**/*.mkv"):
        fileList.append(str(path.absolute()))
    fileList.sort()
    return fileList


# Parses a list of mkvs and uses ffprobe to collect audio track info.
def getFileStats(filelist: list):
    filestats = []
    for file in filelist:
        filestat = {}

        filestat['mkv'] = os.path.expanduser(file)

        filestat['ffaudio_info'] = []

        # Only store information on the audio tracks.
        for stream in ffprobe(filestat['mkv'])['streams']:
            if stream['codec_type'] == 'audio':
                # We only need these
                audioInfo = {}
                audioInfo['index'] = stream['index']
                try:
                    audioInfo['title'] = stream['tags']['title']
                except:
                    audioInfo['title'] = 'Unknown'
                audioInfo['lang'] = stream['tags']['language']
                audioInfo['codec'] = stream['codec_name']
                audioInfo['channel_layout'] = stream['channel_layout']
                audioInfo['sample_rate'] = stream['sample_rate']
                audioInfo['sample_fmt'] = stream['sample_fmt']

                filestat['ffaudio_info'].append(audioInfo)
        filestats.append(filestat)

    return filestats


# Read the filestats and print relevant info.
def printFilestat(filestat):
    ffaudio_info = filestat['ffaudio_info']
    print("File:", os.path.basename(filestat['mkv']))
    for stream in ffaudio_info:
        print(" ".join(["{}".format(stream[x]) for x in stream.keys()]))
    print()


if __name__ == "__main__":
    main()
