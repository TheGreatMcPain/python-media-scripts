#!/usr/bin/env python3

import os
import json
from time import sleep
from shutil import copyfile
from subprocess import Popen, PIPE, STDOUT, DEVNULL

# FFmpeg filter used to downmix the surround audio
# Should work with everything up to 7.1 Surround.
FF_PAN_FILTER = 'pan=stereo|FL=FC+0.60*FL+0.60*FLC+0.60*BL+0.60*SL+0.60*LFE|'
FF_PAN_FILTER += 'FR=FC+0.60*FR+0.60*FRC+0.60*BR+0.60*SR+0.60*LFE'


def main():
    workListFile = 'workDictList.json'
    resumeListFile = 'resumeDictList.json'
    deleteThisShit = [resumeListFile]

    if os.path.isfile(resumeListFile):
        workDictList = jsonToDictList(resumeListFile)
        resumeDictList = workDictList.copy()
    else:
        workDictList = jsonToDictList(workListFile)
        resumeDictList = workDictList.copy()
    for workDict in workDictList:
        print("(" + str(workDictList.index(workDict)) + " out of " +
              str(len(workDictList)) + ") Completed")
        replaceNightmode(workDict)
        if len(resumeDictList) != 0:
            resumeDictList.pop(0)
            distListToJson(resumeListFile, resumeDictList)
        if workDict == workDictList[-1]:
            print("We're completely done cleaning up some stuff")
            for x in deleteThisShit:
                os.remove(x)


def replaceNightmode(workDict):
    maxdB = '-0.5'

    # Generate deleteList
    deleteList = []
    deleteExt = ['flac', 'm4a', 'mkv']
    for file in os.listdir('.'):
        fileExt = file.split('.')[-1].lower()
        if fileExt in deleteExt:
            deleteList.append(file)
    deleteList.append('resume.txt')

    codec = workDict['codec']
    if codec == 'flac':
        extension = '.flac'
    if codec == 'aac':
        extension = '.m4a'
    nightmodeLoudnormFile = 'audio-nightmode-loudnorm'
    nightmodeDRCFile = 'audio-nightmode-drc'

    resumeFile = 'resume.txt'
    resume = None

    if os.path.isfile(resumeFile):
        resume = fileToList(resumeFile)
        resume = resume[0].rstrip()
    if resume == None:
        print("Copying from", workDict['sourceFile'], "to", "./source.mkv")
        copyfile(workDict['sourceFile'], './source.mkv')
        writeToFile(resumeFile, "copyed-to-source")
        resume = 'copyed-to-source'
    for track in workDict['surroundTracks']:
        if resume == 'copyed-to-source' or resume == 'nightmode-drc' + str(
                workDict['surroundTracks'].index(track) - 1):
            print("Extracting Surround Track.")
            extractAudio('source.mkv', track[0], 'audio.flac')
            writeToFile(
                resumeFile, "extracted-audio" +
                str(workDict['surroundTracks'].index(track)))
            resume = 'extracted-audio' + str(
                workDict['surroundTracks'].index(track))
        if resume == 'extracted-audio' + str(
                workDict['surroundTracks'].index(track)):
            print("Creating Nightmode Loudnorm Track.")
            nightmodeLoudnorm(
                'audio.flac',
                nightmodeLoudnormFile + '-' + track[1] + extension, codec,
                maxdB)
            writeToFile(
                resumeFile, "nightmode-loudnorm" +
                str(workDict['surroundTracks'].index(track)))
            resume = 'nightmode-loudnorm' + str(
                workDict['surroundTracks'].index(track))
        if resume == 'nightmode-loudnorm' + str(
                workDict['surroundTracks'].index(track)):
            print("Creating Nightmode DRC+Loudnorm Track.")
            nightmodeDRCplusLoudnorm(
                'audio.flac', nightmodeDRCFile + '-' + track[1] + extension,
                codec, maxdB)
            writeToFile(
                resumeFile,
                "nightmode-drc" + str(workDict['surroundTracks'].index(track)))
            resume = 'nightmode-drc' + str(
                workDict['surroundTracks'].index(track))
    if resume == 'nightmode-drc' + str(len(workDict['surroundTracks']) - 1):
        print("Creating new mkv file.")
        outputMkv(workDict, 'source.mkv', 'output.mkv', nightmodeLoudnormFile,
                  nightmodeDRCFile, codec)
        writeToFile(resumeFile, "created-newmkv")
        resume = 'created-newmkv'
    if resume == 'created-newmkv':
        printTracks('output.mkv')
        print('Here is the list of tracks from the new mkv file.')
        print('Please look to make sure things are okay.')
        print("I'll wait 15 seconds before continuing", end='')
        print(", but if you want me to continue press CTRL-C.")
        try:
            for _ in range(0, 30):
                sleep(1)
            print("No input... continuing.")
        except KeyboardInterrupt:
            print("CTRL-C Entered... continuing.")
        print("Copying from", "./output.mkv", "to", workDict['sourceFile'])
        copyfile('./output.mkv', workDict['sourceFile'])
        writeToFile(resumeFile, "copyed-newmkv")
        resume = 'copyed-newmkv'
    if resume == 'copyed-newmkv':
        print("Cleaning up.")
        for x in deleteList:
            os.remove(x)


