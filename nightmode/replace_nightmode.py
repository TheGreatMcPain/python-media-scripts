#!/usr/bin/env python3
import os
import json
import time
from shutil import copyfile
import subprocess as sp

# Nightmode Downmixing settings.
SUR_CHANNEL_VOL = 0.60  # Volume level to set the non-center channels to.
LFE_CHANNEL_VOL = 0.60  # Volume to set the LFE channel to.

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
        fileExt = os.path.splitext(file)[1].lower()
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
                time.sleep(1)
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
    mkvmerge = sp.Popen(mkvmergeCmd, stdout=sp.DEVNULL, stderr=sp.STDOUT)
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
    ffmpeg = sp.Popen(ffmpegCmd, stdout=sp.DEVNULL, stderr=sp.STDOUT)
    ffmpeg.communicate()


# from: https://github.com/Tatsh/ffmpeg-progress/blob/master/ffmpeg_progress.py
def ffprobe(in_file):
    """ffprobe font-end."""
    return dict(
        json.loads(
            sp.check_output(('ffprobe', '-v', 'quiet', '-print_format', 'json',
                             '-show_format', '-show_streams', in_file),
                            encoding='utf-8')))


def ffmpegAudio(cmd, inFile, trackid):
    print("Total Duration : ", end='')
    if trackid is not None:
        tags = ffprobe(inFile)['streams'][int(trackid)]['tags']
    else:
        tags = ffprobe(inFile)['streams'][0]
    if 'duration' in tags:
        durationSec = int(tags['duration'].split('.')[0])
        durationMili = tags['duration'].split('.')[1]
        duration = time.strftime('%H:%M:%S', time.gmtime(durationSec))
        duration += '.' + durationMili
        print(duration)
    else:
        print(tags['DURATION-eng'])
    print(" ".join(cmd))
    p = sp.Popen(cmd,
                 stderr=sp.STDOUT,
                 stdout=sp.PIPE,
                 universal_newlines=True)
    for line in p.stdout:
        line = line.rstrip()
        if 'size=' in line:
            print(f'{line}\r', end='')
    print()


def nightmode(inFile, outFile, codec, maxdB, ffFilter):
    normFile = 'normin.flac'
    samplerate = getSamplerate(inFile)
    ffmpegCmd = [
        'ffmpeg', '-i', inFile, '-acodec', 'flac', '-compression_level', '8',
        '-af', ffFilter, '-ar', samplerate, '-y', normFile
    ]
    ffmpegAudio(ffmpegCmd, inFile, None)
    normalized = normAudio(normFile, outFile, codec, maxdB)
    if normalized:
        os.remove(normFile)


def getffFilter(surVol: float, lfeVol: float):
    surVol = "{}".format(surVol)
    lfeVol = "{}".format(lfeVol)

    ffPanFilterL = 'FL=FC+{s}*FL+{s}*FLC+{s}*BL+{s}*SL+{l}*LFE'.format(
        s=surVol, l=lfeVol)
    ffPanFilterR = 'FR=FC+{s}*FR+{s}*FRC+{s}*BR+{s}*SR+{l}*LFE'.format(
        s=surVol, l=lfeVol)

    return 'pan=stereo|{}|{}'.format(ffPanFilterL, ffPanFilterR)


def nightmodeDRCplusLoudnorm(inFile, outFile, codec, maxdB):
    ffFilter = getffFilter(SUR_CHANNEL_VOL, LFE_CHANNEL_VOL)
    ffFilter += ',acompressor=ratio=4,loudnorm'
    nightmode(inFile, outFile, codec, maxdB, ffFilter)


def nightmodeLoudnorm(inFile, outFile, codec, maxdB):
    ffFilter = getffFilter(SUR_CHANNEL_VOL, LFE_CHANNEL_VOL)
    ffFilter += ',loudnorm'
    nightmode(inFile, outFile, codec, maxdB, ffFilter)


def getSamplerate(inFile):
    return ffprobe(inFile)['streams'][0]['sample_rate']


def normAudio(inFile, outFile, codec, maxdB):
    maxVolume = getMaxdB(inFile)
    if maxVolume != '0.0':
        volumeAdj = float(maxdB) - float(maxVolume)
    else:
        print("Already Normalized")
        return True
    print("Adjusting Volume by:", volumeAdj)
    # encodeFlacToM4a will change the file extension for us.
    outFile = os.path.splitext(outFile)[0] + '.flac'
    ffmpegCmd = [
        'ffmpeg', '-y', '-i', inFile, '-acodec', 'flac', '-compression_level',
        '8', '-af', 'volume=' + str(volumeAdj) + 'dB', outFile
    ]
    ffmpegAudio(ffmpegCmd, inFile, None)
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
    m4aFile = os.path.splitext(flacFile)[0] + '.m4a'
    ffmpegCmd = [
        'ffmpeg', '-i', flacFile, '-acodec', 'aac', '-b:a', '256K',
        '-movflags', 'faststart', '-y', m4aFile
    ]
    ffmpegAudio(ffmpegCmd, flacFile, None)
    os.remove(flacFile)


def getMaxdB(inFile):
    ffmpegCmd = ['ffmpeg', '-i', inFile, '-acodec', 'pcm_s16le', '-af']
    ffmpegCmd += ['volumedetect', '-f', 'null', 'null']
    ffmpeg = sp.Popen(ffmpegCmd,
                      stdout=sp.PIPE,
                      stderr=sp.STDOUT,
                      universal_newlines=True)
    for line in ffmpeg.stdout:
        line = line.rstrip()
        if 'max_volume' in line:
            temp = line
    return temp[temp.index(':') + 2:-3]


def printTracks(mkvFile):
    ffaudioInfo = []

    for stream in ffprobe(mkvFile)['streams']:
        if stream['codec_type'] == 'audio':
            audioInfo = {}
            audioInfo['index'] = stream['index']
            try:
                audioInfo['title'] = stream['tags']['title']
            except:
                audioInfo['title'] = "Unknown"
            audioInfo['lang'] = stream['tags']['language']
            audioInfo['codec'] = stream['codec_name']
            audioInfo['channel_layout'] = stream['channel_layout']
            audioInfo['sample_rate'] = stream['sample_rate']
            audioInfo['sample_fmt'] = stream['sample_fmt']

            ffaudioInfo.append(audioInfo)

    # print("File:", os.path.basename(mkvFile))
    for stream in ffaudioInfo:
        print(" ".join(["{}".format(stream[x]) for x in stream.keys()]))
    print()


if __name__ == '__main__':
    main()
