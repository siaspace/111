"""Defines classes for solving potential flow scenarios."""

import time

import numpy as np

from .pp_math import vec_inner, vec_norm, norm

class Solver:
    """Base class for solvers."""

    def __init__(self, **kwargs):
        pass


    def export_case_data(self, filename):
        """Writes the case data to the given file.

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
                      ("C_P", "float"),
                      ("dFx", "float"),
                      ("dFy", "float"),
                      ("dFz", "float"),
                      ("circ", "float")]

        table_data = np.zeros(self._N_panels, dtype=item_types)

        # Geometry
        table_data[:]["cpx"] = self._cp[:,0]
        table_data[:]["cpy"] = self._cp[:,1]
        table_data[:]["cpz"] = self._cp[:,2]
        table_data[:]["nx"] = self._n[:,0]
        table_data[:]["ny"] = self._n[:,1]
        table_data[:]["nz"] = self._n[:,2]
        table_data[:]["area"] = self._dA

        # Velocities
        table_data[:]["u"] = self._v[:,0]
        table_data[:]["v"] = self._v[:,1]
        table_data[:]["w"] = self._v[:,2]
        table_data[:]["V"] = self._V
        table_data[:]["C_P"] = self._C_P

        # Circulation and forces
        table_data[:]["dFx"] = self._dF[:,0]
        table_data[:]["dFy"] = self._dF[:,1]
        table_data[:]["dFz"] = self._dF[:,2]
        table_data[:]["circ"] = self._gamma[:self._N_panels]

        # Define header and output
        header = "{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}{:<21}".format(
                 "Control (x)", "Control (y)", "Control (z)", "nx", "ny", "nz", "Area", "u", "v", "w", "V", "C_P", "dFx", "dFy",
                 "dFz", "circ")
        format_string = "%20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e %20.12e"

        # Save
        np.savetxt(filename, table_data, fmt=format_string, header=header)


    def export_vtk(self, filename):
        """Exports the mesh(es) and solver results to a VTK file.

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
            print("POINTS {0} float".format(len(vertices)), file=export_handle)
            for vertex in vertices:
                print("{0:<20.12}{1:<20.12}{2:<20.12}".format(*vertex), file=export_handle)

            # Determine polygon list size
            size = 0
            for pi in panel_indices:
                size += len(pi)

            # Write panel polygons
            print("POLYGONS {0} {1}".format(self._N_panels, size), file=export_handle)
            for panel in panel_indices:
                print(" ".join(panel), file=export_handle)

            # Write flow results
            print("CELL_DATA {0}".format(self._N_panels), file=export_handle)

            # Pressure coefficient
            print("SCALARS pressure_coefficient float 1", file=export_handle)
            print("LOOKUP_TABLE default", file=export_handle)
            for C_P in self._C_P:
                print("{0:<20.12}".format(C_P), file=export_handle)


