# context.area: VIEW_3D

# add-on skeleton taken from: https://blender.stackexchange.com/a/57332

bl_info = {
    "name" : "range_scanner",
    "author" : "Lorenzo Neumann",
    "description" : "Range scanner simulation for Blender",
    "blender" : (2, 81, 0),
    "version" : (0, 0, 1),
    "location" : "3D View > Scanner",
    "warning" : "",
    "category" : "3D View",
    "wiki_url": "https://git.informatik.tu-freiberg.de/masterarbeit/blender-range-scanner",
}

import bpy
from bpy import context
import sys

from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       CollectionProperty,
                       )

from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       UIList
                       )

from bpy.utils import register_class, unregister_class


from ..scanners import hit_info
from ..scanners import generic

import time
import os
import importlib
import pathlib
import random
from mathutils import Vector, Euler
from math import radians

import numpy as np

# define location of UI panels
class MAIN_PANEL:
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Scanner"




############################################################# 
#                                                           #
#                 DEPENDENCY MANAGEMENT                     #
#                                                           #
#############################################################


# source: https://github.com/robertguetzkow/blender-python-examples/tree/master/add-ons/install-dependencies

#    Copyright (C) 2020  Robert Guetzkow
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>


import bpy
import subprocess
from collections import namedtuple

dependencies_installed = False

def import_module(module_name, global_name=None):
    """
    Import a module.
    :param module_name: Module to import.
    :param global_name: (Optional) Name under which the module is imported. If None the module_name will be used.
       This allows to import under a different name with the same effect as e.g. "import numpy as np" where "np" is
       the global_name under which the module can be accessed.
    :raises: ImportError and ModuleNotFoundError
    """

    if global_name is None:
        global_name = module_name

    # Attempt to import the module and assign it to globals dictionary. This allow to access the module under
    # the given name, just like the regular import would.
    globals()[global_name] = importlib.import_module(module_name)


def install_pip():
    """
    Installs pip if not already present. Please note that ensurepip.bootstrap() also calls pip, which adds the
    environment variable PIP_REQ_TRACKER. After ensurepip.bootstrap() finishes execution, the directory doesn't exist
    anymore. However, when subprocess is used to call pip, in order to install a package, the environment variables
    still contain PIP_REQ_TRACKER with the now nonexistent path. This is a problem since pip checks if PIP_REQ_TRACKER
    is set and if it is, attempts to use it as temp directory. This would result in an error because the
    directory can't be found. Therefore, PIP_REQ_TRACKER needs to be removed from environment variables.
    :return:
    """

    try:
        # Check if pip is already installed
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True)
    except subprocess.CalledProcessError:
        import ensurepip

        ensurepip.bootstrap()
        os.environ.pop("PIP_REQ_TRACKER", None)


def install_and_import_module(module, importName):
    """
    Installs the package through pip and attempts to import the installed module.
    :param module_name: Module to import.
    :param package_name: (Optional) Name of the package that needs to be installed. If None it is assumed to be equal
       to the module_name.
    :param global_name: (Optional) Name under which the module is imported. If None the module_name will be used.
       This allows to import under a different name with the same effect as e.g. "import numpy as np" where "np" is
       the global_name under which the module can be accessed.
    :raises: subprocess.CalledProcessError and ImportError
    """

    # Blender disables the loading of user site-packages by default. However, pip will still check them to determine
    # if a dependency is already installed. This can cause problems if the packages is installed in the user
    # site-packages and pip deems the requirement satisfied, but Blender cannot import the package from the user
    # site-packages. Hence, the environment variable PYTHONNOUSERSITE is set to disallow pip from checking the user
    # site-packages. If the package is not already installed for Blender's Python interpreter, it will then try to.
    # The paths used by pip can be checked with `subprocess.run([sys.executable, "-m", "site"], check=True)`

    # Store the original environment variables
    environ_orig = dict(os.environ)
    os.environ["PYTHONNOUSERSITE"] = "1"

    try:
        print(f"Installing {module}")

        # Try to install the package. This may fail with subprocess.CalledProcessError
        subprocess.run([sys.executable, "-m", "pip", "install", module], check=True)
    finally:
        # Always restore the original environment variables
        os.environ.clear()
        os.environ.update(environ_orig)

    # The installation succeeded, attempt to import the module again
    import_module(importName)



class WM_OT_INSTALL_DEPENDENCIES(Operator):
    bl_label = "Install dependencies"
    bl_idname = "wm.install_dependencies"

    @classmethod
    def poll(self, context):
        # Deactivate when dependencies have been installed
        return not dependencies_installed

    def execute(self, context):
        try:
            install_pip()

            requirementsPath = os.path.join(pathlib.Path(__file__).parent.parent.absolute(), "requirements.txt")
            print("Reading dependencies from {0}".format(requirementsPath))
            requirementsFile = open(requirementsPath, 'r')
            requirements = requirementsFile.readlines()
 
            importName = None

            # Strips the newline character
            for requirement in requirements:
                stripped = requirement.strip()

                if stripped.startswith("#/"):
                    importName = stripped.split("#/")[1]
                    continue

                if stripped.startswith("#") or not stripped:
                    continue

                name, version = stripped.split("==")

                if importName is None:
                    importName = name

                print(f"Checking {name}: version {version}, import {importName}")

                install_and_import_module(module=stripped, importName=importName)

                importName = None
        except (subprocess.CalledProcessError, ImportError) as err:
            print("ERROR: %s" % str(err))
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}

        global dependencies_installed
        dependencies_installed = True
        
        return {"FINISHED"}

class EXAMPLE_PT_DEPENDENCIES_PANEL(MAIN_PANEL, Panel):
    bl_label = "Missing dependencies"

    @classmethod
    def poll(self, context):
        return not dependencies_installed

    def draw(self, context):
        layout = self.layout

        lines = [f"You need to install some dependencies to use this add-on.",
                 f"Click the button below to start (requires to run blender",
                 f"with administrative privileges on Windows)."]

        for line in lines:
            layout.label(text=line)

        layout.operator("wm.install_dependencies")










############################################################# 
#                                                           #
#                       PRESETS                             #
#                                                           #
#############################################################

