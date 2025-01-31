#!/usr/bin/env python3
import sys
import os
import subprocess as sp
import json

OUTFILE = "source.mkv"


def main():
    selection = "n"

    # Data is stored in a json file with the same name of this script.
    JSONFILE = os.path.basename(__file__).split(os.extsep)[0] + ".json"

    if os.path.isfile(JSONFILE):
        print(JSONFILE, "found.")
        selection = input("Resume with it? (y or n): ")
    if selection == "y":
        with open(JSONFILE, "r") as f:
            blurayInfo = json.load(f)
    else:
        if len(sys.argv) <= 1:
            print(sys.argv[0], "Requires path to a BluRay.")
            exit(1)
        blurayRoot = sys.argv[1]
        indexBdmv = os.path.join(blurayRoot, "BDMV/index.bdmv")
        if not os.path.isfile(indexBdmv):
            print(blurayRoot, "is not a BluRay Directory.")
            exit(1)
        blurayInfo = getBlurayInfo(blurayRoot, JSONFILE)
    batchCreateMKVs(blurayInfo["blurayDir"], blurayInfo["titles"], OUTFILE)


def batchCreateMKVs(BluRayDir, titles, outFile):
    counter = 0
    for title in titles:
        print()
        print(counter, "out of", len(titles), "done")
        fileName = title["filename"]
        inFile = getBluRayFilePath(BluRayDir, fileName)
        if inFile == "":
            print("Oof!! Something must of broke!")
            exit(1)
        if "n" in title["main"]:
            if not os.path.isdir("extras"):
                os.mkdir("extras")
            output = os.path.join("extras", title["folder"], outFile)
        else:
            output = os.path.join(title["folder"], outFile)

        cmd = ["mkvmerge", "--output", output, inFile]

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


def getBluRayFilePath(BluRayDir, fileName):
    """
    Returns that full path of a m2ts/mpls file.
    """
    ext = fileName.split(".")[-1]

    filePath = ""
    if "m2ts" in ext:
        filePath = os.path.join(BluRayDir, "BDMV/STREAM", fileName)
    if "mpls" in ext:
        filePath = os.path.join(BluRayDir, "BDMV/PLAYLIST", fileName)

    return filePath


def titleExists(BluRayDir, fileName):
    """
    Checks if a file exists in the BluRay.
    """
    ext = fileName.split(".")[-1]
    if ext not in ["m2ts", "mpls"]:
        print(ext, "Is not a BluRay file extention.")
        return False

    filePath = getBluRayFilePath(BluRayDir, fileName)

    if os.path.isfile(filePath):
        return True
    else:
        return False


def getBlurayInfo(BluRayDir, jsonFile):
    """
    Asks that user for information on a BluRay directory,
    and will export create a json file with the infomation.
    """
    blurayInfo = {}
    blurayInfo["blurayDir"] = BluRayDir
    titles = []

    print("BluRay Root:", BluRayDir)
    while True:
        print()
        title = {}
        print("Type filename (Ex: 00800.mpls or 00510.m2ts) ", end="")
        fileName = input("(Type 'done' if finished): ")
        if "done" in fileName:
            break
        if not titleExists(BluRayDir, fileName):
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
        title["filename"] = fileName
        titles.append(title)
    blurayInfo["titles"] = titles
    with open(jsonFile, "w") as f:
        f.write(json.dumps(blurayInfo, indent=4))
    return blurayInfo


if __name__ == "__main__":
    main()
