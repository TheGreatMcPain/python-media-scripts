#!/usr/bin/env python3
import os
import sys
import time
import json
import getopt
import subprocess as sp

# Globals
MAXDB = '-0.5'


def main():
    codec = None
    fileIn = None

    try:
        options, args = getopt.getopt(sys.argv[1:], "hc:i:",
                                      ["help", "codec=", "input="])
        for name, value in options:
            if name in ('-h', '--help'):
                Usage()
                sys.exit()
            if name in ('-c', '--codec'):
                codec = value
            if name in ('-i', '--input'):
                fileIn = value
    except getopt.GetoptError as err:
        print(str(err))
        Usage()
        sys.exit(1)

    if codec is None:
        Usage()
        sys.exit(1)
    if fileIn is None:
        Usage()
        sys.exit(1)

    ext = fileIn.split('.')[-1]

    createNightmodeTracks(codec, ext, fileIn)


def Usage():
    print("Usage:", sys.argv[0],
          "-c,--codec <flac,aac> -i,--input <input file>")


# from: https://github.com/Tatsh/ffmpeg-progress/blob/master/ffmpeg_progress.py
def ffprobe(in_file):
    """ffprobe font-end."""
    return dict(
        json.loads(
            sp.check_output(('ffprobe', '-v', 'quiet', '-print_format', 'json',
                             '-show_format', '-show_streams', in_file),
                            encoding='utf-8')))


def getSamplerate(inFile):
    return ffprobe(inFile)['streams'][0]['sample_rate']


def getMaxdB(inFile):
    cmd = [
        'ffmpeg', '-i', inFile, '-acodec', 'pcm_s16le', '-af', 'volumedetect',
        '-f', 'null', 'null'
    ]
    p = sp.Popen(cmd,
                 stdout=sp.PIPE,
                 stderr=sp.STDOUT,
                 universal_newlines=True)
    for line in p.stdout:
        line = line.rstrip()
        if 'max_volume' in line:
            temp = line
    print()
    return temp[temp.index(':') + 2:-3]


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


def flacToM4a(outFile):
    print("Converting flac to m4a")
    m4aFile = outFile.split('.flac')[0] + '.m4a'
    cmd = [
        'ffmpeg', '-i', outFile, '-acodec', 'aac', '-b:a', '256K', '-movflags',
        'faststart', '-y', m4aFile
    ]
    ffmpegAudio(cmd, outFile, None)
    os.remove(outFile)


def normAudio(inFile, outFile, codec, maxdB):
    maxVolume = getMaxdB(inFile)
    if maxVolume != '0.0':
        volumeAdj = float(maxdB) - float(maxVolume)
    else:
        print("Already Normalized")
        return False
    print("Adjusting Volume by:", volumeAdj)
    cmd = [
        'ffmpeg', '-y', '-i', inFile, '-acodec', 'flac', '-compression_level',
        '8', '-af', 'volume=' + str(volumeAdj) + 'dB', outFile
    ]
    ffmpegAudio(cmd, inFile, None)
    verifyVol = getMaxdB(outFile)
    if verifyVol == maxdB:
        print("Normalize Complete")
        if codec == 'aac':
            flacToM4a(outFile)
        return True
    else:
        print("Volume doesn't match desired result.")
        exit()


def nightmodeTrack(inFile, outFile, codec, withDRC, maxdB):
    normfile = 'prenorm.flac'
    filter = 'pan=stereo|FL=FC+0.30*FL+0.30*FLC+0.30*BL+0.30*SL+0.60*LFE|'
    filter += 'FR=FC+0.30*FR+0.30*FRC+0.30*BR+0.30*SR+0.60*LFE,'
    if withDRC:
        filter += 'acompressor=ratio=4,loudnorm'
    else:
        filter += 'loudnorm'
    samplerate = getSamplerate(inFile)
    cmd = [
        'ffmpeg', '-i', inFile, '-acodec', 'flac', '-compression_level', '8',
        '-af', filter, '-ar', samplerate, '-y', normfile
    ]
    ffmpegAudio(cmd, inFile, None)
    normalized = normAudio(normfile, outFile, codec, maxdB)
    if normalized:
        os.remove(normfile)


def createNightmodeTracks(codec, ext, inFile):
    print('Creating nightmode tracks for:', inFile)
    extension = ext
    inFile = inFile
    loudnormFile = inFile.split('.' +
                                extension)[0] + '-nightmode-loudnorm.flac'
    DRCFile = inFile.split('.' + extension)[0] + '-nightmode-drc.flac'
    print("Creating 'Loudnorm' track.")
    nightmodeTrack(inFile, loudnormFile, codec, False, MAXDB)
    print("Creating 'DRC+Loudnorm' track.")
    nightmodeTrack(inFile, DRCFile, codec, True, MAXDB)


if __name__ == "__main__":
    main()
