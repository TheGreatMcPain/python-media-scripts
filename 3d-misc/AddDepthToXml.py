#!/usr/bin/env python3
import sys
import os
import xml.etree.cElementTree as ET

# Globals
MARGINFOR3DSUBS = 5


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        print("Usage:", sys.argv[0], "<3D-Plane.ofs> <input.xml> <output.xml>")
        exit(1)

    in3dPlane = os.path.expanduser(args[0])
    inXML = os.path.expanduser(args[1])
    outXML = os.path.expanduser(args[2])

    AddDepthTags(inXML, outXML, in3dPlane, 24)


def AddDepthTags(inXml, outXml, in3dp, framerate):
    fps = framerate
    roundfps = round(framerate * 1000) / 1000
    if roundfps == 23.976:
        fps = 24

    with open(in3dp, 'rb') as f:
        plane = f.read()

    if plane[0:7] == b"\x89OFS\r\n\x1a":
        plane = plane[41:]

    numframes = len(plane)

    tree = ET.parse(inXml)
    root = tree.getroot()

    numsubs = 0
    numwarnings = 0
    mindepth = 300
    maxdepth = -300
    alldepths = 0

    for event in root.iter("Event"):
        numsubs += 1
        inframe = Tc2frame(event.attrib['InTC'], fps)
        outframe = Tc2frame(event.attrib['OutTC'], fps)
        graphic = event[0].attrib

        if inframe >= numframes:
            graphic['Depth'] = '0'
            graphic['DepthWarning'] = str(outframe - inframe)
            numwarnings += 1
        else:
            margin = outframe - inframe // 6
            if margin > MARGINFOR3DSUBS:
                margin = MARGINFOR3DSUBS

            p = plane[inframe + margin:outframe - margin + 1]
            depth = -300
            n = len(p)
            warn = 0
            cuts = 0
            val = p[0]
            for i in range(0, n):
                h = p[i]
                if h != val:
                    cuts += 1
                    val = h
                if h == 128:
                    warn += 1
                else:
                    v = (h & 127)
                    if (h & 128) / 128:
                        v = -v
                    v = v * 2
                    if v > depth:
                        depth = v

            if depth == -300:
                depth = 0
            else:
                alldepths += depth
                if depth < mindepth:
                    mindepth = depth
                if depth > maxdepth:
                    maxdepth = depth

            graphic['Depth'] = str(depth)
            if warn > 0:
                graphic['UndefinedFrameDepth'] = str(warn)
                numwarnings += 1

    avgdepth = round(alldepths / numsubs * 100) / 100
    print(numsubs, "Subtitles,", numwarnings, "subtitles with", end=' ')
    print("undefined depth values, average depth: " + str(avgdepth), end='')
    print(", minimum depth: " + str(mindepth), end='')
    print(", maximum depth: " + str(maxdepth))
    print()

    print("Source 3D-plane:", in3dp)
    print("Min depth:", mindepth)
    print("Max depth:", maxdepth)
    print("Average depth:", avgdepth)
    print("Number of warnings for undefined frame's depth:", numwarnings)
    print("Number of subtitles processed:", numsubs)
    print("Frame rate of the stream:", roundfps)
    print("Frame rate used to convert the drop frames", end=" ")
    print("to frame numbers:", fps)

    tree.write(outXml, xml_declaration=True, method="xml", encoding="utf8")


def Tc2frame(timecode, framerate):
    tc = timecode.split(":")
    ff = timecode.split(":")[-1]
    if ff[0] == '0':
        ff = ff[1]

    hours = int(tc[0]) * 60 * 60
    minutes = int(tc[1]) * 60
    secs = hours + minutes + int(tc[2])
    return round(secs * framerate) + int(ff)


if __name__ == "__main__":
    main()
