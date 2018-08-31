#!/usr/bin/env python

import os
import csv
try:
    import simplejson as json
except ImportError:
    import json
from decimal import Decimal

import optparse
# Specify some basic information about our command
opt = optparse.OptionParser(usage="usage: %prog", version="1.0", description="Generate a mixture spectrum.")
opt.add_option("--frequency", action="store", dest="frequency", default="40",
               choices=['40', '100', '200', '300', '400', '500', '600', '700', '800', '900', '950', '1000', '1300'],
               help="Which frequency to calculate spectrum at.")
opt.add_option("--resolution", action="store", dest="resolution", type="int", default=64000,
               help="The number of points to calculate")
opt.add_option("--file", action="store", dest="filename", default='mixture.csv',
               help="The file name to store the result.")
options, input_ids = opt.parse_args()


class SpectralResolver:
    """ Allows you to retrieve y values for arbitrary x values.

    You must go in """
    x = []
    y = []
    x_position = 0
    
    def __init__(self, file_location):
        """ File location should be the full or relative path to the JSON file for the frequency you want."""

        print('Loading file: %s' % file_location)
        self.x, self.y = json.load(open(file_location, "r"))
        self.x = [float(_) for _ in self.x]
        self.y = [float(_) for _ in self.y]

        self.x_position = -1

    def get_y(self, x):

        if x < self.x_position:
            raise ValueError('Cannot decrement X value without first calling reset()')

        while x > self.x[self.x_position]:
            self.x_position += 1

        # Exact match
        if x == self.x[self.x_position]:
            return self.y[self.x_position]
        # If it is the last point (or past it), return it
        else:
            if self.x_position == len(self.x) - 1:
                return self.x[self.x_position]

            slope = self.y[self.x_position + 1] - self.y[self.x_position] / (self.x[self.x_position+1]/self.x[self.x_position])

            # Add the slope between the next two points to this x value to estimate between the points
            return self.y[self.x_position] + slope*(x-self.x[self.x_position])

    def reset(self):
        self.x_position = -1


def get_mixture_spectra(frequency, resolution, gissmo_folder_list, filename=None):
    """ Returns [x_array, y_array] for the mixture with a number of points corresponding to the resolution if
    no filename specified. Otherwise writes to specified filename in JSON format. """

    def path_get(gissmo_folder, frequency):
        return os.path.join('/websites/gissmo/DB', gissmo_folder, 'simulation_1/spectral_data/', 'sim_%sMHz.json' % frequency)
    resolvers = [SpectralResolver(path_get(x, frequency)) for x in gissmo_folder_list]
    x_interval = 13 / float(resolution)

    y = [0]*options.resolution
    x = [0]*options.resolution

    for i in range(0, options.resolution):
        x_pos = -1 + i*x_interval
        x[i] = x_pos
        for resolver in resolvers:
            y[i] += resolver.get_y(x_pos)

    if filename:
        csv.writer(open(filename, "w")).writerows(zip(x, y))
    else:
        return [x, y]


if __name__ == "__main__":
    get_mixture_spectra(options.frequency, options.resolution, input_ids, options.filename)
    print('Wrote results to file: %s' % options.filename)
