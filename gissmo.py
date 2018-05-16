#!/usr/bin/env python

import os
import re
try:
    import simplejson as json
except ImportError:
    import json
import xml.etree.cElementTree as ElementTree

import time
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

import requests
import psycopg2
from psycopg2.extras import DictCursor

from flask import Flask, render_template, send_from_directory, request, redirect, send_file
application = Flask(__name__)

aux_info_path = "/websites/gissmo/DB/aux_info/"
entry_path = "/websites/gissmo/DB/BMRB_DB/"
here = os.path.dirname(__file__)
entries_file = os.path.join(here, "entries.json")


# Helper methods
def get_tag_value(root, tag, all_=False):
    """ Returns the value of the specified tag(s)."""

    nodes = root.getiterator(tag)

    if all_:
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

    title = requests.get("http://webapi.bmrb.wisc.edu/v2/entry/%s?tag=_Assembly.Name" % entry_id,
                         headers={"Application": "GISSMO"}).json()
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

    if not results:
        return None
    elif len(results) == 1:
        return results[0]
    else:
        return results


# URI methods
@application.route('/reload')
def reload_db():
    """ Regenerate the released entry list. """

    valid_entries = []
    for entry_id in os.listdir(entry_path):

        sims = []
        dir_path = os.path.join(entry_path, entry_id)
        if not os.path.isdir(dir_path):
            continue

        for sim in os.listdir(dir_path):

            # Load the entry XML
            try:
                root = ElementTree.parse(os.path.join(entry_path, entry_id, sim, "spin_simulation.xml")).getroot()
            except IOError:
                continue
            except Exception as e:
                print entry_id, e
                continue

            # Check the entry is released
            status = get_tag_value(root, "status")
            if status.lower() in ["done", "approximately done"]:
                sims.append([entry_id, get_tag_value(root, "name"),
                             get_tag_value(root, "field_strength"), sim,
                             get_tag_value(root, "InChI")])

        if sims:
            valid_entries.append(sorted(sims, key=lambda x: x[2]))

    # Sort by protein name
    valid_entries = sorted(valid_entries, key=lambda x: x[0][1].lower())
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
    threshold = request.args.get('threshold', ".1")
    threshold_dec = Decimal(threshold)
    cur = get_postgres_connection()[1]

    # For endogenous organism search
    # http://www.bmrb.wisc.edu/metabolomics/metabolomics_standards_false.shtml

    sql = '''
SELECT bmrb_id,simulation_id,array_agg(DISTINCT ppm)
FROM chemical_shifts'''
    sql += ' WHERE ('
    terms = []

    fpeaks = []

    for peak in peaks:
        try:
            fpeaks.append(Decimal(peak))
        except InvalidOperation:
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
        result.append({'Entry_ID': entry[0],
                       'Simulation_ID': entry[1],
                       'Val': entry[2]})

    # Convert the search to decimal
    peaks = [Decimal(x) for x in peaks]

    def get_closest(collection, number):
        """ Returns the closest number from a list of numbers. """
        return min(collection, key=lambda _: abs(_-number))

    def get_sort_key(res):
        """ Returns the sort key. """

        key = 0

        # Determine how many of the queried peaks were matched
        num_match = 0
        matched_peaks = []
        for tmp_peak in peaks:
            closest = get_closest(res['Val'], tmp_peak)
            if abs(tmp_peak - closest) < threshold_dec:
                num_match += 1
                matched_peaks.append(closest)

                # Add the difference of all the matched shifts
                key += abs(get_closest(matched_peaks, tmp_peak) - tmp_peak)

        # Set the calculated values
        res['Peaks_matched'] = num_match
        res['Combined_offset'] = round(key, 3)
        # Only return the closest matches
        res['Val'] = matched_peaks

        return -num_match, key, res['Entry_ID']

    result = sorted(result, key=get_sort_key)

    # Determine actual entry list
    entry_list = json.loads(open(entries_file, "r").read())

    modified_entry_list = []
    for row in result:
        for entry in entry_list:
            m = []
            for sim in entry:
                if row['Entry_ID'] == sim[0] and row['Simulation_ID'] == sim[3]:
                    sim.append([str(x) for x in row['Val']])
                    sim.append(row['Peaks_matched'])
                    sim.append(row['Combined_offset'])
                    m.append(sim)
            modified_entry_list.append(m)

    return render_template("search_result.html", entries={1: modified_entry_list},
                           base_url=request.path, frequency=frequency,
                           peak_type=peak_type, raw_shift=raw_shift,
                           threshold=threshold)


