#!/usr/bin/env python

from __future__ import print_function

import os
import re

import xml.etree.cElementTree as ElementTree

import time
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

# Local virtualenv imports
import requests
import psycopg2
import pynmrstar
import simplejson as json
from psycopg2.extras import DictCursor, execute_values
from flask import Flask, render_template, send_from_directory, request, redirect, send_file, url_for, jsonify

application = Flask(__name__)

aux_info_path = "/websites/gissmo/DB/aux_info/"
entry_path = "/websites/gissmo/DB/"


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


def get_postgres_connection(user='web', database='webservers', host='pinzgau', port='5432',
                            dictionary_cursor=False):
    """ Returns a connection to postgres and a cursor."""

    if application.debug:
        port = '5901'
        host = 'localhost'

    if dictionary_cursor:
        conn = psycopg2.connect(user=user, database=database, host=host, cursor_factory=DictCursor, port=port)
    else:
        conn = psycopg2.connect(user=user, database=database, host=host, port=port)
    cur = conn.cursor()
    cur.execute("SET search_path TO gissmo, public")

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


def get_sample_conditions(file_name):
    # Get the NMR-STAR entry for sample info

    star_entry = pynmrstar.Entry.from_file(file_name)
    sample_conditions = star_entry.get_loops_by_category("_Sample_condition_variable")[0]
    sample_conditions = sample_conditions.get_tag(["Type", "Val", "Val_units"])
    sample_dict = {}
    for record in sample_conditions:
        if record[0] == "temperature":
            sample_dict[record[0].lower()] = "%s %s" % (record[1], record[2])
        else:
            sample_dict[record[0].lower()] = record[1]

    sample_mix = star_entry.get_loops_by_category("_Sample_component")[0]
    sample_dict['sample'] = sample_mix.get_tag(["Mol_common_Name", "Isotopic_labeling", "Type", "Concentration_val",
                                                "Concentration_val_units"])

    return sample_dict


# URI methods
@application.route('/reload')
def reload_db():
    """ Regenerate the released entry list. """

    conn, cur = get_postgres_connection(user="postgres")

    cur.execute("""
-- Create terms table
DROP TABLE IF EXISTS entries_tmp;
CREATE TABLE entries_tmp (
    id text,
    name text,
    frequency float,
    simulation_id text,
    temperature text,
    ph text,
    inchi text);""")

    valid_entries = []
    for entry_id in os.listdir(entry_path):

        print(entry_id)

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
                print(entry_id, e)
                continue

            sample_conditions = get_sample_conditions(os.path.join(entry_path, entry_id, sim, "%s-%s.str" %
                                                                   (entry_id, sim)))

            # Check the entry is released
            status = get_tag_value(root, "status")
            if status.lower() in ["done", "approximately done"]:
                sims.append([entry_id, get_tag_value(root, "name"),
                             get_tag_value(root, "field_strength"),
                             sim,
                             sample_conditions['temperature'],
                             sample_conditions['ph'],
                             get_tag_value(root, "InChI")])

        if sims:
            valid_entries.extend(sims)
    conn.commit()
    import sys
    sys.exit(0)

    # Sort by protein name
    valid_entries = sorted(valid_entries, key=lambda x: x[0][1].lower())
    execute_values(cur, """INSERT INTO entries_tmp (id, name, frequency, simulation_id, temperature, ph, inchi) VALUES %s;""",
                   valid_entries,
                   page_size=1000)
    cur.execute("""
CREATE INDEX ON entries_tmp (id);
CREATE INDEX ON entries using gin(lower(name) gin_trgm_ops);

-- Move the new table into place
ALTER TABLE IF EXISTS entries RENAME TO entries_old;
ALTER TABLE entries_tmp RENAME TO entries;
DROP TABLE IF EXISTS entries_old CASCADE;""")

    # Reload the chemical shifts
    cur.execute("""
    -- Create terms table
    DROP TABLE IF EXISTS chemical_shifts_tmp;
    CREATE TABLE chemical_shifts_tmp (
        bmrb_id text,
        simulation_ID text,
        frequency integer,
        peak_type text,
        ppm numeric,
        amplitude float);""")
    cur.copy_expert("""COPY chemical_shifts_tmp FROM STDIN WITH (FORMAT csv);""",
                    open('%s/peak_list_GSD.csv' % entry_path, "rb"))
    cur.copy_expert("""COPY chemical_shifts_tmp FROM STDIN WITH (FORMAT csv);""",
                    open('%s/peak_list_standard.csv' % entry_path, "rb"))
    cur.execute("""-- create index: potentially combine these two based on usage
CREATE INDEX ON chemical_shifts_tmp (frequency, peak_type, ppm);

-- Move the new table into place
ALTER TABLE IF EXISTS chemical_shifts RENAME TO chemical_shifts_old;
ALTER TABLE chemical_shifts_tmp RENAME TO chemical_shifts;
DROP TABLE IF EXISTS chemical_shifts_old;

GRANT SELECT ON ALL TABLES IN SCHEMA gissmo TO web;""")
    conn.commit()

    return redirect(url_for('display_list'), 302)


