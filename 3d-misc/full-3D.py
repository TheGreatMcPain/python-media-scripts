#!/usr/bin/env python3
import os
import subprocess as sp
import xml.etree.cElementTree as ET
import sys

# Globals
JAVA = 'java'
BDSUP2SUB = '~/.local/share/bdsup2sub/BDSup2Sub.jar'


def main():
    if len(sys.argv) < 4:
        print("Usage:", sys.argv[0], "<inFolder> <outLeft.sup> <outRight.sup>")
        exit(1)

    args = sys.argv[0:]
    BDXML = args[1]
    outLeftSup = args[2]
    outRightSup = args[3]

    os.chdir(BDXML)

    print("Creating Left, and Right BDXMLs")
    output = make3DXML('Output.xml')
    numSubs = output['numSubs']
    numWarn = output['numWarn']
    leftRoot = output['leftRoot']
    rightRoot = output['rightRoot']
    left = ET.tostring(leftRoot, encoding="utf8", method="xml")
    right = ET.tostring(rightRoot, encoding="utf8", method="xml")

    with open('Output_left.xml', 'wb') as f:
        f.write(left)
    with open('Output_right.xml', 'wb') as f:
        f.write(right)

    os.chdir('..')

    print()
    print("Creating", outLeftSup)
    convertXMLtoSup(os.path.join(BDXML, 'Output_left.xml'), outLeftSup)
    print("Creating", outRightSup)
    convertXMLtoSup(os.path.join(BDXML, 'Output_right.xml'), outRightSup)

    print()
    print("Input file: " + os.path.join(BDXML, 'Output.xml'))
    print("Stereoscopy mode: Full-3D (as 2 independent files)")
    print("Number of subtitles processed: " + str(numSubs))
    print("Number of warnings: " + str(numWarn))


def convertXMLtoSup(inXML, outSup):
    cmd = [
        JAVA, '-jar',
        os.path.expanduser(BDSUP2SUB), '--fps-target', 'keep', '--output',
        outSup, inXML
    ]
    p = sp.Popen(cmd, stderr=sp.DEVNULL, stdout=sp.DEVNULL)
    p.communicate()


def make3DXML(xmlFile):
    """
    Takes in an XMl tree from 'ET.parse' and outputs
    a dictionary containing 'numSubs', 'numWarn', 'leftRoot', and 'rightRoot'
    (based on the ConvertXMLtoFull3D function from BD3D2MK3D)
    """
    inTree = ET.parse(xmlFile)
    leftTree = ET.parse(xmlFile)
    rightTree = ET.parse(xmlFile)
    inRoot = inTree.getroot()
    leftRoot = leftTree.getroot()
    rightRoot = rightTree.getroot()

    inList = list(inRoot.iter('Graphic'))
    leftList = list(leftRoot.iter('Graphic'))
    rightList = list(rightRoot.iter('Graphic'))

    framewidth = 1920
    frameheight = 1080

    numSubs = 0
    numWarn = 0

    def modifyAttrib(attrib, x, y, originalDepth):
        attrib['X'] = str(x)
        attrib['Y'] = str(y)
        if attrib['Depth']:
            attrib.pop('Depth')
        attrib['OriginalDepth'] = str(originalDepth)

    for x in inList:
        index = inList.index(x)
        numSubs += 1
        attrib = x.attrib
        width = int(attrib['Width'])
        height = int(attrib['Height'])
        x = int(attrib['X'])
        y = int(attrib['Y'])
        if attrib['Depth']:
            originalDepth = int(attrib['Depth'])
        else:
            originalDepth = 0

        # Workaround for malformed subtitles as found on Amphibious 3D
        if width == framewidth and x < 0:
            x = 0
        if height == frameheight and y < 0:
            y = 0

        depth = originalDepth

        if (width < framewidth) and (width + (abs(depth / 2)) > framewidth):
            newdepth = (framewidth - width) * 2
            if depth < 0:
                newdepth = newdepth * -1
            print("Warning: Subtitle " + numSubs + ": The depth (" + depth +
                  ") ",
                  end='')
            print("is too great for the width of the subtitle (" + width +
                  "). ",
                  end='')
            print("Depth reduced to " + newdepth)
            depth = newdepth
            numWarn += 1

        leftX = x + (abs(depth + 1) // 2)
        rightX = x - (abs(depth) // 2)

        if rightX < 0:
            leftX += rightX * -1
            rightX = 0

        modifyAttrib(leftList[index].attrib, leftX, y, originalDepth)
        modifyAttrib(rightList[index].attrib, rightX, y, originalDepth)

    output = {}
    output['numSubs'] = numSubs
    output['numWarn'] = numWarn
    output['leftRoot'] = leftRoot
    output['rightRoot'] = rightRoot

    return output


if __name__ == '__main__':
    main()
