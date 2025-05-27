#!/usr/bin/env python3
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import shutil
import subprocess as sp
import threading
import xml.etree.cElementTree as ET

from ffmpeg_normalize import FFmpegNormalize
from subtitle_filter import Subtitles
from utils.info import Info, SubtitleTrackInfo, AudioTrackInfo
from utils.videoinfo import videoInfo
from vapoursynth import core, VideoNode

try:
    import psutil

    print("Setting process niceness to 15.")
    psutil.Process().nice(15)
    print("Setting process ioniceness to idle.")
    psutil.Process().ionice(psutil.IOPRIO_CLASS_IDLE, 7)
except:
    pass

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
    parser = argparse.ArgumentParser(
        prog="batchconvert",
        description="Manipulates Bluray remuxes for use in media server.",
    )

    folders = []
    if Path(INFOFILE).exists():
        folders.append(Path.cwd())
    else:
        for x in Path().cwd().iterdir():
            if x.is_dir():
                if x.joinpath(INFOFILE).exists():
                    folders.append(x)

    if len(sys.argv) == 1:
        currentDir = Path.cwd()
        for folder in folders:
            print("Entering directory:", folder)
            os.chdir(folder)
            print(folders.index(folder), "out of", len(folders), "done.\n")
            convertMKV(INFOFILE)
            os.chdir(currentDir)

    print("Cleaning python cache files.")
    cleanPythonCache(".")

    parser.add_argument(
        "--clean",
        dest="clean",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Delete generated files.",
    )
    parser.add_argument(
        "--clean-sources",
        dest="cleanSources",
        default=False,
        action=argparse.BooleanOptionalAction,
        help="Delete source files.",
    )
    args = parser.parse_args()

    if args.clean:
        cleanFiles(folders, INFOFILE)
    if args.cleanSources:
        cleanSourceFiles(folders, INFOFILE)


def cleanSourceFiles(folders: list, infoFile: str):
    print("\nCleaning source video files")
    for folder in folders:
        info = Info(str(folder.joinpath(infoFile)))
        path = folder.joinpath(info.sourceMKV)
        if path.exists():
            print("Deleting:", path)
            path.unlink()


def cleanFiles(folders: list, infoFile: str):
    exclude = [Path(__file__).name, infoFile]
    for folder in folders:
        info = Info(str(folder.joinpath(infoFile)))
        exclude.append(info.sourceMKV)
        if info.videoInfo.vapoursynthScript != "":
            exclude.append(info.videoInfo.vapoursynthScript)

        for track in info.subInfo:
            if track.external:
                exclude.append(track.external)

        for file in folder.iterdir():
            if file.is_dir():
                continue
            if file.name not in exclude:
                print("Deleting", file)
                file.unlink()

        exclude.remove(info.sourceMKV)


def convertMKV(infoFile):
    info = Info(jsonFile=infoFile)
    outputFilePath = Path(info.outputFile).resolve()
    dstPath = outputFilePath.parent.with_name(outputFilePath.name)

    if not Path(info.sourceMKV).exists():
        print("'{}' not found! skipping".format(info.sourceMKV))
        return

    if dstPath.exists():
        print(dstPath, "already exists! skipping...")
        return

    extractTracks(info)
    print()
    convertSubtitles(info)
    print()
    convertAudio(info)
    print()
    encodeVideo(info)
    print()
    mergeMKV(info)
    outputFilePath.replace(dstPath)
    print("Done")


