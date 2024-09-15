#!/usr/bin/env python3
import json
import os
import pathlib
import sys
import shutil
import subprocess as sp
import threading
import vapoursynth as vs
import importlib.util
import xml.etree.cElementTree as ET
from subtitle_filter import Subtitles

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import videoinfo
from utils import nightmode

import psutil  # Comment out of not using psutil

# Set process niceness (Priority)
psutil.Process(os.getpid()).nice(15)  # Comment out if not using psutil

# Globals
INFOFILE = "info.json"
RESUME = "resume-file"

# BDSup2Sub Settings #
# Use java version
# BDSUP2SUB = ['/usr/bin/java', '-jar',
#              '~/.local/share/bdsup2sub/BDSup2Sub.jar']
# Use C++ version
BDSUP2SUB = ["bdsup2sub++"]


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
                os.chdir(folder)
                index = folders.index(folder)
                total = len(folders)
                print(index, "out of", total, "done.\n")
                convertMKV(INFOFILE)
                os.chdir("..")

    print("Cleaning python cache files.")
    cleanPythonCache(".")

    if len(sys.argv) == 2:
        if "--clean" == sys.argv[1]:
            exclude = [os.path.basename(__file__), INFOFILE]
            print("\nCleaning temp files")
            for folder in folders:
                infoPath = os.path.join(folder, INFOFILE)
                info = getInfo(infoPath)
                exclude.append(info["sourceFile"])
                if "vapoursynthScript" in info["video"]:
                    exclude.append(info["video"]["vapoursynthScript"])
                deleteList = list(set(os.listdir(folder)) - set(exclude))
                for file in deleteList:
                    if os.path.isdir(file):
                        continue
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
        subtitlesOCR(info)
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
    cmd.append(info["video"]["output"])

    if "audio" in info:
        for track in info["audio"]:
            extension = track["extension"]

            cmd += [
                "--track-name",
                "0:" + track["title"],
                "--language",
                "0:" + track["language"],
                "--default-track",
                "0:" + str(int(track["default"])),  # 'True' should become '1'
                "audio-" + track["id"] + "." + extension,
            ]

            if track["nightmode"]:
                titleSuffix = ""
                if "flac" in track["nightmodeCodec"]:
                    extension = "flac"
                    titleSuffix = "(FLAC)"
                else:
                    extension = "m4a"
                    titleSuffix = "(AAC)"
                cmd += [
                    "--track-name",
                    "0:" + track["nightmodeDownmixOnlyName"] + " " + titleSuffix,
                    "--language",
                    "0:" + track["language"],
                    "nightmode-" + track["id"] + "." + extension,
                    "--track-name",
                    "0:" + track["nightmodeLoudnormName"] + " " + titleSuffix,
                    "--language",
                    "0:" + track["language"],
                    "nightmode-loudnorm-" + track["id"] + "." + extension,
                    "--track-name",
                    "0:" + track["nightmodeDrcName"] + " " + titleSuffix,
                    "--language",
                    "0:" + track["language"],
                    "nightmode-drc-" + track["id"] + "." + extension,
                ]

    if "subs" in info:
        for track in info["subs"]:
            extension = track["extension"]
            supFile = "subtitles-" + track["id"] + "." + extension

            if "external" in track:
                supFile = track["external"]

            cmd += [
                "--track-name",
                "0:" + track["title"],
                "--language",
                "0:" + track["language"],
                "--default-track",
                "0:" + str(int(track["default"])),
                supFile,
            ]

    if os.path.isfile("chapters.xml"):
        cmd += ["--chapters", "chapters.xml"]

    print(" ".join(cmd))

    p = sp.Popen(cmd)
    p.communicate()


