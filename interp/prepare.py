'''
Created on Nov 25, 2018

@author: Faizan
'''

from math import ceil

import numpy as np
import pandas as pd
import netCDF4 as nc
import shapefile as shp

from .drift import KrigingDrift as KDT
from .bdpolys import SpInterpBoundaryPolygons as SIBD
from ..misc import get_aligned_shp_bds_and_cell_size
from ..misc import cnvt_to_pt, chk_cntmt, get_ras_props


class SpInterpPrepare(SIBD, KDT):

    def __init__(self):

        SIBD.__init__(self)
        KDT.__init__(self)

        self._plot_polys = None
        self._cntn_idxs = None

        self._prpd_flag = False
        return

    def _cmpt_aligned_coordinates(self):

        '''
        Given the alignment raster compute the cell size and bounds of the
        interpolation grid such that they align completely with the
        alignment raster.
        '''

        assert self._cell_sel_prms_set, (
            'Call set_cell_selection_parameters first!')

        assert self._algn_ras_set_flag, (
            'Call set_alignment_raster first!')

        ((fin_x_min,
          fin_x_max,
          fin_y_min,
          fin_y_max),
         cell_size) = get_aligned_shp_bds_and_cell_size(
             str(self._poly_shp), self._algn_ras)

        fin_x_min -= 2 * cell_size
        fin_x_max += 2 * cell_size
        fin_y_min -= 2 * cell_size
        fin_y_max += 2 * cell_size

        self._x_min = fin_x_min
        self._x_max = fin_x_max
        self._y_min = fin_y_min
        self._y_max = fin_y_max
        self._cell_size = cell_size

        if self._vb:
            print('\n', '#' * 10, sep='')
            print('Computed the following aligned coordinates:')
            print('Minimum X:', self._x_min)
            print('Maximum X:', self._x_max)
            print('Minimum Y:', self._y_min)
            print('Maximum X:', self._x_max)
            print('Cell size:', self._cell_size)
            print('#' * 10)

        return

    def _cmpt_corner_coordinates(self):

        '''
        If alignment raster is unspecified then take the minima and maxima
        of the station coordinates as the bounds for the interpolation
        grids.

        If external drift kriging is turned on then use the cell size of
        the first drift raster.

        Else the  cell size should have been specified manually in
        the set_misc_settings function.

        Error is raised if cell size is not set.
        '''

        self._x_min = self._crds_df['X'].min()
        self._x_max = self._crds_df['X'].max()

        self._y_min = self._crds_df['Y'].min()
        self._y_max = self._crds_df['Y'].max()

        if self._edk_flag:
            self._cell_size = get_ras_props(str(self._drft_rass[0]))[6]

        assert self._cell_size is not None, 'Cell size unspecified!'

        if self._vb:
            print('\n', '#' * 10, sep='')
            print('Computed the following corner coordinates:')
            print('Minimum X:', self._x_min)
            print('Maximum X:', self._x_max)
            print('Minimum Y:', self._y_min)
            print('Maximum X:', self._x_max)
            print('Cell size:', self._cell_size)
            print('#' * 10)
        return

    def _prepare_crds(self):

        if self._edk_flag:
            assert self._x_min > self._drft_x_min, (
                'Grid x_min outside of the drift rasters!')

            assert self._x_max < self._drft_x_max, (
                'Grid x_max outside of drift rtasters!')

            assert self._y_min > self._drft_y_min, (
                'Grid y_min outside of drift rasters!')

            assert self._y_max < self._drft_y_max, (
                'Grid y_max outside of drift rasters!')

            self._min_col = int(
                max(0, (self._x_min - self._drft_x_min) / self._cell_size))

            self._max_col = int(
                ceil((self._x_max - self._drft_x_min) / self._cell_size))

            self._min_row = int(
                max(0, (self._drft_y_max - self._y_max) / self._cell_size))

            self._max_row = int(
                ceil((self._drft_y_max - self._y_min) / self._cell_size))

        else:
            self._min_col = 0

            self._max_col = int(
                ceil((self._x_max - self._x_min) / self._cell_size))

            self._min_row = 0

            self._max_row = int(
                ceil((self._y_max - self._y_min) / self._cell_size))

        assert 0 <= self._min_col <= self._max_col, (
            self._min_col, self._max_col)

        assert 0 <= self._min_row <= self._max_row, (
            self._min_row, self._max_row)

        strt_x_coord = self._x_min + (0.5 * self._cell_size)

        end_x_coord = strt_x_coord + (
            (self._max_col - self._min_col) * self._cell_size)

        strt_y_coord = self._y_max - (0.5 * self._cell_size)

        end_y_coord = strt_y_coord - (
            (self._max_row - self._min_row) * self._cell_size)

        interp_x_coords = np.linspace(
            strt_x_coord, end_x_coord, (self._max_col - self._min_col + 1))

        interp_y_coords = np.linspace(
            strt_y_coord, end_y_coord, (self._max_row - self._min_row + 1))

        interp_x_coords_mesh, interp_y_coords_mesh = np.meshgrid(
            interp_x_coords, interp_y_coords)

        # must not move
        self._interp_crds_orig_shape = interp_x_coords_mesh.shape

        self._interp_x_crds_plt_msh, self._interp_y_crds_plot_msh = None, None

        if self._plot_figs_flag:
            # xy coords for pcolormesh
            pcolmesh_x_coords = np.linspace(
                self._x_min, self._x_max, (self._max_col - self._min_col + 1))

            pcolmesh_y_coords = np.linspace(
                self._y_max, self._y_min, (self._max_row - self._min_row + 1))

            self._interp_x_crds_plt_msh, self._interp_y_crds_plot_msh = (
                np.meshgrid(pcolmesh_x_coords, pcolmesh_y_coords))

        self._nc_x_crds = interp_x_coords
        self._nc_y_crds = interp_y_coords

        self._interp_x_crds_msh = interp_x_coords_mesh.ravel()
        self._interp_y_crds_msh = interp_y_coords_mesh.ravel()
        return

    def _select_nearby_cells(self):

        '''
        If interp_around_polys_flag is True then interpolate only those
        cells that are near or inside the polygons.

        This could be multithreaded.
        '''

        if self._vb:
            print('\n', '#' * 10, sep='')
            print(self._interp_x_crds_msh.shape[0],
                  'cells to interpolate per step before intersection!')

        fin_cntn_idxs = np.zeros(self._interp_x_crds_msh.shape[0], dtype=bool)
        ogr_pts = np.vectorize(cnvt_to_pt)(
            self._interp_x_crds_msh, self._interp_y_crds_msh)

        for poly in self._geom_buff_cells:
            curr_cntn_idxs = np.vectorize(chk_cntmt)(ogr_pts, poly)

            assert curr_cntn_idxs.sum(), 'Polygon intersects zero cells!'

            fin_cntn_idxs = fin_cntn_idxs | curr_cntn_idxs

        fin_idxs_sum = fin_cntn_idxs.sum()

        if self._vb:
            print(
                fin_idxs_sum,
                'cells to interpolate per step after intersection!')
            print('#' * 10)

        assert fin_idxs_sum, 'No cells selected for interpolation!'

        self._interp_x_crds_msh = self._interp_x_crds_msh[fin_cntn_idxs]
        self._interp_y_crds_msh = self._interp_y_crds_msh[fin_cntn_idxs]

        self._cntn_idxs = fin_cntn_idxs
        return

    def _initiate_nc(self):

        '''
        Create the output netCDF4 file. All interpolated grids, cell
        coordinates and time stamps will be saved in this file.
        '''

        self._nc_hdl = nc.Dataset(
            str(self._out_dir / (self._nc_out.split('.')[0] + '.nc')),
            mode='w')

        self._nc_hdl.set_auto_mask(False)
        self._nc_hdl.createDimension(self._nc_xlab, self._nc_x_crds.shape[0])
        self._nc_hdl.createDimension(self._nc_ylab, self._nc_y_crds.shape[0])
        self._nc_hdl.createDimension(self._nc_tlab, self._time_rng.shape[0])

        x_coords_nc = self._nc_hdl.createVariable(
            self._nc_xlab, 'd', dimensions=self._nc_xlab)

        x_coords_nc[:] = self._nc_x_crds

        y_coords_nc = self._nc_hdl.createVariable(
            self._nc_ylab, 'd', dimensions=self._nc_ylab)

        y_coords_nc[:] = self._nc_y_crds

        time_nc = self._nc_hdl.createVariable(
            self._nc_tlab, 'i8', dimensions=self._nc_tlab)

        if self._index_type == 'date':
            time_nc[:] = nc.date2num(
                self._time_rng.to_pydatetime(),
                units=self._nc_tunits,
                calendar=self._nc_tcldr)

            time_nc.units = self._nc_tunits
            time_nc.calendar = self._nc_tcldr

        elif self._index_type == 'obj':
            time_nc[:] = np.arange(self._time_rng.shape[0], dtype=int)

        else:
            raise NotImplementedError(
                f'Unknown index_type: {self._index_type}!')

        for interp_arg in self._interp_args:
            ivar_name = interp_arg[2]

            nc_var = self._nc_hdl.createVariable(
                ivar_name,
                'd',
                dimensions=(self._nc_tlab, self._nc_ylab, self._nc_xlab),
                fill_value=False)

            nc_var.units = self._nc_vunits

            if interp_arg[0] == 'IDW':
                nc_var.standard_name = self._nc_vlab + (
                    f' ({ivar_name[:3]}_exp_{interp_arg[2]})')

            else:
                nc_var.standard_name = self._nc_vlab + f' ({ivar_name})'

        return

    def _prepare(self):

        '''Main call for the preparation of required variables.'''

        assert any([
            self._ork_flag,
            self._spk_flag,
            self._edk_flag,
            self._idw_flag])

        if self._index_type == 'date':
            self._time_rng = pd.date_range(
                self._tbeg, self._tend, freq=self._tfreq)

        elif self._index_type == 'obj':
            self._time_rng = self._data_df.index

        else:
            raise NotImplementedError(
                f'Unknown index_type: {self._index_type}!')

        if self._cell_sel_prms_set:
            self._select_nearest_stations()

        if self._cell_sel_prms_set and self._plot_figs_flag:
            sf = shp.Reader(str(self._poly_shp))

            self._plot_polys = [
                i.__geo_interface__ for i in sf.iterShapes()]

        if self._cell_sel_prms_set and self._algn_ras_set_flag:
            self._cmpt_aligned_coordinates()

        else:
            self._cmpt_corner_coordinates()

        if self._edk_flag:
            self._assemble_drift_data()

        self._prepare_crds()

        if self._cell_sel_prms_set and self._ipoly_flag:
            self._select_nearby_cells()

        if self._edk_flag:
            self._prepare_stns_drift()

        self._out_dir.mkdir(exist_ok=True)

        if self._plot_figs_flag:
            self._plots_dir = self._out_dir / 'interp_plots'
            self._plots_dir.mkdir(exist_ok=True)

            fig_dirs = {}

            if self._ork_flag:
                fig_dirs['OK'] = 'ord_krig_figs'

            if self._spk_flag:
                fig_dirs['SK'] = 'smp_krig_figs'

            if self._edk_flag:
                fig_dirs['EDK'] = 'ext_krig_figs'

            if self._idw_flag:
                for i, idw_exp in enumerate(self._idw_exps):
                    exp_str = ('%0.3f' % idw_exp).replace('.', '').rstrip('0')
                    fig_dirs[f'IDW_{i:03d}'] = 'idw_exp_%s_figs' % exp_str

            interp_plot_dirs = {}

            for fig_dir_lab in fig_dirs:
                fig_dir = self._plots_dir / fig_dirs[fig_dir_lab]

                fig_dir.mkdir(exist_ok=True)

                interp_plot_dirs[fig_dir_lab] = fig_dir

        self._interp_args = []

        if self._ork_flag:
            if self._plot_figs_flag:
                fig_dir = interp_plot_dirs['OK']

            else:
                fig_dir = None

            self._interp_args.append(('OK', fig_dir, 'OK'))

        if self._spk_flag:
            if self._plot_figs_flag:
                fig_dir = interp_plot_dirs['SK']

            else:
                fig_dir = None

            self._interp_args.append(('SK', fig_dir, 'SK'))

        if self._edk_flag:
            if self._plot_figs_flag:
                fig_dir = interp_plot_dirs['EDK']

            else:
                fig_dir = None

            self._interp_args.append(('EDK', fig_dir, 'EDK'))

        if self._idw_flag:
            for i, idw_exp in enumerate(self._idw_exps):
                idw_lab = f'IDW_{i:03d}'

                if self._plot_figs_flag:
                    fig_dir = interp_plot_dirs[idw_lab]

                else:
                    fig_dir = None

                self._interp_args.append(('IDW', fig_dir, idw_lab, idw_exp))

        self._initiate_nc()

        all_stns = self._data_df.columns.intersection(self._crds_df.index)
        assert all_stns.shape[0], (
            'No common stations in data and station coordinates\' '
            'dataframes!')

        if self._edk_flag:
            all_stns = all_stns.intersection(self._stns_drft_df.index)

            assert all_stns.shape[0], (
                'No common stations in data, station coordinates\' '
                'and station drifts\' dataframes!')

            self._stns_drft_df = self._stns_drft_df.loc[all_stns]

        self._data_df = self._data_df.loc[:, all_stns]
        self._crds_df = self._crds_df.loc[all_stns]

        self._data_df = self._data_df.reindex(self._time_rng)

        if not self._vg_ser_set_flag:
            self._vgs_ser = self._vgs_ser.reindex(self._time_rng)

        self._prpd_flag = True
        return