def mergeMKV(info: Info):
    title = info.title
    output = info.outputFile

    cmd = [
        "mkvmerge",
        "--output",
        output,
        "--title",
        title,
        "--track-name",
        "0:" + info.videoInfo.title,
        "--language",
        "0:" + info.videoInfo.language,
        "--no-chapters",
    ]

    cmd += info.videoInfo.mkvmergeOpts
    cmd.append(info.videoInfo.output)

    for track in info.audioInfo:
        if track.sync:
            cmd += ["--sync", "0:" + str(track.sync)]
        cmd += [
            "--track-name",
            "0:" + track.title,
            "--language",
            "0:" + track.language,
            "--default-track",
            "0:" + str(int(track.default)),
            "--no-chapters",
            track.getOutFile(),
        ]

    for track in info.subInfo:
        supFile = track.getOutFile()
        if track.sync:
            cmd += ["--sync", "0:" + str(track.sync)]
        if track.external:
            supFile = track.external
        cmd += [
            "--track-name",
            "0:" + track.title,
            "--language",
            "0:" + track.language,
            "--default-track",
            "0:" + str(int(track.default)),
            supFile,
        ]

    if Path("chapters.xml").exists():
        cmd += ["--chapters", "chapters.xml"]

    print(" ".join(cmd))

    p = sp.Popen(cmd)
    p.communicate()


def encodeVideo(info: Info):
    inputInfo = videoInfo(info.sourceMKV)
    tempOutFile = Path("temp-" + info.videoInfo.output)
    outFile = Path(info.videoInfo.output)

    if outFile.exists():
        print(outFile, "already exists! skipping...")
        return 0

    if not info.videoInfo.convert:
        if inputInfo.DolbyVision:
            print("Dolby Vision detected!!")
            print("Extracting video stream and converting it to DV profile 8.1")
            inputInfo.extractDoviHEVC(str(tempOutFile))
            tempOutFile.replace(outFile)
            return 0

        # Assume video in on track 0.
        mkvOutTrack = "0:" + str(tempOutFile)
        cmd = ["mkvextract", info.sourceMKV, "tracks", mkvOutTrack]

        # Print extract command
        print(" ".join(cmd))

        extractProc = sp.Popen(cmd)
        extractProc.communicate()
        tempOutFile.replace(outFile)
        return 0

    video = None
    # If a vapoursynth script is specified load it in as a module.
    if info.videoInfo.vapoursynthScript:
        vapoursynthScriptPath = info.videoInfo.vapoursynthScript

        if not Path(vapoursynthScriptPath).exists():
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
            if info.videoInfo.vapoursynthVars:
                vsScriptVars = info.videoInfo.vapoursynthVars
            video = vapoursynthScript.vapoursynthFilter(info.sourceMKV, vsScriptVars)
        else:
            print(
                "'vapoursynthFilter()' Doesn't exist in {}".format(
                    vapoursynthScriptPath
                )
            )
            exit(1)
        if type(video) != VideoNode:
            print("'vapoursynthFilter()' did not return VideoNode.")
            exit(1)
        print("Using 'vapoursynthFilter()' from '{}'".format(vapoursynthScriptPath))
    else:
        video = core.ffms2.Source(info.sourceMKV)

    encodeProcess = None

    # Encode thread Function
    def encodeThread(video, cmd):
        nonlocal encodeProcess
        encodeProcess = sp.Popen(cmd, stdin=sp.PIPE)
        video.output(encodeProcess.stdin, y4m=True)
        encodeProcess.communicate()

    for sub in info.subInfo:
        if sub.getForcedFile():
            if sub.hasForcedFile():
                print("Hardcoding Subtitles:", sub.getForcedFile())
                video = core.sub.ImageFile(video, sub.getForcedFile())
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
        str(tempOutFile),
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

    if inputInfo.HDR10:
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

    cmd += info.videoInfo.x265Opts
    cmd2 = cmd.copy()

    if info.videoInfo.twoPass:
        cmd = cmd[:1] + ["--pass", "1", "--no-slow-firstpass"] + cmd[1:]
        cmd2 = cmd2[:1] + ["--pass", "2"] + cmd2[1:]

    print(" ".join(cmd))

    try:
        # We have to run the encode process in a separate thread, because
        # CTRTL-C won't work normally when x265 is used via subprocess.
        t = threading.Thread(target=encodeThread, args=(video, cmd))
        t.start()
        t.join()

        if info.videoInfo.twoPass:
            print(" ".join(cmd2))
            t = threading.Thread(target=encodeThread, args=(video, cmd2))
            t.start()
            t.join()
    except KeyboardInterrupt:
        # Close the processes stdin, because x265 doesn't do it by itself.
        if type(encodeProcess) == sp.Popen:
            encodeProcess.terminate()
        exit(0)

    tempOutFile.replace(outFile)


