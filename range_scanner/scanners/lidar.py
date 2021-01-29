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
import math, mathutils

from .. import error_distribution
from .. import material_helper
from ..export import exporter
from . import hit_info
from .. import fresnel
from ..ui import user_interface
from . import generic


# refractive index of air
# see: https://en.wikipedia.org/wiki/List_of_refractive_indices
iorAir = 1.000293 


def castRay(targets, trees, origin, direction, maxRange, materialMappings, depsgraph, debugLines, debugOutput, currentIOR, isInsideMaterial, remainingReflectionDepth):
    if remainingReflectionDepth < 0:
        return None

    if debugOutput:
        print("")
        print("")
        print("")
        print("### SUBCAST ###")
        print(origin, direction, maxRange)

    closestHit = generic.getClosestHit(targets, trees, origin, direction, maxRange, debugOutput, debugLines)

    if closestHit is not None:
        # the normal is given in local object space, so we need to transform it to global space
        normal = closestHit.target.rotation_euler.to_matrix() @ closestHit.faceNormal

        # calculate angle between our ray and the mesh surface
        normalAngle = direction.angle(normal)

        # get the material's reflectivity properties
        materialProperty = material_helper.getMaterialColorAndMetallic(closestHit, materialMappings, depsgraph, debugOutput)

        closestHit.color = materialProperty.color

        # use simple lambert reflectance to approximate light return
        # see: https://en.wikipedia.org/wiki/Lambertian_reflectance
        closestHit.intensity = abs(math.cos(normalAngle)) *  material_helper.getSurfaceReflectivity(materialProperty.color)

        if debugOutput:
            print("RGBA", materialProperty.color[0], materialProperty.color[1], materialProperty.color[2], materialProperty.color[3])
            print("Metallic ", materialProperty.metallic)
                        
        # if the surface is 100% reflecting reflect the ray
        # aka: recursive raytracing
        # see: https://en.wikipedia.org/wiki/Ray_tracing_(graphics)#Recursive_ray_tracing_algorithm:~:text=rendered.-,Recursive%20ray%20tracing%20algorithm
        if (materialProperty is not None and materialProperty.metallic == 1.0):
            if debugOutput:
                print("### RESULT ###")
                print("Hit point location: ", closestHit.location)
                print("Normal on hit point: ", normal, closestHit.faceNormal)
                print("Index of the tree node: ", closestHit.faceIndex)
                print("Distance to the hit point: ", closestHit.distance)

            # reflect the incoming ray with surface normal
            # see: https://docs.blender.org/api/current/mathutils.html#mathutils.Vector.reflect
            reflectedVec = direction.reflect(normal)

            if debugLines:
                generic.addLine(closestHit.location, closestHit.location + normal)
                generic.addLine(origin, closestHit.location)
                generic.addLine(closestHit.location, closestHit.location + reflectedVec)
            
            if debugOutput:
                print("### REFLECTION ###")
                print("direction: ", direction)
                print("normal: ", normal, normal + closestHit.location)
                print("reflected: ", reflectedVec, closestHit.location + reflectedVec)

            # decrease maximum range by already travelled distance
            newRange = maxRange - closestHit.distance

            if newRange > 0.0:
                # the offset is needed to push the origin 1mm in the direction of the ray as otherwise we might
                # hit the same location again because of rounding errors
                directionOffset = (reflectedVec.normalized() * 0.001)    

                # cast new ray from current hit point            
                reflectedHit = castRay(targets, trees, closestHit.location + directionOffset, reflectedVec, newRange, materialMappings, depsgraph, debugLines, debugOutput, currentIOR, isInsideMaterial, remainingReflectionDepth - 1)

                if reflectedHit is not None:
                    # the scanner does not know if a ray is returned from an object's surface or a mirror
                    # that means it assumes the returned distance was measured along the original direction vector
                    closestHit.distance += reflectedHit.distance

                    # the hit location seems to have the color of the reflected surface
                    closestHit.color = reflectedHit.color
                    closestHit.intensity = material_helper.getSurfaceReflectivity(reflectedHit.color)

                    closestHit.wasReflected = True
                else:
                    return None
        
        if (materialProperty is not None and materialProperty.ior > 0.0):
            # when hitting glass, there are 4 cases:
            #   - the ray goes through the glas and hits the object behind
            #   - the ray is reflected and hits an object in the reflected direction
            #   - the glass directly reflects the ray (only for small angles)
            #   - no hit is detected

            angle = abs(np.pi - normalAngle)

            # for small angles, we return the glass surface as hit
            # see: https://ieeexplore.ieee.org/document/6630875
            # 0.0349066 rad = 2.0 deg
            if (abs(angle)) <= 0.0349066:
                if debugOutput:
                    print("Angle too small, returning...")

                return closestHit

            if debugOutput:
                print("### RESULT ###")
                print("Hit point location: ", closestHit.location)
                print("Normal on hit point: ", normal, closestHit.faceNormal)
                print("Index of the tree node: ", closestHit.faceIndex)
                print("Distance to the hit point: ", closestHit.distance)

            # decrease maximum range by already travelled distance
            newRange = maxRange - closestHit.distance

            if newRange > 0.0:
                # reflect the incoming ray with surface normal
                # see: https://docs.blender.org/api/current/mathutils.html#mathutils.Vector.reflect
                reflectedVec = direction.reflect(normal)

                if debugLines:
                    generic.addLine(closestHit.location, closestHit.location + normal)
                    generic.addLine(origin, closestHit.location)
                    generic.addLine(closestHit.location, closestHit.location + reflectedVec)
                
                if debugOutput:
                    print("### REFLECTION ###")
                    print("direction: ", direction)
                    print("normal: ", normal, normal + closestHit.location)
                    print("reflected: ", reflectedVec, closestHit.location + reflectedVec)

                # now we need to know how much light is reflected and how much is refracted
                # static approach: 
                # https://link.springer.com/content/pdf/10.1007%2F978-3-8348-2101-0.pdf, S. 604
                # Velodyne Scanner 63-HDL64ES2g HDL-64E S2 CD HDL-64E S2 Users Manual low res, S. 39, 905nm -> IR-A (nahes Infrarot)
                # -> 85 % transmission


                # dynamic approach: 
                # https://www.scratchapixel.com/lessons/3d-basic-rendering/introduction-to-shading/reflection-refraction-fresnel
                # https://refractiveindex.info/?shelf=3d&book=glass&page=BK7
                # https://de.wikipedia.org/wiki/Brechungsindex#Brechungsindex_der_Luft_und_anderer_Stoffe
                transmission = fresnel.T_unpolarized(materialProperty.ior, angle, 1.000292)
                reflectivity = 1 - transmission 

                # mirror the ray at the glass surface   
                if isInsideMaterial:
                    reflectedHit = None
                else:
                    # the offset is needed to push the origin 1mm in the direction of the ray as otherwise we might
                    # hit the same location again because of rounding errors
                    directionOffset = (reflectedVec.normalized() * 0.001) 
                    reflectedHit = castRay(targets, trees, closestHit.location + directionOffset, reflectedVec, newRange, materialMappings, depsgraph, debugLines, debugOutput, currentIOR, isInsideMaterial, remainingReflectionDepth - 1)

                intensityReflected = 0.0
                if reflectedHit is not None:
                    reflectedHit.wasReflected = True
                    intensityReflected = material_helper.getSurfaceReflectivity(reflectedHit.color)

                    # the transmission tells us, which amount of light goes through the glass
                    # the rest is split up between absorption and reflection (~ 50/50 -> # https://link.springer.com/content/pdf/10.1007%2F978-3-8348-2101-0.pdf, S. 605, 3-18)
                    # as the ray is reflected at the glass twice, the value is reduced twice
                    intensityReflected *= reflectivity * reflectivity




                # send the ray through the glass
                # see: https://en.wikipedia.org/wiki/Snell%27s_law
                #      https://en.wikipedia.org/wiki/List_of_refractive_indices
                direction = direction.normalized()
                normal = normal.normalized()

                # check if the normal points to the same side of the face as the origin is
                if normal.dot(direction) > 0.0:
                    normal *= -1.0

                # are we going grom air to medium or from medium to air?
                if isInsideMaterial:
                    n = materialProperty.ior / iorAir
                else:
                    n = iorAir / materialProperty.ior

                # calculate new direction vector
                # see: http://www.starkeffects.com/snells-law-vector.shtml
                newDirection = n * (normal.cross(-normal.cross(direction))) - normal * np.sqrt(1 - (n**2) * (normal.cross(direction) @ normal.cross(direction)))

                if debugOutput:
                    print("### REFRACTION ###")
                    print("dot:", normal.dot(direction))
                    print("direction: ", direction)
                    print("normal: ", normal, normal + closestHit.location)
                    print("refracted: ", newDirection, closestHit.location + newDirection)

                directionOffset = (newDirection.normalized() * 0.001)
                passthroughHit = castRay(targets, trees, closestHit.location + directionOffset, newDirection, newRange, materialMappings, depsgraph, debugLines, debugOutput, materialProperty.ior, not isInsideMaterial, remainingReflectionDepth - 1)
                
                intensityPassthrough = 0.0
                if passthroughHit is not None:
                    intensityPassthrough = material_helper.getSurfaceReflectivity(passthroughHit.color)

                    # the transmission tells us, which amount of  light goes through the glass
                    # as the ray passes the glass twice, the value is reduced twice
                    intensityPassthrough *= transmission * transmission


                # decide which return is the brightest
                if intensityPassthrough >= intensityReflected and intensityPassthrough > 0.0:
                    # object behind the glass is the brightest
                    closestHit.distance += passthroughHit.distance

                    closestHit.color = passthroughHit.color
                    closestHit.intensity = intensityPassthrough

                    closestHit.wasReflected = True

                    return closestHit
                elif intensityReflected > intensityPassthrough:
                    # object in the reflection is the brightest
                    closestHit.distance += reflectedHit.distance

                    closestHit.color = reflectedHit.color
                    closestHit.intensity = intensityReflected

                    closestHit.wasReflected = True

                    return closestHit
                else:
                    # we return None, as the sensor can't register a hit on the glass' surface
                    return None
        
        return closestHit
    
    return None



