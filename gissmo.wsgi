#!/usr/bin/env python

import os
import re
import json
import xml.etree.cElementTree as ET

import time
import requests
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

import psycopg2

from flask import Flask, render_template, send_from_directory, request, redirect, send_file, jsonify
application = Flask(__name__)

aux_info_path = "/websites/gissmo/DB/aux_info/"
entry_path = "/websites/gissmo/DB/BMRB_DB/"
here = os.path.dirname(__file__)
entries_file = os.path.join(here, "entries.json")
#entries_file = "/websites/gissmo/entries.json"

# Helper methods
def get_tag_value(root, tag, _all=False):
    """ Returns the value of the specified tag(s)."""

    nodes =  root.getiterator(tag)

    if _all:
        return [x.text for x in nodes]
    else:
        try:
            return nodes.next().text
        except StopIteration:
            return None

def dict_builder(root, tags):
    """ Gets all of the tags from the XML and builds a dictionary. """

    res = {}
    for tag in tags:
        res[tag] = get_tag_value(root, tag)

    return res

def get_title(entry_id):
    """ Fetches the actual compound name from BMRB API. """

    title = requests.get("http://webapi.bmrb.wisc.edu/v2/entry/%s?tag=_Assembly.Name" % entry_id, headers={"Application":"GISSMO"}).json()
    return title[entry_id]['_Assembly.Name'][0].title()

def get_postgres_connection(user='web', database='gissmo',
                            dictionary_cursor=False):
    """ Returns a connection to postgres and a cursor."""

    if dictionary_cursor:
        conn = psycopg2.connect(user=user, database=database, cursor_factory=DictCursor)
    else:
        conn = psycopg2.connect(user=user, database=database)
    cur = conn.cursor()

    return conn, cur

def get_aux_info(entry_id, simulation, aux_name):

    results = []
    try:
        aux_file = os.path.join(aux_info_path, aux_name, "%s_%s" % (entry_id, simulation))
        # If the files aren't simulation specific try just the entry name
        if not os.path.isfile(aux_file):
            aux_file = os.path.join(aux_info_path, aux_name, entry_id)
        with open(aux_file, "r") as aux_file:
            for line in aux_file:
                line = line.strip()
                if aux_name == "pka" and line.startswith("pKa="):
                    line = line[4:]
                results.append(line)
    except IOError:
        pass

    if len(results) == 0:
        return None
    elif len(results) == 1:
        return results[0]
    else:
        return results

# URI methods
@application.route('/reload')
def reload():
    """ Regenerate the released entry list. """

    valid_entries = []
    for entry_id in os.listdir(entry_path):

        sims = []
        for sim in os.listdir(os.path.join(entry_path, entry_id)):

            # Load the entry XML
            try:
                root = ET.parse(os.path.join(entry_path, entry_id, sim, "spin_simulation.xml")).getroot()
            except IOError:
                continue
            except Exception as e:
                print entry_id, e
                continue

            # Check the entry is released
            status = get_tag_value(root, "status")
            if status.lower() in ["done", "approximately done"]:
                sims.append([entry_id, get_title(entry_id),
                             get_tag_value(root, "field_strength"), sim,
                             len(get_tag_value(root, "spin", _all=True)),
                             get_tag_value(root, "InChI")])

        sims = sorted(sims, key=lambda x:x[2])

        if len(sims) > 0:
            valid_entries.append(sims)

    # Sort by protein name
    valid_entries = sorted(valid_entries, key=lambda x:x[0][1].lower())
    # Write out the results
    open(entries_file, "w").write(json.dumps(valid_entries))

    return redirect("", code=302)

@application.route('/')
def display_list():
    """ Display the list of possible entries. """

    entry_list = json.loads(open(entries_file, "r").read())

    entry_letters = {}
    for item in entry_list:
        comp = item[0][1]
        comp = comp.replace("(S)", "").replace("(R)", "")
        for pos, char in enumerate(comp):
            if char.isalpha():
                letter = comp[pos].upper()
                if letter not in entry_letters:
                    entry_letters[letter] = []
                entry_letters[letter].append(item)
                break

    return render_template("list_template.html", entries=entry_letters)

