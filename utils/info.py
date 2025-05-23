#!/usr/bin/python3
import json
import copy
import subprocess as sp
from typing import Self

try:
    import videoinfo
except:
    from utils import videoinfo


class TrackInfo:
    def __init__(self, newData={}):
        self.Data: dict = newData
        self.Index: int = -1
        self.forcedFile = None
        self.supSourceFile = None

    def __str__(self):
        return json.dumps(self.Data, indent=2)

    def __contains__(self, value) -> bool:
        return value in self.Data

    def __getitem__(self, value: str):
        return self.Data[value]

    def setForcedFile(self, value: str):
        self.forcedFile = value

    def getForcedFile(self):
        return self.forcedFile

    def setSupSourceFile(self, track: Self):
        self.supSourceFile = track.getOutFile()

    def getSupSourceFile(self):
        return self.supSourceFile

    def getOutFile(self):
        if "external" in self.Data:
            if self.Data["external"]:
                return ""
        return "{}-{}.{}".format(self.Data["id"], self.Index, self.Data["extension"])

    def nightmodeTemplate(
        self,
        trackName: str,
        downmixCenter: float = 2.0,
        downmixLFE: float = 0.0,
        downmixSurrounds: float = 0.707,
        dynaudnorm: bool = False,
    ) -> Self:
        result = copy.deepcopy(self)
        dynAudNorm = {"ffmpeg": "dynaudnorm=compress=27.0:gausssize=53"}
        normalize = {
            "normalize": {
                "loudness_range_target": "keep",
                "target_level": -23,
            }
        }
        downmixStereo = {
            "downmixStereo": {
                "center": downmixCenter,
                "lfe": downmixLFE,
                "surrounds": downmixSurrounds,
            }
        }
        result.Data["title"] = trackName + " (AAC)"
        result.Data["extension"] = "m4a"
        result.Data["convert"] = {"codec": "aac", "encodeOpts": ["-b:a", "256K"]}
        result.Data["convert"]["filters"] = []
        if dynaudnorm:
            result.Data["convert"]["filters"].append(dynAudNorm)
        result.Data["convert"]["filters"].append(downmixStereo)
        result.Data["convert"]["filters"].append(normalize)
        result.Data["default"] = False

        return result