def encodeVideo(info):
    inputInfo = videoinfo.videoInfo(info["sourceFile"])

    if not info["video"]["convert"]:
        if inputInfo.DolbyVision:
            print("Dolby Vision detected!!")
            print("Extracting video stream and converting it to DV profile 8.1")
            inputInfo.extractDoviHEVC(info["video"]["output"])
            return 0

        # Assume video in on track 0.
        mkvOutTrack = "0:" + info["video"]["output"]
        cmd = ["mkvextract", info["sourceFile"], "tracks", mkvOutTrack]

        # Print extract command
        print(" ".join(cmd))

        extractProc = sp.Popen(cmd)
        extractProc.communicate()
        return 0

    video = None
    # If a vapoursynth script is specified load it in as a module.
    if (
        "vapoursynthScript" in info["video"]
        and info["video"]["vapoursynthScript"] != ""
    ):
        if not os.path.isfile(info["video"]["vapoursynthScript"]):
            print("'{}' doesn't exist!".format(info["video"]["vapoursynthScript"]))
            exit(1)
        vapoursynthScript_spec = importlib.util.spec_from_file_location(
            "vapoursynthScript", info["video"]["vapoursynthScript"]
        )
        # These checks for None suck!
        if not vapoursynthScript_spec:
            print("Loading '{}' failed".format(info["video"]["vapoursynthScript"]))
            exit(1)
        vapoursynthScript = importlib.util.module_from_spec(vapoursynthScript_spec)
        # Like why?
        if not vapoursynthScript_spec.loader:
            print(
                "Failed to load '{}' as a module".format(
                    info["video"]["vapoursynthScript"]
                )
            )
            exit(1)
        vapoursynthScript_spec.loader.exec_module(vapoursynthScript)
        if "vapoursynthFilter" in dir(vapoursynthScript):
            video = vapoursynthScript.vapoursynthFilter(info["sourceFile"])
        else:
            print(
                "'vapoursynthFilter()' Doesn't exist in {}".format(
                    info["video"]["vapoursynthScript"]
                )
            )
            exit(1)
        print(
            "Using 'vapoursynthFilter()' from '{}'".format(
                info["video"]["vapoursynthScript"]
            )
        )
    else:
        video = vs.core.ffms2.Source(info["sourceFile"])

    encodeProcess = None

    # Encode thread Function
    def encodeThread(video, cmd):
        nonlocal encodeProcess
        encodeProcess = sp.Popen(cmd, stdin=sp.PIPE)
        video.output(encodeProcess.stdin, y4m=True)

    if "subs" in info:
        for sub in info["subs"]:
            if "external" not in sub:
                supFile = "subtitles-forced-" + sub["id"] + ".sup"
                if os.path.isfile(supFile):
                    print("Hardcoding Forced Subtitle id:", sub["id"])
                    video = vs.core.sub.ImageFile(video, supFile)
                    break

    if inputInfo.HDR10Plus:
        print("HDR10+ Detected!!")
        print("Extracting it with '{}'.".format(inputInfo.HDR10PlusTool))
        if inputInfo.extractHDR10PlusMetadata() != 0:
            print("'{}' not in PATH".format(inputInfo.HDR10PlusTool))
            exit(1)
    if inputInfo.DolbyVision:
        print("Dolby Vision detected!!")
        print(
            "Extract RPU with '{}'. (converts to Dolby Vision Profile 8.1)".format(
                inputInfo.DoviTool
            )
        )
        if inputInfo.extractDoviRPU() != 0:
            print("'{}' not in PATH".format(inputInfo.DoviTool))
            exit(1)

    cmd = [
        "x265",
        "--y4m",
        "--input",
        "-",
        "--output",
        info["video"]["output"],
        "--frames",
        str(video.num_frames),
    ]

    if inputInfo.ColorRange:
        cmd += ["--range", inputInfo.ColorRange]
    if inputInfo.ColorPrimaries:
        cmd += ["--colorprim", inputInfo.ColorPrimaries]
    if inputInfo.ColorTransfer:
        cmd += ["--transfer", inputInfo.ColorTransfer]
    if inputInfo.ColorMatrix:
        cmd += ["--colormatrix", inputInfo.ColorMatrix]

    cmd += ["--hdr10-opt"]

    if inputInfo.HDR10MasterDisplayData:
        cmd += ["--master-display", inputInfo.X265HDR10MasterDisplayString]
    if inputInfo.HDR10ContentLightLeveData:
        cmd += ["--max-cll", inputInfo.X265HDR10CLLString]

    if inputInfo.DolbyVision:
        cmd += [
            "--dolby-vision-rpu",
            inputInfo.DVMetadataFile,
            "--dolby-vision-profile",
            "8.1",
            "--vbv-bufsize",
            "50000",
            "--vbv-maxrate",
            "50000",
        ]

    if inputInfo.HDR10Plus:
        cmd += ["--dhdr10-info=" + str(inputInfo.HDR10PlusMetadataFile)]

    if "x265Opts" not in info["video"]:
        print("'x265Opts' not found in {}'s 'video' section!".format(INFOFILE))
        exit(1)
    cmd += info["video"]["x265Opts"]

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
        if "external" in track:
            print("Not checking external subtitles for forced subs.")
            return 0

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


