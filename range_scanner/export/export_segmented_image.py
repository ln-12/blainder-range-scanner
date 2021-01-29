import random
import bpy
import numpy as np
import os
import colorsys 

def export(filePath, fileName, data, partIDs, exportPascalVoc, width, height):
    print("Saving scene as image...")

    # source: https://blender.stackexchange.com/a/652/95167

    # blank image
    image = bpy.data.images.new("MyImage", width=width, height=height)

    # as the fill value (black) is a tuple, we need some special packing
    # see: https://stackoverflow.com/a/40711408/13440564
    value = np.empty((), dtype=object)
    value[()] = (0.0, 0.0, 0.0, 1.0)

    pixels = np.full(width * height, value) 
    alphaPixels = np.full(width * height, value) 

    # generate some random color for each object to make all pixels
    # of one target the same color
    colors = {} # target -> (r, g, b, a)

    # dictionary to store the bounding box (minimum, maximum values for x and y) 
    # for each object in the picture
    boundingBoxes = {} # taget -> (minX, minY, maxX, maxY)

    # save the names which should be stored in the pascal voc image description
    names = {}

    total = len(partIDs.items())

    for index, (name, partID) in enumerate(partIDs.items()):
        # we calculate the color based on the HSV color model
        # this way, the contrast between two parts is maximized
        # example: 6 parts, to we calculate the HSV color for
        # 0°, 60°, 120°, 180°, 240° and 300°
        color = colorsys.hsv_to_rgb(index/total,1,1)
        colors[partID] = (color[0], color[1], color[2], 1.0)

        # we set default values for each target, so that we don't have to check on
        # each hit, if there is data available
        boundingBoxes[partID] = (np.inf, np.inf, -np.inf, -np.inf)

        names[partID] = name

    if exportPascalVoc:
        for hit in data:
            pixels[((height - hit.y - 1) * width) + hit.x] = colors[hit.partID]
            alphaPixels[((height - hit.y - 1) * width) + hit.x] = (1.0, 1.0, 1.0, 1.0)

            # read available values
            minX, minY, maxX, maxY = boundingBoxes[hit.partID]

            # update values if necessary
            if hit.x < minX:
                minX = hit.x

            if hit.y < minY:
                minY = hit.y

            if hit.x > maxX:
                maxX = hit.x

            if hit.y > maxY:
                maxY = hit.y

            # write values back
            boundingBoxes[hit.partID] = minX, minY, maxX, maxY
    else:
        for hit in data:
            pixels[((height - hit.y - 1) * width) + hit.x] = colors[hit.partID]
            alphaPixels[((height - hit.y - 1) * width) + hit.x] = (1.0, 1.0, 1.0, 1.0)
        
    # flatten list
    pixels = [chan for px in pixels for chan in px]
    alphaPixels = [chan for px in alphaPixels for chan in px]

    # assign pixels
    image.pixels = pixels

    # write image
    fullFilePath = os.path.join(filePath, "%s_image_segmented.png" % fileName)
    image.filepath_raw = fullFilePath
    image.file_format = 'PNG'
    image.save()



    # assign pixels
    image.pixels = alphaPixels

    # write image
    fullFilePath = os.path.join(filePath, "%s_image_alpha.png" % fileName)
    image.filepath_raw = fullFilePath
    image.file_format = 'PNG'
    image.save()

    if exportPascalVoc:
        from pascal_voc_writer import Writer

        # setup writer with image name and size
        writer = Writer(fullFilePath, width, height)

        # add all object bounding boxes
        for partID, (minX, minY, maxX, maxY) in boundingBoxes.items():
            # if at least one pixel represents the current target ALL values are
            # updated, so one check is enough
            if minX is not np.inf:
                writer.addObject(names[partID], minX, minY, maxX, maxY)

        # write file to disk
        path = os.path.join(filePath, "%s_image_segmented.xml" % fileName)
        print("Writing %s..." % (path))
        writer.save(path)

    print("Done.")