def distListToJson(filename, theList):
    with open(filename, 'w') as fd:
        fd.write(json.dumps(theList))


def jsonToDictList(filename):
    try:
        with open(filename, 'r') as fd:
            return json.load(fd)
    except FileNotFoundError:
        print('"' + filename + '"', "could not be found.")
        exit(1)


def writeToFile(filename, stuffToWrite):
    filename = open(filename, 'w')
    if type(stuffToWrite) is list:
        for line in stuffToWrite:
            filename.write(line + '\n')
    elif type(stuffToWrite) is str:
        filename.write(stuffToWrite)
    filename.close()


def fileToList(filename):
    try:
        filename = open(filename, 'r')
    except FileNotFoundError:
        print('"' + filename + '"', "could not be found.")
        exit(1)
    fileList = []
    for line in filename:
        line = line.rstrip()
        fileList.append(line)
    filename.close()
    return fileList


def outputMkv(workDict, inMkvFile, outMkvFile, nightmodeLoudnormFile,
              nightmodeDRCFile, codec):
    languageMap = {}
    languageMap['eng'] = 'English'
    languageMap['jpn'] = 'Japanese'

    codecMap = {}
    codecMap['flac'] = {}
    codecMap['flac']['title'] = 'FLAC'
    codecMap['flac']['ext'] = 'flac'

    codecMap['aac'] = {}
    codecMap['aac']['title'] = 'AAC'
    codecMap['aac']['ext'] = 'm4a'

    mkvmergeCmd = [
        'mkvmerge', '-o', outMkvFile, '--track-order',
        genTrackOrder(workDict)
    ]
    mkvmergeCmd += ['--audio-tracks', genKeepAudioTracks(workDict), inMkvFile]
    for surroundTrack in workDict['surroundTracks']:
        trackTitleLoudnorm = "{} Stereo Nightmode Loudnorm ({})".format(
            languageMap[surroundTrack[1]], codecMap[codec]['title'])
        trackTitleDRC = "{} Stereo Nightmode DRC+Loudnorm ({})".format(
            languageMap[surroundTrack[1]], codecMap[codec]['title'])

        mkvmergeCmd += ['--track-name', '0:' + trackTitleLoudnorm]
        mkvmergeCmd += [
            '--language', '0:' + surroundTrack[1], nightmodeLoudnormFile +
            '-{}.{}'.format(surroundTrack[1], codecMap[codec]['ext'])
        ]
        mkvmergeCmd += ['--track-name', '0:' + trackTitleDRC]
        mkvmergeCmd += [
            '--language', '0:' + surroundTrack[1], nightmodeDRCFile +
            '-{}.{}'.format(surroundTrack[1], codecMap[codec]['ext'])
        ]
    mkvmerge = Popen(mkvmergeCmd, stdout=DEVNULL, stderr=STDOUT)
    mkvmerge.communicate()


def genKeepAudioTracks(workDict):
    audioTracks = ''
    for x in workDict['keepTracks']:
        if x != workDict['keepTracks'][0]:
            audioTracks += ','
        audioTracks += x
    return audioTracks


def genTrackOrder(workDict):
    externalTracks = '1:0,2:0'
    externalTracks1 = '3:0,4:0'
    trackOrder = '0:0'
    for x in workDict['surroundTracks']:
        if x[0] not in workDict['keepTracks']:
            workDict['keepTracks'].append(x[0])
    workDict['keepTracks'].sort()
    for x in workDict['keepTracks']:
        trackOrder += ','
        trackOrder += '0:' + x
        for y in workDict['surroundTracks']:
            if x == y[0]:
                if externalTracks not in trackOrder:
                    trackOrder += ',' + externalTracks
                else:
                    trackOrder += ',' + externalTracks1
    return trackOrder


def extractAudio(mkvFile, trackNum, outFile):
    ffmpegCmd = [
        'ffmpeg', '-i', mkvFile, '-map', '0:' + trackNum, '-y', outFile
    ]
    ffmpeg = Popen(ffmpegCmd, stdout=DEVNULL, stderr=STDOUT)
    ffmpeg.communicate()