class WM_OT_LOAD_PRESET(Operator):
    bl_label = "Load preset"
    bl_idname = "wm.load_preset"
    bl_description = "Loads all values for the selected scanner type"

    @classmethod
    def poll(self, context):
        return True

    def execute(self, context):
        scene = context.scene
        properties = scene.scannerProperties

        print("Loading preset for %s..." % properties.scannerName)

        for preset in config:
            if preset["name"] != properties.scannerName:
                continue

            scannerMode = preset["type"]

            if scannerMode == generic.ScannerType.rotating.name:
                for key, value in preset.items(): 
                    if key == "name" or key == "description" or key == "category":
                        # we don't need the name, description, ...
                        continue

                    if key == "type":
                        properties.scannerType = value
                    elif key == "reflectivityLower":
                        properties.reflectivityLower = value
                    elif key == "distanceLower":
                        properties.distanceLower = value
                    elif key == "reflectivityUpper":
                        properties.reflectivityUpper = value
                    elif key == "distanceUpper":
                        properties.distanceUpper = value
                    elif key == "fovX":
                        properties.fovX = value
                    elif key == "xStepDegree":
                        properties.xStepDegree = value
                    elif key == "fovY":
                        properties.fovY = value
                    elif key == "yStepDegree":
                        properties.yStepDegree = value
                    elif key == "rotationsPerSecond":
                        properties.rotationsPerSecond = value
                    else:
                        print("Invalid key: %s" % key)

            elif scannerMode == generic.ScannerType.static.name:
                for key, value in preset.items(): 
                    if key == "name" or key == "description" or key == "category":
                        # we don't need the name, description, ...
                        continue

                    if key == "type":
                        properties.scannerType = value
                    elif key == "reflectivityLower":
                        properties.reflectivityLower = value
                    elif key == "distanceLower":
                        properties.distanceLower = value
                    elif key == "reflectivityUpper":
                        properties.reflectivityUpper = value
                    elif key == "distanceUpper":
                        properties.distanceUpper = value
                    elif key == "resolutionX":
                        properties.resolutionX = value
                    elif key == "fovX":
                        properties.fovX = value
                    elif key == "resolutionY":
                        properties.resolutionY = value
                    elif key == "fovY":
                        properties.fovY = value
                    elif key == "resolutionPercentage":
                        properties.resolutionPercentage = value
                    else:
                        print("Invalid key: %s" % key)
            
            elif scannerMode == generic.ScannerType.sideScan.name:
                for key, value in preset.items(): 
                    if key == "name" or key == "description" or key == "category":
                        # we don't need the name, description, ...
                        continue

                    if key == "type":
                        properties.scannerType = value
                    elif key == "reflectivityLower":
                        properties.reflectivityLower = value
                    elif key == "distanceLower":
                        properties.distanceLower = value
                    elif key == "reflectivityUpper":
                        properties.reflectivityUpper = value
                    elif key == "distanceUpper":
                        properties.distanceUpper = value
                        properties.fovX = value
                    elif key == "resolution":
                        properties.sonarStepDegree = value
                    elif key == "fovDown":
                        properties.fovSonar = value
                    elif key == "waterProfile":
                        # remove all entries
                        scene.custom.clear()

                        # add each item to the list
                        for index, item in enumerate(value):
                            if not ("depth" in item):
                                print("Water profile must contain depth value!")
                                continue

                            if not ("speed" in item):
                                print("Water profile must contain speed value!")
                                continue

                            if not ("density" in item):
                                print("Water profile must contain density value!")
                                continue
                            
                            depth = item["depth"]
                            speed = item["speed"]
                            density = item["density"]

                            addItemToList(depth, speed, density, scene.custom, scene.custom_index)

                        # cleanup list
                        removeDuplicatesFromList(scene.custom, scene.custom_index)

                        sortList(scene.custom)

                    else:
                        print("Invalid key: %s" % key)
            else:
                print("Unknown scanner type %s!" % scannerMode)

        print("Done.")

        return {"FINISHED"}

def mapConfig(item):
    return (item["name"], item["name"], item["description"])

def scannerTypeCallback(scene, context):
    # filter all scanners which belong to the category that is currently selected by scannerCategory
    return map(lambda item: mapConfig(item), filter(lambda x: x["category"] == context.scene.scannerProperties.scannerCategory, config))

def scannerCategoryCallback(scene, context):
    return [
        ("lidar", "Lidar", "lidar"), 
        ("sonar", "Sonar", "sonar"), 
        ("tof", "Time of flight", "tof")
    ]

def waetherTypeCallback(scene, context):
    return [
        ("rain", "Rain", "rain"), 
        ("dust", "Dust", "dust"), 
    ]










############################################################# 
#                                                           #
#                      SCANNER SETTINGS                     #
#                                                           #
#############################################################

# decide if we want to show a certain object in the selection dropdown
def scannerObjectPoll(self, object):
    return object.type == 'CAMERA'

