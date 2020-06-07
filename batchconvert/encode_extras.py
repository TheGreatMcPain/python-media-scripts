#!/usr/bin/env python3
import json
import os
import shutil
import time
import psutil
import subprocess as sp
import xml.etree.cElementTree as ET

# Set niceness (I wanna play games dammit)
ps = psutil.Process(os.getpid())
ps.nice(15)

# Globals
INFOFILE = 'info.json'
RESUME = 'resume-file'

JAVA = "/usr/lib64/openjdk-11/bin/java"
BDSUP2SUB = "/home/james/.local/share/bdsup2sub/BDSup2Sub.jar"

MAXDB = '-0.5'


def main():
    lsdir = os.listdir('.')
    if INFOFILE in lsdir:
        print(INFOFILE, "found in current directory.")
        print("We'll only convert one mkv file.\n")
        convertMKV(INFOFILE)
    else:
        folders = []
        for x in lsdir:
            if os.path.isdir(x):
                infoPath = os.path.join(x, INFOFILE)
                if os.path.isfile(infoPath):
                    folders.append(x)

        for folder in folders:
            os.chdir(folder)
            index = folders.index(folder)
            total = len(folders)
            print(index, "out of", total, "done.\n")
            convertMKV(INFOFILE)
            os.chdir("..")


def convertMKV(infoFile):
    if os.path.isfile(RESUME):
        status = readResume()
    else:
        status = "juststarted"

    info = getInfo(infoFile)

    if "juststarted" in status:
        extractTracks(info)
        status = writeResume("extracted")
        print()
    if "extracted" in status:
        createNightmodeTracks(info)
        status = writeResume("nightmode")
        print()
    if "nightmode" in status:
        prepForcedSubs(info)
        print()
        encodeVideo(info)
        status = writeResume("encoded")
        print()
    if "encoded" in status:
        mergeMKV(info)
        os.rename(info['outputFile'], os.path.join("..", info['outputFile']))
        status = writeResume("merged")
        print()
    if "merged" in status:
        print("Done")


def writeResume(status):
    with open(RESUME, 'w') as f:
        f.write(status)
    return status


def readResume():
    with open(RESUME, 'r') as f:
        status = f.readlines()
    return status


def mergeMKV(info):
    title = info['title']
    output = info['outputFile']

    cmd = [
        'mkvmerge', '--output', output, '--title', title, '--track-name',
        '0:' + info['video']['title'], '--language',
        '0:' + info['video']['language'], 'video.mkv'
    ]

    for track in info['audio']:
        extension = track['extension']

        cmd += [
            '--track-name', '0:' + track['title'], '--language',
            '0:' + track['language'], '--default-track',
            '0:' + track['default'], 'audio-' + track['id'] + '.' + extension
        ]

        if "yes" in track['nightmode']:
            if "flac" in track['nightmodeCodec']:
                extension = 'flac'
            else:
                extension = 'm4a'
            cmd += [
                '--track-name', '0:' + track['nightmodeLoudnormName'],
                '--language', '0:' + track['language'], '--default-track',
                '0:' + track['default'],
                'nightmode-loudnorm-' + track['id'] + '.' + extension,
                '--track-name', '0:' + track['nightmodeDrcName'], '--language',
                '0:' + track['language'], '--default-track',
                '0:' + track['default'],
                'nightmode-drc-' + track['id'] + '.' + extension
            ]

    if 'subs' in info:
        for track in info['subs']:
            extension = track['extension']

            cmd += [
                '--track-name', '0:' + track['title'], '--language',
                '0:' + track['language'], '--default-track',
                '0:' + track['default'],
                'subtitles-' + track['id'] + '.' + extension
            ]

    if os.path.isfile('chapters.xml'):
        cmd += ['--chapters', 'chapters.xml']

    for x in cmd:
        print(x, end=' ')
    print()

    p = sp.Popen(cmd)
    p.communicate()


def encodeVideo(info):
    sourceFile = info['sourceFile']
    vpy = info['video']['vapoursynth']

    # VapourSynth stuff
    import vapoursynth as vs
    core = vs.core
    for func in vpy:
        if 'SOURCEFILE' in func:
            func = func.replace('SOURCEFILE', "'" + sourceFile + "'")
        if 'import' in func:
            exec(func)
        else:
            video = eval(func)

    for sub in info['subs']:
        supFile = 'subtitles-forced-' + sub['id'] + '.sup'
        if os.path.isfile(supFile):
            print("Hardcoding Forced Subtitle id:", sub['id'])
            video = core.sub.ImageFile(video, supFile)
            break

    cmd = ['x264', '--demuxer', 'y4m']
    cmd += info['video']['x264opts']
    cmd += ['--frames', str(video.num_frames), '--output', 'video.mkv', '-']

    for x in cmd:
        print(x, end=' ')
    print()

    p = sp.Popen(cmd, stdin=sp.PIPE)
    video.output(p.stdin, y4m=True)
    p.communicate()


