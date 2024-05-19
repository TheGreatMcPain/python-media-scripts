import json
import subprocess as sp
import time
import os
import shutil

# Nightmode Downmixing settings.
SUR_CHANNEL_VOL = 0.707  # Volume level to set the non-center channels to.
LFE_CHANNEL_VOL = 1.0  # Volume to set the LFE channel to.
CENTER_CHANNEL_VOL = 1.0  # Volume to set the center channel to.
MAXDB = "-0.5"


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


def flacToM4a(outFile, keep=False):
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
    if not keep:
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


def downmixTrack(inFile, outFile):
    ffFilter = getffFilter(SUR_CHANNEL_VOL, LFE_CHANNEL_VOL, CENTER_CHANNEL_VOL)
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
        "-y",
        outFile,
    ]
    ffmpegAudio(cmd, inFile, None)


def nightmodeTrack(
    inFile, outFile, codec, withLoudNorm, withDRC, samplerate=None, maxdB=MAXDB
):
    if not withLoudNorm and not withDRC:
        normalized = normAudio(inFile, outFile, maxdB)
        if not normalized:
            shutil.copy2(inFile, outFile)
        return

    normfile = "prenorm.flac"
    ffFilterList = []
    if withDRC:
        ffFilterList.append("acompressor=ratio=4")
    if withLoudNorm:
        ffFilterList.append("loudnorm")
    ffFilter = ",".join(ffFilterList)
    if not samplerate:
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
    if codec == "both":
        flacToM4a(outFile, True)
    if codec == "aac":
        flacToM4a(outFile)


def createNightmodeTracks(codec, ext, inFile, samplerate):
    print("Creating nightmode tracks for:", inFile)
    extension = ext
    inFile = inFile
    initialDownmixFile = "downmix.flac"
    downmixFile = inFile.split("." + extension)[0] + "-nightmode.flac"
    loudnormFile = inFile.split("." + extension)[0] + "-nightmode-loudnorm.flac"
    DRCFile = inFile.split("." + extension)[0] + "-nightmode-drc.flac"
    print("Downmixing audio to stereo.")
    downmixTrack(inFile, initialDownmixFile)
    print("Creating 'DownmixOnly' track.")
    nightmodeTrack(
        initialDownmixFile, downmixFile, codec, False, False, samplerate=samplerate
    )
    print("Creating 'Loudnorm' track.")
    nightmodeTrack(
        initialDownmixFile, loudnormFile, codec, True, False, samplerate=samplerate
    )
    print("Creating 'DRC+Loudnorm' track.")
    nightmodeTrack(
        initialDownmixFile, DRCFile, codec, True, True, samplerate=samplerate
    )
    print("Removing {}.".format(initialDownmixFile))
    os.remove(initialDownmixFile)