# define all properties needed for all types of scanners
class ScannerProperties(PropertyGroup):
    # GENERAL
    scannerObject: PointerProperty(
        name="", 
        description="Select object which should be used as scanner",
        type=bpy.types.Object,
        poll=scannerObjectPoll
    )

    joinMeshes: BoolProperty(
        name="Join static meshes",
        description="Join all static meshes in the scene",
        default = False
    )



    # PRESETS
    scannerCategory: EnumProperty(
        name="Scanner category",
        description="Select scanner type",
        items=scannerCategoryCallback, # https://blender.stackexchange.com/a/10919/95167
    )

    scannerName: EnumProperty(
        name="Scanner",
        description="Select scanner",
        items=scannerTypeCallback, # https://blender.stackexchange.com/a/10919/95167
    )





    # REFLECTIVITY
    reflectivityLower: FloatProperty(
        name = "Lower reflectivity",
        description = "minimum angle (degree)",
        default = 0.1,
        min = 0.0,
        max = 1.0
    )

    distanceLower: FloatProperty(
        name = "Lower distance",
        description = "minimum angle (degree)",
        default = 50.0,
        min = 0,
        max = 99999
    )

    reflectivityUpper: FloatProperty(
        name = "Upper reflectivity",
        description = "minimum angle (degree)",
        default = 0.9,
        min = 0.0,
        max = 1.0
    )

    distanceUpper: FloatProperty(
        name = "Upper distance",
        description = "minimum angle (degree)",
        default = 120,
        min = 0,
        max = 999999
    )

    maxReflectionDepth: IntProperty(
        name = "Maximum reflection depth",
        description = "The maximum number of reflections before a ray is discarded",
        default = 10,
        min = 0,
        max = 1000
    )





    # SCANNER
    fovX: FloatProperty(
        name = "Horizontal FOV",
        description = "Horizontal field of view in degrees",
        default = 90.0,
        min = 0.0,
        max = 360.0
    )

    fovY: FloatProperty(
        name = "Vertical FOV",
        description = "Vertical field of view in degrees",
        default = 45,
        min = 0.0,
        max = 360.0
    )




    # ANIMATION
    enableAnimation: BoolProperty(
        name="Enable animation",
        description="Enable or disable the calculation for multiple frames",
        default = False
    )

    frameStart: IntProperty(
        name = "Frame start",
        description = "The first frame to be rendered",
        default = 1,
    )

    frameEnd: IntProperty(
        name = "Frame end",
        description = "The last frame to be rendered",
        default = 10
    )

    frameStep: IntProperty(
        name = "Frame step",
        description = "Number of frames to skip",
        default = 1,
    )

    frameRate: FloatProperty(
        name = "Frame rate",
        description = "Frames per second",
        default = 24.0,
    )





    # OBJECT MODIFICATION
    swapObject: PointerProperty(
        name="", 
        description="Select object which should be swapped out",
        type=bpy.types.Object,
    )

    enableSwapping: BoolProperty(
        name="Enable swapping",
        description="Enable or disable replacing the selected object with different models",
        default = False
    )

    modelsFilePath : StringProperty(
        name="Models location",
        description="Path to directory of models (.obj)",
        default="",
        maxlen=2048,
        subtype='DIR_PATH'
    )

    enableModification: BoolProperty(
        name="Enable random modification",
        description="Enable or disable modification of the selected object",
        default = False
    )

    numberOfModifications: IntProperty(
        name = "Number of modifications",
        description = "The number of modifications applied to the object",
        default = 1,
        min = 0,
        max = 10000
    )

    minTransX: FloatProperty(
        name = "Lower bound X",
        description = "Lower deviation bound of translation on the X axis",
        default = -1.0,
        min = -10000.0,
        max = 0.0
    )

    maxTransX: FloatProperty(
        name = "Upper bound X",
        description = "Upper deviation bound of translation on the X axis",
        default = 1.0,
        min = 0.0,
        max = 10000.0
    )

    minTransY: FloatProperty(
        name = "Lower bound Y",
        description = "Lower deviation bound of translation on the Y axis",
        default = -1.0,
        min = -10000.0,
        max = 0.0
    )

    maxTransY: FloatProperty(
        name = "Upper bound Y",
        description = "Upper deviation bound of translation on the Y axis",
        default = 1.0,
        min = 0.0,
        max = 10000.0
    )

    minTransZ: FloatProperty(
        name = "Lower bound Z",
        description = "Lower deviation bound of translation on the Z axis",
        default = -1.0,
        min = -10000.0,
        max = 0.0
    )

    maxTransZ: FloatProperty(
        name = "Upper bound Z",
        description = "Upper deviation bound of translation on the Z axis",
        default = 1.0,
        min = 0.0,
        max = 10000.0
    )


    minRotX: FloatProperty(
        name = "Lower bound X",
        description = "Lower deviation bound of rotation around the X axis in degree",
        default = -5.0,
        min = -10000.0,
        max = 0.0
    )

    maxRotX: FloatProperty(
        name = "Upper bound X",
        description = "Upper deviation bound of rotation around the X axis in degree",
        default = 5.0,
        min = 0.0,
        max = 10000.0
    )

    minRotY: FloatProperty(
        name = "Lower bound Y",
        description = "Lower deviation bound of rotation around the Y axis in degree",
        default = -5.0,
        min = -10000.0,
        max = 0.0
    )

    maxRotY: FloatProperty(
        name = "Upper bound Y",
        description = "Upper deviation bound of rotation around the Y axis in degree",
        default = 5.0,
        min = 0.0,
        max = 10000.0
    )

    minRotZ: FloatProperty(
        name = "Lower bound Z",
        description = "Lower deviation bound of rotation around the Z axis in degree",
        default = -5.0,
        min = -10000.0,
        max = 0.0
    )

    maxRotZ: FloatProperty(
        name = "Upper bound Z",
        description = "Upper deviation bound of rotation around the Z axis in degree",
        default = 5.0,
        min = 0.0,
        max = 10000.0
    )



    uniformScaling: BoolProperty(
        name="Enable uniform scaling",
        description="Enable or disable if all axes should be equally scaled",
        default = True
    )

    minScaleAll: FloatProperty(
        name = "Lower bound",
        description = "Lower deviation bound of scale on the X axis",
        default = 0.9,
        min = 0.0,
        max = 1.0
    )

    maxScaleAll: FloatProperty(
        name = "Upper bound",
        description = "Upper deviation bound of scale on the X axis",
        default = 1.1,
        min = 1.0,
        max = 10000.0
    )

    minScaleX: FloatProperty(
        name = "Lower bound X",
        description = "Lower deviation bound of scale on the X axis",
        default = 0.9,
        min = 0.0,
        max = 1.0
    )

    maxScaleX: FloatProperty(
        name = "Upper bound X",
        description = "Upper deviation bound of scale on the X axis",
        default = 1.1,
        min = 1.0,
        max = 10000.0
    )

    minScaleY: FloatProperty(
        name = "Lower bound Y",
        description = "Lower deviation bound of scale on the Y axis",
        default = 0.9,
        min = 0.0,
        max = 1.0
    )

    maxScaleY: FloatProperty(
        name = "Upper bound Y",
        description = "Upper deviation bound of scale on the Y axis",
        default = 1.1,
        min = 1.0,
        max = 10000.0
    )

    minScaleZ: FloatProperty(
        name = "Lower bound Z",
        description = "Lower deviation bound of scale on the Z axis",
        default = 0.9,
        min = 0.0,
        max = 1.0
    )

    maxScaleZ: FloatProperty(
        name = "Upper bound Z",
        description = "Upper deviation bound of scale on the Z axis",
        default = 1.1,
        min = 1.0,
        max = 10000.0
    )





    # NOISE
    addNoise: BoolProperty(
        name="Add noise",
        description="Enable or disable noise",
        default = True
    )

    noiseType: EnumProperty(
        name="Noise type",
        description="Select noise type",
        items=[ ('gaussian', "Gaussian", ""),
        ]
    )

    mu: FloatProperty(
        name = "Mean",
        description = "Mean",
        default = 0.0,
    )

    sigma: FloatProperty(
        name = "Standard deviation",
        description = "Standard deviation",
        default = 0.01,
    )


    addConstantNoise: BoolProperty(
        name="Add constant offset",
        description="Enable or disable constant offset",
        default = True
    )

    noiseAbsoluteOffset: FloatProperty(
        name = "Absolute offset (meter)",
        description = "A constant absolute offset (in meter) which is added on every measurement",
        default = 0.0,
    )

    noiseRelativeOffset: FloatProperty(
        name = "Relative offset (percent)",
        description = "A constant relative offset (in percent) which is added on every measurement",
        default = 0.0,
    )




    # WEATHER
    weatherType: EnumProperty(
        name="Type",
        description="Select weather type",
        items=waetherTypeCallback,
    )

    # RAIN
    simulateRain: BoolProperty(
        name="Simulate Rain",
        description="Enable or disable rain simulation",
        default = False
    )

    rainfallRate: FloatProperty(
        name = "Rainfall rate (mm/h)",
        description = "Rainfall rate in mm/h",
        default = 10.0,
        min = 0.0
    )

    # DUST
    simulateDust: BoolProperty(
        name="Simulate dust",
        description="Enable or disable dust simulation",
        default = False
    )

    particleRadius: FloatProperty(
        name = "Particle radius (µm)",
        description = "Particle radius in microns",
        default = 50.0,
        min = 0.0,
        max = 100000.0
    )

    particlesPcm: FloatProperty(
        name = "Particle density (pcm)",
        description = "Particles per cubic meter",
        default = 100000.0,
        min = 0.0,
        max = 1000000000.0
    )

    dustCloudStart: FloatProperty(
        name = "Distance (m)",
        description = "Distance between sensor and dust cloud in meter",
        default = 5.0,
        min = 0.0,
        max = 1000000000.0
    ) 

    dustCloudLength: FloatProperty(
        name = "Length (m)",
        description = "Length of dust cloud in meter",
        default = 12.5,
        min = 0.0,
        max = 1000000.0
    ) 





    # VISUALIZATION
    addMesh: BoolProperty(
        name="Add datapoint mesh",
        description="Enable or disable if a single mesh of points should be added for all measurements",
        default = True
    ) 





    # EXPORT
    exportLAS: BoolProperty(
        name="Export .las file",
        description="Enable or disable if data should be saved into .las file format",
        default = False
    ) 

    exportHDF: BoolProperty(
        name="Export .hdf file",
        description="Enable or disable if data should be saved into .hdf file format",
        default = False
    ) 

    exportCSV: BoolProperty(
        name="Export .csv file",
        description="Enable or disable if data should be saved into .csv file format",
        default = False
    ) 

    exportSingleFrames: BoolProperty(
        name="Export single frames",
        description="If enabled, each frame of the animation is saved as separate dataset. If disabled, all frames are merged into one dataset",
        default = False
    ) 

    dataFilePath : StringProperty(
        name="Directory",
        description="Path to Directory",
        default="",
        maxlen=2048,
        subtype='DIR_PATH'
    )

    dataFileName : StringProperty(
        name="File name",
        description="File name (without extension!)",
        default="",
        maxlen=2048,
        subtype='FILE_NAME'
    )

    exportRenderedImage: BoolProperty(
        name="Export rendered image",
        description="Enable or disable if scene should be rendered",
        default = False
    ) 

    exportSegmentedImage: BoolProperty(
        name="Export segmented image",
        description="Enable or disable if data should be visualized as segmented image",
        default = False
    ) 

    exportPascalVoc: BoolProperty(
        name="Export pascal voc",
        description="Enable or disable if data should be exported as .xml in the pascal voc format",
        default = False
    )

    exportDepthmap: BoolProperty(
        name="Export depthmap",
        description="Enable or disable if data should be visualized as depthmap",
        default = False
    )

    depthMinDistance: FloatProperty(
        name = "Minimum",
        description = "Minimum distance (white)",
        default = 0.0,
        min = 0.0,
    )

    depthMaxDistance: FloatProperty(
        name = "Maximum",
        description = "Maximum distance (black)",
        default = 50.0,
        min = 0.0,
    )


    imageFilePath : StringProperty(
        name="Save location",
        description="Path to Directory",
        default="",
        maxlen=2048,
        subtype='DIR_PATH'
    )





    # DEBUG
    debugLines: BoolProperty(
        name="Debug lines",
        description="Enable or disable scanner lines (WARNING: can be very slow)",
        default = False
    )

    debugOutput: BoolProperty(
        name="Debug output",
        description="Enable or disable additional output (WARNING: can be very slow)",
        default = False
    )

    outputProgress: BoolProperty(
        name="Output progress",
        description="Enable or disable progress output (WARNING: can be very slow)",
        default = False
    )

    measureTime: BoolProperty(
        name="Measure time",
        description="Enable or disable time measurement",
        default = False
    )

    singleRay: BoolProperty(
        name="Single ray",
        description="Enable or disable if only a single ray should be fired towards 'dest' object",
        default = False
    )

    destinationObject: PointerProperty(
        name="", 
        description="Select destination object which should be used to calculate the ray direction",
        type=bpy.types.Object,
    )

    targetObject: PointerProperty(
        name="", 
        description="Select target object which the ray should hit",
        type=bpy.types.Object,
    )

    scannerType: EnumProperty(
        name="",
        description="Select scanner type",
        items=[
            (generic.ScannerType.static.name, generic.ScannerType.static.name, ""),
            (generic.ScannerType.rotating.name, generic.ScannerType.rotating.name, ""), 
            (generic.ScannerType.sideScan.name, generic.ScannerType.sideScan.name, "") 
         ],
    )


    ############################################################# 
    #                                                           #
    #               ROTATING SCANNER SETTINGS                   #
    #                                                           #
    #############################################################

    # SCANNER
    xStepDegree: FloatProperty(
        name = "Resolution horizontal",
        description = "distance between scan lines (degree)",
        default = 1.0,
        min = 0.01,
        max = 360.0
    )
        
    yStepDegree: FloatProperty(
        name = "Resolution vertical",
        description = "distance between scan lines (degree)",
        default = 1.0,
        min = 0.01,
        max = 180.0
    )

    rotationsPerSecond: FloatProperty(
        name = "Rotations per second",
        description = "Number of rotations the sensor performs in one second",
        default = 10.0,
        min = 0.01,
        max = 1000.0
    )


    ############################################################# 
    #                                                           #
    #                STATIC SCANNER SETTINGS                    #
    #                                                           #
    #############################################################

    # CAMERA
    resolutionX: IntProperty(
        name = "Width",
        description = "Number of pixels in x direction",
        default = 320,
        min = 1,
        max = 1000000
    )

    resolutionY: IntProperty(
        name = "Height",
        description = "Number of pixels in y direction",
        default = 240,
        min = 1,
        max = 1000000,
    )
    
    resolutionPercentage: FloatProperty(
        name = "Scale",
        description = "Percentage to scale the resolution",
        default = 100.0,
        min = 0.01,
        max = 100000.0
    )


    ############################################################# 
    #                                                           #
    #                      SONAR SETTINGS                       #
    #                                                           #
    #############################################################


    
    fovSonar: FloatProperty(
        name = "FOV down",
        description = "Downwards field of view in degrees",
        default = 45.0,
        min = 0.0,
        max = 180.0
    )


    sonarStepDegree: FloatProperty(
        name = "Scan resolution",
        description = "distance between scan lines (degree)",
        default = 1.0,
        min = 0.01,
        max = 180.0
    )

    sonarMode3D: BoolProperty(
        name="3D Mode",
        description="Enable or disable 3D data points",
        default = False
    )

    sonarKeepRotation: BoolProperty(
        name="Use sensor rotation",
        description="Decide if point slices should be perpendicular to sensor movement or aligned in one direction",
        default = False
    )


    # default values taken from this example: https://dosits.org/science/advanced-topics/sonar-equation/sonar-equation-example-active-sonar/
    sourceLevel: FloatProperty(
        name = "Source level",
        description = "The signals source level in dB",
        default = 200.0,
        min = 0.01,
        max = 10000.0
    )

    noiseLevel: FloatProperty(
        name = "Noise level",
        description = "The noise level in dB",
        default = 50.0,
        min = 0.01,
        max = 10000.0
    )

    directivityIndex: FloatProperty(
        name = "Directivity index",
        description = "The directivity index in dB",
        default = 20.0,
        min = 0.01,
        max = 10000.0
    )

    processingGain: FloatProperty(
        name = "Processing gain",
        description = "The processing gain in dB",
        default = 10.0,
        min = 0.01,
        max = 10000.0
    )

    receptionThreshold: FloatProperty(
        name = "Reception threshold",
        description = "The reception threshold in dB",
        default = 10.0,
        min = 0.01,
        max = 10000.0
    )

    maxDistance: FloatProperty(
        name="Maximum distance", 
        description="",
        default = 100.0,
        min = 0.01,
        max = 10000.0
    )

    simulateWaterProfile: BoolProperty(
        name="Simulate water profile",
        description="Enable or disable simulation of the water profile",
        default = False
    )

    surfaceHeight: FloatProperty(
        name="Water surface level", 
        description="The height of the water surface in the scene",
        default = 10.0
    )

    refractionDepth: FloatProperty(
        name="Water depth", 
        description="The lower depth of the water layer with the given refractive index",
    )

    refractionSpeed: FloatProperty(
        name="Speed", 
        description="The propagation speed of the wave in the current water layer (m/s",
    )

    refractionDensity: FloatProperty(
        name="Density", 
        description="The density of the current water layer (kg/m³)",
    )










