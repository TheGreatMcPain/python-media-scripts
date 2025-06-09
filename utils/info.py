#!/usr/bin/python3
import json
import copy
import subprocess as sp
from pathlib import Path
from typing import Self

try:
    import videoinfo
except:
    from utils import videoinfo


class TrackInfo:
    def __init__(
        self,
        title: str = "",
        extension: str = ".bin",
        default: bool = False,
        trackId: int = -1,
        language: str = "und",
        sync: int = 0,
        index: int = -1,
    ):
        self.title = title
        self.extension: str = extension
        self.default: bool = default
        self.id: int = trackId
        self.language: str = language
        self.sync: int = sync
        self.index: int = index

    def getOutFile(self):
        return "{}-{}.{}".format(self.id, self.index, self.extension)


class SubtitleTrackInfo(TrackInfo):
    def __init__(
        self,
        title: str = "",
        extension: str = ".bin",
        default: bool = False,
        trackId: int = -1,
        language: str = "und",
        sync: int = 0,
        sup2srt: bool = False,
        srtFilter: bool = False,
        external: str = "",
    ):
        super().__init__(title, extension, default, trackId, language, sync)
        self.sup2srt = sup2srt
        self.srtFilter = srtFilter
        self.external: str = external
        self.sourceTrack: TrackInfo | None = None

        if external:
            if Path(external).exists():
                self.external = external

    def __iter__(self):
        yield "title", self.title
        yield "extension", self.extension
        yield "default", self.default
        yield "id", self.id
        yield "language", self.language
        if self.sync:
            yield "sync", self.sync
        yield "sup2srt", self.sup2srt
        yield "filter", self.srtFilter
        if self.external:
            yield "external", self.external

    def hasForcedFile(self):
        return Path(self.getForcedFile()).exists()

    def getForcedFile(self):
        return "forced-{}".format(self.getOutFile())


class AudioTrackInfo(TrackInfo):
    def __init__(
        self,
        title: str = "",
        extension: str = ".bin",
        default: bool = False,
        trackId: int = -1,
        language: str = "und",
        sync: int = 0,
        convert: dict = {},
    ):
        super().__init__(title, extension, default, trackId, language, sync)
        self.convert = convert

    def __iter__(self):
        yield "title", self.title
        yield "extension", self.extension
        yield "default", self.default
        yield "id", self.id
        yield "language", self.language
        if self.sync:
            yield "sync", self.sync
        if self.convert:
            yield "convert", self.convert
        else:
            yield "convert", False

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
        result.title = trackName + " (AAC)"
        result.extension = "m4a"
        result.convert = {"codec": "aac", "encodeOpts": ["-b:a", "256K"]}
        result.convert["filters"] = []
        if dynaudnorm:
            result.convert["filters"].append(dynAudNorm)
        result.convert["filters"].append(downmixStereo)
        result.convert["filters"].append(normalize)
        result.default = False

        return result


class VideoTrackInfo:
    def __init__(
        self,
        jsonData: dict = {},
        title: str = "",
        language: str = "und",
        output: str = "video.hevc",
        convert: bool = True,
        twoPass: bool = False,
        x265Opts: list[str] = [],
        vapoursynthScript: str = "",
        vapoursynthVars: dict = {},
        mkvmergeOpts: list[str] = [],
    ):
        self.title = title
        self.language = language
        self.output = output
        self.twoPass = twoPass
        self.convert = convert
        self.x265Opts = x265Opts
        self.vapoursynthScript = vapoursynthScript
        self.vapoursynthVars = vapoursynthVars
        self.mkvmergeOpts: list[str] = mkvmergeOpts

        if jsonData:
            vapoursynth = False
            if self.vapoursynthScript != "":
                vapoursynth = {}
                vapoursynth["script"] = self.vapoursynthScript
            if vapoursynth:
                if self.vapoursynthVars != {}:
                    vapoursynth["variables"] = self.vapoursynthVars
            self.title = jsonData["title"]
            self.language = jsonData["language"]
            self.output = jsonData["output"]
            self.convert = jsonData["convert"]
            if "2pass" in jsonData:
                self.twoPass = jsonData["2pass"]
            self.twoPass = twoPass
            self.x265Opts = jsonData["x265Opts"]
            if "vapoursynth" in jsonData:
                if "script" in jsonData["vapoursynth"]:
                    self.vapoursynthScript = jsonData["vapoursynth"]["script"]
                if "variables" in jsonData["vapoursynth"]:
                    self.vapoursynthVars = jsonData["vapoursynth"]["variables"]
            if "mkvmergeOpts" in jsonData:
                self.mkvmergeOpts = jsonData["mkvmergeOpts"]

    def __iter__(self):
        vapoursynth = {}
        if self.vapoursynthScript != "":
            vapoursynth["script"] = self.vapoursynthScript
        if vapoursynth:
            if self.vapoursynthVars != {}:
                vapoursynth["variables"] = self.vapoursynthVars
        yield "title", self.title
        yield "language", self.language
        yield "output", self.output
        yield "convert", self.convert
        yield "x265Opts", self.x265Opts
        if self.twoPass:
            yield "2pass", self.twoPass
        yield "vapoursynth", vapoursynth
        if self.mkvmergeOpts != []:
            yield "mkvmergeOpts", self.mkvmergeOpts


