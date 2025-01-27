#!/usr/bin/python3
import pathlib
import json
import subprocess as sp


class Info:
    def __init__(self, sourceMKV: str):
        self.ffprobeInfo = dict(
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
                        "-show_frames",
                        "-read_intervals",
                        "%+#20",
                        sourceMKV,
                    ),
                    encoding="utf-8",
                )
            )
        )

    def getAudioTemplate(self, trackid: int) -> dict:
        if self.ffprobeInfo["streams"][trackid]["codec_type"] not in "audio":
            return {}
        streamInfo = self.ffprobeInfo["streams"][trackid]

        output = {}

        if streamInfo["codec_name"].lower() in "dts":
            output["extension"] = "dts"
            if "dts-hd" in streamInfo["profile"].lower():
                output["extension"] = "dtshd"
        elif streamInfo["codec_name"].lower() in "truehd":
            output["extension"] = "truehd"
        elif streamInfo["codec_name"].lower() in "ac3":
            output["extension"] = "ac3"
        else:
            output["extension"] = "mka"

        output["convert"] = False

        # For codecs we don't already know just remux it ffmpeg.
        if output["extension"] in "mka":
            output["convert"] = {}
            output["convert"]["codec"] = "copy"

        output["default"] = False
        output["id"] = trackid

        if streamInfo["tags"]["language"]:
            output["language"] = streamInfo["tags"]["language"]

        output["title"] = ""
        if streamInfo["channel_layout"].lower() in "stereo":
            output["title"] = "Stereo "
        else:
            output["title"] = streamInfo["channel_layout"][:3] + " "
            subType = "Surround "
            if "profile" in streamInfo:
                if "atmos" in streamInfo["profile"].lower():
                    subType = "Atmos "
                if "dts:x" in streamInfo["profile"].lower():
                    subType = "DTS:X "
            output["title"] += subType

        if output["extension"] == "mka":
            output["title"] += "({})".format(streamInfo["codec_name"].upper())
        else:
            output["title"] += "({})".format(output["extension"].upper())

        return output

    def getSubtitleTemplate(self, trackid: int) -> dict:
        if self.ffprobeInfo["streams"][trackid]["codec_type"].lower() not in "subtitle":
            return {}
        streamInfo = self.ffprobeInfo["streams"][trackid]

        output = {}
        if streamInfo["codec_name"].lower() in "hdmv_pgs_subtitle":
            output["extension"] = "sup"
        else:
            output["extension"] = "srt"

        output["sup2srt"] = False
        output["filter"] = False
        output["default"] = False
        output["id"] = trackid

        if streamInfo["tags"]["language"]:
            output["language"] = streamInfo["tags"]["language"]

        output["title"] = "{} Subtitles".format(output["language"].upper())

        if output["extension"] == "sup":
            output["title"] += " (PGS)"
        if output["extension"] == "srt":
            output["title"] += " (SRT)"

        return output


if __name__ == "__main__":
    import sys

    test = Info(sys.argv[1])
    print(json.dumps(test.ffprobeInfo["streams"], indent=2))

    # for i in range(len(test.ffprobeInfo["streams"])):
    #    print(json.dumps(test.getAudioTemplate(i), indent=2))
