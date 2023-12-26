#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import shutil
import subprocess as sp
import time
import threading
import xml.etree.cElementTree as ET

import psutil  # Comment out of not using psutil

import encodeInfo

# Set process niceness (Priority)
psutil.Process(os.getpid()).nice(15)  # Comment out if not using psutil

# Globals
INFOFILE = "info.json"
ENCODEINFO = "encodeInfo.py"
RESUME = "resume-file"

# BDSup2Sub Settings #
# Use java version
# BDSUP2SUB = ['/usr/bin/java', '-jar',
#              '~/.local/share/bdsup2sub/BDSup2Sub.jar']
# Use C++ version
BDSUP2SUB = ["bdsup2sub++"]

# This is a maximum volume level the nightmode tracks will have. (in dB).
# 0.0 would be the highest without clipping.
MAXDB = "-0.5"

# Nightmode Downmixing settings.
SUR_CHANNEL_VOL = 0.707  # Volume level to set the non-center channels to.
LFE_CHANNEL_VOL = 1.0  # Volume to set the LFE channel to.
CENTER_CHANNEL_VOL = 1.0  # Volume to set the center channel to.


def main():
    folders = []
    lsdir = os.listdir(".")
    if INFOFILE in lsdir:
        folders.append(".")
        if len(sys.argv) == 1:
            print(INFOFILE, "found in current directory.")
            print("We'll only convert one mkv file.\n")
            convertMKV(INFOFILE)
    else:
        for x in lsdir:
            if os.path.isdir(x):
                infoPath = os.path.join(x, INFOFILE)
                if os.path.isfile(infoPath):
                    folders.append(x)

        if len(sys.argv) == 1:
            for folder in folders:
                # Check if a 'encodeInfo.py' file exists.
                encodeInfoFile = os.path.join(folder, ENCODEINFO)
                # If it exists override the previous 'encodeInfo'
                if os.path.isfile(encodeInfoFile):
                    global encodeInfo
                    # Delete the old 'encodeInfo' import
                    del sys.modules["encodeInfo"]
                    # insert the path to 'encodeInfoFile' in system PATH
                    sys.path.insert(0, os.path.dirname(os.path.abspath(encodeInfoFile)))
                    # Import the new 'encodeInfo' into our global imports
                    globals()["encodeInfo"] = __import__("encodeInfo")
                    # Cleanup the system PATH
                    sys.path.remove(os.path.dirname(os.path.abspath(encodeInfoFile)))
                os.chdir(folder)
                index = folders.index(folder)
                total = len(folders)
                print(index, "out of", total, "done.\n")
                convertMKV(INFOFILE)
                os.chdir("..")

                # Reimport the "global" 'encodeInfo'
                del sys.modules["encodeInfo"]
                globals()["encodeInfo"] = __import__("encodeInfo")

    print("Cleaning python cache files.")
    cleanPythonCache(".")

    if len(sys.argv) == 2:
        if "--clean" == sys.argv[1]:
            exclude = [os.path.basename(__file__), INFOFILE, ENCODEINFO]
            print("\nCleaning temp files")
            for folder in folders:
                infoPath = os.path.join(folder, INFOFILE)
                info = getInfo(infoPath)
                exclude.append(info["sourceFile"])
                deleteList = list(set(os.listdir(folder)) - set(exclude))
                for file in deleteList:
                    filePath = os.path.join(folder, file)
                    print("Deleting:", filePath)
                    os.remove(filePath)
                exclude.remove(info["sourceFile"])

        if "--clean-sources" == sys.argv[1]:
            print("\nCleaning source video files")
            for folder in folders:
                infoPath = os.path.join(folder, INFOFILE)
                info = getInfo(infoPath)
                path = os.path.join(folder, info["sourceFile"])
                if os.path.exists(path):
                    print("Deleting:", path)
                    os.remove(path)


def convertMKV(infoFile):
    if os.path.isfile(RESUME):
        status = readResume()
    else:
        status = "juststarted"

    info = getInfo(infoFile)

    if "juststarted" == status:
        extractTracks(info)
        status = writeResume("extracted")
        print()
    if "extracted" == status:
        createNightmodeTracks(info)
        status = writeResume("nightmode")
        print()
    if "nightmode" == status:
        prepForcedSubs(info)
        print()
        encodeVideo(info)
        status = writeResume("encoded")
        print()
    if "encoded" == status:
        mergeMKV(info)
        os.rename(info["outputFile"], os.path.join("..", info["outputFile"]))
        status = writeResume("merged")
        print()
    if "merged" == status:
        print("Done")


def writeResume(status):
    with open(RESUME, "w") as f:
        f.write(status)
    return status


def readResume():
    with open(RESUME, "r") as f:
        # Read first line in file and strip unneeded charaters.
        status = f.readline().strip()
    return status


