#!/usr/bin/env python3
import xml.etree.cElementTree as ET
import json
import os
import subprocess as sp

# GLOBALS
SOURCE = 'source.mkv'
CHAPJSON = 'chapNames.json'


def main():
    # Get List of folders
    dirs = getDirsMkvs(SOURCE)
    # Ask the user for chapter titles
    if os.path.isfile(CHAPJSON):
        print(CHAPJSON, " was found.")
        option = input("Read chapter titles from " + CHAPJSON + " (y or n): ")
        while option not in ('y', 'n'):
            option = input("Invalid option try again: ")
        if 'y' == option:
            with open(CHAPJSON, 'r') as f:
                titles = json.load(f)
        elif 'n' == option:
            titles = getChapterTitles(dirs)
            with open(CHAPJSON, 'w') as f:
                f.write(json.dumps(titles, indent=4))
    else:
        titles = getChapterTitles(dirs)
        with open(CHAPJSON, 'w') as f:
            f.write(json.dumps(titles, indent=4))
    # Create a mkv from the other mkvs
    createMKV(dirs, SOURCE, SOURCE)
    # Update chapter names.
    extractChapters(SOURCE)
    applyCustomTitles(titles)
    applyNewChapters(SOURCE)
    for x in ['chapters-new.xml', 'chapters.xml']:
        os.remove(x)


def getDirsMkvs(sourceFile):
    """
    Returns a list of directories, within the current directory,
    that contain 'sourceFile'.
    """
    lsdir = os.listdir('.')
    dirs = []
    for x in lsdir:
        if os.path.isdir(x):
            mkvpath = os.path.join(x, sourceFile)
            if os.path.isfile(mkvpath):
                dirs.append(x)
    return dirs


def getChapterTitles(dirs):
    """
    Returns a list of chapter names created by the user.
    """
    titles = []
    for folder in dirs:
        print("\nThe folder name is:", folder)
        titles.append(str(input("Chapter Title?: ")))
    return titles


def createMKV(dirs, sourceFile, outFile):
    """
    Creates a appended mkv via mkvmerge.
    """
    cmd = ['mkvmerge', '--output', outFile]

    cmd.append(os.path.join(dirs[0], sourceFile))

    for folder in dirs[1:]:
        mkvfile = os.path.join(folder, sourceFile)
        cmd.append('+' + mkvfile)

    cmd += ['--generate-chapters', 'when-appending']

    for x in cmd:
        print(x, end=' ')
    print()

    p = sp.Popen(cmd)
    p.communicate()


def extractChapters(sourceFile):
    """
    Extracts 'chapters.xml' from 'sourceFile' via 'mkvextract'.
    """
    cmd = ['mkvextract', sourceFile, 'chapters', 'chapters.xml']
    p = sp.Popen(cmd)
    p.communicate()


def applyCustomTitles(titles):
    """
    Creates 'chapters-new.xml' which has the user created chapter names.
    """
    # Read chapters.xml into xmlstr.
    with open('chapters.xml', 'rb') as f:
        xmlstr = f.read()
    # Get DOCTYPE entry from xmlstr
    for x in xmlstr.split(b'\n'):
        if b'DOCTYPE' in x:
            doctype = x
            break
    # Parse XML data from xmlstr.
    root = ET.fromstring(xmlstr)
    # Modify chapter names.
    index = 0
    for chapStr in root.iter('ChapterString'):
        chapStr.text = titles[index]
        index += 1

    # Generate list of strings from new XML data.
    newxmllist = ET.tostring(root, encoding='utf8', method='xml').split(b'\n')
    with open('chapters-new.xml', 'wb') as f:
        # Write xml_definition to file
        f.write(newxmllist[0] + b'\n')
        # Write DOCTYPE to file
        f.write(doctype + b'\n')
        # Dump the rest to file
        for line in newxmllist[1:]:
            line += b'\n'
            f.write(line)


def applyNewChapters(sourceFile):
    """
    Applies 'chapters-new.xml' to 'sourceFile' via 'mkvpropedit'.
    """
    cmd = ['mkvpropedit', sourceFile, '--chapters', 'chapters-new.xml']
    p = sp.Popen(cmd)
    p.communicate()


if __name__ == '__main__':
    main()
