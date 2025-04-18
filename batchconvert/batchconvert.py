#!/usr/bin/env python3
import os
import pathlib
import sys
import shutil
import subprocess as sp
import threading
import vapoursynth as vs
import importlib.util
import xml.etree.cElementTree as ET
from ffmpeg_normalize import FFmpegNormalize

from subtitle_filter import Subtitles

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import videoinfo
from utils import nightmode
from utils.info import Info
from utils.info import TrackInfo

import psutil  # Comment out of not using psutil

# Set process niceness (Priority)
psutil.Process().nice(15)  # Comment out if not using psutil

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
    if pathlib.Path(INFOFILE).exists():
        folders.append(pathlib.Path.cwd())
    else:
        for x in pathlib.Path().cwd().iterdir():
            if x.is_dir():
                if x.joinpath(INFOFILE).exists():
                    folders.append(x)

    if len(sys.argv) == 1:
        currentDir = pathlib.Path.cwd()
        for folder in folders:
            os.chdir(folder)
            print(folders.index(folder), "out of", len(folders), "done.\n")
            convertMKV(INFOFILE)
            os.chdir(currentDir)

    print("Cleaning python cache files.")
    cleanPythonCache(".")

    if len(sys.argv) == 2:
        if "--clean" == sys.argv[1]:
            exclude = [os.path.basename(__file__), INFOFILE]
            print("\nCleaning temp files")
            for folder in folders:
                infoPath = os.path.join(folder, INFOFILE)
                info = Info(jsonFile=infoPath)
                exclude.append(info["sourceFile"])
                if "vapoursynth" in info["video"]:
                    if "script" in info["video"]["vapoursynth"]:
                        exclude.append(info["video"]["vapoursynth"]["script"])
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
                info = Info(infoPath)
                path = os.path.join(folder, info["sourceFile"])
                if os.path.exists(path):
                    print("Deleting:", path)
                    os.remove(path)


def convertMKV(infoFile):
    if os.path.isfile(RESUME):
        status = readResume()
    else:
        status = "juststarted"

    info = Info(jsonFile=infoFile)

    if not os.path.isfile(info["sourceFile"]):
        print("'{}' not found! skipping".format(info["sourceFile"]))
        return

    if "juststarted" == status:
        extractTracks(info)
        status = writeResume("extracted")
        print()
    if "extracted" == status:
        print()
        convertAudio(info)
        status = writeResume("audio")
    if "audio" == status:
        print()
        encodeVideo(info)
        status = writeResume("video")
        print()
    if "video" == status:
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
        "--no-chapters",
    ]

    if "mkvmergeOpts" in info["video"]:
        cmd += info["video"]["mkvmergeOpts"]
    cmd.append(info["video"]["output"])

    if "audio" in info:
        for track in info["audio"]:
            if "sync" in track:
                cmd += ["--sync", "0:" + str(int(track["sync"]))]
            cmd += [
                "--track-name",
                "0:" + track["title"],
                "--language",
                "0:" + track["language"],
                "--default-track",
                "0:" + str(int(track["default"])),
                "--no-chapters",
                track.getOutFile(),
            ]

    if "subs" in info:
        for track in info["subs"]:
            supFile = track.getOutFile()

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
    if "vapoursynth" in info["video"] and info["video"]["vapoursynth"]:
        if "script" not in info["video"]["vapoursynth"]:
            print("'script' variable missing from 'vapoursynth'!")
            exit(1)
        vapoursynthScriptPath = info["video"]["vapoursynth"]["script"]

        if not os.path.isfile(vapoursynthScriptPath):
            print("'{}' doesn't exist!".format(vapoursynthScriptPath))
            exit(1)

        vapoursynthScript_spec = importlib.util.spec_from_file_location(
            "vapoursynthScript", vapoursynthScriptPath
        )
        if not vapoursynthScript_spec:
            print("Loading '{}' failed".format(vapoursynthScriptPath))
            exit(1)

        vapoursynthScript = importlib.util.module_from_spec(vapoursynthScript_spec)
        if not vapoursynthScript_spec.loader:
            print("Failed to load '{}' as a module".format(vapoursynthScriptPath))
            exit(1)

        vapoursynthScript_spec.loader.exec_module(vapoursynthScript)
        if "vapoursynthFilter" in dir(vapoursynthScript):
            vsScriptVars = None
            if "variables" in info["video"]["vapoursynth"]:
                vsScriptVars = info["video"]["vapoursynth"]["variables"]
            video = vapoursynthScript.vapoursynthFilter(
                info["sourceFile"], vsScriptVars
            )
        else:
            print(
                "'vapoursynthFilter()' Doesn't exist in {}".format(
                    vapoursynthScriptPath
                )
            )
            exit(1)
        if type(video) != vs.VideoNode:
            print("'vapoursynthFilter()' did not return VideoNode.")
            exit(1)
        print("Using 'vapoursynthFilter()' from '{}'".format(vapoursynthScriptPath))
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
            if sub.getForcedFile():
                if os.path.isfile(sub.getForcedFile()):
                    print("Hardcoding Subtitles:", sub.getForcedFile())
                    video = vs.core.sub.ImageFile(video, sub.getForcedFile())
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


