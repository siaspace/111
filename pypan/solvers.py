import time
import os

import numpy as np
import matplotlib.pyplot as plt

from abc import abstractmethod
from pypan.pp_math import vec_inner, vec_norm, norm

class Solver:
    """Base class for solvers. This class should never be instantiated directly but only through one of its derived classes."""

    def __init__(self, **kwargs):

        # Store mesh
        self._mesh = kwargs["mesh"]
        self._verbose = kwargs.get("verbose", False)

        # Gather control point locations and normals
        self._N_panels = self._mesh.N

        # Determine projection matrix onto plane of each panel
        self._P_surf = np.repeat(np.identity(3)[np.newaxis,:,:], self._N_panels, axis=0)-np.matmul(self._mesh.n[:,:,np.newaxis], self._mesh.n[:,np.newaxis,:])

        # Set solved flag
        self._solved = False


    def export_vtk(self, filename):
        """Exports the solver results on the mesh to a VTK file. If a wake exists, the only meaningful scalar result which will be specified on the wake filaments is the filament strength. All other results are arbitrarily set to zero on the wake.

        Parameters
        ----------
        filename : str
            Name of the file to write the results to. Must have '.vtk' extension.
        """

        # Check extension
        if '.vtk' not in filename:
            raise IOError("Filename for VTK export must contain .vtk extension.")

        # Open file
        with open(filename, 'w') as export_handle:
            
            # Write header
            print("# vtk DataFile Version 3.0", file=export_handle)
            print("PyPan results file. Generated by PyPan, USU AeroLab (c) 2020.", file=export_handle)
            print("ASCII", file=export_handle)

            # Write dataset
            print("DATASET POLYDATA", file=export_handle)

            # Write vertices
            vertices, panel_indices = self._mesh.get_vtk_data()
            wake_vertices, wake_filament_indices, N_segments = self._mesh.wake.get_vtk_data()
            print("POINTS {0} float".format(len(vertices)+len(wake_vertices)), file=export_handle)
            for vertex in vertices:
                print("{0:<20.12}{1:<20.12}{2:<20.12}".format(*vertex), file=export_handle)
            for vertex in wake_vertices:
                print("{0:<20.12}{1:<20.12}{2:<20.12}".format(*vertex), file=export_handle)

            # Determine wake filament list size
            size = 0
            for li in wake_filament_indices:
                size += len(li)

            # Write wake filaments
            print("LINES {0} {1}".format(N_segments, size), file=export_handle)
            for filament in wake_filament_indices:
                print(" ".join([str(index) if i==0 else str(index+len(vertices)) for i, index in enumerate(filament)]), file=export_handle)

            # Determine polygon list size
            size = 0
            for pi in panel_indices:
                size += len(pi)

            # Write panel polygons
            print("POLYGONS {0} {1}".format(self._N_panels, size), file=export_handle)
            for panel in panel_indices:
                print(" ".join([str(i) for i in panel]), file=export_handle)

            # Write flow results
            print("CELL_DATA {0}".format(self._N_panels+N_segments), file=export_handle)

            # Normals
            print("NORMALS panel_normals float", file=export_handle)
            for i in range(N_segments):
                print("0.00 0.00 0.00", file=export_handle)
            for n in self._mesh.n:
                print("{0:<20.12} {1:<20.12} {2:<20.12}".format(n[0], n[1], n[2]), file=export_handle)

            # Pressure coefficient
            print("SCALARS pressure_coefficient float 1", file=export_handle)
            print("LOOKUP_TABLE default", file=export_handle)
            for i in range(N_segments):
                print("0.0", file=export_handle)
            for C_P in self._C_P:
                print("{0:<20.12}".format(C_P), file=export_handle)

            # Singularity strength
            if hasattr(self, "_mu"):
                print("SCALARS doublet_strength float 1", file=export_handle)
                print("LOOKUP_TABLE default", file=export_handle)
                for i in range(self._mesh.wake.N):

                    # Determine strength of filament
                    mu = 0

                    # Add for outbound panels
                    outbound_panels = self._mesh.wake.outbound_panels[i]
                    if len(outbound_panels)>0:
                        mu -= self._mu[outbound_panels[0]]
                        mu += self._mu[outbound_panels[1]]

                    # Add for inbound panels
                    inbound_panels = self._mesh.wake.inbound_panels[i]
                    if len(inbound_panels)>0:
                        mu += self._mu[inbound_panels[0]]
                        mu -= self._mu[inbound_panels[1]]

                    # Print out
                    for i in range(self._mesh.wake.N_segments):
                        print("{0:<20.12}".format(mu), file=export_handle)

                for mu in self._mu:
                    print("{0:<20.12}".format(mu), file=export_handle)

            # Velocity
            if hasattr(self, "_v"):
                print("VECTORS velocity float", file=export_handle)
                for i in range(N_segments):
                    print("0.0 0.0 0.0", file=export_handle)
                for v in self._v:
                    print("{0:<20.12} {1:<20.12} {2:<20.12}".format(v[0], v[1], v[2]), file=export_handle)

                # Normal velocity
                print("SCALARS normal_velocity float", file=export_handle)
                print("LOOKUP_TABLE default", file=export_handle)
                for i in range(N_segments):
                    print("0.0", file=export_handle)
                for v_n in vec_inner(self._v, self._mesh.n):
                    print("{0:<20.12}".format(v_n), file=export_handle)

        if self._verbose:
            print()
            print("Case results successfully written to '{0}'.".format(filename))


    def export_case_data(self, filename):
        """Writes the results of the solver to the given file. Data will be formatted in columns with each row containing the data for a single panel.

        Parameters
        ----------
        filename : str
            File location at which to store the case data.
        """

        # Setup data table
        item_types = [("cpx", "float"),
                      ("cpy", "float"),
                      ("cpz", "float"),
                      ("nx", "float"),
                      ("ny", "float"),
                      ("nz", "float"),
                      ("area", "float"),
                      ("u", "float"),
                      ("v", "float"),
                      ("w", "float"),
                      ("V", "float"),
                      ("C_P", "float")]

        table_data = np.zeros(self._N_panels, dtype=item_types)

        # Geometry
        table_data[:]["cpx"] = self._mesh.cp[:,0]
        table_data[:]["cpy"] = self._mesh.cp[:,1]
        table_data[:]["cpz"] = self._mesh.cp[:,2]
        table_data[:]["nx"] = self._mesh.n[:,0]
        table_data[:]["ny"] = self._mesh.n[:,1]
        table_data[:]["nz"] = self._mesh.n[:,2]
        table_data[:]["area"] = self._mesh.dA

        # Velocities
        table_data[:]["u"] = self._v[:,0]
        table_data[:]["v"] = self._v[:,1]
        table_data[:]["w"] = self._v[:,2]
        table_data[:]["V"] = self._V

        # Pressure coefficient
        table_data[:]["C_P"] = self._C_P

        # Define header and output
        header = "{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}".format(
                 "x", "y", "z", "nx", "ny", "nz", "A", "u", "v", "w", "V", "C_P")
        format_string = "%20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e"

        # Save
        np.savetxt(filename, table_data, fmt=format_string, header=header)

    
    @abstractmethod
    def set_condition(self, **kwargs):
        """Sets the aerodynamic condition. Specific behavior is defined in the derived classes."""
        pass


    @abstractmethod
    def solve(self, **kwargs):
        """Solves the aerodynamics. Specific behavior is defined in the derived classes."""
        pass