@application.route('/gui')
def return_vm():
    """ Renders the downloadable VM page."""

    return render_template("vm.html")


@application.route('/js/<fname>')
def js(fname):
    """ Send the JS"""
    return send_from_directory("javascript", fname)


@application.route("/mixture", methods=['GET', 'POST'])
def get_mixture():
    """ Allow the user to specify a mixture. """

    # Get the list of valid entries
    entry_list = [x[0][0] for x in json.loads(open(entries_file, "r").read())]
    entry_list = "var valid_entries = " + json.dumps(entry_list) + ";"

    # Send them the page to enter a mixture
    if request.method == "GET":
        return render_template("mixture.html", entry_list=entry_list)
    # They sent a mixture, send them the spectra
    else:
        try:
            data = request.get_json()
            mixture = data['mixture']
            field_strength = data['fieldstrength']
        except KeyError:
            # No compounds specified
            return ""

        # mixture is dictionary with compound information
        """ get coefficient for FID's from concentration of the reference compound """
        con_coefficient = []
        ref_index = 0
        for iter_ in range(len(mixture)):
            a_cmp = mixture[iter_]
            if 'concentration' not in a_cmp:
                a_cmp['concentration'] = '0'
            con_coefficient.append(float(a_cmp['concentration']))
            if 'reference' in a_cmp and a_cmp['reference']:
                ref_index = iter_
        for iter_ in range(len(con_coefficient)):
            con_coefficient[iter_] = con_coefficient[iter_]/con_coefficient[ref_index]
        """ convert input spectra to float and apply the coefficient """
        """ Note that the length of the simulated spectra are/must be identical """
        cmp_spectra = []
        cmp_names = []
        mixture_ppm = []
        mixture_fid = []
        for iter_ in range(len(mixture)):
            cmp_id = mixture[iter_]['id']
            path = os.path.join(entry_path, cmp_id, "/simulation_1/spectral_data/sim_", str(field_strength), "MHz.json")
            # we need some sort of indication that the file doesnt exit!
            if not os.path.exists(path):
                continue
            fin = open(path, 'r')
            data = json.load(fin)
            data[0] = [float(x) for x in data[0]]
            data[1] = [con_coefficient[iter_]*float(x) for x in data[1]]
            cmp_spectra.append([data[0], data[1]])
            cmp_names.append(str(mixture[iter_]['compound']))
            if not mixture_ppm:
                mixture_ppm = data[0]
            if not mixture_fid:
                mixture_fid = data[1]
            else:
                mixture_fid = [mixture_fid[i]+data[1][i] for i in range(len(data[1]))]
            fin.close()
        args = {'input_mixture_info': mixture, 'mixture_spectra': [mixture_ppm, mixture_fid],
                'field_strength': field_strength, 'cmp_spectra': cmp_spectra, 'cmp_names': cmp_names}
        # field_strength is field_strength in mhz
        return render_template("mixture_render.html", **args)


@application.route('/entry/<entry_id>')
def display_summary(entry_id):
    """ Renders the page with a list of simulations available. """

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
        root = ElementTree.parse(os.path.join(entry_path, entry_id, sim_dir, "spin_simulation.xml")).getroot()
        data.append({'field_strength': get_tag_value(root, "field_strength"), 'sim': sim_dir, 'entry_id': entry_id})
        name = get_tag_value(root, "name")
    if not sims:
        return "No simulations available."

    return render_template("simulations_list.html", data=data, name=name)