def prepForcedSubs(track: TrackInfo):
    if "external" in track:
        print("Not checking external subtitles for forced subs.")
        return 0

    origOutFile = track.getOutFile()
    forcedOutFile = "forced-{}".format(track.getOutFile())

    cmd = BDSUP2SUB + [
        "--forced-only",
        "--output",
        forcedOutFile,
        origOutFile,
    ]
    p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    p.communicate()
    print("Checking if '" + origOutFile + "' has forced subs")
    if os.path.isfile(forcedOutFile):
        track.setForcedFile(forcedOutFile)
        os.mkdir("subtitles")
        os.chdir("subtitles")
        cmd = BDSUP2SUB + [
            "--output",
            "subtitles.xml",
            os.path.join("..", origOutFile),
        ]
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
        print("Exporting to", origOutFile)
        cmd = BDSUP2SUB + [
            "--forced-only",
            "--output",
            "subtitles-temp.sup",
            os.path.join("subtitles", "subtitles-new.xml"),
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        cmd = BDSUP2SUB + [
            "--force-all",
            "clear",
            "--output",
            origOutFile,
            "subtitles-temp.sup",
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        shutil.rmtree("subtitles", ignore_errors=True)
        os.remove("subtitles-temp.sup")


def subtitlesOCR(track: TrackInfo):
    if not shutil.which("sup2srt"):
        print("'sup2srt' is not found!")
        exit(1)

    if not track.getForcedFile():
        print("'sup2srt' enabled, but no matching 'sup' track.")
        exit(1)

    cmd = [
        "sup2srt",
        "-l",
        track["language"],
        "-o",
        track.getOutFile(),
        track.getSupSourceFile(),
    ]

    print("\nCreating SRT of track {} via sup2srt.".format(track["id"]))
    print(" ".join(cmd))
    sup2srtProcess = sp.Popen(cmd)
    sup2srtProcess.communicate()

    if "filter" not in track:
        return
    if track["filter"]:
        print("Creating non-SDH subtitles.")
        srt = Subtitles(track.getOutFile())
        srt.filter()
        srt.save()


def convertSubtitles(info: Info):
    subs = None
    if "subs" in info:
        subs = info["subs"]
    if not subs:
        return 0

    for track in subs:
        if "sup2srt" in track:
            if track["sup2srt"]:
                subtitlesOCR(track)
            else:
                prepForcedSubs(track)
        else:
            prepForcedSubs(track)


def convertAudioTrack(sourceFile: str, audioTrack: TrackInfo):
    normalize: bool = False
    encodeOpts = None
    Filter: list = []
    ffmpeg_normalize = FFmpegNormalize(
        audio_codec=audioTrack["convert"]["codec"],
        extra_output_options=encodeOpts,
    )

    if [] != audioTrack["convert"]["encodeOpts"]:
        encodeOpts = audioTrack["convert"]["encodeOpts"]

    if "filters" in audioTrack["convert"]:
        for ffFilter in audioTrack["convert"]["filters"]:
            if "ffmpeg" in ffFilter.keys():
                Filter.append(ffFilter["ffmpeg"])

            if "downmixStereo" in ffFilter.keys():
                downmixAlgo = ffFilter["downmixStereo"]
                Filter.append(
                    nightmode.getffFilter(
                        surVol=downmixAlgo["surrounds"],
                        lfeVol=downmixAlgo["lfe"],
                        centerVol=downmixAlgo["center"],
                    )
                )

            if "normalize" in ffFilter.keys():
                normalize = True
                ffmpeg_normalize.pre_filter = ",".join(Filter)
                Filter = []
                if "keep" == ffFilter["normalize"]["loudness_range_target"]:
                    ffmpeg_normalize.keep_lra_above_loudness_range_target = True
                else:
                    ffmpeg_normalize.loudness_range_target = ffFilter["normalize"][
                        "loudness_range_target"
                    ]
                ffmpeg_normalize.target_level = ffFilter["normalize"]["target_level"]
                if "true_peak" in ffFilter["normalize"]:
                    ffmpeg_normalize.true_peak = ffFilter["normalize"]["true_peak"]

    if normalize:
        ffmpeg_normalize.post_filter = ",".join(Filter)
        normTemp = pathlib.Path(
            "norm-temp-{}".format(audioTrack.getOutFile())
        ).with_suffix(".flac")
        # Creating a flac file, because it'll go faster than reading from the source.
        # Plus, 'ffmpeg-normalize' doesn't have an option to just output one audio track.
        print("'normalize' enabled! creating intermediate 'flac' file.")
        nightmode.ffmpegAudio(
            [
                "ffmpeg",
                "-y",
                "-i",
                sourceFile,
                "-map",
                "0:{}".format(audioTrack["id"]),
                "-acodec",
                "flac",
                normTemp,
            ],
            sourceFile,
            audioTrack["id"],
        )
        print("Normalizing and converting audio using 'ffmpeg-normalize'")
        ffmpeg_normalize.add_media_file(str(normTemp), audioTrack.getOutFile())
        ffmpeg_normalize.run_normalization()
        normTemp.unlink()
    else:
        cmd = ["ffmpeg", "-y", "-i", sourceFile]
        cmd += ["-map", "0:{}".format(audioTrack["id"])]
        cmd += ["-c:a", audioTrack["convert"]["codec"]]
        if encodeOpts:
            cmd += encodeOpts
        if len(Filter) > 0:
            cmd += ["-af", ",".join(Filter)]
        cmd += [audioTrack.getOutFile()]

        print("Converting Audio via ffmpeg")
        nightmode.ffmpegAudio(cmd, sourceFile, audioTrack["id"])


def convertAudio(info: Info):
    if "audio" not in info:
        return
    audio = info["audio"]
    sourceFile = info["sourceFile"]

    for track in audio:
        if track["convert"]:
            convertAudioTrack(sourceFile, track)


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

    cmd = ["mkvextract", sourceFile, "tracks"]
    if audio != 0:
        for track in audio:
            if not track["convert"]:
                cmd += ["{}:".format(track["id"]) + track.getOutFile()]

    if subs != 0:
        for track in subs:
            if "sup2srt" in track:
                if track["sup2srt"]:
                    continue
            if "external" in track:
                continue
            cmd += ["{}:".format(track["id"]) + track.getOutFile()]

    cmd += ["chapters", "chapters.xml"]

    print("\nExtracting tracks via mkvextract.")
    print(" ".join(cmd))
    p = sp.Popen(cmd)
    p.communicate()


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
