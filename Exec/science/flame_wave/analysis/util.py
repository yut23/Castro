from collections import defaultdict

from yt.units import cm
from yt.utilities.periodic_table import periodic_table


def get_parameter(ds, name):
    try:
        return ds.parameters[name]
    except KeyError:
        # try adding '[*] ' to the front
        return ds.parameters[f"[*] {name}"]


def get_fuel_info(ds):
    info = {}
    for i in range(4):
        try:
            fuel_name = get_parameter(ds, f"problem.fuel{i+1}_name")
        except KeyError:
            continue
        if not fuel_name:
            continue
        el_str, _, aion_str = fuel_name.partition("-")
        if not aion_str:
            continue
        if el_str.title() not in periodic_table.elements_by_name:
            continue
        element = periodic_table.elements_by_name[el_str.title()]
        try:
            aion = int(aion_str)
        except ValueError:
            continue
        try:
            fuel_frac = get_parameter(ds, f"problem.fuel{i+1}_frac")
        except KeyError:
            continue
        info[i+1] = (element, aion, fuel_frac)
    return info


def get_fuel_fracs(fuel_info):
    fracs = defaultdict(lambda: 0.0)
    for element, aion, frac in fuel_info.values():
        fracs[f"{element.symbol}{aion}"] = frac
    return fracs


def get_sliceplot_bounds(ds, plotfile):
    print(ds.domain_width)

    xmin = ds.domain_left_edge[0]
    xmax = ds.domain_right_edge[0]
    xctr = 0.5*(xmin + xmax)
    L_x = xmax - xmin

    ymin = 0.0*cm
    ymax = 1.0e4*cm

    yctr = 0.5*(ymin + ymax)
    L_y = 1.0*(ymax - ymin)

    aspect = 3

    return {
        "center": [xctr, yctr, 0.0*cm],
        "width": [L_x, L_y, 0.0*cm],
        "aspect": aspect,
    }


def add_label(fig, ds, hydrogen_fraction):
    fig.text(0.54, 0.94, "{:.1f} ms, {:d}% H".format(
        float(ds.current_time) * 1000,
        round(hydrogen_fraction * 100)
    ), transform=fig.transFigure, ha="right", fontsize=24)
