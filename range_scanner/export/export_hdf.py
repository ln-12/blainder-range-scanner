import h5py
import numpy as np
import os
from pathlib import Path

# this datatype allows us to write arrays with arbitrary lengths in each row
# see: https://stackoverflow.com/a/42659049
dt = h5py.special_dtype(vlen=np.dtype('float64'))

def createDataset(handle, attribute, data):
    # create the dataset with 1 row, the special data type and an unlimited maximum size (so we can expand it later)
    # see: http://docs.h5py.org/en/stable/high/dataset.html#resizable-datasets
    dset = handle.create_dataset(attribute, (1,), dtype=dt, maxshape=(None,))

    # set data
    handle[attribute][...] = data

    # write column name
    dset.attrs['column_names'] = [attribute]

def appendData(handle, attribute, data):
    # see: https://stackoverflow.com/a/47074545/13440564

    # add a new line
    handle[attribute].resize((handle[attribute].shape[0] + 1), axis = 0)
    
    # write data at the end
    handle[attribute][-1] = data

def export(filePath, fileName, data, exportNoiseData):
    print("Exporting data into .hdf format...") 

    # in contrast to the other export methods, we only have ONE
    # file to export all data
    filePath = os.path.join(filePath, "%s.hdf5" % fileName)

    hdfFile = Path(filePath)
    if not hdfFile.is_file():
        # the file does not exist yet, so we need to create it
        with h5py.File(filePath, "w") as f: 
            # category ID
            createDataset(f, "categoryID", [data[0]])
            
            # part ID
            createDataset(f, "partID", [data[1]])

            # real location
            createDataset(f, "location_x", [data[2]])
            createDataset(f, "location_y", [data[3]])
            createDataset(f, "location_z", [data[4]])
            createDataset(f, "distance", [data[5]])

            # noise location
            if exportNoiseData:
                createDataset(f, "location_noise_x", [data[10]])
                createDataset(f, "location_noise_y", [data[11]])
                createDataset(f, "location_noise_z", [data[12]])
                createDataset(f, "distance_noise", [data[13]])
            
            # color
            createDataset(f, "color_r", [data[7]])
            createDataset(f, "color_g", [data[8]])
            createDataset(f, "color_b", [data[9]])

            # intensity
            createDataset(f, "intensity", [data[6]])              
    else:
        # the file already exists, so we want to append it
        with h5py.File(filePath, "a") as f: 
            # category ID
            appendData(f, "categoryID", [data[0]])
            
            # part ID
            appendData(f, "partID", [data[1]])

            # real location
            appendData(f, "location_x", [data[2]])
            appendData(f, "location_y", [data[3]])
            appendData(f, "location_z", [data[4]])
            appendData(f, "distance", [data[5]])

            # noise location
            if exportNoiseData:
                appendData(f, "location_noise_x", [data[10]])
                appendData(f, "location_noise_y", [data[11]])
                appendData(f, "location_noise_z", [data[12]])
                appendData(f, "distance_noise", [data[13]])
            
            # color
            appendData(f, "color_r", [data[7]])
            appendData(f, "color_g", [data[8]])
            appendData(f, "color_b", [data[9]])

            # intensity
            appendData(f, "intensity", [data[6]])  
        
    print("Done.")