def prepForcedSubs(track: SubtitleTrackInfo):
    if not track.external:
        print("Not checking external subtitles for forced subs.")
        return 0

    cmd = BDSUP2SUB + [
        "--forced-only",
        "--output",
        track.getForcedFile(),
        track.getOutFile(),
    ]
    p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    p.communicate()
    print("Checking if '" + track.getOutFile() + "' has forced subs")
    if track.hasForcedFile():
        os.mkdir("subtitles")
        os.chdir("subtitles")
        cmd = BDSUP2SUB + [
            "--output",
            "subtitles.xml",
            str(Path("..", track.getOutFile())),
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
        print("Exporting to", track.getOutFile())
        cmd = BDSUP2SUB + [
            "--forced-only",
            "--output",
            "subtitles-temp.sup",
            str(Path("subtitles", "subtitles-new.xml")),
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        cmd = BDSUP2SUB + [
            "--force-all",
            "clear",
            "--output",
            track.getOutFile(),
            "subtitles-temp.sup",
        ]
        p = sp.Popen(cmd, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        p.communicate()
        shutil.rmtree("subtitles", ignore_errors=True)
        os.remove("subtitles-temp.sup")


def subtitlesOCR(track: SubtitleTrackInfo):
    if not shutil.which("sup2srt"):
        print("'sup2srt' is not found!")
        exit(1)

    if not track.sourceTrack:
        print("'sup2srt' enabled, but no matching 'sup' track.")
        exit(1)

    cmd = [
        "sup2srt",
        "-l",
        track.language,
        "-o",
        track.getOutFile(),
        track.sourceTrack.getOutFile(),
    ]

    print("\nCreating SRT of track {} via sup2srt.".format(track.id))
    print(" ".join(cmd))
    sup2srtProcess = sp.Popen(cmd)
    sup2srtProcess.communicate()

    if track.srtFilter:
        print("Creating non-SDH subtitles.")
        srt = Subtitles(track.getOutFile())
        srt.filter()
        srt.save()


def convertSubtitles(info: Info):
    for track in info.subInfo:
        if track.sup2srt:
            subtitlesOCR(track)
        else:
            prepForcedSubs(track)


def ffmpegRun(cmd):
    print(" ".join(cmd))
    p = sp.Popen(cmd, stderr=sp.STDOUT, stdout=sp.PIPE, universal_newlines=True)
    if not p.stdout:
        return None
    for line in p.stdout:
        line = line.rstrip()
        if "size=" in line:
            print(f"{line}\r", end="")
    print()


def getffFilter(surVol: float, lfeVol: float, centerVol: float):
    surVolStr = "{}".format(surVol)
    lfeVolStr = "{}".format(lfeVol / 2)
    centerVolStr = "{}".format(centerVol / 2)

    ffPanFilterL = "FL<{c}*FC+{s}*FL+{s}*FLC+{s}*BL+{s}*SL+{l}*LFE".format(
        c=centerVolStr, s=surVolStr, l=lfeVolStr
    )
    ffPanFilterR = "FR<{c}*FC+{s}*FR+{s}*FRC+{s}*BR+{s}*SR+{l}*LFE".format(
        c=centerVolStr, s=surVolStr, l=lfeVolStr
    )

    return "pan=stereo|{}|{}".format(ffPanFilterL, ffPanFilterR)


def convertAudioTrack(sourceFile: str, audioTrack: AudioTrackInfo):
    normalize: bool = False
    encodeOpts = None
    tempOutFile = Path("temp-" + audioTrack.getOutFile())
    Filter: list = []
    ffmpeg_normalize = FFmpegNormalize(
        audio_codec=audioTrack.convert["codec"],
        extra_output_options=encodeOpts,
    )

    if Path(audioTrack.getOutFile()).exists():
        print(audioTrack.getOutFile(), "already exists! skipping...")
        return 0

    if [] != audioTrack.convert["encodeOpts"]:
        encodeOpts = audioTrack.convert["encodeOpts"]

    if "filters" in audioTrack.convert:
        for ffFilter in audioTrack.convert["filters"]:
            if "ffmpeg" in ffFilter.keys():
                Filter.append(ffFilter["ffmpeg"])

            if "downmixStereo" in ffFilter.keys():
                downmixAlgo = ffFilter["downmixStereo"]
                Filter.append(
                    getffFilter(
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
        normTemp = Path(str(audioTrack.id) + ".norm.flac")
        print("'normalize' enabled!")
        if not normTemp.exists():
            # Creating a flac file, because it'll go faster than reading from the source.
            # Plus, 'ffmpeg-normalize' doesn't have an option to just output one audio track.
            print("Creating intermediate 'flac' file.")
            normTempTemp = Path(normTemp).with_suffix(".temp.flac")
            ffmpegRun(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    sourceFile,
                    "-map",
                    "0:{}".format(audioTrack.id),
                    "-acodec",
                    "flac",
                    str(normTempTemp),
                ],
            )
            normTempTemp.replace(normTemp)
        else:
            print("Intermediate 'flac' file already exists.")
        print("Normalizing and converting audio using 'ffmpeg-normalize'")
        ffmpeg_normalize.add_media_file(str(normTemp), str(tempOutFile))
        ffmpeg_normalize.run_normalization()
    else:
        cmd = ["ffmpeg", "-y", "-i", sourceFile]
        cmd += ["-map", "0:{}".format(audioTrack.id)]
        cmd += ["-c:a", audioTrack.convert["codec"]]
        if encodeOpts:
            cmd += encodeOpts
        if len(Filter) > 0:
            cmd += ["-af", ",".join(Filter)]
        cmd += [str(tempOutFile)]

        print("Converting Audio via ffmpeg")
        ffmpegRun(cmd)

    tempOutFile.replace(audioTrack.getOutFile())


def convertAudio(info: Info):
    for track in info.audioInfo:
        if track.convert:
            convertAudioTrack(info.sourceMKV, track)


def extractTracks(info: Info):
    sourceFile = info.sourceMKV
    tracks = []
    for track in info.audioInfo:
        if Path(track.getOutFile()).exists():
            print(track.getOutFile(), "already exists! skipping...")
            continue
        if track.convert:
            continue
        tracks.append(track)
    for track in info.subInfo:
        if Path(track.getOutFile()).exists():
            print(track.getOutFile(), "already exists! skipping...")
            continue
        if track.sup2srt:
            continue
        if track.external:
            continue
        tracks.append(track)

    if len(tracks) == 0:
        return 0

    tempTracks = []

    cmd = ["mkvextract", sourceFile, "tracks"]
    for track in tracks:
        tempOut = Path("temp-" + track.getOutFile())
        cmd += ["{}:{}".format(track.id, tempOut)]
        tempTracks.append(tempOut)

    cmd += ["chapters", "chapters.xml"]

    print("\nExtracting tracks via mkvextract.")
    print(" ".join(cmd))
    p = sp.Popen(cmd)
    p.communicate()

    for i in range(len(tracks)):
        tempTracks[i].replace(tracks[i].getOutFile())


# Based on this: https://code-examples.net/en/q/1ba5e27
def cleanPythonCache(path):
    if not Path(path).is_dir():
        print(path, "doesn't exist, or isn't a directory.")
        exit(1)

    # Search and delete .pyc and .pyo files
    for p in Path(path).rglob("*.py[co]"):
        print("Deleting:", p)
        p.unlink()

    # Search and delete '__pycache__' directories
    for p in Path(path).rglob("__pycache__"):
        print("Deleting:", p)
        p.rmdir()


if __name__ == "__main__":
    main()
