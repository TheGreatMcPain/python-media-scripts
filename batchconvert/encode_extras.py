#!/usr/bin/env python3
import vapoursynth as vs
import havsfunc as haf
import json
import os
import shutil
import psutil
import subprocess as sp
import xml.etree.cElementTree as ET
# Initialize VapourSynth
core = vs.get_core()

# Set niceness (I wanna play games dammit)
ps = psutil.Process(os.getpid())
ps.nice(15)

# Globals
INFOFILE = 'info.json'
RESUME = 'resume-file'

JAVA = "/usr/lib64/openjdk-11/bin/java"
BDSUP2SUB = "/home/james/.local/share/bdsup2sub/BDSup2Sub.jar"


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
        print("This one is done.")


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

    # VapourSynth stuff
    video = core.ffms2.Source(sourceFile)
    video = haf.GSMC(video, thSAD=150, radius=1)
    video = core.f3kdb.Deband(video, dynamic_grain=False, preset="Low")
    for sub in info['subs']:
        supFile = 'subtitles-forced-' + sub['id'] + '.sup'
        if os.path.isfile(supFile):
            video = core.sub.ImageFile(video, supFile)
            break

    framecount = video.num_frames

    cmd = [
        'x264', '--demuxer', 'y4m', '--preset', 'veryslow', '--tune', 'film',
        '--level', '4.1', '--crf', '18', '--qcomp', '0.65', '--input-range',
        'tv', '--range', 'tv', '--colorprim', 'bt709', '--transfer', 'bt709',
        '--colormatrix', 'bt709', '--frames',
        str(framecount), '--output', 'video.mkv', '-'
    ]

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
            print("Total Duration: ", end='')
            print(
                ffprobe(sourceFile)['streams'][int(
                    track['id'])]['tags']['DURATION-eng'])
            p = sp.Popen(cmd,
                         stderr=sp.STDOUT,
                         stdout=sp.PIPE,
                         universal_newlines=True)
            for line in p.stdout:
                line = line.rstrip()
                if 'size=' in line:
                    print(f'{line}\r', end='')
            print()

    cmd = ['mkvextract', sourceFile, 'tracks']
    for track in audio:
        extension = track['extension']
        cmd += [track['id'] + ':' + 'audio-' + track['id'] + '.' + extension]

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
