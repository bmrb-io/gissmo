import csv
import os
from tempfile import NamedTemporaryFile
import json
import generate_spectra
import model_prepare_input
import nns
from flask import Flask, render_template, send_from_directory, request, redirect, send_file, url_for, jsonify
from matplotlib import pyplot as plt

application = Flask(__name__)

 
def draw_spectrum(ppm, sim_fid):
    plt.plot(ppm.real, sim_fid.real)
    plt.gca().invert_xaxis()
    plt.xlabel("PPM")
    plt.show()


def load_spin_info(input_parameters):
    input_parameters["water_min"] = 4.5
    input_parameters["water_max"] = 4.7
    input_parameters["DSS_min"] = -0.1
    input_parameters["DSS_max"] = 0.1
    input_parameters["spin_matrix"] = []
    input_parameters["sw"] = 13 * input_parameters["field"]
    input_parameters["dw"] = 2 / input_parameters["sw"]
    return input_parameters


def write_spin_system(proton_indices, spin_matrix, input_parameters):
    fout = open("spin_system.csv", "w")
    writer = csv.writer(fout)
    a_row = [""]
    for _ in range(len(proton_indices)):
        a_row.append(proton_indices[_]+1)
    writer.writerow(a_row)
    for _ in range(spin_matrix.shape[0]):
        a_row = [proton_indices[_]+1]
        for __ in range(spin_matrix.shape[1]):
            val = spin_matrix[_, __]
            if _ == __:
                val = val / input_parameters["field"]
            a_row.append(val)
        writer.writerow(a_row)
    fout.close()


def write_spectrum(ppm, sim_fid):
    fout = open("spectrum.csv", "w")
    writer = csv.writer(fout)
    writer.writerow(["PPM", "AMP"])
    for _ in range(len(ppm)):
        writer.writerow([ppm[_], sim_fid[_]])
    fout.close()


@application.route('/simulate')
def simulate():
    """ Run the code. """

    # File can come from either place
    file_ = request.files.get('molfile', None)

    # if there is no uploaded structure
    if not file_:
        return 'No file uploaded or structure entered.'

    with NamedTemporaryFile() as temp_file:
        file_.save(temp_file.name)

        input_parameters = {"input_mol_file_path": temp_file.name,
                            "numpoints": int(request.args.get('numpoint', 32768)),
                            "field": float(request.args.get('field', 500)),
                            "line_width": float(request.args.get('lw', 0.74)),
                            "lor_coeff": float(request.args.get('lor', 1)),
                            "gau_coeff": float(request.args.get('gaus', 0)),
                            "err": ""}

        try:
            input_parameters = load_spin_info(input_parameters)
            table_out_cs, proton_indices, proton_distances = model_prepare_input.parse_input_structure_file(
                input_parameters["input_mol_file_path"])
            spin_matrix = nns.run(table_out_cs, proton_distances)

            input_parameters["spin_matrix"] = spin_matrix
            ppm, sim_fid = generate_spectra.calculate_spectrum(input_parameters)

            write_spectrum(ppm, sim_fid)
            write_spin_system(proton_indices, spin_matrix, input_parameters)
        except:
            input_parameters["err"] = "Something went wrong!"
        json.dump(input_parameters, open("params.json", "w"))

        os.system("zip outputs.zip params.json spectrum.csv spin_system.csv")

        return send_file("outputs.zip")