def mergeMKV(info):
    title = info["title"]
    output = info["outputFile"]
    sourceFile = info["sourceFile"]
    videoInfo = encodeInfo.encodeInfo(sourceFile)
    videoInputFile = videoInfo.getEncodeFile()

    cmd = [
        "mkvmerge",
        "--output",
        output,
        "--title",
        title,
        "--track-name",
        "0:" + info["video"]["title"],
        "--language",
        "0:" + info["video"]["language"],
    ]

    if "mkvmergeOpts" in info["video"]:
        cmd += info["video"]["mkvmergeOpts"]
    cmd.append(videoInputFile)

    if "audio" in info:
        for track in info["audio"]:
            extension = track["extension"]

            cmd += [
                "--track-name",
                "0:" + track["title"],
                "--language",
                "0:" + track["language"],
                "--default-track",
                "0:" + track["default"],
                "audio-" + track["id"] + "." + extension,
            ]

            if "yes" in track["nightmode"]:
                if "flac" in track["nightmodeCodec"]:
                    extension = "flac"
                else:
                    extension = "m4a"
                cmd += [
                    "--track-name",
                    "0:" + track["nightmodeDownmixOnlyName"],
                    "--language",
                    "0:" + track["language"],
                    "--default-track",
                    "0:" + track["default"],
                    "nightmode-" + track["id"] + "." + extension,
                    "--track-name",
                    "0:" + track["nightmodeLoudnormName"],
                    "--language",
                    "0:" + track["language"],
                    "--default-track",
                    "0:" + track["default"],
                    "nightmode-loudnorm-" + track["id"] + "." + extension,
                    "--track-name",
                    "0:" + track["nightmodeDrcName"],
                    "--language",
                    "0:" + track["language"],
                    "--default-track",
                    "0:" + track["default"],
                    "nightmode-drc-" + track["id"] + "." + extension,
                ]

    if "subs" in info:
        for track in info["subs"]:
            extension = track["extension"]

            cmd += [
                "--track-name",
                "0:" + track["title"],
                "--language",
                "0:" + track["language"],
                "--default-track",
                "0:" + track["default"],
                "subtitles-" + track["id"] + "." + extension,
            ]

    if os.path.isfile("chapters.xml"):
        cmd += ["--chapters", "chapters.xml"]

    print(" ".join(cmd))

    p = sp.Popen(cmd)
    p.communicate()


def encodeVideo(info):
    sourceFile = info["sourceFile"]
    # VapourSynth stuff
    videoInfo = encodeInfo.encodeInfo(sourceFile)

    if not info["video"]["convert"]:
        # Assume video in on track 0.
        mkvOutTrack = "0:" + videoInfo.getEncodeFile()
        cmd = ["mkvextract", info["sourceFile"], "tracks", mkvOutTrack]

        # Print extract command
        print(" ".join(cmd))

        extractProc = sp.Popen(cmd)
        extractProc.communicate()
        return 0

    encodeProcess = None

    # Encode thread Function
    def encodeThread(video, cmd):
        nonlocal encodeProcess
        encodeProcess = sp.Popen(cmd, stdin=sp.PIPE)
        video.output(encodeProcess.stdin, y4m=True)

    core = videoInfo.getVSCore()
    video = videoInfo.vapoursynthFilter()

    if "subs" in info:
        for sub in info["subs"]:
            supFile = "subtitles-forced-" + sub["id"] + ".sup"
            if os.path.isfile(supFile):
                print("Hardcoding Forced Subtitle id:", sub["id"])
                video = core.sub.ImageFile(video, supFile)
                break

    cmd = videoInfo.getEncodeCmd()

    print(" ".join(cmd))

    # We have to run the encode process in a separate thread, because
    # CTRTL-C won't work normally when x265 is used via subprocess.
    # x265 will exit, but the python process will not react to the signal.
    t = threading.Thread(target=encodeThread, args=(video, cmd))

    # This will close the python/vapoursynth thread first which will then
    # cause the encoder to exit via EOF.
    try:
        t.start()
        t.join()  # Wait for the encode to finish.
    except KeyboardInterrupt:
        # Close the processes stdin, because x265 doesn't do it by itself.
        if encodeProcess:
            encodeProcess.stdin.close()
        exit(0)


