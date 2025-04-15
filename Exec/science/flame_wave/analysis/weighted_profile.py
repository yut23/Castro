#!/usr/bin/env python3
import argparse
import concurrent.futures
import csv
import re
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import yt


def lookup_datasets():
    plotfile_paths = {}
    with open("ftime.out", "r") as f:
        for line in f:
            pltfile, time_str = line.rstrip("\n").split()
            if Path(pltfile).exists():
                ms = round(float(time_str) * 1000)
                plotfile_paths[ms] = pltfile

    def get_dataset(ms: int) -> Any:
        assert ms in plotfile_paths, f"don't have plotfile for {ms}ms"
        print(f"loading {plotfile_paths[ms]} ({ms}ms)...")
        return yt.load(plotfile_paths[ms])

    return get_dataset


try:
    _get_dataset = lookup_datasets()  # type: ignore[no-untyped-call]
except FileNotFoundError:
    _get_dataset = None


def load_dataset(fname):
    path = Path(fname.rstrip("/"))
    if _get_dataset is not None and not path.exists():
        # try looking up by time
        if fname.endswith("ms"):
            return _get_dataset(int(fname.removesuffix("ms")))
    print(f"loading {path}...", flush=True)
    return yt.load(path)


class _Arguments(argparse.Namespace):
    # pylint: disable=too-few-public-methods
    datasets: list[str]
    out: str
    fields: list[str]
    percentile: float
    weight_field: str
    jobs: int


def parse_args() -> _Arguments:
    ################################
    # set up parser and parse args #
    ################################

    description = "Script for calculating weighted average profiles of a dataset as a function of time."

    datasets_help = "Datasets to calculate profiles over."
    out_help = 'Output filename for the profile information (defaults to "{weight-field}_profile.dat".'
    fields_help = "A list of fields to generate profiles for."
    weight_field_help = "The field to weight by (defaults to density)."
    percentile_help = """The percentile selection cutoff (defaults to 99).
        Only cells with field values at or above this cutoff will be included
        in the weighted average."""
    jobs_help = "Use this many workers to process the plotfiles in parallel."

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("datasets", nargs="+", help=datasets_help)
    parser.add_argument("-o", "--out", default=None, help=out_help)
    parser.add_argument(
        "--fields", nargs="*", default=["Temp", "enuc"], help=fields_help
    )
    parser.add_argument(
        "--weight-field", default="density", help=weight_field_help
    )
    parser.add_argument(
        "-p", "--percentile", type=float, default=99, help=percentile_help
    )
    parser.add_argument("-j", "--jobs", type=int, default=1, help=jobs_help)

    args = parser.parse_args(sys.argv[1:], namespace=_Arguments())

    assert 0 <= args.percentile <= 100
    if args.out is None:
        args.out = f"{args.weight_field}_profile.dat"

    # sort datasets by the numbers in the filename (natural sort)
    digit_pat = re.compile(r"\d+")
    args.datasets.sort(key=lambda x: tuple(map(int, digit_pat.findall(x))))

    # make sure all the fields are present
    ds = load_dataset(args.datasets[0])  # type: ignore[no-untyped-call]
    ad = ds.all_data()
    for f in args.fields:
        _ = ad[f]
    _ = ad[args.weight_field]

    del ds, ad
    return args


########################################
# Compute profiles and write data file #
########################################


def process_dataset(fname: str, args: _Arguments) -> tuple[Any, list[Any]]:
    ds = load_dataset(fname)  # type: ignore[no-untyped-call]
    values = []
    ad = ds.all_data()
    for f in args.fields:
        cutoff = np.quantile(ad[f], args.percentile / 100)
        f_per = ad.exclude_below(f, cutoff)
        values.append(f_per.quantities.weighted_average_quantity(f, args.weight_field))
    return ds.current_time, values


def main():
    args = parse_args()

    times: list[Any] = [None] * len(args.datasets)
    profiles: list[list[Any]] = [None] * len(args.datasets)  # type: ignore[list-item]

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as executor:
        future_to_index = {
            executor.submit(process_dataset, fname, args): i
            for i, fname in enumerate(args.datasets)
        }
        try:
            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index.pop(future)
                try:
                    time, values = future.result()
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    if isinstance(exc, concurrent.futures.BrokenExecutor):
                        # something went wrong internally, so stop everything
                        # and print a full traceback
                        print(
                            f"{args.datasets[i]} generated an exception:",
                            file=sys.stderr
                        )
                        traceback.print_exception(exc)
                        sys.stderr.flush()
                        break
                    # note the exception and keep going
                    print(
                        f"{args.datasets[i]} generated an exception: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                else:
                    times[i] = time
                    profiles[i] = values
        except KeyboardInterrupt:
            print(
                "\n*** got ctrl-c, cancelling remaining tasks and waiting for existing ones to finish...\n",
                flush=True,
            )
            executor.shutdown(wait=True, cancel_futures=True)
            sys.exit(1)

    # remove entries for skipped plotfiles
    times = [t for t in times if t is not None]
    profiles = [v for v in profiles if v is not None]

    with open(args.out, "w", newline="") as file:
        csvwriter = csv.writer(
            file, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL
        )
        header = ["time"]
        header.extend(args.fields)
        csvwriter.writerow(header)

        for time, values in zip(times, profiles):
            row = [time.to_value("s")]
            row.extend(v.to_value() for v in values)
            csvwriter.writerow(row)

    print("Task completed.")


if __name__ == "__main__":
    main()  # type: ignore[no-untyped-call]