@application.route('/peak_search')
def peak_search():
    """ Returns a page with compounds that match the provided peaks. """

    raw_shift = request.args.get('rs', "")
    peaks = re.split('[\s\n\t,;]+', raw_shift)
    frequency = request.args.get('frequency', "800")
    peak_type = request.args.get('peak_type', "standard")
    threshold = request.args.get('threshold', ".01")
    threshold_dec = Decimal(threshold)
    cur = get_postgres_connection()[1]

    sql = '''
SELECT bmrb_id,simulation_id,array_agg(DISTINCT ppm)
FROM chemical_shifts
WHERE ('''
    terms = []

    fpeaks = []
    try:
        for peak in peaks:
            fpeaks.append(Decimal(peak))
    except ValueError:
        raise RequestError("Invalid peak specified. All peaks must be numbers. Invalid peak: '%s'" % peak)
    except:
        pass

    peaks = sorted(fpeaks)

    for peak in peaks:
        sql += '''
(ppm < %s  AND ppm > %s) OR '''
        terms.append(peak + threshold_dec)
        terms.append(peak - threshold_dec)

    # End the OR
    sql += '''
1=2 ) AND
frequency=%s AND peak_type=%s
GROUP BY bmrb_id, simulation_id
ORDER BY count(DISTINCT ppm) DESC;
'''
    terms.extend([frequency, peak_type])

    # Do the query
    cur.execute(sql, terms)

    result = []

    for entry in cur:
        result.append({'Entry_ID':entry[0],
                       'Simulation_ID': entry[1],
                       'Val': entry[2]})

    # Convert the search to decimal
    peaks = [Decimal(x) for x in peaks]

    def get_closest(collection, number):
        """ Returns the closest number from a list of numbers. """
        return min(collection, key=lambda x: abs(x-number))

    def get_sort_key(res):
        """ Returns the sort key. """

        key = 0

        # Determine how many of the queried peaks were matched
        num_match = 0
        matched_peaks = []
        for peak in peaks:
            closest = get_closest(res['Val'], peak)
            if abs(peak-closest) < threshold_dec:
                num_match += 1
                matched_peaks.append(closest)

                # Add the difference of all the matched shifts
                key += abs(get_closest(matched_peaks, peak) - peak)

        # Set the calculated values
        res['Peaks_matched'] = num_match
        res['Combined_offset'] = round(key, 3)
        # Only return the closest matches
        res['Val'] = matched_peaks

        return (-num_match, key, res['Entry_ID'])

    result = sorted(result, key=get_sort_key)

    # Determine actual entry list
    entry_list = json.loads(open(entries_file, "r").read())

    mentry_list = []
    for row in result:
        for entry in entry_list:
            m = []
            for sim in entry:
                if row['Entry_ID'] == sim[0] and row['Simulation_ID'] == sim[3]:
                    sim.append([str(x) for x in row['Val']])
                    sim.append(row['Peaks_matched'])
                    sim.append(row['Combined_offset'])
                    m.append(sim)
            mentry_list.append(m)

    return render_template("search_result.html", entries={1:mentry_list},
                           base_url=request.path, frequency=frequency,
                           peak_type=peak_type, raw_shift=raw_shift,
                           threshold=threshold )

@application.route('/vm')
def return_vm():
    """ Renders the downloadable VM page."""

    return render_template("vm.html")

@application.route("/mixture")
def get_mixture():
    """ Allow the user to specify a mixture. """

    return render_template("mixture.html")

@application.route('/entry/<entry_id>')
def display_summary(entry_id):
    """ Renders the page with a list of simulations available. """

    # Add the bmse if needed
    if not entry_id.startswith("bmse"):
        entry_id = "bmse" + entry_id

    data = []

    # Get the simulations
    try:
        sims = os.listdir(os.path.join(entry_path, entry_id))
    except OSError:
        return "No such entry exists."

    # If only one simulation, send them there
    if len(sims) == 1:
        return redirect("/entry/%s/%s" % (entry_id, sims[0]), 302)

    # Go through the simulations
    for sim_dir in sims:
        root = ET.parse(os.path.join(entry_path, entry_id, sim_dir, "spin_simulation.xml")).getroot()
        sim_dict = {}
        sim_dict['field_strength'] = get_tag_value(root, "field_strength")
        sim_dict['sim'] = sim_dir
        sim_dict['entry_id'] = entry_id
        data.append(sim_dict)
        #name = get_tag_value(root, "name")

    name = get_title(entry_id)

    return render_template("simulations_list.html", data=data, name=name)

