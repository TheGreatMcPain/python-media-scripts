#!/usr/bin/env python3
import sys
import os
import xml.etree.cElementTree as ET


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("Usage:", sys.argv[0], "<subtitles-1.xml> <subtitles-2.xml>")
        exit(1)

    in1 = os.path.expanduser(args[0])
    in2 = os.path.expanduser(args[1])

    if not compareDepth(in1, in2):
        exit(1)


def compareDepth(inXML1, inXML2):
    tree1 = ET.parse(inXML1)
    tree2 = ET.parse(inXML2)
    root1 = tree1.getroot()
    root2 = tree2.getroot()

    eleList1 = list(root1.iter('Graphic'))
    eleList2 = list(root2.iter('Graphic'))

    if len(eleList1) != len(eleList2):
        print("Number of Subtitles differ!")
        exit(1)

    for x in range(0, len(eleList1)):
        attrib1 = eleList1[x].attrib
        attrib2 = eleList2[x].attrib

        depth1 = attrib1['Depth']
        depth2 = attrib2['Depth']

        if depth1 != depth2:
            print("Depths differ on subtitle:", x)
            return False

    print("Depths are the same.")
    return True


if __name__ == '__main__':
    main()
