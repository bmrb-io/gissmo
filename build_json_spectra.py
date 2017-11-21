#!/usr/bin/python

import os
import csv
import sys
import json


def to_csv(filename):
    fd = open(filename, "r")
    fd.next()
    ppm = []
    val = []
    for x in csv.reader(fd):
        ppm.append(x[0])
        val.append(x[1])

    return json.dumps( [ppm, val] )

def do_ent(ent):
    print ent
    if not os.path.isdir(ent):
        return
    sims = os.listdir(ent)
    for sim in sims:
        try:
            sd = os.path.join(ent, sim, "spectral_data")
            open(os.path.join(sd, "experimental.json"), "w").write(to_csv(os.path.join(ent, sim, "exp_0")))
            open(os.path.join(sd, "sim_default.json"), "w").write(to_csv(os.path.join(ent, sim, "sim_0")))
            bdir = os.path.join(ent, sim, "B0s")
            for s in os.listdir(bdir):
                open(os.path.join(sd, s+".json"), "w").write(to_csv(os.path.join(bdir, s)))
        except IOError:
            continue

if len(sys.argv) > 1:
    for entry in sys.argv[1:]:
        do_ent(entry)
else:
    # Do all of them
    ents = os.listdir(".")
    for entry in ents:
        do_ent(entry)