def nightmode(inFile, outFile, codec, maxdB, ffFilter):
    normFile = 'normin.flac'
    samplerate = getSamplerate(inFile)
    ffmpegCmd = ['ffmpeg', '-hide_banner', '-i', inFile]
    ffmpegCmd += ['-acodec', 'flac', '-compression_level', '8', '-af']
    ffmpegCmd += [ffFilter, '-ar', samplerate, '-y', normFile]
    ffmpeg = Popen(ffmpegCmd, stdout=DEVNULL, stderr=STDOUT)
    ffmpeg.communicate()
    normalized = normAudio(normFile, outFile, codec, maxdB)
    if normalized:
        os.remove(normFile)


def nightmodeDRCplusLoudnorm(inFile, outFile, codec, maxdB):
    ffFilter = FF_PAN_FILTER
    ffFilter += ',acompressor=ratio=4,loudnorm'
    nightmode(inFile, outFile, codec, maxdB, ffFilter)


def nightmodeLoudnorm(inFile, outFile, codec, maxdB):
    ffFilter = FF_PAN_FILTER
    ffFilter += ',loudnorm'
    nightmode(inFile, outFile, codec, maxdB, ffFilter)


def getSamplerate(inFile):
    ffmpegCmd = ['ffmpeg', '-i', inFile]
    ffmpeg = Popen(ffmpegCmd,
                   stdout=PIPE,
                   stderr=STDOUT,
                   universal_newlines=True)
    for line in ffmpeg.stdout:
        line = line.rstrip()
        if 'Stream' in line:
            metadata = line
    metadata = metadata.split(',')
    samplerate = ''
    for x in range(1, len(metadata[1]) - 3):
        samplerate += metadata[1][x]
    return samplerate


def normAudio(inFile, outFile, codec, maxdB):
    maxVolume = getMaxdB(inFile)
    if maxVolume != '0.0':
        volumeAdj = float(maxdB) - float(maxVolume)
    else:
        print("Already Normalized")
        return True
    if codec == 'aac':
        outFile = outFile.split('.m4a')[0] + '.flac'
    print("Adjusting Volume by:", volumeAdj)
    ffmpegCmd = ['ffmpeg', '-hide_banner', '-i', inFile]
    ffmpegCmd += ['-acodec', 'flac', '-compression_level', '8']
    ffmpegCmd += ['-af', 'volume=' + str(volumeAdj) + 'dB', '-y', outFile]
    ffmpeg = Popen(ffmpegCmd, stdout=DEVNULL, stderr=STDOUT)
    ffmpeg.communicate()
    verifyVol = getMaxdB(outFile)
    if verifyVol == maxdB:
        print("Normalize Complete")
        if codec == 'aac':
            encodeFlacToM4a(outFile)
        return True
    else:
        print("Volumes don't match desired result")
        return False


def encodeFlacToM4a(flacFile):
    print('Converting flac to m4a')
    m4aFile = flacFile.split('.flac')[0] + '.m4a'
    ffmpegCmd = ['ffmpeg', '-hide_banner', '-i', flacFile]
    ffmpegCmd += ['-acodec', 'aac', '-b:a', '256K']
    ffmpegCmd += ['-movflags', 'faststart', '-y', m4aFile]
    ffmpeg = Popen(ffmpegCmd, stdout=DEVNULL, stderr=STDOUT)
    ffmpeg.communicate()
    os.remove(flacFile)


def getMaxdB(inFile):
    ffmpegCmd = ['ffmpeg', '-i', inFile, '-acodec', 'pcm_s16le', '-af']
    ffmpegCmd += ['volumedetect', '-f', 'null', 'null']
    ffmpeg = Popen(ffmpegCmd,
                   stdout=PIPE,
                   stderr=STDOUT,
                   universal_newlines=True)
    temp = ''
    maxVolume = ''
    for line in ffmpeg.stdout:
        line = line.rstrip()
        if 'max_volume' in line:
            temp = line
    for x in range(temp.index(':') + 2, len(temp) - 3):
        maxVolume += temp[x]
    return maxVolume


def printTracks(mkvFile):
    ffmpegCmd = ['ffmpeg', '-i', mkvFile]
    ffmpeg = Popen(ffmpegCmd,
                   stdout=PIPE,
                   stderr=STDOUT,
                   universal_newlines=True)
    metadata = []
    for line in ffmpeg.stdout:
        line = line.rstrip()
        if '      title ' in line or 'Stream' in line:
            if 'Chapter' not in line:
                metadata.append(line)

    for x in metadata:
        print(x)


if __name__ == '__main__':
    main()