############################################################# 
#                                                           #
#                      USER INTERFACE                       #
#                                                           #
#############################################################

def modifyAndScan(context, dependencies_installed, properties, objectName):
    # random modifications enabled
    if properties.enableModification:
        # store the objects pose as default
        matrixWorld = properties.swapObject.matrix_world.copy() # use copy or the variable itself is also changed
        matrixWorldDecomposed = matrixWorld.decompose()
        oldLocation = matrixWorldDecomposed[0]
        oldRotation = matrixWorldDecomposed[1].to_euler()
        oldScale = matrixWorldDecomposed[2]

        # repeat the given number of times
        for i in range(properties.numberOfModifications):
            # generate random values for translation, rotation and scaling
            transX = random.uniform(properties.minTransX, properties.maxTransX)
            transY = random.uniform(properties.minTransY, properties.maxTransY)
            transZ = random.uniform(properties.minTransZ, properties.maxTransZ)

            # add the values
            properties.swapObject.location = oldLocation + Vector((transX, transY, transZ))
            
            rotX = random.uniform(properties.minRotX, properties.maxRotX)
            rotY = random.uniform(properties.minRotY, properties.maxRotY)
            rotZ = random.uniform(properties.minRotZ, properties.maxRotZ)

            properties.swapObject.rotation_mode = 'XYZ'
            properties.swapObject.rotation_euler = Euler((oldRotation[0] + radians(rotX), oldRotation[1] + radians(rotY), oldRotation[2] + radians(rotZ)), 'XYZ')

            # if uniform sclaing is enabled, all values should be scaled the same
            if properties.uniformScaling:
                scaleAll = random.uniform(properties.minScaleAll, properties.maxScaleAll)
                properties.swapObject.scale[0] = oldScale[0] * scaleAll
                properties.swapObject.scale[1] = oldScale[1] * scaleAll
                properties.swapObject.scale[2] = oldScale[2] * scaleAll
            else:
                scaleX = random.uniform(properties.minScaleX, properties.maxScaleX)
                scaleY = random.uniform(properties.minScaleY, properties.maxScaleY)
                scaleZ = random.uniform(properties.minScaleZ, properties.maxScaleZ)
                properties.swapObject.scale[0] = oldScale[0] * scaleX
                properties.swapObject.scale[1] = oldScale[1] * scaleY
                properties.swapObject.scale[2] = oldScale[2] * scaleZ

            generic.startScan(context, dependencies_installed, properties, "%s_mod_%d" % (objectName, i))

        # reset the matrix so that the next run can start from zero
        properties.swapObject.matrix_world = matrixWorld
    else:
        generic.startScan(context, dependencies_installed, properties, objectName)

