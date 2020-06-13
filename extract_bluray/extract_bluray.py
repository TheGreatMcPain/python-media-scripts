#!/usr/bin/env python3
import sys
import os
import subprocess as sp
import json

OUTFILE = 'source.mkv'
JSONFILE = 'bluray_data.json'


def main():
    selection = 'n'
    if os.path.isfile(JSONFILE):
        print(JSONFILE, "found.")
        selection = input("Resume with it? (y or n): ")
    if selection == 'y':
        with open(JSONFILE, 'r') as f:
            blurayInfo = json.load(f)
    else:
        if len(sys.argv) <= 1:
            print(sys.argv[0], "Requires path to a BluRay.")
            exit(1)
        blurayRoot = sys.argv[1]
        indexBdmv = os.path.join(blurayRoot, 'BDMV/index.bdmv')
        if not os.path.isfile(indexBdmv):
            print(blurayRoot, "is not a BluRay Directory.")
            exit(1)
        blurayInfo = getBlurayInfo(blurayRoot, JSONFILE)
        print(json.dumps(blurayInfo, indent=4))
    batchCreateMKVs(blurayInfo['blurayDir'], blurayInfo['titles'], OUTFILE)


def batchCreateMKVs(BluRayDir, titles, outFile):
    if not os.path.isdir("extras"):
        os.mkdir("extras")
    if not os.path.isdir("main"):
        os.mkdir("main")
    counter = 0
    for title in titles:
        print()
        print(counter, "out of", len(titles), "done")
        fileName = title['filename']
        inFile = getBluRayFilePath(BluRayDir, fileName)
        if 'n' in title['main']:
            output = os.path.join('extras', title['folder'], outFile)
        else:
            output = os.path.join(title['folder'], outFile)

        cmd = ['mkvmerge', '--output', output, inFile]

        print("Running: ", end='')
        for x in cmd:
            print(x, end=' ')
        print()
        p = sp.Popen(cmd,
                     stdout=sp.PIPE,
                     stderr=sp.DEVNULL,
                     universal_newlines=True)
        for line in p.stdout:
            line = line.rstrip()
            if 'Progress:' in line:
                print(f'{line}\r', end='')
                # Clean the rest of the line.
                print("\033[K", end='')
        counter += 1


def getBluRayFilePath(BluRayDir, fileName):
    """
    Returns that full path of a m2ts/mpls file.
    """
    ext = fileName.split('.')[-1]
    if 'm2ts' in ext:
        filePath = os.path.join(BluRayDir, "BDMV/STREAMS", fileName)
    if 'mpls' in ext:
        filePath = os.path.join(BluRayDir, "BDMV/PLAYLIST", fileName)

    return filePath


def titleExists(BluRayDir, fileName):
    """
    Checks if a file exists in the BluRay.
    """
    ext = fileName.split('.')[-1]
    if ext not in ['m2ts', 'mpls']:
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
    blurayInfo['blurayDir'] = BluRayDir
    titles = []
    mainBool = False

    print("BluRay Root:", BluRayDir)
    while True:
        print()
        title = {}
        print("Type filename (Ex: 00800.mpls or 00510.m2ts) ", end='')
        fileName = input("(Type 'done' if finished): ")
        if 'done' in fileName:
            break
        if not titleExists(BluRayDir, fileName):
            print(fileName, "does not exist.")
            continue
        main = 'n'
        if not mainBool:
            main = input("Is this the main title (y or n): ")
        if 'y' in main:
            mainBool = True
            title['main'] = 'yes'
            title['folder'] = 'main'
        else:
            title['main'] = 'no'
            folder = input("Type the folder name for these title: ")
            title['folder'] = folder
        title['filename'] = fileName
        titles.append(title)
    blurayInfo['titles'] = titles
    with open(jsonFile, 'w') as f:
        f.write(json.dumps(blurayInfo, indent=4))
    return blurayInfo


if __name__ == "__main__":
    main()
