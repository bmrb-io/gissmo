import model_prepare_input
import generate_spectra
import nns
import csv
import os
from matplotlib import pyplot as plt
from time import gmtime, strftime
import json


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


def write_gissmo_input(proton_indices, spin_matrix, input_mol_path, field):
    head, mol_file_name = os.path.split(input_mol_path)
    temp_id = strftime("%Y%m%d_%H%M%S", gmtime())
    gissmo_folder = temp_id
    os.system("mkdir %s" % gissmo_folder)
    os.system("mkdir %s/1H" % gissmo_folder)
    os.system("cp %s %s" % (input_mol_path, gissmo_folder))
    fout = open(os.path.join(gissmo_folder, "spin_simulation.xml"), "w")
    fout.write("<spin_simulation>\n")
    fout.write("	<version>2</version>\n")
    fout.write("	<name>GIISMOML_cmp</name>\n")
    fout.write("	<ID>%s</ID>\n" % temp_id)
    fout.write('	<SRC name="GISSMOML" ID="%s"></SRC>\n' % temp_id)
    fout.write("	<InChI></InChI>\n")
    fout.write("	<comp_db_link>\n")
    fout.write("	</comp_db_link>\n")
    fout.write("	<mol_file_path>./%s</mol_file_path>\n" % mol_file_name)
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


def write_spectrum(ppm, sim_fid):
    fout = open("spectrum.csv", "w")
    writer = csv.writer(fout)
    writer.writerow(["PPM", "AMP"])
    for _ in range(len(ppm)):
        writer.writerow([ppm[_], sim_fid[_]])
    fout.close()


input_parameters = {}
input_parameters["input_mol_file_path"] = "/Users/hesam/Dropbox (Partners HealthCare)/Desktop/Collaboration_exploring/GISSMO_ML/GISSMO_ML_codes/run_gissmo_trained_models/bmse000060.mol"
input_parameters["numpoints"] = 32768  # sys.argv[2]
input_parameters["field"] = 500  # sys.argv[3]
input_parameters["line_width"] = 0.74  # sys.argv[4]
input_parameters["lor_coeff"] = 1  # sys.argv[5]
input_parameters["gau_coeff"] = 0  # sys.argv[6]


input_parameters = load_spin_info(input_parameters)
table_out_cs, proton_indices, proton_distances = model_prepare_input.parse_input_structure_file(
                input_parameters["input_mol_file_path"])

spin_matrix = nns.run(table_out_cs, proton_distances)
print(spin_matrix)
input_parameters["spin_matrix"] = spin_matrix
ppm, sim_fid = generate_spectra.calculate_spectrum(input_parameters)

# write_spectrum(ppm, sim_fid)

# write_spin_system(proton_indices, spin_matrix)

# gissmo_folder = write_gissmo_input(proton_indices, spin_matrix, input_parameters["input_mol_file_path"],
#                                   input_parameters["field"])

#input_parameters["gissmo_folder"] = gissmo_folder
#json.dump(input_parameters, open("output.json", "w"))
# os.system("zip outputs.zip spectrum.csv output.json %s %s" % (input_parameters["input_mol_file_path"], gissmo_folder))
