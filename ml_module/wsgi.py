import csv
import json
import os
import zipfile
from tempfile import NamedTemporaryFile
from datetime import datetime

import requests
from flask import Flask, request, send_file
from matplotlib import pyplot as plt

import generate_spectra
import model_prepare_input
import nns

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
        a_row.append(proton_indices[_] + 1)
    writer.writerow(a_row)
    for _ in range(spin_matrix.shape[0]):
        a_row = [proton_indices[_] + 1]
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


def write_gissmo_input(proton_indices, spin_matrix, input_mol_path, field, inchi):
    temp_id = datetime.now().strftime('%Y%m%d%H%M%S')
    gissmo_folder = os.path.join("/tmp/", temp_id)
    os.system("mkdir %s" % gissmo_folder)
    os.system("mkdir %s/1H" % gissmo_folder)
    os.system("cp %s %s/input.mol" % (input_mol_path, gissmo_folder))
    fout = open(os.path.join(gissmo_folder, "spin_simulation.xml"), "w")
    fout.write("<spin_simulation>\n")
    fout.write("	<version>2</version>\n")
    fout.write("	<name>GIISMOML_cmp</name>\n")
    fout.write("	<ID>%s</ID>\n" % temp_id)
    fout.write('	<SRC name="GISSMOML" ID="%s"></SRC>\n' % temp_id)
    fout.write("	<InChI>%s</InChI>\n" % inchi)
    fout.write("	<comp_db_link>\n")
    fout.write("	</comp_db_link>\n")
    fout.write("	<mol_file_path>./input.mol</mol_file_path>\n")
    fout.write("	<experimental_spectrum>\n")
    fout.write("        <type>Bruker</type>\n")
    fout.write("        <root_folder>./1H/</root_folder>\n")
    fout.write("	</experimental_spectrum>\n")
    fout.write("	<field_strength>%f</field_strength>\n" % field)
    fout.write("	<field_strength_applied_flag>1</field_strength_applied_flag>\n")
    fout.write("	<num_simulation_points>32768</num_simulation_points>\n")
    fout.write("	<num_simulation_points_applied_flag>1</num_simulation_points_applied_flag>\n")
    fout.write("	<path_2D_image>.</path_2D_image>\n")
    fout.write("	<num_split_matrices>0</num_split_matrices>\n")
    fout.write("	<roi_rmsd>1000</roi_rmsd>\n")
    fout.write("	<notes>\n")
    fout.write("	    <status>Initial values</status>\n")
    fout.write("	    <note></note>\n")
    fout.write("	</notes>\n")
    fout.write("	<coupling_matrix>\n")
    fout.write("        <label>merged</label>\n")
    fout.write("        <index>1</index>\n")
    fout.write("        <lw>1</lw>\n")
    fout.write("        <peak_shape_coefficients>\n")
    fout.write("            <lorentzian>0.8</lorentzian>\n")
    fout.write("            <gaussian>0.2</gaussian>\n")
    fout.write("        </peak_shape_coefficients>\n")
    fout.write("        <water_region>\n")
    fout.write("            <min_ppm>4.7000</min_ppm>\n")
    fout.write("            <max_ppm>5.0000</max_ppm>\n")
    fout.write("            <remove_flag>1</remove_flag>\n")
    fout.write("        </water_region>\n")
    fout.write("        <DSS_region>\n")
    fout.write("            <min_ppm>-0.1000</min_ppm>\n")
    fout.write("            <max_ppm>0.1000</max_ppm>\n")
    fout.write("            <remove_flag>1</remove_flag>\n")
    fout.write("        </DSS_region>\n")
    fout.write("        <additional_coupling_constants>\n")
    fout.write("        </additional_coupling_constants>\n")
    fout.write("        <spin_names>\n")
    for _ in range(len(proton_indices)):
        fout.write('            <spin index="%d" name="%d"></spin>\n' % (_+1, proton_indices[_]))
    fout.write("        </spin_names>\n")
    fout.write("        <chemical_shifts_ppm>\n")
    for _ in range(spin_matrix.shape[0]):
        fout.write('            <cs index="%d" ppm="%f"></cs>\n' % (_+1, spin_matrix[_][_]/field))
    fout.write("        </chemical_shifts_ppm>\n")
    fout.write("        <couplings_Hz>\n")
    for _ in range(spin_matrix.shape[0]):
        for __ in range(spin_matrix.shape[1]):
            if _ == __ or spin_matrix[_][__] == 0:
                continue
            fout.write('            <coupling from_index="%d" to_index="%d" value="%f"></coupling>\n' %
                       (_+1, __+1, spin_matrix[_][__]))
    fout.write("        </couplings_Hz>\n")
    fout.write("        <peak_list>\n")
    fout.write("        </peak_list>\n")
    fout.write("        <spectrum>\n")
    fout.write("        </spectrum>\n")
    fout.write("    </coupling_matrix>\n")
    fout.write("</spin_simulation>\n")
    return gissmo_folder


@application.route('/simulate')
def simulate():
    """ Run the code. """

    # File can come from either place
    file_ = request.files.get('molfile', None)

    # if there is no uploaded structure
    if not file_:
        return 'No file uploaded or structure entered.'

    with NamedTemporaryFile() as temp_file:
        # ALATIS-ify
        files = {'infile': file_}
        data = {'format': 'mol',
                'response_type': 'json',
                'project_2_to_3': 'on',
                'add_hydrogens': 'on'
                }
        alatis_output = requests.post('http://alatis.nmrfam.wisc.edu/upload',  data=data, files=files).json()
        inchi = alatis_output["inchi"]
        temp_file.write(alatis_output['structure'].encode())
        temp_file.seek(0)

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
            input_parameters['spin_matrix'] = input_parameters['spin_matrix'].tolist()
            gissmo_folder = write_gissmo_input(proton_indices, spin_matrix,
                                               input_parameters["input_mol_file_path"], input_parameters["field"],
                                               inchi)
            input_parameters["gissmo_folder"] = gissmo_folder
            input_parameters["inchi"] = inchi
        except Exception as exp:
            input_parameters["err"] = "Something went wrong: %s" % exp
            gissmo_folder = ""

        json.dump(input_parameters, open("params.json", "w"))

        with NamedTemporaryFile(suffix='.zip') as output_file:
            zip_file = zipfile.ZipFile(output_file.name, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True)
            zip_file.write('params.json')
            zip_file.write('spectrum.csv')
            zip_file.write('spin_system.csv')
            zip_file.write(gissmo_folder)
            zip_file.close()

            return send_file(output_file.name)
