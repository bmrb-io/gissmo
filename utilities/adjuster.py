#!/usr/bin/python

from __future__ import print_function

import os
import csv
import sys


def reduce_list(raw_ppm, raw_val):

    ppm, val = [], []
    last, two_ago = None, None

    for pos, x in enumerate(raw_val):
        if x == "0" and last == "0" and two_ago == "0":
            continue
        ppm.push(raw_ppm[pos])
        val.push(x)
        two_ago = last
        last = x

    return ppm, val


def get_minimal(number):
    trimmed = "%.4f" % number
    while len(trimmed) > 0 and trimmed[-1] in [".", "0"]:
        trimmed = trimmed[:-1]

    if not trimmed:
        return "0"
    return trimmed


def to_json(filename):
    fd = open(filename, "r")
    fd.next()
    ppm = []
    val = []

    x = 4
    for _ in csv.reader(fd):
        if x % 4 == 0:
            ppm.append(float(_[0]))
            val.append(float(_[1]))
        x += 1

    ppm_list, val_list = reduce_list([get_minimal(x) for x in ppm], [get_minimal(x) for x in val])
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