def performScan(context, dependencies_installed, properties):
    if properties.joinMeshes:
        # for large groups of objects it seems to be a good idea to join them into one
        # mesh to speed up performance
        # of course this also needs some time, but it still faster overall

        # get all meshes, but exclude animated objects and the swap object as they are
        # modified during the simulation
        targets = list(filter(lambda x: x.type == 'MESH' and # object has some kind of geometry
                                        x != properties.swapObject and # exclude swap object
                                        (x.animation_data == None or x.animation_data.action == None) and # exclude animated objects
                                        x.hide_get() == False and # exclude hidden objects
                                        x.active_material != None and # only consider targets with a material set
                                        'categoryID' not in x and 'partID' not in x # exclude objects with semantic mappings
        , bpy.context.scene.objects))

        if len(targets) > 1:
            # the following block joins all objects so that there is only one BVHTree for all of them
            # this leads to some perfomance improvement, but needs more memory as objects are stored
            # multiple times instead of using instances
            bpy.ops.object.select_all(action='DESELECT')

            for target in targets:
                target.select_set(True)

            context.view_layer.objects.active = targets[0]

            print("Joining %d meshes..." % len(targets))
            
            bpy.ops.object.join()

            print("Done.")

    # swapping enabled, so load all objects inside the given path and place them into the scene
    if properties.enableSwapping:
        # get all files that can be imported in a given directory
        filePaths = []

        absolutePath = bpy.path.abspath(properties.modelsFilePath)

        for path, _, files in os.walk(absolutePath):
            for name in files:
                if name.endswith(".fbx") or name.endswith(".gltf") or name.endswith(".glb") or name.endswith(".obj"): # or name.endswith(".x3d") or name.endswith(".wrl"):
                    # get the full path wich is used to load the obj file
                    fullPath = os.path.join(path, name)

                    # get the relative path inside the chosen directory to use it as unique name for the output file
                    relativePath = os.path.relpath(fullPath, absolutePath)
                    
                    filePaths.append((fullPath, relativePath))
                    
                    print("Found file: ", fullPath)
                    
        for (currentFile, fileName) in filePaths:
            print("Loading model %s" % currentFile)

            # import file
            if fileName.endswith(".glb") or fileName.endswith(".gltf") :
                bpy.ops.import_scene.gltf(filepath=currentFile)
                bpy.context.active_object.select_set(True)

            else:   
                if fileName.endswith(".fbx"):
                    bpy.ops.import_scene.fbx(filepath=currentFile)

                if fileName.endswith(".glb") or fileName.endswith(".gltf") :
                    bpy.ops.import_scene.gltf(filepath=currentFile)

                if fileName.endswith(".obj"):
                    bpy.ops.import_scene.obj(filepath=currentFile)

                # the .x3d format importer seems to not support materials -> the scanner needs some material to perform calculations,
                # so we don't use this format for now :(
                #if fileName.endswith(".x3d") or fileName.endswith(".wrl"):
                #    bpy.ops.import_scene.x3d(filepath=currentFile)
                
                # set the selected objects active
                # we don't need this step fpr gltf files as the importer already sets the object as active
                context.view_layer.objects.active = bpy.context.selected_objects[0]
            
            # join objects in case the model consists of multiple parts
            # otherwise we can't simply transfer all properties of the original object
            bpy.ops.object.join()

            # get reference to imported object
            importedObject = context.view_layer.objects.active

            # we copy the data instead of deleting the old and adding the new object
            # to keep properties like translation, rotation, animation steps, etc.
            properties.swapObject.data = importedObject.data

            # if you want to keep the translation (or any other property) of the original object, you can use following code
            #originalTranslation = properties.swapObject.matrix_world.translation.copy()
            #properties.swapObject.matrix_world = importedObject.matrix_world
            #properties.swapObject.matrix_world.translation = originalTranslation

            # delete the imported object as we copied it and don't need it anymore
            bpy.ops.object.delete({"selected_objects": [importedObject]})

            modifyAndScan(context, dependencies_installed, properties, fileName)
    else:
        modifyAndScan(context, dependencies_installed, properties, None)

def scan_rotating(context, 
        scannerObject,

        xStepDegree, fovX, yStepDegree, fovY, rotationsPerSecond,

        reflectivityLower, distanceLower, reflectivityUpper, distanceUpper, maxReflectionDepth,
        
        enableAnimation, frameStart, frameEnd, frameStep, frameRate,

        addNoise, noiseType, mu, sigma, noiseAbsoluteOffset, noiseRelativeOffset,

        simulateRain, rainfallRate, 

        addMesh,

        exportLAS, exportHDF, exportCSV, exportSingleFrames,
        dataFilePath, dataFileName,
        
        debugLines, debugOutput, outputProgress, measureTime, singleRay, destinationObject, targetObject,
):

    scene = context.scene
    properties = scene.scannerProperties

    properties.scannerType = 'rotating'
    properties.scannerObject = scannerObject

    properties.fovX = fovX
    properties.fovY = fovY
    properties.xStepDegree = xStepDegree
    properties.yStepDegree = yStepDegree
    properties.rotationsPerSecond = rotationsPerSecond

    properties.reflectivityLower = reflectivityLower
    properties.distanceLower = distanceLower
    properties.reflectivityUpper = reflectivityUpper
    properties.distanceUpper = distanceUpper
    properties.maxReflectionDepth = maxReflectionDepth
    
    properties.enableAnimation = enableAnimation
    properties.frameStart = frameStart
    properties.frameEnd = frameEnd
    properties.frameStep = frameStep
    properties.frameRate = frameRate

    properties.addNoise = addNoise
    properties.noiseType = noiseType
    properties.mu = mu
    properties.sigma = sigma
    properties.noiseAbsoluteOffset = noiseAbsoluteOffset
    properties.noiseRelativeOffset = noiseRelativeOffset

    properties.simulateRain = simulateRain
    properties.rainfallRate = rainfallRate

    properties.addMesh = addMesh

    properties.exportLAS = exportLAS
    properties.exportHDF = exportHDF
    properties.exportCSV = exportCSV
    properties.exportSingleFrames = exportSingleFrames
    properties.dataFilePath = dataFilePath
    properties.dataFileName = dataFileName
    
    properties.debugLines = debugLines
    properties.debugOutput = debugOutput
    properties.outputProgress = outputProgress
    properties.measureTime = measureTime
    properties.singleRay = singleRay
    properties.destinationObject = destinationObject
    properties.targetObject = targetObject

    performScan(context, dependencies_installed, properties)

def scan_sonar(context, 
        scannerObject,

        maxDistance, fovSonar, sonarStepDegree, sonarMode3D, sonarKeepRotation,

        sourceLevel, noiseLevel, directivityIndex, processingGain, receptionThreshold,   

        simulateWaterProfile, depthList,  

        enableAnimation, frameStart, frameEnd, frameStep,

        addNoise, noiseType, mu, sigma, noiseAbsoluteOffset, noiseRelativeOffset,

        simulateRain, rainfallRate, 

        addMesh,

        exportLAS, exportHDF, exportCSV, exportSingleFrames,
        dataFilePath, dataFileName,
        
        debugLines, debugOutput, outputProgress, measureTime, singleRay, destinationObject, targetObject,
):

    scene = context.scene
    properties = scene.scannerProperties

    properties.scannerType = 'sideScan'
    properties.scannerObject = scannerObject

    properties.maxDistance = maxDistance
    properties.fovSonar = fovSonar
    properties.sonarStepDegree = sonarStepDegree
    properties.sonarMode3D = sonarMode3D
    properties.sonarKeepRotation = sonarKeepRotation

    properties.sourceLevel = sourceLevel
    properties.noiseLevel = noiseLevel
    properties.directivityIndex = directivityIndex
    properties.processingGain = processingGain
    properties.receptionThreshold = receptionThreshold

    properties.simulateWaterProfile = simulateWaterProfile
    properties.depthList = depthList

    properties.enableAnimation = enableAnimation
    properties.frameStart = frameStart
    properties.frameEnd = frameEnd
    properties.frameStep = frameStep

    properties.addNoise = addNoise
    properties.noiseType = noiseType
    properties.mu = mu
    properties.sigma = sigma
    properties.noiseAbsoluteOffset = noiseAbsoluteOffset
    properties.noiseRelativeOffset = noiseRelativeOffset

    properties.simulateRain = simulateRain
    properties.rainfallRate = rainfallRate

    properties.addMesh = addMesh

    properties.exportLAS = exportLAS
    properties.exportHDF = exportHDF
    properties.exportCSV = exportCSV
    properties.exportSingleFrames = exportSingleFrames
    properties.dataFilePath = dataFilePath
    properties.dataFileName = dataFileName
    
    properties.debugLines = debugLines
    properties.debugOutput = debugOutput
    properties.outputProgress = outputProgress
    properties.measureTime = measureTime
    properties.singleRay = singleRay
    properties.destinationObject = destinationObject
    properties.targetObject = targetObject

    performScan(context, dependencies_installed, properties)