class VortexRingSolver(Solver):
    """Vortex ring solver.

    Parameters
    ----------
    mesh : Mesh
        A mesh object.

    verbose : bool, optional
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Store mesh
        self._mesh = kwargs["mesh"]
        verbose = kwargs.get("verbose", False)

        # Gather control point locations and normals
        if verbose: print("\nParsing mesh into solver...", end='', flush=True)
        self._N_panels = self._mesh.N
        self._N_edges = self._mesh.N_edges
        self._cp = np.copy(self._mesh.cp)
        self._n = np.copy(self._mesh.n)
        self._dA = np.copy(self._mesh.dA)

        # Gather edges
        self._N_edges = self._mesh.N_edges
        if self._N_edges != 0:
            self._edge_panel_ind = np.zeros((self._N_edges, 2))
            for i, edge in enumerate(self._mesh.kutta_edges):
                self._edge_panel_ind[i,:] = edge.panel_indices
        if verbose: print("Finished", flush=True)

        # Create panel influence matrix; first index is the influencing panel, second is the influenced panel
        if verbose: print("\nDetermining panel influence matrix...", end='', flush=True)
        self._panel_influence_matrix = np.zeros((self._N_panels, self._N_panels, 3))
        for i, panel in enumerate(self._mesh.panels):
            self._panel_influence_matrix[i,:] = panel.get_ring_influence(self._cp)

        # Determine panel part of A matrix
        self._A_panels = vec_inner(self._panel_influence_matrix, self._n[np.newaxis,:])
        if verbose: print("Finished", flush=True)


    def set_condition(self, **kwargs):
        """Sets the atmospheric conditions for the computation.

        V_inf : list
            Freestream velocity vector.

        rho : float
            Freestream density.
        """

        # Get freestream
        self._v_inf = np.array(kwargs["V_inf"])
        self._V_inf = norm(self._v_inf)
        self._u_inf = self._v_inf/self._V_inf
        self._V_inf_2 = self._V_inf*self._V_inf
        self._rho = kwargs["rho"]

        # Create part of b vector dependent upon V_inf
        self._b = -vec_inner(self._v_inf, self._n)


    def solve(self, **kwargs):
        """Solves the panel equations to determine the flow field around the mesh.

        Parameters
        ----------
        lifting : bool, optional
            Whether the Kutta condition is to be enforced. Defaults to False.

        verbose : bool, optional
        """
        start_time = time.time()

        # Get kwargs
        lifting = kwargs.get("lifting", False)
        verbose = kwargs.get("verbose", False)

        # Lifting
        if lifting:

            # Create horseshoe vortex influence matrix; first index is the influencing panels (bordering the horseshoe vortex), second is the influenced panel
            if verbose: print("\nDetermining horseshoe vortex influences...", end='', flush=True)
            self._vortex_influence_matrix = np.zeros((self._N_panels, self._N_panels, 3))
            for edge in self._mesh.kutta_edges:
                p_ind = edge.panel_indices
                V = -edge.get_vortex_influence(self._cp, self._u_inf[np.newaxis,:])
                self._vortex_influence_matrix[p_ind[0],:] = V
                self._vortex_influence_matrix[p_ind[1],:] = V

            # Determine panel part of A matrix
            self._A_vortices = vec_inner(self._panel_influence_matrix, self._n[np.newaxis,:])
            if verbose: print("Finished", flush=True)

            if verbose: print("\nSolving lifting case...", end='', flush=True)

            # Specify A matrix
            A = self._A_panels+self._A_vortices

            # Specify b vector
            b = np.copy(self._b)

        # Nonlifting
        else:
            if verbose: print("\nSolving nonlifting case...", end='', flush=True)
            
            # Specify A matrix
            A = np.zeros((self._N_panels+1, self._N_panels))
            A[:-1] = self._A_panels
            A[-1,:] = 1.0

            # Specify b vector
            b = np.zeros(self._N_panels+1)
            b[:-1] = self._b

        # Solve system using least-squares approach
        self._gamma, res, rank, s_a = np.linalg.lstsq(A, b, rcond=None)
        end_time = time.time()
        if verbose:
            print("Finished. Time: {0} s.".format(end_time-start_time), flush=True)
            if rank >= self._N_panels:
                print("    Maximum residual: {0}".format(np.max(res)))
            print("    Circulation sum: {0}".format(np.sum(self._gamma)))
            print("    Rank of A matrix: {0}".format(rank))
            print("    Max singular value of A: {0}".format(np.max(s_a)))
            print("    Min singular value of A: {0}".format(np.min(s_a)))

        # Determine velocities at each control point
        if verbose: print("\nDetermining velocities, pressure coefficients, and forces...", end='', flush=True)
        start_time = time.time()
        self._v = np.sum(self._panel_influence_matrix*self._gamma[:,np.newaxis,np.newaxis], axis=0)
        if lifting:
            self._v += np.sum(self._vortex_influence_matrix*self._gamma[:,np.newaxis,np.newaxis], axis=0)
        self._V = vec_norm(self._v)

        # Determine coefficients of pressure
        self._C_P = 1.0-(self._V*self._V)/self._V_inf_2
        end_time = time.time()

        # Determine forces
        self._dF = self._rho*self._V_inf_2*(self._dA*self._C_P)[:,np.newaxis]*self._n
        self._F = np.sum(self._dF, axis=0).flatten()
        if verbose: print("Finished. Time: {0} s.".format(end_time-start_time), flush=True)
        return self._F