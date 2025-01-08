#!/usr/bin/env python3
import json
import os
import sys
import hashlib
from pathlib import Path
from ffmpeg_normalize import FFmpegNormalize

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import nightmode


def main():
    inputFile = sys.argv[1]
    settingsFile = sys.argv[2]
    settings = importSettings(settingsFile)

    if "tracks" not in settings:
        print("'tracks' list entry not in '{}'.".format(settingsFile))

    convertTracks(inputFile, settings=settings["tracks"])

    return


def convertTracks(sourceFile: str, settings: dict):
    for index in range(len(settings)):
        track = settings[index]
        outFile = (
            Path(sourceFile)
            .with_name("{}-{}_{}".format(sourceFile, "nightmode", index))
            .with_suffix(track["extension"])
        )
        if track["convert"]:
            normalize: bool = False
            encodeOpts = None
            Filter: list = []
            ffmpeg_normalize = FFmpegNormalize(
                audio_codec=track["convert"]["codec"],
                extra_output_options=encodeOpts,
            )

            if [] != track["convert"]["encodeOpts"]:
                encodeOpts = track["convert"]["encodeOpts"]

            for ffFilter in track["convert"]["filters"]:
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
                    ffmpeg_normalize.target_level = ffFilter["normalize"][
                        "target_level"
                    ]
                    ffmpeg_normalize.true_peak = ffFilter["normalize"]["true_peak"]

            if normalize:
                ffmpeg_normalize.post_filter = ",".join(Filter)
                normTemp = "audio-norm-temp-{}.flac".format(
                    hashlib.sha1(
                        json.dumps(track, sort_keys=True).encode("utf-8")
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
                        "0:{}".format(track["id"]),
                        "-acodec",
                        "flac",
                        normTemp,
                    ],
                    sourceFile,
                    track["id"],
                )
                print("Normalizing and converting audio using 'ffmpeg-normalize'")
                ffmpeg_normalize.add_media_file(normTemp, outFile.name)
                ffmpeg_normalize.run_normalization()
                os.remove(normTemp)
            else:
                cmd = ["ffmpeg", "-y", "-i", sourceFile]
                cmd += ["-map", "0:" + track["id"]]
                cmd += ["-c:a", track["convert"]["codec"]]
                if encodeOpts:
                    cmd += encodeOpts
                if len(Filter) > 0:
                    cmd += ["-af", ",".join(Filter)]
                cmd += [outFile.name]

                print("Converting Audio via ffmpeg")
                nightmode.ffmpegAudio(cmd, sourceFile, track["id"])


def importSettings(jsonPath: str):
    with open(jsonPath, "r") as f:
        return json.load(f)


if __name__ == "__main__":
    main()
