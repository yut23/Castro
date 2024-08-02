#!/usr/bin/env python3
# pylint: disable=wrong-import-position, wrong-import-order

import matplotlib
matplotlib.use('agg')

import os
import sys
import yt
import matplotlib.pyplot as plt

from mpl_toolkits.axes_grid1 import ImageGrid

# assume that our data is in CGS
from yt.units import cm
from yt.frontends.boxlib.api import CastroDataset

from util import get_fuel_info

# yt.enable_parallelism()

plt.rcParams.update({"font.family": "stixgeneral", "mathtext.fontset": "cm"})

files = sys.argv[1:]
force = False
if files[0] in ('-f', '--force'):
    files = files[1:]
    force = True

imagefile_suffixes = ("_species.png", "_species_linear.png")

# filter out any images that already exist
actual_files = []
for plotfile in sorted(set(files)):
    if not force and all(
        os.path.exists(os.path.basename(plotfile) + suffix)
        for suffix in imagefile_suffixes
    ):
        print(f"skipping {os.path.basename(plotfile)} since all images already exist")
        continue
    if plotfile not in actual_files:
        actual_files.append(plotfile)

# for plotfile in yt.parallel_objects(actual_files, njobs=njobs):
for plotfile in actual_files:
    basename = os.path.basename(plotfile)
    print("\nprocessing " + os.path.basename(plotfile) + "...")

    ds = CastroDataset(plotfile)

    xmin = ds.domain_left_edge[0]
    xmax = ds.domain_right_edge[0]
    xctr = 0.5*(xmin + xmax)
    L_x = xmax - xmin

    ymin = 0.0*cm
    ymax = 2.0e4*cm

    yctr = 0.5*(ymin + ymax)
    L_y = 1.0*(ymax - ymin)

    buff_size = (2400, 2400)

    fig = plt.figure()
    fig.set_size_inches(12.0, 9.0)


    # rprox
    rprox_elements = ["H1", "He4", "C12", "O16", "F17", "Mg22"]
    # alpha-chain networks
    elements = ["H1", "He4", "C12", "O16", "Ne20", "Mg24"]
    if ("boxlib", f"X(He4)") not in ds.field_list:
        elements = [e.lower() for e in elements]
        rprox_elements = [e.lower() for e in rprox_elements]
    if not all(("boxlib", f"X({e})") in ds.field_list for e in elements):
        elements = rprox_elements
    fields = [f"X({e})" for e in elements]

    initial_mass_fractions = {}
    for element, aion, fuel_frac in get_fuel_info(ds).values():
        # pynucastro networks use lowercase, other networks use title case
        for field_name in [
            f"X({element.symbol}{aion})",
            f"X({element.symbol.lower()}{aion})",
        ]:
            initial_mass_fractions[field_name] = fuel_frac

    grid = ImageGrid(fig, 111, nrows_ncols=(len(fields), 1),
                     axes_pad=0.27, label_mode="L", cbar_mode="each")


    slice_plots = {}
    for i, f in enumerate(fields):
        # pylint: disable=no-member

        kwargs = {}
        # if f == "enuc":
        #     # mask out any negative values, since they can screw up the log-scale
        #     # colormap bounds and make the background white instead of red
        #     kwargs["data_source"] = ds.all_data().include_above("enuc", 0)
        if yt.version_info >= (4, 0, 0):
            kwargs["buff_size"] = buff_size
        sp = yt.SlicePlot(ds, "theta", f, center=[xctr, yctr, 0.0*cm], width=[L_x, L_y, 0.0*cm], fontsize=16, aspect=1, **kwargs)
        if "buff_size" not in kwargs:
            sp.set_buff_size(buff_size)
        slice_plots[f] = sp

        # if f == "Temp":
        #     sp.set_zlim(f, 5.e7, 1.5e9)
        #     sp.set_cmap(f, "magma_r")
        # elif f == "enuc":
        #     sp.set_zlim(f, 1.e14, 3.e17)
        # elif f == "density":
        #     sp.set_zlim(f, 1.e-3, 5.e8)
        # elif f == "z_velocity":
        #     sp.set_zlim(f, -2.e8, 2.e8)
        #     sp.set_log(f, False)
        #     sp.set_cmap(f, "bwr")
        # elif f == "abar":
        #     sp.set_zlim(f, abar_min, 5)
        #     sp.set_log(f, False)
        #     sp.set_cmap(f, "plasma_r")
        # elif f == "ash":
        #     sp.set_zlim(f, 1.e-5, 0.1)
        #     sp.set_log(f, True)
        #     sp.set_cmap(f, "plasma_r")
        sp.set_zlim(f, 1e-10, 1)
        # sp.set_zlim(f, 0, 1)
        sp.set_log(f, True)
        sp.set_cmap(f, "plasma")

        #if f != "density":
        #    # now do a contour of density
        #    sp.annotate_contour("density", ncont=2, clim=(1.e2, 2.e6),
        #                        plot_args={"colors": "0.5", "linewidths": 1, "linestyle": ":"})

        sp.set_axes_unit("cm")

        #sp.annotate_text((0.05, 0.05), "{:8.5f} s".format(float(ds.current_time.in_cgs())),
        #                 coord_system="figure", text_args={"color": "black"})

        plot = sp.plots[f]
        plot.figure = fig
        plot.axes = grid[i].axes
        plot.cax = grid.cbar_axes[i]
        if i < len(fields)-1:
            grid[i].axes.xaxis.offsetText.set_visible(False)

        if f == "enuc":
            sp.set_log(f, True)

        sp._setup_plots()

    fig.text(0.52, 0.96, "{:.1f} ms".format(float(ds.current_time) * 1000), transform=fig.transFigure, ha="right", fontsize=24)

    fig.set_size_inches(19.2, 10.8)
    plt.tight_layout()
    plt.savefig(basename + imagefile_suffixes[0])

    for f, sp in slice_plots.items():
        sp.set_zlim(f, 0, min(initial_mass_fractions.get(f, 1.0 / 1.1) * 1.1, 1.0))
        sp.set_log(f, False)
        sp._setup_plots()
    fig.set_size_inches(19.2, 10.8)
    # plt.tight_layout()
    plt.savefig(basename + imagefile_suffixes[1])
    plt.close(fig)
    ds.index.clear_all_data()
    del ds, grid, sp
