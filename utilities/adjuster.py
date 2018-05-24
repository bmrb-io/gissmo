#!/usr/bin/python

from __future__ import print_function

import os
import csv
import sys


def reduce_list(raw_ppm, raw_val):

    last_yield, last_yield_pos = None, 0

    for pos in range(0, len(raw_val)-2):
        v = raw_val[pos]

        # If this is the first new value in a while
        if v != last_yield:
            if pos - last_yield_pos > 1:
                yield raw_ppm[pos-1], raw_val[pos-1]
            yield raw_ppm[pos], v
            last_yield, last_yield_pos = v, pos

    # Always yield the final point
    yield raw_ppm[-1], raw_val[-1]


def get_minimal(number, need_convert=True):

    if need_convert:
        trimmed = "%.5f" % number
    else:
        trimmed = number

    while len(trimmed) > 0 and trimmed[-1] in [".", "0", "-"]:
        trimmed = trimmed[:-1]

    if not trimmed:
        return "0"
    return trimmed


def to_json(filename):
    fd = open(filename, "r")
    fd.next()
    ppm = []
    val = []

    for _ in csv.reader(fd):
        ppm.append(_[0])
        val.append(float(_[1]))

    ppm_list = []
    val_list = []
    list_gen = reduce_list([get_minimal(x, False) for x in ppm], [get_minimal(x) for x in val])
    for pos, value in list_gen:
        ppm_list.append(pos)
        val_list.append(value)
    ppm_string = ",".join(ppm_list)
    val_string = ",".join(val_list)
    return "[[%s],[%s]]" % (ppm_string, val_string)


def do_ent(ent):
    print(ent)
    if not os.path.isdir(ent):
        return
    sims = os.listdir(ent)
    for sim in sims:
        print("  %s" % sim)
        try:
            sd = os.path.join(ent, sim, "spectral_data")
            if not os.path.exists:
                os.mkdir(sd)
            open(os.path.join(sd, "experimental.json"), "w").write(to_json(os.path.join(ent, sim, "exp_0")))
            open(os.path.join(sd, "sim_default.json"), "w").write(to_json(os.path.join(ent, sim, "sim_0")))
            bdir = os.path.join(ent, sim, "B0s")
            for s in os.listdir(bdir):
                print("    %s" % s)
                open(os.path.join(sd, s + ".json"), "w").write(to_json(os.path.join(bdir, s)))
        except IOError:
            continue


if len(sys.argv) > 1:
    for entry in sys.argv[1:]:
        do_ent(entry)
else:
    # Do all of them
    for entry in os.listdir("."):
        do_ent(entry)