@application.route('/entry/<entry_id>/<simulation>/peaks/<frequency>')
def display_peaks(entry_id, simulation, frequency):

    # Get the chemical shifts from postgres
    cur = get_postgres_connection()[1]
    cur.execute('''
SELECT frequency, ppm, amplitude FROM chemical_shifts
  WHERE bmrb_id=%s AND simulation_id=%s AND frequency=%s AND peak_type = 'GSD'
  ORDER BY frequency ASC, ppm ASC''', [entry_id, simulation, frequency])

    if frequency == '0':
        frequency = 'Default'
    res_dict = {'frequency': frequency,
                'entry_id': entry_id,
                'simulation': simulation,
                'shifts': cur.fetchall()}

    return render_template("gsd_peaks.html", **res_dict)


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
                    data.external_attr = 0666 << 16L  # Give all relevant permissions to downloaded file
                    data.compress_type = ZIP_DEFLATED
                    data.date_time = time.strptime(time.ctime(os.path.getmtime(fn)))
                    zf.writestr(data, open(fn, "r").read())

            comment = "Data downloaded from GISSMO server %s. To view entry: %sentry/%s/%s" % \
                      (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
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
        root = ElementTree.parse(os.path.join(exp_full_path, "spin_simulation.xml")).getroot()
    except IOError:
        return "No XML found."

    # Check the entry is released
    status = get_tag_value(root, "status")
    if status.lower() not in ["done", "approximately done"]:
        if not request.args.get('show_held', None):
            return "Entry not yet released."

    # Get all the values we will need
    tags_to_get = ["name", "InChI", "path_2D_image", "field_strength", "roi_rmsd"]
    ent_dict = dict_builder(root, tags_to_get)
    ent_dict['note'] = get_tag_value(root, 'note', all_=True)
    ent_dict['entry_id'] = entry_id
    ent_dict['simulation'] = simulation

    # Look up what simulated field strengths are available
    field_strengths = sorted([int(x[4:].replace("MHz", "")) for x in os.listdir(os.path.join(exp_full_path, "B0s"))])
    ent_dict['simulated_fields'] = field_strengths

    # Make sure the image file exists
    if not os.path.isfile(os.path.join(exp_full_path, ent_dict['path_2D_image'])):
        ent_dict['path_2D_image'] = entry_id + "_.jpg"

    # Get the entry directories
    ent_dict['sim_dirs'] = os.listdir(os.path.join(entry_path, entry_id))

    # Get the auxiliary info
    for aux_type in ["pka", "buffer", "cytocide", "reference", "solvent", "solvent", "ph", "temperature"]:
        ent_dict[aux_type] = get_aux_info(entry_id, simulation, aux_type)
    ent_dict['name'] = get_tag_value(root, "name")

    # Get the spin matrix data only for the first coupling matrix
    coupling_matrix = root.getiterator("coupling_matrix").next()
    column_names = get_tag_value(coupling_matrix, "spin", all_=True)
    diagonal = get_tag_value(coupling_matrix, "cs", all_=True)
    couplings = get_tag_value(coupling_matrix, "coupling", all_=True)

    def extract(attribute):
        return attribute.split('"')[1]

    ent_dict['acc'] = []
    for item in get_tag_value(coupling_matrix, "acc", all_=True):
        spin_index, coupling, spin_group_index, coupling_group_index = map(extract, item.split())
        try:
            spin_index = column_names[int(spin_index)-1]
        except (ValueError, IndexError):
            spin_index = "???"
        ent_dict['acc'].append({'spin_index': spin_index,
                                'coupling': coupling,
                                'spin_group_index': spin_group_index,
                                'coupling_group_index': coupling_group_index})

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
        from_index, to_index, value = map(extract, datum.split())
        from_index = int(from_index)
        to_index = int(to_index)
        if value != "0.0000000":
            matrix[from_index][to_index] = round(float(value), 3)

    ent_dict['matrix'] = matrix

    # Get the chemical shifts from postgres
    cur = get_postgres_connection()[1]
    cur.execute('''
SELECT frequency, ppm, amplitude, peak_type FROM chemical_shifts
  WHERE bmrb_id=%s AND simulation_id=%s AND peak_type='standard'
  ORDER BY frequency ASC, ppm ASC''', [entry_id, simulation])
    ent_dict['shifts'] = cur.fetchall()

    # Return the page
    return render_template("entry_template.html", **ent_dict)


if __name__ == "__main__":
    print "Called main."
