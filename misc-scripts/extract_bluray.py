#!/usr/bin/env python3
import argparse
from pathlib import Path
import subprocess as sp
import json
import shutil


def main():
    if not shutil.which("mkvmerge"):
        print("Dependency 'mkvmerge' not found! Is MKVToolNix installed?")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bluray-directory",
        "-d",
        dest="blurayDirs",
        action="extend",
        nargs="+",
        help="Path to Bluray file structure.",
        type=str,
        default=[],
    )
    parser.add_argument(
        "--config-file",
        "-c",
        dest="jsonFile",
        help="Path to '.json' config file.",
        type=str,
        default=str(Path(__file__).with_suffix(".json")),
    )
    parser.add_argument(
        "--output-filename",
        "-o",
        dest="outFile",
        help="Name of '.mkv' files",
        type=str,
        default="source.mkv",
    )
    args = parser.parse_args()
    jsonFile = Path(args.jsonFile)
    blurayInfoList = []

    selection = "n"
    if jsonFile.exists():
        print(jsonFile, "found.")
        selection = input("Resume with it? (y or n): ")

    if selection == "y":
        blurayInfoList = filterBlurayInfo(jsonFile)

        for blurayRoot in args.blurayDirs:
            blurayPath = Path(blurayRoot)

            if not isBluray(blurayPath):
                print(blurayPath, "is not a BluRay Directory.")
                parser.print_usage()
                exit(1)

            if str(blurayPath) not in [x["blurayDir"] for x in blurayInfoList]:
                selection = input(
                    "Add {} to {}. (y or n): ".format(blurayPath, jsonFile)
                )
            if selection == "y":
                blurayInfo = getBlurayInfo(blurayPath)
                blurayInfoList.append(blurayInfo)
                jsonFile.write_text(json.dumps(blurayInfoList))
    else:
        if len(args.blurayDirs) == 0:
            print(
                jsonFile.relative_to(Path.cwd()),
                "not found!",
                "Bluray directory required.",
            )
            parser.print_usage()
            exit(1)

        for blurayRoot in args.blurayDirs:
            blurayPath = Path(blurayRoot)

            if not isBluray(blurayPath):
                print(blurayPath, "is not a BluRay Directory.")
                parser.print_usage()
                exit(1)

            blurayInfo = getBlurayInfo(blurayPath)
            blurayInfoList.append(blurayInfo)
            jsonFile.write_text(json.dumps(blurayInfoList))

    for blurayInfo in blurayInfoList:
        batchCreateMKVs(blurayInfo["blurayDir"], blurayInfo["titles"], args.outFile)


def isBluray(blurayPath: Path) -> bool:
    return blurayPath.joinpath("BDMV", "index.bdmv").exists()


def filterBlurayInfo(jsonFile: Path) -> list[dict]:
    if not jsonFile.exists():
        return []

    newInfo = []
    blurayInfo = json.loads(jsonFile.read_text())
    if type(blurayInfo) == dict:
        blurayInfo = [blurayInfo]

    for root in blurayInfo:
        blurayDir = Path(root["blurayDir"])
        if not blurayDir.exists():
            print(blurayDir, "doesn't exist! skipping...")
            continue
        if not isBluray(blurayDir):
            print(blurayDir, "isn't a Bluray. skipping...")
            continue

        titles = []
        for title in root["titles"]:
            blurayFile = getBluRayFilePath(root["blurayDir"], title["filename"])
            if not blurayFile.exists():
                print(
                    blurayFile,
                    "doesn't exist! Bluray. skipping bluray...",
                )
                print("Bluray folder is either incomplete or incorrect.\n")
                titles = []
                break
            titles.append(title)

        if len(titles) > 0:
            newInfo.append(root)

    return newInfo


def batchCreateMKVs(BluRayDir, titles, outFile):
    counter = 0
    for title in titles:
        print()
        print(counter, "out of", len(titles), "done")
        fileName = title["filename"]
        inFile: Path = getBluRayFilePath(BluRayDir, fileName)
        if not inFile.exists():
            print("Oof!! Something must of broke!")
            exit(1)
        if "n" in title["main"]:
            extrasPath = Path("extras")
            if not extrasPath.is_dir():
                extrasPath.mkdir()
            output = extrasPath.joinpath(title["folder"], outFile)
        else:
            output = Path(title["folder"], outFile)

        if output.exists():
            print(output, "exists!! skipping...")
            continue
        outputTemp = output.with_name("temp-" + outFile)

        cmd = ["mkvmerge", "--output", str(outputTemp), str(inFile)]

        print("Running: ", end="")
        for x in cmd:
            print(x, end=" ")
        print()
        p = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.DEVNULL, universal_newlines=True)
        if not p.stdout:
            print("Oof!! Something must of broke!")
            exit(1)

        for line in p.stdout:
            line = line.rstrip()
            if "Progress:" in line:
                print(f"{line}\r", end="")
                # Clean the rest of the line.
                print("\033[K", end="")
        counter += 1
        outputTemp.replace(output)


def getBluRayFilePath(BluRayPath: Path, fileName: Path) -> Path:
    BluRayPath = Path(BluRayPath)
    fileName = Path(fileName)
    """
    Returns that full path of a m2ts/mpls file.
    """
    ext = fileName.suffix

    filePath = BluRayPath.joinpath("BDMV")
    if ".m2ts" in ext:
        filePath = filePath.joinpath(filePath, Path("STREAM"), fileName)
    if ".mpls" in ext:
        filePath = filePath.joinpath(filePath, Path("PLAYLIST"), fileName)

    return filePath


def titleExists(BluRayPath: Path, fileName: Path):
    BluRayPath = Path(BluRayPath)
    fileName = Path(fileName)
    """
    Checks if a file exists in the BluRay.
    """
    ext = fileName.suffix
    if ext not in [".m2ts", ".mpls"]:
        print(ext, "Is not a BluRay file extention.")
        return False

    return getBluRayFilePath(BluRayPath, fileName).exists()


def getBlurayInfo(BluRayPath: Path):
    """
    Asks that user for information on a BluRay directory,
    and will export create a json file with the infomation.
    """
    blurayInfo = {}
    blurayInfo["blurayDir"] = str(BluRayPath)
    titles = []

    print("BluRay Root:", BluRayPath)
    while True:
        print()
        title = {}
        print("Type filename (Ex: 00800.mpls or 00510.m2ts) ", end="")
        fileName = input("(Type 'done' if finished): ")
        if "done" in fileName:
            break
        if not titleExists(BluRayPath, Path(fileName)):
            print(fileName, "does not exist.")
            continue
        extra = input("Is this an extra feature (y or n): ")
        while extra.lower() not in ["y", "n"]:
            print("Invalid input: must be 'y' or 'n'")
            extra = input("Is this an extra feature (y or n): ")
        if "y" in extra.lower():
            title["main"] = "no"
            folder = input("Type the folder name for this title: ")
            title["folder"] = folder
        else:
            title["main"] = "yes"
            folder = input("Type the folder name for this title: ")
            title["folder"] = folder
        title["filename"] = str(fileName)
        titles.append(title)
    blurayInfo["titles"] = titles
    return blurayInfo


if __name__ == "__main__":
    main()