def scan_static(context, 
        scannerObject,

        resolutionX, fovX, resolutionY, fovY, resolutionPercentage,

        reflectivityLower, distanceLower, reflectivityUpper, distanceUpper, maxReflectionDepth,
        
        enableAnimation, frameStart, frameEnd, frameStep, frameRate,

        addNoise, noiseType, mu, sigma, noiseAbsoluteOffset, noiseRelativeOffset,

        simulateRain, rainfallRate, 

        addMesh,

        exportLAS, exportHDF, exportCSV, exportSingleFrames,
        exportRenderedImage, exportSegmentedImage, exportPascalVoc, exportDepthmap, depthMinDistance, depthMaxDistance, 
        dataFilePath, dataFileName,
        
        debugLines, debugOutput, outputProgress, measureTime, singleRay, destinationObject, targetObject,
):

    scene = context.scene
    properties = scene.scannerProperties

    properties.scannerType = 'static'
    properties.scannerObject = scannerObject

    properties.resolutionX =  resolutionX
    properties.fovX = fovX
    properties.resolutionY = resolutionY
    properties.fovY = fovY
    properties.resolutionPercentage = resolutionPercentage

    properties.reflectivityLower = reflectivityLower
    properties.distanceLower = distanceLower
    properties.reflectivityUpper = reflectivityUpper
    properties.distanceUpper = distanceUpper
    properties.maxReflectionDepth = maxReflectionDepth
    
    properties.enableAnimation = enableAnimation
    properties.frameStart = frameStart
    properties.frameEnd = frameEnd
    properties.frameStep = frameStep
    properties.frameRate = frameRate

    properties.addNoise = addNoise
    properties.noiseType = noiseType
    properties.mu = mu
    properties.sigma = sigma
    properties.noiseAbsoluteOffset = noiseAbsoluteOffset
    properties.noiseRelativeOffset = noiseRelativeOffset

    properties.simulateRain = simulateRain
    properties.rainfallRate = rainfallRate

    properties.addMesh = addMesh

    properties.exportLAS = exportLAS
    properties.exportHDF = exportHDF
    properties.exportCSV = exportCSV
    properties.exportSingleFrames = exportSingleFrames
    properties.exportRenderedImage = exportRenderedImage
    properties.exportSegmentedImage = exportSegmentedImage
    properties.exportPascalVoc = exportPascalVoc
    properties.exportDepthmap = exportDepthmap
    properties.depthMinDistance = depthMinDistance
    properties.depthMaxDistance = depthMaxDistance
    properties.dataFilePath = dataFilePath
    properties.dataFileName = dataFileName
    
    properties.debugLines = debugLines
    properties.debugOutput = debugOutput
    properties.outputProgress = outputProgress
    properties.measureTime = measureTime
    properties.singleRay = singleRay
    properties.destinationObject = destinationObject
    properties.targetObject = targetObject

    performScan(context, dependencies_installed, properties)

class WM_OT_GENERATE_POINT_CLOUDS(Operator):
    bl_label = "Generate point clouds"
    bl_idname = "wm.execute_scan"
    bl_description = "Generate a point cloud from the scene using the parameters below"

    def execute(self, context):
        scene = context.scene
        properties = scene.scannerProperties

        
        if properties.measureTime:
            startTime = time.time()

            
        performScan(context, dependencies_installed, properties)
        
        """
        scan_static(
            context, 

            scannerObject=bpy.context.scene.objects["Camera"],

            resolutionX=100, fovX=60, resolutionY=100, fovY=60, resolutionPercentage=100,

            reflectivityLower=0.0, distanceLower=0.0, reflectivityUpper=0.0, distanceUpper=99999.9, maxReflectionDepth=10,
            
            enableAnimation=False, frameStart=1, frameEnd=1, frameStep=1, frameRate=1,

            addNoise=False, noiseType='gaussian', mu=0.0, sigma=0.01, noiseAbsoluteOffset=0.0, noiseRelativeOffset=0.0,

            simulateRain=False, rainfallRate=0.0, 

            addMesh=True,

            exportLAS=False, exportHDF=False, exportCSV=False, exportSingleFrames=False,
            exportRenderedImage=False, exportSegmentedImage=False, exportPascalVoc=False, exportDepthmap=False, depthMinDistance=0.0, depthMaxDistance=100.0, 
            dataFilePath="//output", dataFileName="output file",
            
            debugLines=False, debugOutput=False, outputProgress=True, measureTime=False, singleRay=False, destinationObject=None, targetObject=None
        )       
        """

        """
        scan_rotating(
            context, 

            scannerObject=bpy.context.scene.objects["Camera"],

            xStepDegree=0.2, fovX=30.0, yStepDegree=0.33, fovY=40.0, rotationsPerSecond=20,

            reflectivityLower=0.0, distanceLower=0.0, reflectivityUpper=0.0, distanceUpper=99999.9, maxReflectionDepth=10,
            
            enableAnimation=False, frameStart=1, frameEnd=1, frameStep=1, frameRate=1,

            addNoise=False, noiseType='gaussian', mu=0.0, sigma=0.01, noiseAbsoluteOffset=0.0, noiseRelativeOffset=0.0,

            simulateRain=False, rainfallRate=0.0, 

            addMesh=True,

            exportLAS=False, exportHDF=False, exportCSV=False, exportSingleFrames=False,
            dataFilePath="//output", dataFileName="output file",
            
            debugLines=False, debugOutput=False, outputProgress=True, measureTime=False, singleRay=False, destinationObject=None, targetObject=None
        )  
        """

        """
        scan_sonar(
            context, 

            scannerObject=bpy.context.scene.objects["Camera"],

            maxDistance=100.0, fovSonar=135.0, sonarStepDegree=0.25, sonarMode3D=True,

            sourceLevel=220.0, noiseLevel=63.0, directivityIndex=20.0, processingGain=10.0, receptionThreshold=10.0,   

            simulateWaterProfile=True, depthList= [
                (15.0, 1.333, 1.0),
                (14.0, 1.0, 1.1),
                (12.5, 1.52, 1.3),
                (11.23, 1.4, 1.1),
                (7.5, 1.2, 1.4),
                (5.0, 1.333, 1.5),
            ],
        
            enableAnimation=True, frameStart=1, frameEnd=1, frameStep=1,

            addNoise=False, noiseType='gaussian', mu=0.0, sigma=0.01, noiseAbsoluteOffset=0.0, noiseRelativeOffset=0.0,

            simulateRain=False, rainfallRate=0.0, 

            addMesh=True,

            exportLAS=False, exportHDF=False, exportCSV=False, exportSingleFrames=False,
            dataFilePath="//output", dataFileName="output file",
            
            debugLines=False, debugOutput=False, outputProgress=True, measureTime=False, singleRay=False, destinationObject=None, targetObject=None
        )  
        """
        
        if properties.measureTime:
            print("Total execution time: %s s" % (time.time() - startTime))

        return {'FINISHED'}

# define UI panels
class OBJECT_PT_MAIN_PANEL(MAIN_PANEL, Panel):
    bl_label = "Point clouds"
    bl_idname = "OBJECT_PT_MAIN_PANEL"
 
    @classmethod
    def poll(self,context):
        return context.object is not None and dependencies_installed

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties
        
        layout.label(text="Scanner object")
        layout.prop(properties, "scannerObject")

        layout.separator()

        layout.prop(properties, "joinMeshes")

        layout.operator("wm.execute_scan")

class OBJECT_PT_PRESET_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Presets"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties

        layout.label(text="Scanner category")
        layout.prop(properties, "scannerCategory", text="") 

        layout.label(text="Scanner name")
        layout.prop(properties, "scannerName", text="") 
        layout.operator("wm.load_preset")


