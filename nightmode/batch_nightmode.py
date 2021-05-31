#!/usr/bin/env python
import subprocess as sp
import json
import sys
import os
import pathlib
import time
import hashlib
from shutil import copyfile

# Nightmode Downmixing settings.
SUR_CHANNEL_VOL = 0.60  # Volume level to set the non-center channels to.
LFE_CHANNEL_VOL = 0.60  # Volume to set the LFE channel to.

def main():
    jobsDatabaseFile = 'jobs_database.json'
    rejectedFile = 'rejected_files.txt'
    resumeDatabaseFile = 'resume_database.json'
    deleteThisShit = [resumeDatabaseFile]
    resume = False

    # See if the jobsDatabaseFile exists.
    # If it does ask the user if they want to resume.
    if os.path.isfile(resumeDatabaseFile) or os.path.isfile(jobsDatabaseFile):
        selections = {'y': True, 'n': False}
        found = "'{}' exists!".format(jobsDatabaseFile)
        if os.path.isfile(resumeDatabaseFile):
            found = "'{}' exists!".format(resumeDatabaseFile)
        selection = input(found + "Want to resume? (y or n): ").lower()
        while selection not in selections.keys():
            print("Invalid option!")
            selection = input(found + "Want to resume? (y or n): ").lower()

        status = "Please re-run {} with <directory of mkvs> ".format(
            os.path.basename(sys.argv[0])) + "as first argument."
        if selection == 'y':
            status = "Resuming..."
        print(status)
        resume = selections[selection]

    if not resume:
        if len(sys.argv) < 2:
            print("Usage:", sys.argv[0], "<directory of mkvs>")
            exit(1)

        # Create work database 'jobs_database.json'
        # and the rejected file list 'rejectedFiles.txt'
        generateJobList(sys.argv[1], rejectedFile, jobsDatabaseFile)

    # Load jobsDatabaseFile
    with open(jobsDatabaseFile, 'r') as f:
        jobList = json.load(f)

    # If the resumeDatabaseFile exists compare the blake2b
    # of jobsDatabaseFile with the one stored in the resumeDatabaseFile.
    # If the hashes match overwrite jobList with resumeDatabaseFile.
    if os.path.isfile(resumeDatabaseFile):
        with open(resumeDatabaseFile, 'r') as f:
            resumeData = json.load(f)

        jobsDatabaseHash = hashlib.blake2b()
        with open(jobsDatabaseFile, 'rb') as f:
            chunk = f.read(1024)
            while chunk:
                jobsDatabaseHash.update(chunk)
                chunk = f.read(1024)
        jobsDatabaseHash = jobsDatabaseHash.hexdigest()

        if resumeData['jobs_database_b2hash'] == jobsDatabaseHash:
            jobList = resumeData['jobList']

    # Create a copy of jobList which will be used to track what
    # jobs we have left.
    resumeJobList = jobList.copy()
    for job in jobList:
        print("({} out of {}) Completed".format(jobList.index(job),
                                                len(jobList)))
        replaceNightmode(job)
        if len(resumeJobList) != 0:
            resumeJobList.pop(0)
            createResumeJson(resumeDatabaseFile, resumeJobList,
                             jobsDatabaseFile)
        if job == jobList[-1]:
            print("We're completely done cleaning up some stuff")
            for x in deleteThisShit:
                os.remove(x)


