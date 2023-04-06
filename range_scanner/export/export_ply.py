import open3d as o3d
import numpy as np
import os


def export(filePath, fileName, data, exportNoiseData):
    print("Exporting data into .ply format...")

    hits_xyz = data[:, 2:5]
    pcd = o3d.geometry.PointCloud()
    # the method Vector3dVector() will convert numpy array of shape (n, 3) to Open3D format.
    # see http://www.open3d.org/docs/release/python_api/open3d.utility.Vector3dVector.html#open3d.utility.Vector3dVector
    pcd.points = o3d.utility.Vector3dVector(hits_xyz)
    o3d.io.write_point_cloud(os.path.join(filePath, "%s.ply" % fileName), pcd, write_ascii=False)
    
    if exportNoiseData:
        hits_xyz = data[:, 10:13]
        pcd = o3d.geometry.PointCloud()
        # the method Vector3dVector() will convert numpy array of shape (n, 3) to Open3D format.
        # see http://www.open3d.org/docs/release/python_api/open3d.utility.Vector3dVector.html#open3d.utility.Vector3dVector
        pcd.points = o3d.utility.Vector3dVector(hits_xyz)
        o3d.io.write_point_cloud(os.path.join(filePath, "%s_noise.ply" % fileName), pcd, write_ascii=False)

    print("Done.")
