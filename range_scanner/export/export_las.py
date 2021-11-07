import laspy
import numpy as np
import os

def export(filePath, fileName, data, exportNoiseData, usePartIDs):
    print("Exporting data into .las format...")

    # create header 
    # see https://laspy.readthedocs.io/en/latest/tut_background.html for info on point formats
    header = laspy.LasHeader(point_format=2)

    # create output file path
    if usePartIDs:
        outfile = laspy.LasData(header=header)
        
        # assign data
        outfile.pt_src_id = data[1]
    else:
        outfile = laspy.LasData(header=header)
    
        # assign data
        outfile.pt_src_id = data[0]

    allX = data[2]
    allY = data[3]
    allZ = data[4]

    # generate some additional information
    xmin = np.floor(np.min(allX))
    ymin = np.floor(np.min(allY))
    zmin = np.floor(np.min(allZ))

    outfile.header.offset = [xmin,ymin,zmin]
    scaleFactor = 0.0001
    outfile.header.scale = [scaleFactor, scaleFactor, scaleFactor]

    outfile.x = allX
    outfile.y = allY
    outfile.z = allZ

    # for scaling factors see: https://www.asprs.org/wp-content/uploads/2010/12/LAS_1_4_r13.pdf
    outfile.intensity = data[6] * 65535

    outfile.red = data[7] * 65535
    outfile.green = data[8] * 65535
    outfile.blue = data[9] * 65535

    if usePartIDs:
        outfile.write(os.path.join(filePath, "%s_parts.las" % fileName))
    else:
        outfile.write(os.path.join(filePath, "%s.las" % fileName))
    
    if exportNoiseData:
        # create output file path
        if usePartIDs:
            outfile = laspy.LasData(header=header)
            
            # assign data
            outfile.pt_src_id = data[1]
        else:
            outfile = laspy.LasData(header=header)
        
            # assign data
            outfile.pt_src_id = data[0]

        allX = data[10]
        allY = data[11]
        allZ = data[12]

        # generate some additional information
        xmin = np.floor(np.min(allX))
        ymin = np.floor(np.min(allY))
        zmin = np.floor(np.min(allZ))

        outfile.header.offset = [xmin,ymin,zmin]
        outfile.header.scale = [0.001,0.001,0.001]

        outfile.x = allX
        outfile.y = allY
        outfile.z = allZ

        outfile.intensity = data[6] * 65535

        outfile.red = data[7] * 65535
        outfile.green = data[8] * 65535
        outfile.blue = data[9] * 65535

        if usePartIDs:
            outfile.write(os.path.join(filePath, "%s_noise_parts.las" % fileName))
        else:
            outfile.write(os.path.join(filePath, "%s_noise.las" % fileName))
        
    print("Done.")