@application.route('/entry/<entry_id>/<simulation>')
@application.route('/entry/<entry_id>/<simulation>/<some_file>')
def display_entry(entry_id, simulation=None, some_file=None):
    """ Renders an entry. If a filename is specified send them that file
    from the entry directory. """

    exp_full_path = os.path.join(entry_path, entry_id, simulation)

    # Make sure the entry directory exists
    if not os.path.isdir(os.path.join(entry_path, entry_id)):
        return "No such entry exists."

    # Make sure the experiment directory exists.
    if not os.path.isdir(exp_full_path):
        return "Experiment directory '%s' not found." % simulation

    # If they just want a file from the directory
    if some_file:
        if some_file == 'zip':
            memory_file = BytesIO()
            zf = ZipFile(memory_file, 'w')
            for root, dirs, files in os.walk(exp_full_path):
                for _file in files:
                    fn = os.path.join(root, _file)
                    np = os.path.join(root, _file)
                    np = np[np.index(entry_id):]
                    data = ZipInfo(np)
                    data.external_attr = 0666 << 16L # Give all relevant permissions to downloaded file
                    data.compress_type = ZIP_DEFLATED
                    data.date_time = time.strptime(time.ctime(os.path.getmtime(fn)))
                    zf.writestr(data, open(fn, "r").read())

            comment = "Data downloaded from GISSMO server %s. To view entry: %sentry/%s/%s" % (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                      request.url_root, entry_id.encode('ascii'), simulation.encode('ascii'))
            zf.comment = comment.encode()

            zf.close()
            memory_file.seek(0)
            return send_file(memory_file,
                             attachment_filename="%s_%s.zip" % (entry_id, simulation),
                             as_attachment=True)

        # Send individual files from the dir
        else:
            if some_file.endswith(".json"):
                return send_from_directory(os.path.join(exp_full_path, "spectral_data"), some_file)
            else:
                return send_from_directory(exp_full_path, some_file)

    # Load the entry XML
    try:
        root = ET.parse(os.path.join(exp_full_path, "spin_simulation.xml")).getroot()
    except IOError as e:
        return "No XML found."

    # Check the entry is released
    status = get_tag_value(root, "status")
    if status.lower() not in ["done", "approximately done"]:
        if not request.args.get('show_held', None):
            return "Entry not yet released."

    # Get all the values we will need
    tags_to_get = ["name", "InChI", "path_2D_image", "field_strength", "roi_rmsd", "note"]
    ent_dict = dict_builder(root, tags_to_get)
    ent_dict['entry_id'] = entry_id
    ent_dict['simulation'] = simulation

    # Look up what simulated field strengths are available
    field_strengths = sorted([int(x[4:].replace("MHz","")) for x in os.listdir(os.path.join(exp_full_path, "B0s"))])
    ent_dict['simulated_fields'] = field_strengths

    # Make sure the image file exists
    if not os.path.isfile(os.path.join(exp_full_path, ent_dict['path_2D_image'])):
        ent_dict['path_2D_image'] = entry_id + "_.jpg"

    # Get the entry directories
    ent_dict['sim_dirs'] = os.listdir(os.path.join(entry_path, entry_id))

    # Get the auxiliary info
    for aux_type in ["pka", "buffer", "cytocide", "reference", "solvent", "solvent", "ph", "temperature"]:
        ent_dict[aux_type] = get_aux_info(entry_id, simulation, aux_type)
    ent_dict['name'] = get_aux_info(entry_id, simulation, "titles")

    # Get the spin matrix data
    column_names = get_tag_value(root, "spin", _all=True)
    diagonal = get_tag_value(root, "cs", _all=True)
    couplings = get_tag_value(root, "coupling", _all=True)

    # Build the spin matrix
    size = len(column_names)+1
    matrix = [[0 for x in range(size)] for x in range(size)]

    # Add in the labels
    matrix[0] = [""] + column_names
    for pos, name in enumerate(column_names):
        matrix[pos+1][0] = name

    # Add the diagonals
    for pos, cs in enumerate(diagonal):
        matrix[pos+1][pos+1] = round(float(cs), 3)

    # Add the other values
    for datum in couplings:
        from_index, to_index, value = datum.split()
        from_index = int(from_index.split('"')[1])
        to_index = int(to_index.split('"')[1])
        value = value.split('"')[1]
        if value == "0.0000000":
            value = 0
        else:
            matrix[from_index][to_index] = round(float(value), 3)

    ent_dict['matrix'] = matrix

    # Return the page
    return render_template("entry_template.html", **ent_dict)


if __name__ == "__main__":
    print "Called main."
