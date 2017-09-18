#!/usr/bin/env python

import os
import json
import xml.etree.cElementTree as ET

import time
import requests
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

from flask import Flask, render_template, send_from_directory, request, redirect, send_file
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

    title = requests.get("http://webapi.bmrb.wisc.edu/v1/rest/tag/%s/_Assembly.Name" % entry_id).json()
    return title[entry_id]['_Assembly.Name'][0].title()

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
            return send_from_directory(exp_full_path, some_file)

    # Load the entry XML
    try:
        root = ET.parse(os.path.join(exp_full_path, "spin_simulation.xml")).getroot()
    except IOError:
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
