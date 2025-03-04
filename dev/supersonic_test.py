import time
import os

import pypan as pp
import numpy as np
import matplotlib.pyplot as plt


if __name__=="__main__":

    # Load mesh
    #mesh_file = "dev/meshes/swept_wing_low_grid.vtk"
    #mesh_file = "dev/meshes/swept_wing_and_tail.vtk"
    #mesh_file = "dev/meshes/demo.tri"
    #mesh_file = "dev/meshes/swept_wing_high_grid.vtk"
    mesh_file = "dev/meshes/F-22.tri"
    #mesh_file = "dev/meshes/supersonic_wing_body.vtk"
    #mesh_file = "dev/meshes/1250_polygon_sphere.stl"
    #mesh_file = "dev/meshes/5000_polygon_sphere.vtk"
    #mesh_file = "dev/meshes/20000_polygon_sphere.stl"
    #mesh_file = "dev/meshes/1250_sphere.vtk"
    #mesh_file = "dev/meshes/F16_Original_withFins.vtk"

    # Start timer
    start_time = time.time()
    name = mesh_file.replace("dev/meshes/", "").replace(".stl", "").replace(".vtk", "").replace(".tri", "")
    pam_file = "dev/meshes/"+name+".pam"

    # Load mesh
    my_mesh = pp.Mesh(name=name, mesh_file=mesh_file, adjacency_file=pam_file, verbose=True)

    # Export vtk if we need to
    vtk_file = "dev/meshes/"+name+".vtk"
    if not os.path.isfile(vtk_file):
        my_mesh.export_vtk(vtk_file)

    # Export adjacency mapping if we need to
    if not os.path.isfile(pam_file):
        my_mesh.export_panel_adjacency_mapping(pam_file)

    # Set wake
    my_mesh.set_wake(type='full_streamline')

    # Initialize solver
    my_solver = pp.SupersonicSolver(mesh=my_mesh, verbose=True)

    # Set condition
    my_solver.set_condition(M=1.6)

    # Plot
    #my_mesh.plot(kutta_edges=False)

    print()
    print("Total execution time: {0} s".format(time.time()-start_time))