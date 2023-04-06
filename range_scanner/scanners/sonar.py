import bpy
from bpy import context
from mathutils import Vector, Quaternion
from math import radians, degrees
import numpy as np
import time
import bmesh
from mathutils.bvhtree import BVHTree
import colorsys
import os
import sys
import math

from .. import error_distribution
from .. import material_helper
from ..export import exporter
from . import hit_info
from .. import fresnel
from ..ui import user_interface
from . import generic



def castRay(targets, trees, origin, direction, maxRange, materialMappings, depsgraph, debugLines, debugOutput,
            sourceLevel, noiseLevel, directivityIndex, processingGain, receptionThreshold):
    if debugOutput:
        print("")
        print("")
        print("")
        print("### SUBCAST ###")
        print(origin, direction, maxRange)

    closestHit = generic.getClosestHit(targets, trees, origin, direction, maxRange, debugOutput, debugLines)

    if closestHit is not None:
        materialProperty = material_helper.getMaterialColorAndMetallic(closestHit, materialMappings, depsgraph, debugOutput)
        closestHit.color = materialProperty.color

        if debugOutput:
            print("RGBA", materialProperty.color[0], materialProperty.color[1], materialProperty.color[2], materialProperty.color[3])
            print("Metallic ", materialProperty.metallic)

        # see: https://link.springer.com/book/10.1007/978-1-349-20508-0, p. 18
        transmissionLoss = 10 * np.log10(closestHit.distance)
        
        #backscatteringCrossSection = material_helper.getSurfaceReflectivity(closestHit.color)
        #targetStrength = 10 * np.log10(backscatteringCrossSection)

        # same as for light: instead of some formula to calculate a value, we let the user
        # directly set the value for simplification the input process
        # just use it as factor how much of the incoming energy should be refelcted
        targetStrength = material_helper.getSurfaceReflectivity(closestHit.color)


        ' SONAR EQUATION '
        # see: https://www.uio.no/studier/emner/matnat/ifi/INF-GEO4310/h12/undervisningsmateriale/sonar_introduction_2012_compressed.pdf
        # eq. (19)
        receivedSignalLevel = sourceLevel - 2*transmissionLoss - noiseLevel + directivityIndex + processingGain # + targetStrength
        receivedSignalLevel *= targetStrength

        isMeasured = receivedSignalLevel > receptionThreshold

        if debugOutput:
            print("SEND ", sourceLevel, transmissionLoss, targetStrength, noiseLevel, directivityIndex, processingGain)
            print("RECEIVE ", receivedSignalLevel, isMeasured)

        if isMeasured:
            closestHit.intensity = receivedSignalLevel / sourceLevel
            return closestHit
            
    return None