def replaceNightmode(job):
    maxdB = '-0.5'

    codec = job['codec']
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
        print("Copying from", job['sourceFile'], "to", "./source.mkv")
        copyfile(job['sourceFile'], './source.mkv')
        writeToFile(resumeFile, "copyed-to-source")
        resume = 'copyed-to-source'
    for track in job['surroundTracks']:
        if resume == 'copyed-to-source' or resume == 'nightmode-drc' + str(
                job['surroundTracks'].index(track) - 1):
            print("Extracting Surround Track.")
            extractAudio('source.mkv', track[0], 'audio.flac')
            writeToFile(
                resumeFile,
                "extracted-audio" + str(job['surroundTracks'].index(track)))
            resume = 'extracted-audio' + str(
                job['surroundTracks'].index(track))
        if resume == 'extracted-audio' + str(
                job['surroundTracks'].index(track)):
            print("Creating Nightmode Loudnorm Track.")
            nightmodeLoudnorm(
                'audio.flac',
                nightmodeLoudnormFile + '-' + track[1] + extension, codec,
                maxdB)
            writeToFile(
                resumeFile,
                "nightmode-loudnorm" + str(job['surroundTracks'].index(track)))
            resume = 'nightmode-loudnorm' + str(
                job['surroundTracks'].index(track))
        if resume == 'nightmode-loudnorm' + str(
                job['surroundTracks'].index(track)):
            print("Creating Nightmode DRC+Loudnorm Track.")
            nightmodeDRCplusLoudnorm(
                'audio.flac', nightmodeDRCFile + '-' + track[1] + extension,
                codec, maxdB)
            writeToFile(
                resumeFile,
                "nightmode-drc" + str(job['surroundTracks'].index(track)))
            resume = 'nightmode-drc' + str(job['surroundTracks'].index(track))
    if resume == 'nightmode-drc' + str(len(job['surroundTracks']) - 1):
        print("Creating new mkv file.")
        outputMkv(job, 'source.mkv', 'output.mkv', nightmodeLoudnormFile,
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
        print("Copying from", "./output.mkv", "to", job['sourceFile'])
        copyfile('./output.mkv', job['sourceFile'])
        writeToFile(resumeFile, "copyed-newmkv")
        resume = 'copyed-newmkv'
    if resume == 'copyed-newmkv':
        print("Cleaning up.")
        # Delete All flac, m4a, and mkv files.
        # Also delete 'resumeFile'
        deleteList = []
        deleteExt = ['flac', 'm4a', 'mkv']
        for file in os.listdir('.'):
            fileExt = os.path.splitext(file)[1].lower()
            if fileExt in deleteExt:
                deleteList.append(file)
        deleteList.append(resumeFile)
        for x in deleteList:
            print("Deleting: ", x)
            os.remove(x)


def createResumeJson(resumeDatabaseFile, resumeJobList, jobsDatabaseFile):
    # Get hash of jobsDatabaseFile and store it in resume json.
    jobsDatabaseFileHash = hashlib.blake2b()
    with open(jobsDatabaseFile, 'rb') as f:
        chunk = f.read(1024)
        while chunk:
            jobsDatabaseFileHash.update(chunk)
            chunk = f.read(1024)

    resumeData = {}
    resumeData['jobs_database_b2hash'] = jobsDatabaseFileHash.hexdigest()
    resumeData['jobList'] = resumeJobList

    with open(resumeDatabaseFile, 'w') as f:
        json.dump(resumeData, f, indent=2)


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


def outputMkv(job, inMkvFile, outMkvFile, nightmodeLoudnormFile,
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
        genTrackOrder(job)
    ]
    mkvmergeCmd += ['--audio-tracks', genKeepAudioTracks(job), inMkvFile]
    for surroundTrack in job['surroundTracks']:
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


def genKeepAudioTracks(job):
    audioTracks = ''
    for x in job['keepTracks']:
        if x != job['keepTracks'][0]:
            audioTracks += ','
        audioTracks += x
    return audioTracks


def genTrackOrder(job):
    externalTracks = '1:0,2:0'
    externalTracks1 = '3:0,4:0'
    trackOrder = '0:0'
    for x in job['surroundTracks']:
        if x[0] not in job['keepTracks']:
            job['keepTracks'].append(x[0])
    job['keepTracks'].sort()
    for x in job['keepTracks']:
        trackOrder += ','
        trackOrder += '0:' + x
        for y in job['surroundTracks']:
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


# Create the jobList which will have the data that will be used to
# process each file.
def generateJobList(mkvsPath: str, rejectedFile: str, jobsDatabaseFile: str):
    filelist = getFilesList(mkvsPath)
    fileStats = getFileStats(filelist)
    rejectedStats = getRejectedFiles(fileStats)

    # Subtract rejected files from filestats
    for rejectedStat in rejectedStats:
        fileStats.remove(rejectedStat)

    reducedStats = getSimilarTracks(fileStats)

    jobList = []

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

        # Start building the jobList
        for mkv in stats['mkvs']:
            job = {}
            job['sourceFile'] = mkv
            job.update(trackLists)
            jobList.append(job)

    # Write rejected files into a text file
    rejectedFiles = [x['mkv'] for x in rejectedStats]
    with open(rejectedFile, 'w') as f:
        for line in rejectedFiles:
            f.write(line + '\n')

    # Dump jobList into a json file
    with open(jobsDatabaseFile, 'w') as f:
        json.dump(jobList, f, indent=2)


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