def prepForcedSubs(info):
    if "subs" in info:
        subs = info["subs"]
    else:
        return 0

    for track in subs:
        if not os.path.isfile("subtitles-" + track["id"] + ".sup"):
            print("Subtitles doesn't exist!")
            return 0

        cmd = BDSUP2SUB
        cmd += [
            "--forced-only",
            "--output",
            "subtitles-forced-" + track["id"] + ".sup",
            "subtitles-" + track["id"] + ".sup",
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        print("Checking if 'subtitles-" + track["id"] + ".sup' has forced subs")
        if os.path.isfile("subtitles-forced-" + track["id"] + ".sup"):
            sourceFile = "subtitles-" + track["id"] + ".sup"
            os.mkdir("subtitles")
            os.chdir("subtitles")
            cmd = BDSUP2SUB
            cmd += ["--output", "subtitles.xml", os.path.join("..", sourceFile)]
            print("Exporting to BDXML.")
            p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            p.communicate()

            print("Swapping forced subtitle flag.")
            tree = ET.parse("subtitles.xml")
            root = tree.getroot()
            for event in root.iter("Event"):
                if event.attrib["Forced"] in "False":
                    event.set("Forced", "True")
                else:
                    event.set("Forced", "False")
            tree.write("subtitles-new.xml")
            os.chdir("..")
            print("Exporting to", sourceFile)
            cmd = BDSUP2SUB
            cmd += [
                "--forced-only",
                "--output",
                "subtitles-temp.sup",
                os.path.join("subtitles", "subtitles-new.xml"),
            ]
            p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            p.communicate()
            cmd = BDSUP2SUB
            cmd += [
                "--force-all",
                "clear",
                "--output",
                sourceFile,
                "subtitles-temp.sup",
            ]
            p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
            p.communicate()
            shutil.rmtree("subtitles", ignore_errors=True)
            os.remove("subtitles-temp.sup")


# from: https://github.com/Tatsh/ffmpeg-progress/blob/master/ffmpeg_progress.py
def ffprobe(in_file):
    """ffprobe font-end."""
    return dict(
        json.loads(
            sp.check_output(
                (
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-print_format",
                    "json",
                    "-show_format",
                    "-show_streams",
                    in_file,
                ),
                encoding="utf-8",
            )
        )
    )


def getSamplerate(inFile):
    return ffprobe(inFile)["streams"][0]["sample_rate"]


def getMaxdB(inFile):
    cmd = [
        "ffmpeg",
        "-i",
        inFile,
        "-acodec",
        "pcm_s16le",
        "-af",
        "volumedetect",
        "-f",
        "null",
        "null",
    ]
    p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, universal_newlines=True)

    if not p.stdout:
        print("Error: failed to start", cmd[0])
        exit(1)

    temp = ""
    for line in p.stdout:
        line = line.rstrip()
        if "max_volume" in line:
            temp = line
    print()
    return temp[temp.index(":") + 2 : -3]


def ffmpegAudio(cmd, inFile, trackid):
    print("Total Duration : ", end="")
    info = ffprobe(inFile)
    if trackid is not None:
        tags = info["streams"][int(trackid)]
    else:
        tags = info["streams"][0]
    if "tags" in tags:
        tags = tags["tags"]
    if "duration" in tags:
        durationSec = int(tags["duration"].split(".")[0])
        durationMili = tags["duration"].split(".")[1]
        duration = time.strftime("%H:%M:%S", time.gmtime(durationSec))
        duration += "." + durationMili
        print(duration)
    elif "DURATION" in tags:
        print(tags["DURATION"])
    elif "DURATION-eng" in tags:
        print(tags["DURATION-eng"])
    else:
        print("UNKNOWN (try remuxing audio into a .mka container)")
    print(" ".join(cmd))
    p = sp.Popen(cmd, stderr=sp.STDOUT, stdout=sp.PIPE, universal_newlines=True)

    if not p.stdout:
        print("Error: failed to start", cmd[0])
        exit(1)

    for line in p.stdout:
        line = line.rstrip()
        if "size=" in line:
            print(f"{line}\r", end="")
    print()


def flacToM4a(outFile):
    print("Converting flac to m4a")
    m4aFile = outFile.split(".flac")[0] + ".m4a"
    cmd = [
        "ffmpeg",
        "-i",
        outFile,
        "-acodec",
        "aac",
        "-b:a",
        "256K",
        "-movflags",
        "faststart",
        "-y",
        m4aFile,
    ]
    ffmpegAudio(cmd, outFile, None)
    os.remove(outFile)


def getffFilter(surVol: float, lfeVol: float, centerVol: float):
    surVolStr = "{}".format(surVol)
    lfeVolStr = "{}".format(lfeVol / 2)
    centerVolStr = "{}".format(centerVol / 2)

    ffPanFilterL = "FL={c}*FC+{s}*FL+{s}*FLC+{s}*BL+{s}*SL+{l}*LFE".format(
        c=centerVolStr, s=surVolStr, l=lfeVolStr
    )
    ffPanFilterR = "FR={c}*FC+{s}*FR+{s}*FRC+{s}*BR+{s}*SR+{l}*LFE".format(
        c=centerVolStr, s=surVolStr, l=lfeVolStr
    )

    return "pan=stereo|{}|{}".format(ffPanFilterL, ffPanFilterR)


