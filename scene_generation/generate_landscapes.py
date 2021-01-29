#!/usr/bin/env python3

import subprocess
from os.path import dirname, abspath, join

directory = dirname(abspath(__file__))

# the blueprint file contains some custom gras models which are randomly
# chosen and placed in the scene
blueprintPath = join(directory, "blueprint.blend")
scriptPath = join(directory, "landscape.py")

# we want to constantly print the output from our script
# source: https://stackoverflow.com/a/4417735/13440564
def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line 
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)


for i in range(3):
    print("Generating scene %d..." % (i+1))
    
    #print(subprocess.check_output(['blender', blueprintPath, '--background', '--python', scriptPath]).decode())

    for path in execute(['blender', blueprintPath, '--background', '--python', scriptPath]):
        print(path, end="")