def createNightmodeTracks(info):
    if "audio" not in info:
        return
    audio = info["audio"]
    for track in audio:
        if track["nightmode"]:
            print("Creating nightmode tracks for trackid:", track["id"])
            codec = track["nightmodeCodec"]
            extension = track["extension"]
            inFile = "audio-" + track["id"] + "." + extension
            downmixFile = "nightmode-" + track["id"] + ".flac"
            loudnormFile = "nightmode-loudnorm-" + track["id"] + ".flac"
            DRCFile = "nightmode-drc-" + track["id"] + ".flac"
            print("Creating 'DownmixOnly' track.")
            nightmode.nightmodeTrack(inFile, downmixFile, codec, True, False)
            print("Creating 'Loudnorm' track.")
            nightmode.nightmodeTrack(inFile, loudnormFile, codec, True, False)
            print("Creating 'DRC+Loudnorm' track.")
            nightmode.nightmodeTrack(inFile, DRCFile, codec, True, True)


def subtitlesOCR(info):
    subs = None
    if "subs" in info:
        subs = info["subs"]
    if not subs:
        return 0
    if not shutil.which("sup2srt"):
        print("'sup2srt' is not found!")
        exit(1)

    for track in subs:
        if "sup2srt" not in track:
            continue
        if track["sup2srt"]:
            cmd = [
                "sup2srt",
                "-l",
                track["language"],
                "-o",
                "subtitles-" + track["id"] + "." + track["extension"],
                "subtitles-" + track["id"] + ".sup",
            ]

            print("\nCreating SRT of track {} via sup2srt.".format(track["id"]))
            print(" ".join(cmd))
            sup2srtProcess = sp.Popen(cmd)
            sup2srtProcess.communicate()

            if "filter" not in track:
                continue
            if track["filter"]:
                print("Creating non-SDH subtitles.")
                subs = Subtitles("subtitles-" + track["id"] + "." + track["extension"])
                subs.filter()
                subs.save()


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
            if track["convert"]:
                if "ffmpegopts" not in track:
                    print("'convert' enabled, but 'ffmpegopts' not found!")
                    exit(1)

                extension = track["extension"]
                cmd += ["-map", "0:" + track["id"]]
                cmd += track["ffmpegopts"]
                cmd += ["audio-" + track["id"] + "." + extension]

                print("Converting Audio via ffmpeg")
                nightmode.ffmpegAudio(cmd, sourceFile, track["id"])

    cmd = ["mkvextract", sourceFile, "tracks"]
    if audio != 0:
        for track in audio:
            if not track["convert"]:
                extension = track["extension"]
                cmd += [track["id"] + ":" + "audio-" + track["id"] + "." + extension]

    if subs != 0:
        for track in subs:
            if "sup2srt" in track:
                continue
            if "external" in track:
                continue
            extension = track["extension"]
            cmd += [
                track["id"] + ":" + "subtitles-" + track["id"] + "." + extension
            ]

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
