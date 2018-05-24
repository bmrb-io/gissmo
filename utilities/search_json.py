#!/usr/bin/env python

import sys
import simplejson as json

f = json.load(open("sim_900MHz.json", "r"))
c = zip(f[0], f[1])

for x in c:
  if float(x[0]) > float(sys.argv[1]) and float(x[0]) < float(sys.argv[2]):
    print(x)