def prepForcedSubs(info):
    def createNonForced(sourceFile):
        os.mkdir('subtitles')
        os.chdir('subtitles')
        cmd = [
            JAVA, '-jar', BDSUP2SUB, '--output', 'subtitles.xml',
            os.path.join('..', sourceFile)
        ]
        print("Exporting to BDXML.")
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()

        print("Swapping forced subtitle flag.")
        tree = ET.parse('subtitles.xml')
        root = tree.getroot()
        for event in root.iter('Event'):
            if event.attrib['Forced'] in 'False':
                event.set("Forced", "True")
            else:
                event.set("Forced", "False")
        tree.write('subtitles-new.xml')
        os.chdir("..")
        print("Exporting to", sourceFile)
        cmd = [
            JAVA, '-jar', BDSUP2SUB, '--forced-only', '--output',
            'subtitles-temp.sup',
            os.path.join('subtitles', 'subtitles-new.xml')
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        cmd = [
            JAVA, '-jar', BDSUP2SUB, '--force-all', 'clear', '--output',
            sourceFile, 'subtitles-temp.sup'
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        shutil.rmtree('subtitles', ignore_errors=True)
        os.remove('subtitles-temp.sup')

    if "subs" in info:
        subs = info['subs']
    else:
        return 0

    for track in subs:
        if not os.path.isfile("subtitles-" + track['id'] + '.sup'):
            print("Subtitles doesn't exist!")
            return 0

        cmd = [
            JAVA, '-jar', BDSUP2SUB, '--forced-only', '--output',
            'subtitles-forced-' + track['id'] + '.sup',
            'subtitles-' + track['id'] + '.sup'
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        print("Checking if 'subtitles-" + track['id'] +
              ".sup' has forced subs")
        if os.path.isfile('subtitles-forced-' + track['id'] + '.sup'):
            createNonForced('subtitles-' + track['id'] + '.sup')


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


def createNightmodeTracks(info):
    audio = info['audio']
    for track in audio:
        if "yes" in track['nightmode']:
            print('Creating nightmode tracks for trackid:', track['id'])
            codec = track['nightmodeCodec']
            extension = track['extension']
            inFile = 'audio-' + track['id'] + '.' + extension
            loudnormFile = 'nightmode-loudnorm-' + track['id'] + '.flac'
            DRCFile = 'nightmode-drc-' + track['id'] + '.flac'
            print("Creating 'Loudnorm' track.")
            nightmodeTrack(inFile, loudnormFile, codec, True, MAXDB)
            print("Creating 'DRC+Loudnorm' track.")
            nightmodeTrack(inFile, DRCFile, codec, True, MAXDB)


def extractTracks(info):
    sourceFile = info['sourceFile']
    audio = info['audio']
    if "subs" in info:
        subs = info['subs']
    else:
        subs = 0

    cmd = ['ffmpeg', '-y', '-i', sourceFile]
    for track in audio:
        if "yes" in track['convert']:
            extension = track['extension']
            cmd += ['-map', '0:' + track['id']]
            cmd += track['ffmpegopts']
            cmd += ['audio-' + track['id'] + '.' + extension]

            print("Converting Audio via ffmpeg")
            ffmpegAudio(cmd, sourceFile, track['id'])

    cmd = ['mkvextract', sourceFile, 'tracks']
    for track in audio:
        if "no" in track['convert']:
            extension = track['extension']
            cmd += [
                track['id'] + ':' + 'audio-' + track['id'] + '.' + extension
            ]

    if subs != 0:
        for track in subs:
            extension = track['extension']
            cmd += [
                track['id'] + ':' + 'subtitles-' + track['id'] + '.' +
                extension
            ]

    cmd += ['chapters', 'chapters.xml']

    print("\nExtracting tracks via mkvextract.")
    for x in cmd:
        print(x, end=' ')
    print()
    p = sp.Popen(cmd)
    p.communicate()


def getInfo(infoFile):
    try:
        info = json.load(open('info.json', 'r'))
    except IOError:
        print("Error: 'info.json' not found.")

    return info


if __name__ == "__main__":
    main()