class OBJECT_PT_REFLECTIVITY_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Reflectivity"

    @classmethod
    def poll(self,context):
        return context.object is not None and context.scene.scannerProperties.scannerType != generic.ScannerType.sideScan.name

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties

        layout.label(text="Lower bound")
        layout.prop(properties, "reflectivityLower")
        layout.prop(properties, "distanceLower")

        layout.separator()

        layout.label(text="Upper bound")
        layout.prop(properties, "reflectivityUpper")
        layout.prop(properties, "distanceUpper")

        layout.separator()
        layout.prop(properties, "maxReflectionDepth")


class OBJECT_PT_SCANNER_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Scanner"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties

        layout.label(text="Scanner type")
        layout.prop(properties, "scannerType")

        layout.separator()

        if properties.scannerType == generic.ScannerType.sideScan.name:
            layout.prop(properties, "fovSonar")
            layout.prop(properties, "sonarStepDegree")
            row = layout.row()
            row.prop(properties, "sonarMode3D")
            column = row.column()
            column.prop(properties, "sonarKeepRotation")
            column.enabled = not properties.sonarMode3D
                
            layout.separator()

            layout.prop(properties, "sourceLevel")
            layout.prop(properties, "noiseLevel")
            layout.prop(properties, "directivityIndex")
            layout.prop(properties, "processingGain")
            layout.prop(properties, "receptionThreshold")
            layout.prop(properties, "maxDistance")

            layout.separator()
            layout.separator()
            layout.separator()

            layout.label(text="Water profile")
            layout.prop(properties, "simulateWaterProfile")

            profileColumn = layout.column()
            profileColumn.enabled = properties.simulateWaterProfile

            profileColumn.prop(properties, "surfaceHeight")

            # list adapted from https://blender.stackexchange.com/a/30446/95167
            rows = 3
            row = profileColumn.row()
            row.template_list("CUSTOM_UL_items", "", scene, "custom", scene, "custom_index", rows=rows, sort_lock=True)
            
            profileColumn.label(text="New item")
            row = profileColumn.row()
            col = row.column(align=True)
            row = col.row(align=True)
            
            row.prop(properties, "refractionDepth")
            row.prop(properties, "refractionSpeed")
            row.prop(properties, "refractionDensity")
            col.separator()
            col.operator("custom.add_items", icon='ADD')
            col.operator("custom.remove_item", icon='REMOVE')

            col.separator()
            col.separator()
            col.separator()

            row = col.row(align=True)
            row.operator("custom.clear_list", icon="X")
                
        elif properties.scannerType == generic.ScannerType.rotating.name:
                layout.label(text="Horizontal")
                horizontalLayout = layout.row()
                horizontalLayout.prop(properties, "fovX")
                horizontalLayout.prop(properties, "xStepDegree")

                layout.label(text="Vertical")
                horizontalLayout = layout.row()
                horizontalLayout.prop(properties, "fovY")
                horizontalLayout.prop(properties, "yStepDegree")
            
                layout.separator()
                
                layout.label(text="Rotation")
                layout.prop(properties, "rotationsPerSecond")

        elif properties.scannerType == generic.ScannerType.static.name:
            layout.label(text="Horizontal")
            horizontalLayout = layout.row()
            horizontalLayout.prop(properties, "fovX")
            horizontalLayout.prop(properties, "resolutionX")

            layout.label(text="Vertical")
            horizontalLayout = layout.row()
            horizontalLayout.prop(properties, "fovY")
            horizontalLayout.prop(properties, "resolutionY")

            layout.separator()

            layout.prop(properties, "resolutionPercentage")

class OBJECT_PT_ANIMATION_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Animation"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties

        layout.prop(properties, "enableAnimation")

        subLayout = layout.column()
        verticalLayout = subLayout.row()
        verticalLayout.prop(properties, "frameStart")
        verticalLayout.prop(properties, "frameEnd")
        subLayout.prop(properties, "frameStep")
        subLayout.prop(properties, "frameRate")
        subLayout.enabled = properties.enableAnimation       

class OBJECT_PT_OBJECT_MODIFICATION_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Object Modification"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties
        
        layout.label(text="Object to be modified")
        layout.prop(properties, "swapObject")

        layout.separator()
        layout.separator()

        layout.prop(properties, "enableSwapping")
        verticalLayout = layout.column()
        verticalLayout.enabled = properties.enableSwapping
        verticalLayout.prop(properties, "modelsFilePath")

        layout.separator()
        layout.separator()

        layout.prop(properties, "enableModification")
        verticalLayout = layout.column()
        verticalLayout.enabled = properties.enableModification

        verticalLayout.prop(properties, "numberOfModifications")

        verticalLayout.separator()

        verticalLayout.label(text="Random translation")
        horizontalLayout = verticalLayout.row()
        horizontalLayout.prop(properties, "minTransX")
        horizontalLayout.prop(properties, "maxTransX")

        horizontalLayout = verticalLayout.row()
        horizontalLayout.prop(properties, "minTransY")
        horizontalLayout.prop(properties, "maxTransY")

        horizontalLayout = verticalLayout.row()
        horizontalLayout.prop(properties, "minTransZ")
        horizontalLayout.prop(properties, "maxTransZ")

        verticalLayout.separator()

        verticalLayout.label(text="Random rotation")
        horizontalLayout = verticalLayout.row()
        horizontalLayout.prop(properties, "minRotX")
        horizontalLayout.prop(properties, "maxRotX")

        horizontalLayout = verticalLayout.row()
        horizontalLayout.prop(properties, "minRotY")
        horizontalLayout.prop(properties, "maxRotY")

        horizontalLayout = verticalLayout.row()
        horizontalLayout.prop(properties, "minRotZ")
        horizontalLayout.prop(properties, "maxRotZ")

        verticalLayout.separator()

        verticalLayout.label(text="Random scaling factor")
        verticalLayout.prop(properties, "uniformScaling")

        if properties.uniformScaling:
            horizontalLayout = verticalLayout.row()
            horizontalLayout.prop(properties, "minScaleAll")
            horizontalLayout.prop(properties, "maxScaleAll")
        else:
            horizontalLayout = verticalLayout.row()
            horizontalLayout.prop(properties, "minScaleX")
            horizontalLayout.prop(properties, "maxScaleX")

            horizontalLayout = verticalLayout.row()
            horizontalLayout.prop(properties, "minScaleY")
            horizontalLayout.prop(properties, "maxScaleY")

            horizontalLayout = verticalLayout.row()
            horizontalLayout.prop(properties, "minScaleZ")
            horizontalLayout.prop(properties, "maxScaleZ")


class OBJECT_PT_NOISE_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Noise"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties

        layout.prop(properties, "addConstantNoise")
        column = layout.column()
        column.prop(properties, "noiseAbsoluteOffset")
        column.prop(properties, "noiseRelativeOffset")
        column.enabled = properties.addConstantNoise
        
        layout.separator()

        layout.prop(properties, "addNoise")
        column = layout.column()
        column.prop(properties, "noiseType")
        verticalLayout = column.row()
        verticalLayout.prop(properties, "mu")
        verticalLayout.prop(properties, "sigma")
        column.enabled = properties.addNoise


class OBJECT_PT_WEATHER_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Weather simulation"

    @classmethod
    def poll(self,context):
        return context.object is not None and context.scene.scannerProperties.scannerType != generic.ScannerType.sideScan.name

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties

        layout.prop(properties, "weatherType")
       
        if properties.weatherType == "rain":
            layout.prop(properties, "simulateRain")
            layout.prop(properties, "rainfallRate")

        elif properties.weatherType == "dust":
            layout.prop(properties, "simulateDust")
            layout.prop(properties, "particleRadius")
            layout.prop(properties, "particlesPcm")
            layout.prop(properties, "dustCloudStart")
            layout.prop(properties, "dustCloudLength") 

class OBJECT_PT_VISUALIZATION_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Visualization"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties
        
        layout.prop(properties, "addMesh")