def get_entry_list(term=None):
    """ Return the entry list in the format that the functions expect."""

    cur = get_postgres_connection()[1]

    if term:
        cur.execute('''
SELECT set_limit(.75);
SELECT * FROM gissmo.entries
  WHERE lower(%s) %% lower(name) OR inchi = %s OR inchi = %s''', [term, term, 'InChI=' + term])
    else:
        cur.execute("SELECT * FROM entries ORDER BY id, simulation_ID")

    entry_list = []
    last_entry = None
    working_list = []
    for sim in cur:
        sim = list(sim)
        if sim[0] == last_entry:
            working_list.append(sim)
        else:
            if working_list:
                entry_list.append(working_list)
            last_entry = sim[0]
            working_list = [sim]
    if working_list:
        entry_list.append(working_list)

    return entry_list


@application.route('/')
def home():
    return render_template("home.html")


@application.route('/tutorial')
def tutorial_page():
    return render_template("tutorial.html")


@application.route('/search')
def name_search():
    """ Render the name search."""

    term = request.args.get('term', "")
    if term:
        cur = get_postgres_connection()[1]
        sql = '''
SELECT set_limit(.6);
SELECT id, name FROM gissmo.entries
  WHERE lower(%s) %% lower(name) OR inchi = %s OR inchi = %s
  ORDER BY similarity(lower(name), lower(%s)) DESC'''
        cur.execute(sql, [term, term, 'InChI=' + term, term])
        results = []
        for item in cur:
            results.append({'id': item[0], 'name': item[1]})
    else:
        results = []
    return jsonify(results)


@application.route('/library')
def display_list():
    """ Display the list of possible entries. """

    term = request.args.get('term', "")
    entry_list = get_entry_list(term)

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

    return render_template("list_template.html", entries=entry_letters, term=term)


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
        return Decimal(min(collection, key=lambda _: abs(_ - number)))

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
    entry_list = get_entry_list()

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


@application.route('/convert_mol_svg')
def mol_svn_converter_page():
    """ Render the mol -> svn conversion page."""

    return render_template('convert_mol_svg.html')


@application.route("/mixture")
def get_mixture():
    """ Allow the user to specify a mixture. """

    # Get the list of valid entries
    entry_list = [x[0][0] for x in get_entry_list()]
    entry_list = "let valid_entries = " + json.dumps(entry_list) + ";"

    # Send them the page to enter a mixture
    return render_template("mixture.html", entry_list=entry_list)


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
    name = "unknown"
    for sim_dir in sims:
        root = ElementTree.parse(os.path.join(entry_path, entry_id, sim_dir, "spin_simulation.xml")).getroot()
        data.append({'field_strength': get_tag_value(root, "field_strength"), 'sim': sim_dir, 'entry_id': entry_id})
        name = get_tag_value(root, "name")
    if not sims:
        return "No simulations available."

    return render_template("simulations_list.html", data=data, name=name)


@application.route('/entry/list')
def get_gissmo_entries():
    """ Returns a list of all entries currently in GISSMO. """

    cur = get_postgres_connection()[1]
    cur.execute('SELECT id FROM entries;')
    return jsonify([x[0] for x in cur.fetchall()])


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
                    # Python 3.7 fix for the above line:
                    # data.external_attr = 0o0666 << 16  # Give all relevant permissions to downloaded file
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
    field_strengths = []
    for x in os.listdir(os.path.join(exp_full_path, "B0s")):
        try:
            field_strengths.append(int(x[4:].replace("MHz.csv", "")))
        except ValueError:
            pass
    ent_dict['simulated_fields'] = sorted(field_strengths)

    # Make sure the image file exists
    if not os.path.isfile(os.path.join(exp_full_path, ent_dict['path_2D_image'])):
        ent_dict['path_2D_image'] = entry_id + "_.jpg"

    # Get the entry directories
    ent_dict['sim_dirs'] = os.listdir(os.path.join(entry_path, entry_id))

    ent_dict['name'] = get_tag_value(root, "name")

    # Get the pka from the accessory file
    ent_dict["pka"] = get_aux_info(entry_id, simulation, "pka")

    # Get the NMR-STAR entry for sample info
    sample_conditions = get_sample_conditions(os.path.join(entry_path, entry_id, simulation, "%s-%s.str" %
                                                           (entry_id, simulation)))
    ent_dict.update(sample_conditions)

    # Get the spin matrix data only for the first coupling matrix
    coupling_matrix = root.getiterator("coupling_matrix").next()

    column_names = [x.attrib['name'] for x in coupling_matrix.getiterator("spin")]

    ent_dict['acc'] = []
    for item in coupling_matrix.getiterator('acc'):
        spin_index = item.attrib['spin_index']
        coupling = item.attrib['coupling']
        spin_group_index = item.attrib['spin_group_index']
        coupling_group_index = item.attrib['coupling_group_index']
        try:
            spin_index = column_names[int(spin_index) - 1]
        except (ValueError, IndexError):
            spin_index = "???"
        ent_dict['acc'].append({'spin_index': spin_index,
                                'coupling': coupling,
                                'spin_group_index': spin_group_index,
                                'coupling_group_index': coupling_group_index})

    # Build the spin matrix
    size = len(column_names) + 1
    matrix = [[0 for _ in range(size)] for _ in range(size)]

    # Add in the labels
    matrix[0] = [""] + column_names
    for pos, name in enumerate(column_names):
        matrix[pos + 1][0] = name

    # Add the diagonals
    for pos, item in enumerate(coupling_matrix.getiterator("cs")):
        matrix[pos + 1][pos + 1] = round(float(item.attrib['ppm']), 3)

    # Add the other values
    for item in coupling_matrix.getiterator("coupling"):
        from_index, to_index, value = item.attrib['from_index'], item.attrib['to_index'], item.attrib['value']
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
    print("Called main.")