def normAudio(inFile, outFile, codec, maxdB):
    maxVolume = getMaxdB(inFile)
    if maxVolume != "0.0":
        volumeAdj = float(maxdB) - float(maxVolume)
    else:
        print("Already Normalized")
        return False
    print("Adjusting Volume by:", volumeAdj)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        inFile,
        "-acodec",
        "flac",
        "-compression_level",
        "8",
        "-af",
        "volume=" + str(volumeAdj) + "dB",
        outFile,
    ]
    ffmpegAudio(cmd, inFile, None)
    verifyVol = getMaxdB(outFile)
    if verifyVol == maxdB:
        print("Normalize Complete")
        if codec == "aac":
            flacToM4a(outFile)
        return True
    else:
        print("Volume doesn't match desired result.")
        exit()


def nightmodeTrack(inFile, outFile, codec, withLoudNorm, withDRC, maxdB):
    normfile = "prenorm.flac"
    ffFilter = getffFilter(SUR_CHANNEL_VOL, LFE_CHANNEL_VOL, CENTER_CHANNEL_VOL)
    if withDRC:
        ffFilter += ",acompressor=ratio=4"
    if withLoudNorm:
        ffFilter += ",loudnorm"
    samplerate = getSamplerate(inFile)
    cmd = [
        "ffmpeg",
        "-i",
        inFile,
        "-acodec",
        "flac",
        "-compression_level",
        "8",
        "-af",
        ffFilter,
        "-ar",
        samplerate,
        "-y",
        normfile,
    ]
    ffmpegAudio(cmd, inFile, None)
    normalized = normAudio(normfile, outFile, codec, maxdB)
    if normalized:
        os.remove(normfile)
    else:
        os.rename(normfile, outFile)


def createNightmodeTracks(info):
    if "audio" not in info:
        return
    audio = info["audio"]
    for track in audio:
        if "yes" in track["nightmode"]:
            print("Creating nightmode tracks for trackid:", track["id"])
            codec = track["nightmodeCodec"]
            extension = track["extension"]
            inFile = "audio-" + track["id"] + "." + extension
            downmixFile = "nightmode-" + track["id"] + ".flac"
            loudnormFile = "nightmode-loudnorm-" + track["id"] + ".flac"
            DRCFile = "nightmode-drc-" + track["id"] + ".flac"
            print("Creating 'DownmixOnly' track.")
            nightmodeTrack(inFile, downmixFile, codec, True, False, MAXDB)
            print("Creating 'Loudnorm' track.")
            nightmodeTrack(inFile, loudnormFile, codec, True, False, MAXDB)
            print("Creating 'DRC+Loudnorm' track.")
            nightmodeTrack(inFile, DRCFile, codec, True, True, MAXDB)


def extractTracks(info):
    sourceFile = info["sourceFile"]
    if "audio" in info:
        audio = info["audio"]
    else:
        audio = 0
    if "subs" in info:
        subs = info["subs"]
    else:
        subs = 0

    cmd = ["ffmpeg", "-y", "-i", sourceFile]
    if audio != 0:
        for track in audio:
            if "yes" in track["convert"]:
                extension = track["extension"]
                cmd += ["-map", "0:" + track["id"]]
                cmd += track["ffmpegopts"]
                cmd += ["audio-" + track["id"] + "." + extension]

                print("Converting Audio via ffmpeg")
                ffmpegAudio(cmd, sourceFile, track["id"])

    cmd = ["mkvextract", sourceFile, "tracks"]
    if audio != 0:
        for track in audio:
            if "no" in track["convert"]:
                extension = track["extension"]
                cmd += [track["id"] + ":" + "audio-" + track["id"] + "." + extension]

    if subs != 0:
        for track in subs:
            extension = track["extension"]
            cmd += [track["id"] + ":" + "subtitles-" + track["id"] + "." + extension]

    cmd += ["chapters", "chapters.xml"]

    print("\nExtracting tracks via mkvextract.")
    print(" ".join(cmd))
    p = sp.Popen(cmd)
    p.communicate()


def getInfo(infoFile):
    try:
        info = json.load(open(infoFile, "r"))
    except IOError:
        print("Error:", infoFile, "not found.")
        exit(1)

    return info


# Based on this: https://code-examples.net/en/q/1ba5e27
def cleanPythonCache(path):
    if not os.path.isdir(path):
        print(path, "doesn't exist, or isn't a directory.")
        exit(1)

    # Search and delete .pyc and .pyo files
    for p in pathlib.Path(path).rglob("*.py[co]"):
        print("Deleting:", p)
        p.unlink()

    # Search and delete '__pycache__' directories
    for p in pathlib.Path(path).rglob("__pycache__"):
        print("Deleting:", p)
        p.rmdir()


if __name__ == "__main__":
    main()
