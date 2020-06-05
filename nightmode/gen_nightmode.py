#!/usr/bin/env python3
import os
import json
from subprocess import PIPE, Popen, STDOUT


def main():
    sourceFiles = readFile('filelist.txt')
    workDictList = []
    rejectedList = []
    for source in sourceFiles:
        print("(" + str(sourceFiles.index(source)) + " out of " +
              str(len(sourceFiles)) + ") Done")
        workDict = {}
        selection = ''
        while selection not in ['y', 'Y', 'n', 'N']:
            print(source)
            printTracks(source)
            selection = input("Do you want to reject this file? (y or n): ")
        if selection in ['y', 'Y']:
            rejectedList.append(source)
        if selection in ['n', 'N']:
            workDict['sourceFile'] = source
            workDict.update(getTrackLists(source))
            workDictList.append(workDict)
    dictListToJson('workDictList.json', workDictList)
    listToFile('rejectFiles.txt', rejectedList)


def listToFile(filename, theList):
    with open(filename, 'w') as fd:
        for line in theList:
            fd.write(line + '\n')


def dictListToJson(filename, theList):
    with open(filename, 'w') as fd:
        fd.write(json.dumps(theList))


def readFile(filename):
    fileList = []
    theFile = ''
    try:
        theFile = open(filename, 'r')
    except FileNotFoundError:
        print("The File:", filename, "could not be found.")
        exit(1)
    for line in theFile:
        line = line.rstrip()
        if '#' != line[0]:
            fileList.append(line)
    theFile.close()
    return fileList


def getTrackLists(mkvFile):
    print("Please list tracks that you wish to keep (separated by comma)")
    keepTracks = input('Ex: (0:1 and 0:2 = 1,2): ')
    while ',' not in keepTracks and len(keepTracks) != 1:
        keepTracks = input('Error: Please separate numbers with comma: ')
    keepTracks = keepTracks.split(',')
    print(
        "Now select the tracks, and their language that the nightmode tracks will be based on: ",
        end='')
    surroundTracks = input("Example: (1:eng,2:jpn): ")
    newList = []
    for x in surroundTracks.split(','):
        track = x.split(':')
        newList.append(track)
    surroundTracks = newList
    while len(surroundTracks) < 1:
        surroundTracks = input(
            "Please select ONE track number, and language: ")
    print("Select a codec for the nightmode tracks. (flac or aac): ", end='')
    codec = input()
    trackLists = {}
    trackLists['surroundTracks'] = surroundTracks
    trackLists['keepTracks'] = keepTracks
    trackLists['codec'] = codec
    return trackLists


def printTracks(mkvFile):
    ffmpegCmd = ['ffmpeg', '-i', mkvFile]
    ffmpeg = Popen(ffmpegCmd,
                   stdout=PIPE,
                   stderr=STDOUT,
                   universal_newlines=True)
    metadata = []
    for line in ffmpeg.stdout:
        line = line.rstrip()
        if 'title' in line or 'Stream' in line:
            metadata.append(line)

    for line in metadata:
        if 'Stream' in line:
            firstStream = metadata.index(line)
            break

    for index in range(firstStream, len(metadata)):
        line = metadata[index]
        print(line)


if __name__ == '__main__':
    main()