class Info:
    def __init__(self, jsonFile=None, sourceMKV=None, nightmode: bool = False):
        self.Data = {}
        if jsonFile:
            with open(jsonFile, "r") as f:
                self.Data = json.load(f)
                if "audio" in self.Data:
                    for i in range(len(self.Data["audio"])):
                        self.Data["audio"][i] = TrackInfo(self.Data["audio"][i])
                if "subs" in self.Data:
                    for i in range(len(self.Data["subs"])):
                        self.Data["subs"][i] = TrackInfo(self.Data["subs"][i])
        elif sourceMKV:
            self.Data = self.generateTemplate(sourceMKV, nightmode=nightmode)

        if "audio" in self.Data:
            for i in range(len(self.Data["audio"])):
                audioTrack = self.Data["audio"][i]
                audioTrack.Index = i
        if "subs" in self.Data:
            for i in range(len(self.Data["subs"])):
                subtitleTrack = self.Data["subs"][i]
                subtitleTrack.Index = i

            for track in self.Data["subs"]:
                if "sup2srt" not in track:
                    continue
                if not track["sup2srt"]:
                    continue
                for x in self.Data["subs"]:
                    if "sup2srt" not in x and str(x["id"]) == str(track["id"]):
                        track.setSupSourceFile(x)
                        break
                    if not x["sup2srt"] and str(x["id"]) == str(track["id"]):
                        track.setSupSourceFile(x)
                        break

    def __str__(self):
        printData = copy.deepcopy(self.Data)
        if "audio" in printData:
            for i in range(len(printData["audio"])):
                printData["audio"][i] = printData["audio"][i].Data
        if "subs" in printData:
            for i in range(len(printData["subs"])):
                printData["subs"][i] = printData["subs"][i].Data
        return json.dumps(printData, indent=2)

    def __contains__(self, value) -> bool:
        return value in self.Data

    def __getitem__(self, value: str):
        return self.Data[value]

    def generateTemplate(self, sourceMKV: str, nightmode: bool = False) -> dict:
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
        if "tags" in ffprobeInfo["format"]:
            if "title" in ffprobeInfo["format"]["tags"]:
                output["title"] = ffprobeInfo["format"]["tags"]["title"]
        output["outputFile"] = "Insert Name Here.mkv"

        output["video"] = self.getVideoTemplate(ffprobeInfo, sourceMKV)
        audio = []
        subs = []

        for i in range(len(ffprobeInfo["streams"])):
            template = self.getAudioTemplate(ffprobeInfo, i)
            if template.Data != {}:
                audio.append(template)
                if nightmode:
                    nightmode = False
                    audio.append(
                        template.nightmodeTemplate(
                            "Stereo 'downmix'",
                            downmixCenter=2.0,
                            downmixLFE=0.707,
                            downmixSurrounds=0.707,
                            dynaudnorm=False,
                        )
                    )
                    audio.append(
                        template.nightmodeTemplate(
                            "Stereo 'dynaudnorm,downmix'",
                            downmixCenter=2.0,
                            downmixLFE=0.707,
                            downmixSurrounds=0.707,
                            dynaudnorm=True,
                        )
                    )
                    audio.append(
                        template.nightmodeTemplate(
                            "Stereo 'dynaudnorm,downmix-nolfe'",
                            downmixCenter=2.0,
                            downmixLFE=0.0,
                            downmixSurrounds=0.707,
                            dynaudnorm=True,
                        )
                    )
        for i in range(len(ffprobeInfo["streams"])):
            template = self.getSubtitleTemplate(ffprobeInfo, i)
            if template.Data != {}:
                subs.append(template)

        if len(audio) > 0:
            output["audio"] = audio
        if len(subs) > 0:
            output["subs"] = subs

        return output

    def getVideoTemplate(self, ffInfo: dict, inFile: str) -> dict:
        videoInfo = videoinfo.videoInfo(inFile)
        output = {}

        title = "{}x{}p{} ".format(videoInfo.Width, videoInfo.Height, videoInfo.FPS)
        hdrSpec = []
        if videoInfo.DolbyVision:
            hdrSpec.append("DV")
        if videoInfo.HDR10Plus:
            hdrSpec.append("HDR10+")
        elif videoInfo.HDR10:
            hdrSpec.append("HDR10")
        title += "/".join(hdrSpec) + " "

        # We are always using HEVC anyways.
        output["title"] = title + "(HEVC)"

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

    def getAudioTemplate(self, ffInfo: dict, trackid: int) -> TrackInfo:
        if ffInfo["streams"][trackid]["codec_type"] not in "audio":
            return TrackInfo()
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
        if streamInfo["channels"] == 1:
            output["title"] = "Mono "
        elif streamInfo["channels"] == 2:
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

        return TrackInfo(output)

    def getSubtitleTemplate(self, ffInfo, trackid: int) -> TrackInfo:
        if ffInfo["streams"][trackid]["codec_type"].lower() not in "subtitle":
            return TrackInfo()
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

        return TrackInfo(output)

    def filterLanguages(self, audLangs: list[str] = [], subLangs: list[str] = []):
        if len(audLangs) > 0:
            if "audio" in self.Data:
                newList = []
                for track in self.Data["audio"]:
                    if track["language"] in audLangs:
                        newList.append(track)
                self.Data["audio"] = newList

        if len(subLangs) > 0:
            if "subs" in self.Data:
                newList = []
                for track in self.Data["subs"]:
                    if track["language"] in subLangs:
                        newList.append(track)
                self.Data["subs"] = newList


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="info", description="Batchconvert info.json generator"
    )
    parser.add_argument("sourceFile")
    parser.add_argument("--nightmode", action=argparse.BooleanOptionalAction)
    parser.add_argument(
        "--audio-languages",
        dest="audLangs",
        action="extend",
        nargs="+",
        type=str,
        help="List of audio languages to keep.",
        default=[],
    )
    parser.add_argument(
        "--sub-languages",
        action="extend",
        dest="subLangs",
        nargs="+",
        type=str,
        help="List of subtitle languages to keep.",
        default=[],
    )
    args = parser.parse_args()
    test = Info(sourceMKV=args.sourceFile, nightmode=args.nightmode)
    test.filterLanguages(audLangs=args.audLangs, subLangs=args.subLangs)

    print(test)
