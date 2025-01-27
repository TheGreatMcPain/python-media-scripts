#!/usr/bin/env python3
import json
import os
import sys
import hashlib
from ffmpeg_normalize import FFmpegNormalize

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import nightmode


def main():
    inputFile = sys.argv[1]
    settingsFile = sys.argv[2]
    settings = importSettings(settingsFile)

    if "tracks" not in settings:
        print("'tracks' list entry not in '{}'.".format(settingsFile))

    convertAudioTracks(inputFile, settings=settings["tracks"])

    return


def convertAudioTracks(sourceFile: str, settings: list):
    for track in settings:
        convertAudioTrack(sourceFile, settings, track)
    return


def convertAudioTrack(sourceFile: str, tracks: list, audioTrack):
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
                ffmpeg_normalize.true_peak = ffFilter["normalize"]["true_peak"]

    if normalize:
        ffmpeg_normalize.post_filter = ",".join(Filter)
        normTemp = "audio-norm-temp-{}.flac".format(
            hashlib.sha1(
                json.dumps(audioTrack, sort_keys=True).encode("utf-8")
            ).hexdigest()
        )
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
        ffmpeg_normalize.add_media_file(
            normTemp, getOutFile("audio", tracks, audioTrack)
        )
        ffmpeg_normalize.run_normalization()
        os.remove(normTemp)
    else:
        cmd = ["ffmpeg", "-y", "-i", sourceFile]
        cmd += ["-map", "0:" + audioTrack["id"]]
        cmd += ["-c:a", audioTrack["convert"]["codec"]]
        if encodeOpts:
            cmd += encodeOpts
        if len(Filter) > 0:
            cmd += ["-af", ",".join(Filter)]
        cmd += [getOutFile("audio", tracks, audioTrack)]

        print("Converting Audio via ffmpeg")
        nightmode.ffmpegAudio(cmd, sourceFile, audioTrack["id"])


def getOutFile(base: str, tracks: list, track: dict):
    ext = track["extension"]
    trackId = track["id"]
    trackNum = tracks.index(track)
    return "{}-{}-{}.{}".format(base, trackId, trackNum, ext)


def importSettings(jsonPath: str):
    with open(jsonPath, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    main()
