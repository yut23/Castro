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
