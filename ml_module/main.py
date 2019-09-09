import model_prepare_input
import generate_spectra
import nns
import csv
import os
from matplotlib import pyplot as plt


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
    input_parameters["spin_matrix"]=[]
    input_parameters["sw"] = 13 * input_parameters["field"]
    input_parameters["dw"] = 2 / input_parameters["sw"]
    return input_parameters


def write_spin_system(proton_indices, spin_matrix):
    fout = open("spin_system.csv", "w")
    writer = csv.writer(fout)
    a_row = [""]
    for _ in range(len(proton_indices)):
        a_row.append(proton_indices[_])
    writer.writerow(a_row)
    for _ in range(spin_matrix.shape[0]):
        a_row = [proton_indices[_]]
        for __ in range(spin_matrix.shape[1]):
            val = spin_matrix[_, __]
            if _ == __:
                val = val/input_parameters["field"]
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


input_parameters = {}
input_parameters["input_mol_file_path"] = "bmse000001.mol"  # sys.argv[1]
input_parameters["numpoints"] = 32768  # sys.argv[2]
input_parameters["field"] = 500  # sys.argv[3]
input_parameters["line_width"] = 0.74  # sys.argv[4]
input_parameters["lor_coeff"] = 1  # sys.argv[5]
input_parameters["gau_coeff"] = 0  # sys.argv[6]

input_parameters = load_spin_info(input_parameters)
table_out_cs, proton_indices, proton_distances = model_prepare_input.parse_input_structure_file(input_parameters["input_mol_file_path"])
spin_matrix = nns.run(table_out_cs, proton_distances)

input_parameters["spin_matrix"] = spin_matrix
ppm, sim_fid = generate_spectra.calculate_spectrum(input_parameters)

write_spectrum(ppm, sim_fid)

write_spin_system(proton_indices, spin_matrix)

os.system("zip outputs.zip ")