def performScan(context, 
                scannerType, scannerObject,
                maxDistance,
                fovSonar, sonarStepDegree, sonarMode3D, sonarKeepRotation,
                sourceLevel, noiseLevel, directivityIndex, processingGain, receptionThreshold,    
                simulateWaterProfile, depthList,  
                addNoise, noiseType, mu, sigma, addConstantNoise, noiseAbsoluteOffset, noiseRelativeOffset,
                addMesh,
                exportLAS, exportHDF, exportCSV, exportPLY, exportSingleFrames,
                dataFilePath, dataFileName,
                debugLines, debugOutput, outputProgress, measureTime, singleRay, destinationObject, targetObject,
                enableAnimation, frameStart, frameEnd, frameStep,
                targets, materialMappings,
                categoryIDs, partIDs):

    if measureTime:
        startTime = time.time()

    # sensor object which defines ray cast source
    sensor = scannerObject #bpy.data.objects['sensor']

    # defining sensor properties
    # left side and right side
    xRange = np.array([-90, 90])

    # down/up angle
    #  -----------------
    #  |\
    #  |  \
    #  | a  \
    #  |      \
    #  |
    ySteps = (fovSonar / 2.0) / sonarStepDegree + 1
    yRange = np.linspace(-89.999, -90 + (fovSonar / 2.0), int(ySteps))

    if debugOutput:
        print("Angles")
        print(xRange)
        print(yRange)

    totalNumberOfRays = xRange.size * yRange.size * int((frameEnd - frameStart + 1) / frameStep)

    # array to store hit information
    # we don't know how many of our rays will actually hit an object, so we allocate
    # memory for the worst case of every ray hitting the scene
    # (TODO depending on the RAM usage, it might be a good idea to use some kind of caching)
    scannedValues = np.full(totalNumberOfRays, None, dtype=hit_info.HitInfo)

    valueIndex = 0

    if enableAnimation:
        # read the needed camera settings
        # alternative: get needed values from the main Blender GUI ('Output Properties' tab on the right)
        firstFrame = frameStart  # bpy.context.scene.frame_start
        lastFrame = frameEnd     # bpy.context.scene.frame_end
        frameStep = frameStep    # bpy.context.scene.frame_step
    else:
        firstFrame = bpy.context.scene.frame_current
        lastFrame = bpy.context.scene.frame_current
        frameStep = 1  
    
    bpy.context.scene.frame_set(firstFrame)

    # graph needed for BVH tree
    depsgraph = context.evaluated_depsgraph_get()

    trees = {}

    origin = sensor.matrix_world.translation
    startLocation = origin.copy()

    # set counter of scanned rays to 0
    indexX = 0
    indexY = 0

    if measureTime:
        print("Prepare: %s s" % (time.time() - startTime))
        startTime = time.time()

    # print empty progress bar
    if outputProgress:
        generic.updateProgress("Scanning scene", 0.0)

    exportNoiseData = addNoise or addConstantNoise

    for frameNumber in range(firstFrame, lastFrame + 1, frameStep):
        bpy.context.scene.frame_set(frameNumber)

        # setup BVH tree for each object
        trees = generic.getBVHTrees(trees, targets, depsgraph)
        
        sensorHeight = sensor.matrix_world.translation.z

        firstValueBelowSensor = -1

        # for each timestep, calculate the traveled distance for normalization
        traveledDistance = math.sqrt((startLocation.x - origin.x)**2 + (startLocation.y - origin.y)**2 + (startLocation.z - origin.z)**2)

        for index, value in enumerate(depthList):
            if value[0] < sensorHeight:
                firstValueBelowSensor = index
                break
        
        if firstValueBelowSensor == 0:
            # the first value is below the sensor, so we don't know the 
            # refractive index at the start of the ray
            print("You must set at least 1 refractive index above the sensor!")
            return 

        if firstValueBelowSensor == -1:
            # all values are above the sensor or no values are given
            # in both cases we don't have to care about refraction
            simulateWaterProfile = False

        # iterate over all X/Y coordinates
        for x in xRange:
            # setup vector in the according direction
            quatX = Quaternion((0.0, 1.0, 0.0), radians(x))
            
            for y in yRange:
                quatY = Quaternion((1.0, 0.0, 0.0), radians(y))

                # define "zero" direction of sensor
                vec = Vector((0.0, 0.0, -1.0))
                
                # calculate destination translation from X/Y directions
                quatAll = quatX @ quatY
                vec.rotate(quatAll)

                # caution: we can't use sensor.rotation_euler as it only gives us the 
                # object's local rotation
                # instead, we need to use the global rotation after "Follow Path" constraint is applied
                # see comments of: https://blender.stackexchange.com/a/38179/95167 
                vec.rotate(sensor.matrix_world.decompose()[1])
                            
                # calculate destination location
                destination = vec + sensor.matrix_world.translation

                if singleRay:
                    destination = destinationObject.matrix_world.translation

                # calculate ray direction 
                direction = (destination - origin).normalized()
                
                closestHit = None
                internalOrigin = origin

                if simulateWaterProfile:
                    angle = Vector((0.0, 0.0, -1.0)).angle(direction) 

                    remainingDistance = maxDistance   

                    oldHeight = sensorHeight        

                    remainingSourceLevel = sourceLevel

                    distanceTraveled = 0.0

                    for layerIndex in range(firstValueBelowSensor, len(depthList) + 1):
                        # after passing the final layer, the ray distance is only limited by the
                        # sensor's parameters, not the water layers
                        if layerIndex == len(depthList):
                            newRange = remainingDistance
                        else:
                            # else, determine the range until the next water layer
                            newRange = (oldHeight - depthList[layerIndex][0]) / np.cos(angle)

                            oldHeight = depthList[layerIndex][0]

                            if debugOutput:
                                print(sensorHeight, depthList[layerIndex][0], depthList[layerIndex][1], angle, remainingDistance, newRange)
                            
                        closestHit = castRay(targets, trees, internalOrigin, direction, min(remainingDistance, newRange), materialMappings, depsgraph, debugLines, debugOutput,
                                        remainingSourceLevel, noiseLevel, directivityIndex, processingGain, receptionThreshold)
                        
                        if debugLines:
                            generic.addLine(internalOrigin, internalOrigin + direction * min(remainingDistance, newRange))
                            
                        if closestHit is None:
                            # no hit was found
                            # decrease the scanning distance for next run
                            remainingDistance -= newRange
                            distanceTraveled += newRange

                            # no scanning distance left or final layer reached, abort
                            if remainingDistance < 0 or layerIndex == len(depthList):
                                break
                            
                            if debugOutput:
                                print("No hit from ", internalOrigin, " in direction ", direction, " within range of ", min(remainingDistance, newRange))
                                print("Adding line from ", internalOrigin, " to ", internalOrigin + direction * min(remainingDistance, newRange) )
                                                        
                            # for the next ray we need to refract the current ray at the border
                            # of the two adjacent layers

                            # see: https://en.wikipedia.org/wiki/Snell%27s_law
                            #      https://en.wikipedia.org/wiki/List_of_refractive_indices

                            # as the water layers are not represented by Blender objects, we
                            # need to define the normal manually as upwards (positive Z axis)
                            normal = Vector((0.0, 0.0, 1.0)).normalized()

                            # determine n by the refractive index of the layer above and below the border
                            # https://en.wikipedia.org/wiki/Snell%27s_law
                            # sin a1   v2   n1 
                            # ------ = -- = --
                            # sin a2   v1   n2

                            # we now need to get n1 / n2, so we can also take v2 / v1
                            v1 = depthList[layerIndex - 1][1]
                            v2 = depthList[layerIndex][1]
                            
                            n = v2 / v1

                            if debugOutput:
                                print(v1, v2, n)

                            # calculate new direction vector
                            # see: http://www.starkeffects.com/snells-law-vector.shtml
                            newDirection = n * (normal.cross(-normal.cross(direction))) - normal * np.sqrt(1 - (n**2) * (normal.cross(direction) @ normal.cross(direction)))

                            incidentAngle = normal.angle(direction)
                            refractionAngle = normal.angle(newDirection)

                            if debugOutput:
                                print(normal.normalized(), direction.normalized(), newDirection.normalized())
                                print(incidentAngle, refractionAngle)

                            # now we need to calculate how much of the waves energy is transmitted as some fraction is reflected away from the receiver
                            # see: https://epic.awi.de/id/eprint/29175/1/Hat2009b.pdf, p. 38, 2.7.4 Schalltransmission
                            p1 = depthList[layerIndex - 1][2]
                            p2 = depthList[layerIndex][2]

                            denominator = p2 * v2 * np.cos(incidentAngle) + p1 * v1 * np.cos(refractionAngle)
                            transmission = (4 * p1 * v1 * p2 * v2 * np.cos(incidentAngle) * np.cos(refractionAngle)) / denominator**2 # equation (2.42)

                            if debugOutput:
                                print("density ", p1, p2, "transmission", transmission)
                            
                            # set ray parameters for next run
                            internalOrigin = direction * newRange + internalOrigin
                            direction = newDirection
                            remainingSourceLevel *= transmission

                            if debugOutput:
                                print("New origin ", internalOrigin, ", new direction ", direction)
                        else:
                            break
                    
                    if closestHit is not None:
                        # important: update the total distance, as currently it is set so the distance
                        # between the hitpoint and water layer above!
                        closestHit.distance = closestHit.distance + distanceTraveled                
                else:
                    closestHit = castRay(targets, trees, origin, direction, maxDistance, materialMappings, depsgraph, debugLines, debugOutput,
                                     sourceLevel, noiseLevel, directivityIndex, processingGain, receptionThreshold)

                # if location is None, no hit was found within the given range
                if closestHit is not None:
                    # set category/part id for that hit to enable segmentation
                    if "partID" in closestHit.target:
                        partIDIndex = closestHit.target["partID"]
                    else:
                        partIDIndex = closestHit.target.material_slots[materialMappings[closestHit.target][closestHit.faceIndex]].name

                    closestHit.categoryID = categoryIDs[closestHit.target["categoryID"]]
                    closestHit.partID = partIDs[partIDIndex]
                    
                    noise = noiseAbsoluteOffset + (closestHit.distance * noiseRelativeOffset / 100.0)

                    if addNoise:
                        # generate some noise
                        # error model: https://github.com/mgschwan/blensor/blob/master/release/scripts/addons/blensor/gaussian_error_model.py#L21
                        #              https://github.com/mgschwan/blensor/blob/0b6cca9f189b1e072cfd8aaa6360deeab0b96c61/release/scripts/addons/blensor/generic_lidar.py#L172
                        noise += error_distribution.applyNoise(mu, sigma)

                    # we can't simply move the hit location around by some random translation
                    # instead, we have to move it along the ray direction

                    # calculate distance with noise
                    noiseDistance = closestHit.distance + noise
                    
                    # calculate the direction vector with noise applied
                    noiseDirection =  direction.normalized() * noiseDistance

                    # calculate the noise location of the hit point
                    noiseLocation = noiseDirection + origin

                    if debugOutput:
                        print("Noise Distance ", noiseDistance)
                        print("Noise Location ", noiseLocation)
                    
                    closestHit.noiseLocation = noiseLocation
                    closestHit.noiseDistance = noiseDistance

                    if debugOutput:
                        print("Location ", closestHit.location)
                        print("Direction ", direction)
                        print("Length ", closestHit.location.length)
                        print("Noise ", noise)
                        print("Distance ", closestHit.distance)     

                    if not sonarMode3D:
                        # to simulate sonar, we have to move all values into one plane
                        if sonarKeepRotation:
                            closestHit.location = Vector((direction.x, direction.y, 0)).normalized() * closestHit.distance + origin
                        else:
                            if x > 0:
                                closestHit.location.x = -closestHit.distance
                            else:
                                closestHit.location.x = closestHit.distance
                            
                            closestHit.location.y = traveledDistance
                            closestHit.location.z = startLocation.z

                    # save closest hit into array
                    scannedValues[valueIndex] = closestHit

                    valueIndex += 1
                else:
                    if debugOutput:
                        print("NO HIT within range of %f" % maxDistance)
                
                indexY += 1

                if singleRay:
                    break
            
            indexX += 1
            indexY = 0

            if outputProgress:
                percentage = (indexX * yRange.size) / totalNumberOfRays 
                generic.updateProgress("Scanning scene", percentage)

            if singleRay:
                break

    if measureTime:
        print("Loop: %s s" % (time.time() - startTime))
        startTime = time.time()

    # we now have the final number of hits so we could shrink the array here
    # as explained here (https://stackoverflow.com/a/32398318/13440564), resizing
    # would cause a copy, so we slice the array instead
    slicedScannedValues = scannedValues[:valueIndex]

    if addMesh:
        generic.addMeshToScene("real_values", slicedScannedValues, False)

        if exportNoiseData:
            generic.addMeshToScene("noise_values", slicedScannedValues, True)

    if measureTime:
        print("Meshes: %s s" % (time.time() - startTime))
        startTime = time.time()

    # save data to files
    if debugOutput:
        print("File path ", os.path.abspath(dataFilePath))

    if len(slicedScannedValues) > 0:
        # setup exporter with our data
        if exportLAS or exportHDF or exportCSV or exportPLY:
            fileExporter = exporter.Exporter(dataFilePath, "%s_frame_%d" % (dataFileName, frameNumber), dataFileName, slicedScannedValues, targets, categoryIDs, partIDs, materialMappings, exportNoiseData, 0, 0)

            # export to each format
            if exportLAS:
                fileExporter.exportLAS()

            if exportHDF:
                fileExporter.exportHDF(fileNameExtra="_frames_%d_to_%d_single" % (frameStart, frameEnd))

            if exportCSV:
                fileExporter.exportCSV()

            if exportPLY:
                fileExporter.exportPLY()
    else:
        print("No data to export!")

    if measureTime:
        print("Output: %s s" % (time.time() - startTime))

    print("Done.")