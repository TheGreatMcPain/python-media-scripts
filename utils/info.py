#!/usr/bin/python3
import pathlib
import videoinfo
import json
import subprocess as sp


class Info:
    def __init__(self, jsonFile=None, sourceMKV = None):
        self.Data = None
        if jsonFile:
            with open(jsonFile, "r") as f:
                self.Data = json.load(f)
        elif sourceMKV:
            self.Data = self.generateTemplate(sourceMKV)

    def __str__(self):
        return json.dumps(self.Data)

    def __dir__(self):
        if self.Data:
            return self.Data
        return {}


    def generateTemplate(self, sourceMKV: str) -> dict:
        ffprobeInfo = dict(
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
        output = {}
        output["sourceFile"] = sourceMKV
        output["title"] = "Insert Title Here"
        output["outputFile"] = "Insert Name Here.mkv"

        output["video"] = self.getVideoTemplate(ffprobeInfo, sourceMKV)
        audio = []
        subs = []

        for i in range(len(ffprobeInfo["streams"])):
            template = self.getAudioTemplate(ffprobeInfo, i)
            if template != {}:
                audio.append(template)
        for i in range(len(ffprobeInfo["streams"])):
            template = self.getSubtitleTemplate(ffprobeInfo, i)
            if template != {}:
                subs.append(template)

        if len(audio) > 0:
            output["audio"] = audio
        if len(subs) > 0:
            output["subs"] = subs

        return output

    def getVideoTemplate(self, ffInfo: dict, inFile: str) -> dict:
        videoInfo = videoinfo.videoInfo(inFile)
        output = {}

        title = "{}x{}p{} ".format(
            videoInfo.Width, videoInfo.Height, videoInfo.FPS
        )
        hdrSpec = []
        if videoInfo.DolbyVision:
            hdrSpec.append("DV")
        if videoInfo.HDR10Plus:
            hdrSpec.append("HDR10+")
        elif videoInfo.HDR10:
            hdrSpec.append("HDR10")
        title += "/".join(hdrSpec)

        # We are always using HEVC anyways.
        output["title"] = title + " (HEVC)"

        output["language"] = "und"
        if "tags" in ffInfo["streams"][0]:
            tags = ffInfo["streams"][0]["tags"]
            if "language" in tags:
                output["language"] = tags["language"]

        output["output"] = "video.hevc"
        output["convert"] = True
        output["x265Opts"] = [
            "--preset",
            "medium",
            "--crf",
            "16",
            "--qcomp",
            "0.75",
            "--tune",
            "grain",
            "--output-depth",
            "10",
        ]
        output["vapoursynth"] = {
            "script": "vapoursynth-filter.py",
            "variables": {"coolValue": "yeet"},
        }

        mkvmergeOpts = []
        if "display_aspect_ratio" in ffInfo["streams"][0]:
            aspectRatio = ffInfo["streams"][0]["display_aspect_ratio"]
            aspectRatio = aspectRatio.replace(":", "/")
            mkvmergeOpts = ["--aspect-ratio", "0:{}".format(aspectRatio)]
        output["mkvmergeOpts"] = mkvmergeOpts

        return output

    def getAudioTemplate(self, ffInfo: dict, trackid: int) -> dict:
        if ffInfo["streams"][trackid]["codec_type"] not in "audio":
            return {}
        streamInfo = ffInfo["streams"][trackid]

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

    def getSubtitleTemplate(self, ffInfo, trackid: int) -> dict:
        if ffInfo["streams"][trackid]["codec_type"].lower() not in "subtitle":
            return {}
        streamInfo = ffInfo["streams"][trackid]

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

    test = Info(sourceMKV=sys.argv[1])
    print(test)
    # for i in range(len(test.ffprobeInfo["streams"])):
    #    print(json.dumps(test.getAudioTemplate(i), indent=2))