class Info:
    def __init__(self, jsonFile=None, sourceMKV=None, nightmode: bool = False):
        self.title: str = ""
        self.sourceMKV: str = ""
        self.outputFile: str = ""
        self.videoInfo: VideoTrackInfo
        self.audioInfo: list[AudioTrackInfo] = []
        self.subInfo: list[SubtitleTrackInfo] = []
        if jsonFile:
            jsonData: dict = json.loads(Path(jsonFile).read_text())
            self.sourceMKV = jsonData["sourceFile"]
            self.title = jsonData["title"]
            self.outputFile = jsonData["outputFile"]

            self.videoInfo = VideoTrackInfo(
                title=jsonData["video"]["title"],
                language=jsonData["video"]["language"],
                output=jsonData["video"]["output"],
                convert=jsonData["video"]["convert"],
            )
            if "2pass" in jsonData["video"]:
                self.videoInfo.twoPass = jsonData["video"]["2pass"]
            if "x265Opts" in jsonData["video"]:
                self.videoInfo.x265Opts = jsonData["video"]["x265Opts"]
            if "vapoursynth" in jsonData["video"]:
                vapoursynth = jsonData["video"]["vapoursynth"]
                if "script" in vapoursynth:
                    self.videoInfo.vapoursynthScript = vapoursynth["script"]
                if "variables" in vapoursynth:
                    self.videoInfo.vapoursynthVars = vapoursynth["variables"]
            if "mkvmergeOpts" in jsonData["video"]:
                self.videoInfo.mkvmergeOpts = jsonData["video"]["mkvmergeOpts"]

            if "audio" in jsonData:
                for i in range(len(jsonData["audio"])):
                    track = jsonData["audio"][i]
                    trackInfo = AudioTrackInfo(
                        title=track["title"],
                        extension=track["extension"],
                        default=track["default"],
                        trackId=track["id"],
                        language=track["language"],
                    )
                    if "sync" in track:
                        trackInfo.sync = track["sync"]
                    if "convert" in track:
                        if track["convert"]:
                            trackInfo.convert = track["convert"]
                    self.audioInfo.append(trackInfo)

            if "subs" in jsonData:
                for i in range(len(jsonData["subs"])):
                    track = jsonData["subs"][i]
                    trackInfo = SubtitleTrackInfo(
                        track["title"],
                        track["extension"],
                        track["default"],
                        track["id"],
                        track["language"],
                    )
                    if "sup2srt" in track:
                        trackInfo.sup2srt = track["sup2srt"]
                    if "filter" in track:
                        trackInfo.srtFilter = track["filter"]
                    if "sync" in track:
                        trackInfo.sync = track["sync"]
                    if "external" in track:
                        if track["external"]:
                            trackInfo.external = track["external"]
                    self.subInfo.append(trackInfo)

        elif sourceMKV:
            self.generateTemplate(sourceMKV, nightmode=nightmode)

        for i in range(len(self.audioInfo)):
            audioTrack: AudioTrackInfo = self.audioInfo[i]
            audioTrack.index = i
        for i in range(len(self.subInfo)):
            subTrack: SubtitleTrackInfo = self.subInfo[i]
            subTrack.index = i

            if not subTrack.sup2srt:
                continue
            for x in self.subInfo:
                if not x.sup2srt and x.id == subTrack.id:
                    subTrack.sourceTrack = x
                    break

    def __iter__(self):
        audio = []
        subs = []
        for audTrack in self.audioInfo:
            audio.append(dict(audTrack))
        for subTrack in self.subInfo:
            subs.append(dict(subTrack))
        yield "title", self.title
        yield "sourceFile", self.sourceMKV
        yield "outputFile", self.outputFile
        yield "video", dict(self.videoInfo)
        yield "audio", audio
        yield "subs", subs

    def __str__(self):
        return json.dumps(dict(self), indent=2)

    def generateTemplate(self, sourceMKV: str, nightmode: bool = False):
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
        self.sourceMKV = sourceMKV
        self.title = "Insert Title Here"
        if "tags" in ffprobeInfo["format"]:
            if "title" in ffprobeInfo["format"]["tags"]:
                self.title = ffprobeInfo["format"]["tags"]["title"]
        self.outputFile = "Insert Name Here.mkv"

        self.videoInfo = self.getVideoTemplate(ffprobeInfo, sourceMKV)

        for i in range(len(ffprobeInfo["streams"])):
            template = self.getAudioTemplate(ffprobeInfo, i)
            if template:
                self.audioInfo.append(template)
                if nightmode:
                    nightmode = False
                    self.audioInfo.append(
                        template.nightmodeTemplate(
                            "Stereo 'downmix'",
                            downmixCenter=2.0,
                            downmixLFE=0.707,
                            downmixSurrounds=0.707,
                            dynaudnorm=False,
                        )
                    )
                    self.audioInfo.append(
                        template.nightmodeTemplate(
                            "Stereo 'dynaudnorm,downmix'",
                            downmixCenter=2.0,
                            downmixLFE=0.707,
                            downmixSurrounds=0.707,
                            dynaudnorm=True,
                        )
                    )
                    self.audioInfo.append(
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
            if template:
                self.subInfo.append(template)

    def getVideoTemplate(self, ffInfo: dict, inFile: str) -> VideoTrackInfo:
        videoInfo = videoinfo.videoInfo(inFile)
        output = VideoTrackInfo()

        title = ["{}x{}p{}".format(videoInfo.Width, videoInfo.Height, videoInfo.FPS)]
        hdrSpec = []
        if videoInfo.DolbyVision:
            hdrSpec.append("DV")
        if videoInfo.HDR10Plus:
            hdrSpec.append("HDR10+")
        elif videoInfo.HDR10:
            hdrSpec.append("HDR10")
        if hdrSpec:
            title.append("/".join(hdrSpec))

        # We are always using HEVC anyways.
        title.append("(HEVC)")
        output.title = " ".join(title)

        output.language = "und"
        if "tags" in ffInfo["streams"][0]:
            tags = ffInfo["streams"][0]["tags"]
            if "language" in tags:
                output.language = tags["language"]

        output.output = "video.hevc"
        output.convert = True
        output.x265Opts = [
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
        output.vapoursynthScript = "vapoursynth-filter.py"
        output.vapoursynthVars = {"coolValue": "yeet"}

        if "display_aspect_ratio" in ffInfo["streams"][0]:
            aspectRatio = ffInfo["streams"][0]["display_aspect_ratio"]
            aspectRatio = aspectRatio.replace(":", "/")
            output.mkvmergeOpts = ["--aspect-ratio", "0:{}".format(aspectRatio)]

        return output

    def getAudioTemplate(self, ffInfo: dict, trackid: int) -> AudioTrackInfo | None:
        if ffInfo["streams"][trackid]["codec_type"] not in "audio":
            return None
        streamInfo = ffInfo["streams"][trackid]
        output = AudioTrackInfo()

        if streamInfo["codec_name"].lower() in "dts":
            output.extension = "dts"
            if "dts-hd" in streamInfo["profile"].lower():
                output.extension = "dtshd"
        elif streamInfo["codec_name"].lower() in "truehd":
            output.extension = "truehd"
        elif streamInfo["codec_name"].lower() in "ac3":
            output.extension = "ac3"
        else:
            output.extension = "mka"

        output.convert = {}

        # For codecs we don't already know just remux it ffmpeg.
        if output.extension in "mka":
            output.convert = {}
            output.convert["codec"] = "copy"

        output.default = False
        output.id = trackid

        if streamInfo["tags"]["language"]:
            output.language = streamInfo["tags"]["language"]

        title = []
        if streamInfo["channels"] == 1:
            title.append("Mono")
        elif streamInfo["channels"] == 2:
            title.append("Stereo")
        else:
            title.append(streamInfo["channel_layout"][:3])
            subType = "Surround"
            if "profile" in streamInfo:
                if "atmos" in streamInfo["profile"].lower():
                    subType = "Atmos"
                if "dts:x" in streamInfo["profile"].lower():
                    subType = "DTS:X"
            title.append(subType)

        if output.extension == "mka":
            title.append("({})".format(streamInfo["codec_name"].upper()))
        else:
            title.append("({})".format(output.extension.upper()))

        output.title = " ".join(title)

        return output

    def getSubtitleTemplate(self, ffInfo, trackid: int) -> SubtitleTrackInfo | None:
        if ffInfo["streams"][trackid]["codec_type"].lower() not in "subtitle":
            return None
        streamInfo = ffInfo["streams"][trackid]
        output = SubtitleTrackInfo()

        if streamInfo["codec_name"].lower() in "hdmv_pgs_subtitle":
            output.extension = "sup"
        else:
            output.extension = "srt"

        output.sup2srt = False
        output.srtFilter = False
        output.default = False
        output.id = trackid

        if streamInfo["tags"]["language"]:
            output.language = streamInfo["tags"]["language"]

        output.title = "{} Subtitles".format(output.language.upper())

        if output.extension == "sup":
            output.title += " (PGS)"
        if output.extension == "srt":
            output.title += " (SRT)"

        return output

    def filterLanguages(self, audLangs: list[str] = [], subLangs: list[str] = []):
        if len(audLangs) > 0:
            newList = []
            for track in self.audioInfo:
                if track.language in audLangs:
                    newList.append(track)
            self.audioInfo = newList

        if len(subLangs) > 0:
            newList = []
            for track in self.subInfo:
                if track.language in subLangs:
                    newList.append(track)
            self.subInfo = newList


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
