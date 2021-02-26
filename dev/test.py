import time
import os

import pypan as pp
import numpy as np
import matplotlib.pyplot as plt


if __name__=="__main__":

    # Load mesh
    #mesh_file = "dev/meshes/swept_wing_vtk.vtk"
    #mesh_file = "dev/meshes/1250_polygon_sphere.stl"
    mesh_file = "dev/meshes/5000_polygon_sphere.vtk"
    #mesh_file = "dev/meshes/20000_polygon_sphere.stl"
    #mesh_file = "dev/meshes/1250_sphere.vtk"
    #mesh_file = "dev/meshes/F16_Original_withFins.stl"
    #mesh_file = "dev/meshes/cool_body_7000.stl"

    # Start timer
    start_time = time.time()

    # Load mesh
    if 'stl' in mesh_file or 'STL' in mesh_file:
        my_mesh = pp.Mesh(mesh_file=mesh_file, mesh_file_type="STL", kutta_angle=90.0, verbose=True)
    else:
        my_mesh = pp.Mesh(mesh_file=mesh_file, mesh_file_type="VTK", verbose=True, kutta_angle=90.0)

    # Export vtk if we need to
    if not os.path.isfile(mesh_file.replace(".stl", ".vtk")):
        my_mesh.export_vtk(mesh_file.replace(".stl", ".vtk"))

    # Plot mesh
    #my_mesh.plot(centroids=False)

    # Initialize solver
    my_solver = pp.VortexRingSolver(mesh=my_mesh, verbose=True)

    # Set condition
    my_solver.set_condition(V_inf=[0.0, 0.0, -10.0], rho=0.0023769)

    # Solve using direct method
    F, M = my_solver.solve(verbose=True, lifting=False)
    print("F: ", F)
    print("M: ", M)
    print("Max C_P: ", np.max(my_solver._C_P))
    print("Min C_P: ", np.min(my_solver._C_P))

    # Export results as VTK
    my_solver.export_vtk("5000_sphere_direct.vtk")

    # Solve using svd
    F, M = my_solver.solve(verbose=True, lifting=False, method='svd')
    print("F: ", F)
    print("M: ", M)
    print("Max C_P: ", np.max(my_solver._C_P))
    print("Min C_P: ", np.min(my_solver._C_P))

    # Export results as VTK
    my_solver.export_vtk("5000_sphere_svd.vtk")
    end_time = time.time()
    print("\nTotal run time: {0} s".format(end_time-start_time))