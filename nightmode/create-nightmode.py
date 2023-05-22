#!/usr/bin/env python3
import os
import sys
import time
import json
import getopt
import subprocess as sp

# Nightmode Downmixing settings.
SUR_CHANNEL_VOL = 0.707  # Volume level to set the non-center channels to.
LFE_CHANNEL_VOL = 1.0  # Volume to set the LFE channel to.
CENTER_CHANNEL_VOL = 1.0  # Volume to set the center channel to.
MAXDB = "-0.5"


def main():
    codec = None
    fileIn = None

    try:
        options, args = getopt.getopt(
            sys.argv[1:], "hc:i:", ["help", "codec=", "input="]
        )
        for name, value in options:
            if name in ("-h", "--help"):
                Usage()
                sys.exit()
            if name in ("-c", "--codec"):
                codec = value
            if name in ("-i", "--input"):
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

    if len(args) > 0:
        print("Error: Trailing arguments")
        sys.exit(1)

    ext = fileIn.split(".")[-1]

    createNightmodeTracks(codec, ext, fileIn)


def Usage():
    print("Usage:", sys.argv[0], "-c,--codec <flac,aac> -i,--input <input file>")


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
    temp = None
    if not p.stdout:
        return "0.0"
    for line in p.stdout:
        line = line.rstrip()
        if "max_volume" in line:
            temp = line
    print()
    if temp == None:
        return "0.0"
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
        print("UNKNOWN (try remuxing audio into a container like .mka, .m4a, etc.)")
    for x in cmd:
        print(x, end=" ")
    print()
    p = sp.Popen(cmd, stderr=sp.STDOUT, stdout=sp.PIPE, universal_newlines=True)
    if not p.stdout:
        return None
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


def normAudio(inFile, outFile, maxdB):
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
    normalized = normAudio(normfile, outFile, maxdB)
    if normalized:
        os.remove(normfile)
    else:
        os.rename(normfile, outFile)
    if codec == "aac":
        flacToM4a(outFile)


def createNightmodeTracks(codec, ext, inFile):
    print("Creating nightmode tracks for:", inFile)
    extension = ext
    inFile = inFile
    downmixFile = inFile.split("." + extension)[0] + "-nightmode.flac"
    loudnormFile = inFile.split("." + extension)[0] + "-nightmode-loudnorm.flac"
    DRCFile = inFile.split("." + extension)[0] + "-nightmode-drc.flac"
    print("Creating 'DownmixOnly' track.")
    nightmodeTrack(inFile, downmixFile, codec, False, False, MAXDB)
    print("Creating 'Loudnorm' track.")
    nightmodeTrack(inFile, loudnormFile, codec, True, False, MAXDB)
    print("Creating 'DRC+Loudnorm' track.")
    nightmodeTrack(inFile, DRCFile, codec, True, True, MAXDB)


if __name__ == "__main__":
    main()
