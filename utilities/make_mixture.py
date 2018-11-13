#!/usr/bin/env python

import os
import csv
try:
    import simplejson as json
except ImportError:
    import json

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
opt.add_option("--precise", action="store_true", dest="precise", default=False,
               help="Use exact precision. Way slower.")
options, input_ids = opt.parse_args()

# Use Decimal() rather than float
if options.precise:
    from decimal import Decimal as float


class SpectralResolver:
    """ Allows you to retrieve y values for arbitrary x values.

    You must go in """
    x = []
    y = []
    x_position = 0
    
    def __init__(self, file_location, scale=1):
        """ File location should be the full or relative path to the JSON file for the frequency you want."""

        print('Loading file: %s of scale %s' % (file_location, scale))
        self.x, self.y = json.load(open(file_location, "r"))
        self.x = [float(_) for _ in self.x]
        self.y = [scale*float(_) for _ in self.y]
        self.x_position = 0

    def get_y(self, x):

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


def get_mixture_spectra(frequency, resolution, gissmo_id_and_scale_tuple, filename=None):
    """ Returns [x_array, y_array] for the mixture with a number of points corresponding to the resolution if
    no filename specified. Otherwise writes to specified filename in JSON format.

     Input:
       frequency, as string or int
       resolution: number of points to generate in the range [-1,12]
       gissmo_id_and_scale_tuple: A list of tuples of GISSMO ID and scale factor. Example:
         [(bmse000001, 1), (bmse000002, .5)]
       filename: The filename to write the results to as CSV. If omitted, returns the results to the caller
     """

    def get_path(gissmo_id):
        return os.path.join('/websites/gissmo/DB', gissmo_id, 'simulation_1/spectral_data/', 'sim_%sMHz.json' % frequency)
    resolvers = [SpectralResolver(get_path(x[0]), x[1]) for x in gissmo_id_and_scale_tuple]
    x_interval = 13 / float(resolution)

    y = [0]*options.resolution
    x = [0]*options.resolution

    for i in range(0, options.resolution):
        x_pos = -1 + i*x_interval
        x[i] = x_pos
        for resolver in resolvers:
            y[i] += resolver.get_y(x_pos)

    # Scale amplitude to 1
    max_y = 0
    for y_val in y:
        if y_val > max_y:
            max_y = y_val
    y = [_/max_y for _ in y]

    if filename:
        x = ["%.6f" % _ for _ in x]
        y = ["%.6f" % _ for _ in y]
        writer = csv.writer(open(filename, "w"))
        writer.writerow(['ppm', 'val'])
        writer.writerows(zip(x, y))
    else:
        return [x, y]


if __name__ == "__main__":

    def args_parse(gissmo_folder):
        try:
            id, scale = gissmo_folder.split(":")
        except ValueError:
            id, scale = gissmo_folder, 1
        return id, float(scale)

    gissmo_compound_list = [args_parse(x) for x in input_ids]
    get_mixture_spectra(options.frequency, options.resolution, gissmo_compound_list, options.filename)
    print('Wrote results to file: %s' % options.filename)
