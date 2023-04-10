import numpy as np
import bpy
import os

class Exporter:
    def __init__(self, filePath, fileName, rawFileName, data, targets, categoryIDs, partIDs, materialMappings, exportNoiseData, width, height):
        # we need Blender's custom file path manipulation methods
        # to avoid error because of relative paths
        # see: https://blender.stackexchange.com/a/12153/95167
        self.filePath = bpy.path.abspath(filePath)
        os.makedirs(self.filePath, exist_ok=True)
        self.fileName = fileName
        self.rawFileName = rawFileName
        self.data = data
        self.targets = targets
        self.categoryIDs = categoryIDs
        self.partIDs = partIDs
        self.materialMappings = materialMappings
        self.exportNoiseData = exportNoiseData
        self.width = width
        self.height = height

        # map data tuples to arrays
        if exportNoiseData:
            self.mappedData = np.array(list(map(lambda hit: self.tupleToArrayWithNoise(hit), data))).transpose()
        else:
            self.mappedData = np.array(list(map(lambda hit: self.tupleToArray(hit), data))).transpose()

    def tupleToArray(self, hit):
        return np.array([
            hit.categoryID, hit.partID,                                             # 0, 1   
            hit.location.x, hit.location.y, hit.location.z,                         # 2, 3, 4
            hit.distance,                                                           # 5
            hit.intensity,                                                          # 6
            hit.color[0], hit.color[1], hit.color[2],                               # 7, 8, 9
        ])

    def tupleToArrayWithNoise(self, hit):
        return np.array([
            hit.categoryID, hit.partID,                                             # 0, 1
            hit.location.x, hit.location.y, hit.location.z,                         # 2, 3, 4
            hit.distance,                                                           # 5
            hit.intensity,                                                          # 6
            hit.color[0], hit.color[1], hit.color[2],                               # 7, 8, 9
            hit.noiseLocation.x, hit.noiseLocation.y, hit.noiseLocation.z,          # 10, 11, 12
            hit.noiseDistance                                                       # 13
        ])


    def exportLAS(self):  
        from . import export_las   
        # export using categoryIDs as source ID 
        export_las.export(self.filePath, self.fileName, self.mappedData, self.exportNoiseData, usePartIDs=False)

        # export using partIDs as source ID 
        export_las.export(self.filePath, self.fileName, self.mappedData, self.exportNoiseData, usePartIDs=True)
    
    def exportHDF(self, fileNameExtra=""):
        from . import export_hdf
        export_hdf.export(self.filePath, self.rawFileName + fileNameExtra, self.mappedData, self.exportNoiseData)

    def exportCSV(self):
        from . import export_csv
        export_csv.export(self.filePath, self.fileName, self.mappedData.transpose(), self.exportNoiseData)
        
    def exportPLY(self):
        from . import export_ply
        export_ply.export(self.filePath, self.fileName, self.mappedData.transpose(), self.exportNoiseData)

    def exportSegmentedImage(self, exportPascalVoc):
        from . import export_segmented_image
        export_segmented_image.export(self.filePath, self.fileName, self.data, self.partIDs, exportPascalVoc, self.width, self.height)

    def exportRenderedImage(self):
        from . import export_rendered_image
        export_rendered_image.export(self.filePath, self.fileName)

    def exportDepthmap(self, depthMinDistance, depthMaxDistance):
        from . import export_depthmap
        export_depthmap.export(self. filePath, self.fileName, self.data, depthMinDistance, depthMaxDistance, self.width, self.height)