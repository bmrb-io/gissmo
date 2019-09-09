import pandas as pd
import tensorflow as tf
import matplotlib.pyplot as plt
import numpy as np
import csv
import os
from datetime import datetime



def norm(input_dic, describe_stats):
    return (input_dic - describe_stats['mean']) / describe_stats['std']


def draw_hist_error(error):
    #plt.hist(error, bins=30)
    #plt.xlabel("Prediction Error [Chemical Shift; Hz]")
    #plt.ylabel("Count")
    #plt.show()
    i = 0


def load_cs_model():
    model_file_path = "cs.h5"
    model = tf.keras.models.load_model(model_file_path)
    model.compile(loss='mae',  optimizer=tf.keras.optimizers.Adam(lr=1e-3, decay=1e-5), metrics=['mae'])
    #model.summary()
    train_stats = pd.read_pickle("trained_cs_stats.pickle")
    return model, train_stats


def load_jc_model():
    model_file_path = "jc_mse.h5"
    model = tf.keras.models.load_model(model_file_path)
    model.compile(loss='mse', optimizer=tf.keras.optimizers.Adam(lr=1e-3, decay=1e-5), metrics=['mse', 'mae'])
    #model.summary()
    train_stats = pd.read_pickle("trained_jc_stats.pickle")
    return model, train_stats


def get_chemical_shift(model_cs, train_stats_cs, table_out_cs):
    tmp_table_cs = "/tmp/cs_table_%s.csv" % datetime.now().strftime('%Y%m%d%H%M%S')
    fout = open(tmp_table_cs, "w")
    writer = csv.writer(fout)
    for _ in table_out_cs:
        writer.writerow(_)
    fout.close()
    raw_dataset = pd.read_csv(tmp_table_cs)
    normalized_dataset = norm(raw_dataset, train_stats_cs)
    test_predictions = model_cs.predict(normalized_dataset).flatten()
    return test_predictions


def get_couplings(model_jc, table_out_cs, proton_distances, train_stats_jc):
    tmp_table_jc = "/tmp/jc_table_%s.csv" % datetime.now().strftime('%Y%m%d%H%M%S')
    fout = open(tmp_table_jc, "w")
    writer = csv.writer(fout)
    row = [x for x in table_out_cs[0]]
    row.append("bond_distance")
    writer.writerow(row)
    atom_indices = []
    for _ in range(proton_distances.shape[0]-1):
        for __ in range(_+1, proton_distances.shape[0]):
            if proton_distances[_, __] <= 3:
                atom_indices.append([_, __])
                row = [x for x in table_out_cs[_+1]]
                row.append(proton_distances[_, __])
                writer.writerow(row)
    fout.close()
    to_be_removed_tags = ['num_O_nghs_r2', 'num_O_nghs_r3', 'num_P_nghs_r3', 'num_O_nghs_r4', 'num_O_nghs_r5']
    raw_dataset = pd.read_csv(tmp_table_jc)
    dataset = raw_dataset.copy()
    normalized_dataset = norm(dataset, train_stats_jc)
    normalized_dataset = normalized_dataset.drop(to_be_removed_tags, axis=1)
    test_predictions = model_jc.predict(normalized_dataset).flatten()
    return test_predictions, atom_indices


def run(table_out_cs, proton_distances):

    model_cs, train_stats_cs = load_cs_model()
    model_jc, train_stats_jc = load_jc_model()

    test_predictions_cs = get_chemical_shift(model_cs, train_stats_cs, table_out_cs)
    test_predictions_jc, jc_atom_indices = get_couplings(model_jc, table_out_cs, proton_distances, train_stats_jc)

    spin_matrix = np.zeros([len(test_predictions_cs), len(test_predictions_cs)])
    for _ in range(len(test_predictions_cs)):
        spin_matrix[_, _] = test_predictions_cs[_]
    for _ in range(len(jc_atom_indices)):
        from_index = jc_atom_indices[_][0]
        to_index = jc_atom_indices[_][1]
        coupling = test_predictions_jc[_]
        spin_matrix[from_index, to_index] = coupling
        spin_matrix[to_index, from_index] = coupling

    os.system("rm -f cs_table*; rm -f jc_table*")
    return spin_matrix


