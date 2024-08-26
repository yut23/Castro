#!/usr/bin/env python3
# pylint: disable=wrong-import-position, wrong-import-order

import matplotlib
matplotlib.use('agg')

import os
import re
import sys
import traceback
import yt
import matplotlib.pyplot as plt

from mpl_toolkits.axes_grid1 import ImageGrid

# assume that our data is in CGS
from yt.units import cm
from yt.frontends.boxlib.api import CastroDataset

import util

# yt.enable_parallelism()

plt.rcParams.update({"font.family": "stixgeneral", "mathtext.fontset": "cm"})

# define ash
def _ash(field, data):
    """ash is anything beyond O, excluding Fe and Ni"""

    ash_sum = None
    for f in data.ds.field_list:
        field_name = f[-1]
        # matches names like "X(ne21)" or "X(He4)"
        m = re.match(r"^X\(([A-Za-z]+)(\d+)\)$", field_name)
        if m is None:
            continue
        element = m[1].lower()
        aion = int(m[2])
        if element not in {"h", "he", "c", "n", "o", "fe", "ni"}:
            if ash_sum is None:
                ash_sum = data[f]
            else:
                ash_sum += data[f]
    # if ash_sum is None:
    #     raise ValueError("no ash found")
    return ash_sum


yt.add_field(("gas", "ash"), function=_ash, display_name="ash", units="(dimensionless)", sampling_type="cell")


files = sys.argv[1:]
force = False
if files[0] in ('-f', '--force'):
    files = files[1:]
    force = True

imagefile_template = "{}_slice_density.png"

# filter out any images that already exist
actual_files = []
for plotfile in sorted(set(files)):
    imagefile = imagefile_template.format(os.path.basename(plotfile))
    if os.path.exists(imagefile) and not force:
        print(f"skipping {os.path.basename(plotfile)} since an image already exists")
        continue
    actual_files.append(plotfile)

# for plotfile in yt.parallel_objects(actual_files):
for plotfile in actual_files:
    imagefile = imagefile_template.format(os.path.basename(plotfile))
    print("\nprocessing " + os.path.basename(plotfile) + "...", flush=True)

    ds = CastroDataset(plotfile)

    bounds_kwargs = util.get_sliceplot_bounds(ds, plotfile)

    buff_size = (2400, 2400)

    fig = plt.figure()
    fig.set_size_inches(12.0, 9.0)

    if ("boxlib", "X(ash)") in ds.field_list:
        fields = ["Temp", "ash_density", "density", "enuc"]
    elif "_smallplt" in plotfile:
        fields = ["Temp", "X(ash)", "enuc", "density"]
    else:
        fields = ["Temp", "ash", "enuc", "density"]

    fuel_info = util.get_fuel_info(ds)
    abar_min = 1.0 / sum(X / A for _, A, X in fuel_info.values())
    fuel_fracs = util.get_fuel_fracs(fuel_info)

    grid = ImageGrid(fig, 111, nrows_ncols=(len(fields), 1),
                     axes_pad=0.27, label_mode="L", cbar_mode="each")

    ad = ds.all_data()
    print("ash_density:", ad.quantities.extrema(("gas", "ash_density")))
    print("density:    ", ad.quantities.extrema(("gas", "density")))
    print("enuc:       ", ad.quantities.extrema("enuc"))

    try:
        for i, f in enumerate(fields):
            # pylint: disable=no-member

            kwargs = bounds_kwargs.copy()
            if f == "enuc":
                # mask out any negative values, since they can screw up the log-scale
                # colormap bounds and make the background white instead of red
                kwargs["data_source"] = ds.all_data().include_above("enuc", 0)
            if yt.version_info >= (4, 0, 0):
                kwargs["buff_size"] = buff_size
            sp = yt.SlicePlot(ds, "theta", f, fontsize=16, **kwargs)
            if "buff_size" not in kwargs:
                sp.set_buff_size(buff_size)

            if f == "Temp":
                sp.set_zlim(f, 5.e7, 1.5e9)
                sp.set_cmap(f, "magma_r")
            elif f == "enuc":
                sp.set_zlim(f, 1.e14, 1.e18)
            elif f == "density":
                sp.set_zlim(f, 1.e-3, 5.e7)
            elif f == "z_velocity":
                sp.set_zlim(f, -2.e8, 2.e8)
                sp.set_log(f, False)
                sp.set_cmap(f, "bwr")
            elif f == "abar":
                sp.set_zlim(f, abar_min, 5)
                sp.set_log(f, False)
                sp.set_cmap(f, "plasma_r")
            elif f in {"ash", "X(ash)"}:
                sp.set_zlim(f, 1.e-5, 0.1)
                sp.set_log(f, True)
                sp.set_cmap(f, "plasma_r")
            elif f == "ash_density":
                sp.set_zlim(f, 1.e-2, 2e5)
                sp.set_log(f, True)
                sp.set_cmap(f, "plasma_r")

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

        util.add_label(fig, ds, fuel_fracs["H1"])

        fig.set_size_inches(19.2, 10.8)
        plt.tight_layout()
        plt.savefig(imagefile)
        plt.close(fig)
        del sp
    except Exception:
        print(f"ERROR: rendering {os.path.basename(plotfile)} failed:")
        traceback.print_exc(file=sys.stdout)
    ds.index.clear_all_data()
    del ds, grid