class OBJECT_PT_EXPORT_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "Export"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties

        layout.label(text="Raw data")
        layout.prop(properties, "exportLAS")
        layout.prop(properties, "exportHDF")
        layout.prop(properties, "exportCSV")
        layout.prop(properties, "exportSingleFrames")

        layout.separator()

        if properties.scannerType == generic.ScannerType.static.name:
            layout.label(text="Images")

            layout.prop(properties, "exportRenderedImage")


            verticalLayout = layout.row()
            verticalLayout.prop(properties, "exportSegmentedImage") 
            xmlLayout = verticalLayout.column()
            xmlLayout.prop(properties, "exportPascalVoc")
            xmlLayout.enabled = properties.exportSegmentedImage

            layout.prop(properties, "exportDepthmap")
            verticalLayout = layout.row()
            verticalLayout.prop(properties, "depthMinDistance")
            verticalLayout.prop(properties, "depthMaxDistance")

        layout.separator()

        layout.label(text="Disk location")
        layout.prop(properties, "dataFilePath")
        layout.prop(properties, "dataFileName")

        


class OBJECT_PT_DEBUG_PANEL(MAIN_PANEL, Panel):
    bl_parent_id = "OBJECT_PT_MAIN_PANEL"
    bl_label = "DEBUG"

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        properties = scene.scannerProperties
        
        layout.prop(properties, "debugLines")
        layout.prop(properties, "debugOutput")
        layout.prop(properties, "outputProgress")

        layout.prop(properties, "measureTime")

        layout.separator()

        layout.prop(properties, "singleRay")
        verticalLayout = layout.row()
        column1 = verticalLayout.column()
        column1.label(text="Destination")
        column1.prop(properties, "destinationObject")
        column2 = verticalLayout.column()
        column2.label(text="Target")
        column2.prop(properties, "targetObject")
            







############################################################# 
#                                                           #
#                   WATER PROFILE LIST                      #
#                                                           #
#############################################################

def sortList(customList):
    # sort list items
    # selection sort is just fine as it is simple and we don't have that many items
    # see: https://en.wikipedia.org/wiki/Selection_sort#Implementations
    for index in range(len(customList.items()) - 1):          
        minimumIndex = index

        for innerIndex in range(index, len(customList.items())):
            if customList.items()[innerIndex][1].depth < customList.items()[minimumIndex][1].depth:
                minimumIndex = innerIndex
        
        customList.move(minimumIndex, index)

# adapted from https://blender.stackexchange.com/a/30446/95167
def addItemToList(depth, speed, density, customList, customIndex):
    # add new item to the list
    item = customList.add()
    item.name = str(depth)
    item.depth = depth
    item.speed = speed
    item.density = density
    customIndex = len(customList)-1

def removeDuplicatesFromList(customList, customIndex):
    # remove potential duplicates
    removed_items = []
    for i in find_duplicates(customList)[::-1]:
        customList.remove(i)
        removed_items.append(i)

    if removed_items:
        customIndex = len(customList)-1

def find_duplicates(customList):
    """find all duplicates by name"""
    name_lookup = {}
    for c, i in enumerate(customList):
        name_lookup.setdefault(i.depth, []).append(c)
    duplicates = set()
    for name, indices in name_lookup.items():
        for i in indices[:-1]:
            duplicates.add(i)
    return sorted(list(duplicates))

class CUSTOM_OT_addItem(Operator):
    """Add item"""
    bl_idname = "custom.add_items"
    bl_label = "Add /Edit item"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}
    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        scene = context.scene

        addItemToList(scene.scannerProperties.refractionDepth, scene.scannerProperties.refractionSpeed, scene.scannerProperties.refractionDensity, scene.custom, scene.custom_index)

        removeDuplicatesFromList(scene.custom, scene.custom_index)

        sortList(scene.custom)

        return{'FINISHED'}

class CUSTOM_OT_removeItem(Operator):
    """Remove item"""
    bl_idname = "custom.remove_item"
    bl_label = "Remove item"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def execute(self, context):
        scn = context.scene

        # source: https://sinestesia.co/blog/tutorials/using-uilists-in-blender/
        index = scn.custom_index
        my_list = scn.custom

        my_list.remove(index)
        scn.custom_index = min(max(0, index - 1), len(my_list) - 1)

        return{'FINISHED'}

class CUSTOM_OT_clearList(Operator):
    """Clear all items of the list"""
    bl_idname = "custom.clear_list"
    bl_label = "Clear List"
    bl_description = "Clear all items of the list"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.custom)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if bool(context.scene.custom):
            context.scene.custom.clear()
            self.report({'INFO'}, "All items removed")
        else:
            self.report({'INFO'}, "Nothing to remove")
        return{'FINISHED'}



class CUSTOM_UL_items(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if index == len(context.scene.custom) - 1:
            layout.label(text="Depth: > %.2f m, Speed: %.3f m/s, Density: %.3f kg/m³" % (item.depth, item.speed, item.density))
        else:
            layout.label(text="Depth: %.2f m - %.2fm, Speed: %.3f m/s, Density: %.3f kg/m³" % (item.depth, context.scene.custom[index + 1].depth, item.speed, item.density))

    def invoke(self, context, event):
        pass   

class CUSTOM_objectCollection(PropertyGroup):
    depth: FloatProperty()
    speed: FloatProperty()
    density: FloatProperty()
    





# merge all classes to be displayed
classes = (
    WM_OT_INSTALL_DEPENDENCIES,
    WM_OT_LOAD_PRESET,

    EXAMPLE_PT_DEPENDENCIES_PANEL,

    ScannerProperties,
    WM_OT_GENERATE_POINT_CLOUDS,
    OBJECT_PT_MAIN_PANEL,
    OBJECT_PT_PRESET_PANEL,
    OBJECT_PT_SCANNER_PANEL,
    OBJECT_PT_REFLECTIVITY_PANEL,
    OBJECT_PT_ANIMATION_PANEL,
    OBJECT_PT_OBJECT_MODIFICATION_PANEL,
    OBJECT_PT_NOISE_PANEL,
    OBJECT_PT_WEATHER_PANEL,
    OBJECT_PT_VISUALIZATION_PANEL,
    OBJECT_PT_EXPORT_PANEL,
    OBJECT_PT_DEBUG_PANEL,

    CUSTOM_OT_addItem,
    CUSTOM_OT_removeItem,
    CUSTOM_OT_clearList,
    CUSTOM_UL_items,
    CUSTOM_objectCollection,
)

config = []

# register all needed classes on startup
def register():
    global config 

    global dependencies_installed
    dependencies_installed = False

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.scannerProperties = PointerProperty(type=ScannerProperties)
    bpy.types.Scene.custom = CollectionProperty(type=CUSTOM_objectCollection)

    missingDependency = None

    try:
        requirementsPath = os.path.join(pathlib.Path(__file__).parent.parent.absolute(), "requirements.txt")
        print("Reading dependencies from {0}".format(requirementsPath))
        requirementsFile = open(requirementsPath, 'r')
        requirements = requirementsFile.readlines()

        importName = None

        # Strips the newline character
        for requirement in requirements:
            stripped = requirement.strip()

            if stripped.startswith("#/"):
                importName = stripped.split("#/")[1]
                continue

            if stripped.startswith("#") or not stripped:
                continue

            name, version = stripped.split("==")

            if importName is None:
                importName = name

            print(f"Checking {name}: version {version}, import {importName}")

            missingDependency = name
            import_module(module_name=importName)

            importName = None

        dependencies_installed = True
        missingDependency = None

        print("All dependencies found.")
    except ModuleNotFoundError:
        print("ERROR: Missing dependency %s." % str(missingDependency))
        # Don't register other panels, operators etc.
        return

    # load scanner config file
    configPath = os.path.join(pathlib.Path(__file__).parent.absolute(), "presets.yaml")

    print("Loading config file from %s ..." % configPath)

    with open(configPath, 'r') as stream:
        try:
            # we can't load it before checking for our dependencies, as we need the yaml module here
            import yaml
            config = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    print("Done.")

# delete all classes on shutdown
def unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.Scene.scannerProperties
    del bpy.types.Scene.custom