def performScan(context, 
                scannerType, scannerObject,
                reflectivityLower, distanceLower, reflectivityUpper, distanceUpper, maxReflectionDepth,
                intervalStart, intervalEnd, fovX, stepsX, fovY, stepsY, percentage,
                scannedValues, startIndex,
                firstFrame, lastFrame, frameNumber, rotationsPerSecond,
                addNoise, noiseType, mu, sigma, addConstantNoise, noiseAbsoluteOffset, noiseRelativeOffset,
                simulateRain, rainfallRate, 
                simulateDust, particleRadius, particlesPcm, dustCloudLength, dustCloudStart,
                addMesh,
                exportLAS, exportHDF, exportCSV, 
                exportRenderedImage, exportSegmentedImage, exportPascalVoc, exportDepthmap, depthMinDistance, depthMaxDistance, 
                dataFilePath, dataFileName,
                debugLines, debugOutput, outputProgress, measureTime, singleRay, destinationObject, targetObject,
                targets, materialMappings,
                categoryIDs, partIDs, trees, depsgraph):

    if measureTime:
        startTime = time.time()

    scene = bpy.context.scene
    sensor = scannerObject
    valueIndex = startIndex

    if scannerType == generic.ScannerType.rotating.name:
        # defining sensor properties
        # [-180, 180] degree
        xSteps = (intervalEnd - intervalStart) / stepsX + 1
        xRange = np.linspace(intervalStart, intervalEnd, int(xSteps))

        # [-90, 90] degree
        ySteps = fovY / stepsY + 1
        yRange = np.linspace(-(fovY / 2.0), fovY / 2.0, int(ySteps))

        totalNumberOfRays = xRange.size * yRange.size
    elif scannerType == generic.ScannerType.static.name:
        # setup camera properties
        sensor.data.lens_unit = 'FOV'
        scene.render.resolution_x = stepsX
        scene.render.resolution_y = stepsY

        scale = (fovY / fovX) / (stepsY / stepsX)

        # the camera's FOV is dependent on the angles
        # and the aspect ratio of the resolution 
        # see: https://blender.stackexchange.com/a/38571
        if fovX < fovY:
            sensor.data.angle = math.radians(fovY)
        else:
            sensor.data.angle = math.radians(fovX)

        if scale > 1.0:
            scene.render.pixel_aspect_x = 1.0
            scene.render.pixel_aspect_y = scale
        else:
            scene.render.pixel_aspect_x = 1.0 / scale
            scene.render.pixel_aspect_y = 1.0
            
        scene.render.resolution_percentage = percentage

        # defining sensor properties
        frame = sensor.data.view_frame(scene=scene)
        topRight = frame[0]
        bottomRight = frame[1]
        bottomLeft = frame[2]
        topLeft = frame[3]

        xRange = np.linspace(topLeft[0], topRight[0], stepsX)
        yRange = np.linspace(topLeft[1], bottomLeft[1], stepsY)

        totalNumberOfRays = xRange.size * yRange.size
    else:
        print("ERROR: Unknown scanner type %s!" % scannerType)
        return {'FINISHED'}

    origin = sensor.matrix_world.translation

    # set counter of scanned rays to 0
    indexX = 0
    indexY = 0

    if measureTime:
        print("Prepare: %s s" % (time.time() - startTime))
        startTime = time.time()

    # print empty progress bar
    if outputProgress:
        generic.updateProgress("Scanning scene", 0.0)

    # define "zero" direction of sensor
    sensorZero = Vector((0.0, 0.0, -1.0))
    sensorZero.rotate(sensor.matrix_world.decompose()[1])

    exportNoiseData = addNoise or simulateRain or addConstantNoise
    # iterate over all X/Y coordinates
    for x in xRange:
        # setup vector in the according direction
        quatX = Quaternion((0.0, 1.0, 0.0), radians(x))
        
        for y in yRange:
            if scannerType == generic.ScannerType.rotating.name:
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
                            
            elif scannerType == generic.ScannerType.static.name:
                # get current pixel vector from camera center
                vec = Vector((x, y, topLeft[2]))
                
                # rotate that vector according to camera rotation
                vec.rotate(sensor.matrix_world.decompose()[1])
                           
            # calculate destination location
            destination = vec + sensor.matrix_world.translation

            if singleRay:
                destination = destinationObject.matrix_world.translation

            # calculate ray direction 
            direction = destination - origin

            closestHit = castRay(targets, trees, origin, direction, distanceUpper, materialMappings, depsgraph, debugLines, debugOutput, iorAir, False, maxReflectionDepth - 1)

            # if location is None, no hit was found within the given range
            if closestHit is not None: 
                # set the image x/y coordinates for tof sensor
                closestHit.x = indexX
                closestHit.y = indexY

                # the Kinect raw depth data does not measure the distance between camera lens (L)
                # and hit point (H) -> d_1, but between the (virtual) camera plane and hit point, 
                # so we need to correct the distance
                #
                #   -----------------------H----
                #             |          / |
                #             |        /   |
                #             |  d_1 /     |
                #             |    /       |
                #             |  /         |
                #             |/           |
                #   ----------L------------------
                if scannerType == generic.ScannerType.static.name:
                    # only modify the distance, not the XYZ values!
                    closestHit.distance = mathutils.geometry.distance_point_to_plane(closestHit.location, origin, sensorZero)
                
                # set category/part id for that hit to enable segmentation
                if "partID" in closestHit.target:
                    partIDIndex = closestHit.target["partID"]
                else:
                    partIDIndex = closestHit.target.material_slots[materialMappings[closestHit.target][closestHit.faceIndex]].name

                closestHit.categoryID = categoryIDs[closestHit.target["categoryID"]]
                closestHit.partID = partIDs[partIDIndex]
                    
                if closestHit.wasReflected:
                    if debugLines:
                        generic.addLine(origin, closestHit.location)
                    
                    fakePoint = direction.normalized() * closestHit.distance + origin
                    
                    if debugOutput:
                        print(fakePoint)
                        print("Total reflected distance ", closestHit.distance)
                        
                    # update the original hit location (on the mirror) with the fake position from the total distance
                    closestHit.location = fakePoint
                    
                    if debugLines:
                        generic.addLine(origin, closestHit.location)

                
                noise = noiseAbsoluteOffset + (closestHit.distance * noiseRelativeOffset / 100.0)
                
                surfaceReflectivity = closestHit.intensity

                # source: https://github.com/mgschwan/blensor/blob/0b6cca9f189b1e072cfd8aaa6360deeab0b96c61/release/scripts/addons/blensor/scan_interface_pure.py#L9
                rMin = 0.0
                if closestHit.distance >= distanceLower:
                    rMin = reflectivityLower + ((reflectivityUpper - reflectivityLower) * closestHit.distance) / (distanceUpper - distanceLower)

                delta = 0

                if simulateRain:
                    # see https://www.researchgate.net/publication/330415308_Predicting_the_influence_of_rain_on_LIDAR_in_ADAS for details
                    noise += error_distribution.applyNoise(0.0, 0.02 * closestHit.distance * (1 - np.e ** -rainfallRate) ** 2) # equation (9)
                
                    # coefficient following observation
                    backScatteringCoefficientRain = 0.01 * rainfallRate ** 0.6 # equation (5)

                    delta = np.e ** (-2 * backScatteringCoefficientRain * closestHit.distance) - 1

                surfaceReflectivity += delta

                alpha = 1.0

                if simulateDust:
                    # see: https://www.researchgate.net/publication/313582355_When_the_Dust_Settles_The_Four_Behaviors_of_LiDAR_in_the_Presence_of_Fine_Airborne_Particulates
                    Rt = closestHit.distance

                    r = particleRadius * 10**(-6)
                    n = particlesPcm
                    Ld = dustCloudLength
                    Rd = dustCloudStart

                    if Rt < Rd:
                        # target is in front of dust cloud -> no backscatter or reduction -> no action to perform
                        pass
                    else:
                        # target in or behind dust cloud
                        beta = (r**2 * n) / 4 # eq. (31)

                        if beta > rMin:
                            # light is reflected by the cloud -> appears as solid object

                            # calculate the direction vector 
                            dustDirection =  direction.normalized() * Rd

                            # calculate the dust cloud location of the hit point
                            dustLocation = dustDirection + origin

                            if debugOutput:
                                print("Dust Distance ", dustDirection)
                                print("Dust Location ", dustLocation)
                            
                            # update the closest hit to the dust cloud
                            closestHit.location = dustLocation
                            closestHit.distance = Rd
                            closestHit.intensity = beta
                        else:
                            # light enters the dust cloud

                            # the end is the length + the start distance
                            dustCloudEnd = Rd + Ld

                            if Rt < dustCloudEnd: 
                                # target inside dust cloud, so we need to calculate the part of the dust cloud
                                # which is IN FRONT of our target
                                relevantDustCloudLength = Rt - Rd
                                
                            else:
                                # target behind dust cloud, so the full length of the dust cloud reduces the power
                                relevantDustCloudLength = Ld
                            
                            # calculate the transmission loss
                            alpha = np.exp(-2 * np.pi * r**2 * n * (relevantDustCloudLength)) # eq. (32)

                surfaceReflectivity *= alpha

                isVisible = surfaceReflectivity > rMin #relativeSensorPower > minimumRelativePower:
                
                # if the return is not powerful enough, the detector can't see it at all
                if not isVisible:
                    closestHit.intensity = 0.0

                #if not isVisible:
                #    continue
                
                if debugOutput:
                    print("Visible ", isVisible, surfaceReflectivity, rMin)

                if addNoise:
                    # generate some noise
                    # error model: https://github.com/mgschwan/blensor/blob/master/release/scripts/addons/blensor/gaussian_error_model.py#L21
                    #              https://github.com/mgschwan/blensor/blob/0b6cca9f189b1e072cfd8aaa6360deeab0b96c61/release/scripts/addons/blensor/generic_lidar.py#L172
                    noise += error_distribution.applyNoise(mu, sigma)

                if debugOutput:
                    print("Location ", closestHit.location)
                    print("Direction ", direction)
                    print("Length ", closestHit.location.length)
                    print("Noise ", noise)
                    print("Distance ", closestHit.distance)
                
                if exportNoiseData:
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

                # save closest hit into array
                scannedValues[valueIndex] = closestHit
                valueIndex += 1
            else:
                if debugOutput:
                    print("NO HIT within range of %f" % distanceUpper)
            
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
    slicedScannedValues = scannedValues[startIndex:valueIndex]

    if addMesh:
        generic.addMeshToScene("real_values_frame_%d" % frameNumber, slicedScannedValues, False)

        if exportNoiseData:
            generic.addMeshToScene("noise_values_frame_%d" % frameNumber, slicedScannedValues, True)

    if measureTime:
        print("Meshes: %s s" % (time.time() - startTime))
        startTime = time.time()

    # save data to files
    if debugOutput:
        print("File path ", os.path.abspath(dataFilePath))

    if len(slicedScannedValues) > 0:
        # setup exporter with our data
        if exportLAS or exportHDF or exportCSV or exportSegmentedImage or exportRenderedImage or exportDepthmap:
            fileExporter = exporter.Exporter(dataFilePath, "%s_frame_%d" % (dataFileName, frameNumber), dataFileName, slicedScannedValues, targets, categoryIDs, partIDs, materialMappings, exportNoiseData, stepsX, stepsY)

            # export to each format
            if exportLAS:
                fileExporter.exportLAS()

            if exportHDF:
                fileExporter.exportHDF(fileNameExtra="_frames_%d_to_%d_single" % (firstFrame, lastFrame))

            if exportCSV:
                fileExporter.exportCSV()

            if scannerType == generic.ScannerType.static.name:
                if exportSegmentedImage:
                    fileExporter.exportSegmentedImage(exportPascalVoc)

                if exportRenderedImage:
                    fileExporter.exportRenderedImage()

                if exportDepthmap:
                    fileExporter.exportDepthmap(depthMinDistance, depthMaxDistance)
    else:
        print("No data to export!")

    if measureTime:
        print("Output: %s s" % (time.time() - startTime))

    

    print("Done.")

    return (valueIndex - startIndex)