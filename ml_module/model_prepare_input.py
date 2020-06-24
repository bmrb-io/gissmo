import os
import compound
import networkx as nx
import numpy as np

List_of_atoms_to_consider = ['C', 'N', 'O', 'H', 'P']


def parse_atom_nghs(mol, nghs, atoms_of_interest):
    nums = {}
    nghs_list = {}
    for an_atom in atoms_of_interest:
        nums[an_atom] = 0
        nghs_list[an_atom] = []
    for _ in nghs:
        if _[1] not in atoms_of_interest:
            continue
        nums[_[1]] += 1
        nghs_list[_[1]].append(_[0])
    return nums, nghs_list


def get_chx_groups(atoms, mol):
    ch_groups = []
    ch2_groups = []
    ch3_groups = []
    for c_index in range(len(atoms)):
        name = atoms[c_index].get_atom_name()
        if name != 'C':
            continue
        nghs_c = atoms[c_index].get_ngh()
        num_ngh_H = 0
        for _ in nghs_c:
            if _[1] == 'H':
                num_ngh_H += 1
        if num_ngh_H == 1:
            ch_groups.append(c_index)
        if num_ngh_H == 2:
            ch2_groups.append(c_index)
        if num_ngh_H == 3:
            ch3_groups.append(c_index)
    return ch_groups, ch2_groups, ch3_groups


def get_chx_group_label(mol, atom_iter, atoms, ch_groups, ch2_groups, ch3_groups):
    nghs_h = atoms[atom_iter].get_ngh()
    nums_h, nghs_list_h = parse_atom_nghs(mol, nghs_h, ['C'])
    if nums_h["C"] == 0:
        return -1, -1  # the proton is attached to non-C atoms
    base_carbon_index = nghs_list_h["C"][0]
    chx_group_label = -1
    if base_carbon_index in ch_groups:
        chx_group_label = 1
    if base_carbon_index in ch2_groups:
        chx_group_label = 2
    if base_carbon_index in ch3_groups:
        chx_group_label = 3
    return base_carbon_index, chx_group_label


def update_chx_groups(base_carbon_index, main_ch_groups, main_ch2_groups, main_ch3_groups):
    def remove_an_index_from_a_group(base_carbon_index, main_groups):
        out = []
        for _ in main_groups:
            if _ != base_carbon_index:
                out.append(_)
        return out
    ch_groups = remove_an_index_from_a_group(base_carbon_index, main_ch_groups)
    ch2_groups = remove_an_index_from_a_group(base_carbon_index, main_ch2_groups)
    ch3_groups = remove_an_index_from_a_group(base_carbon_index, main_ch3_groups)
    return ch_groups, ch2_groups, ch3_groups


def parse_atom_nghs_from_ngh_indices(mol, nghs_indices, atoms_of_interest):
    nums = {}
    nghs_list = {}
    for an_atom in atoms_of_interest:
        nums[an_atom] = 0
        nghs_list[an_atom] = []
    nghs = []
    for _ in nghs_indices:
        nghs.append([_, mol.get_an_atom(_).get_atom_name()])
    for a_ngh in nghs:
        if a_ngh[1] in nums:
            nums[a_ngh[1]] += 1
            nghs_list[a_ngh[1]].append(a_ngh[0])
    return nums, nghs_list


def update_nghs_info(num_total_nghs_2, nums_2, nghs_list_2, num_total_nghs_3, nums_3, nghs_list_3, num_total_nghs_4, nums_4, nghs_list_4, num_total_nghs_5, nums_5, nghs_list_5):
    #num_total_nghs_2, nums_2, nghs_list_2,
    #num_total_nghs_3, nums_3, nghs_list_3,
    #num_total_nghs_4, nums_4, nghs_list_4,
    #num_total_nghs_5, nums_5, nghs_list_5

    num_total_nghs_3 -= num_total_nghs_2
    num_total_nghs_4 -= num_total_nghs_2 + num_total_nghs_3
    num_total_nghs_5 -= num_total_nghs_2 + num_total_nghs_3 + num_total_nghs_4

    for _ in List_of_atoms_to_consider:
        nums_3[_] -= nums_2[_]
        nums_4[_] -= nums_2[_] + nums_3[_]
        nums_5[_] -= nums_2[_] + nums_3[_] + nums_4[_]
    return num_total_nghs_2, nums_2, nghs_list_2, num_total_nghs_3, nums_3, nghs_list_3, num_total_nghs_4, nums_4, nghs_list_4, num_total_nghs_5, nums_5, nghs_list_5


def get_info_for_a_radius(mol, curr_nx, atom_iter, curr_input):
    G = nx.ego_graph(curr_nx, atom_iter, radius=curr_input, center=False)
    nx.draw(G)
    nghs = G.nodes()
    num_total_nghs = len(nghs)
    nums, nghs_list = parse_atom_nghs_from_ngh_indices(mol, nghs, List_of_atoms_to_consider)
    return num_total_nghs, nums, nghs_list


def get_num_chx_from_nghs_list(c_atoms_list, ch_groups, ch2_groups, ch3_groups):
    num_ch_nghs = 0
    num_ch2_nghs = 0
    num_ch3_nghs = 0
    for _ in c_atoms_list:
        if _ in ch_groups:
            num_ch_nghs += 1
        if _ in ch2_groups:
            num_ch2_nghs += 1
        if _ in ch3_groups:
            num_ch3_nghs += 1
    return num_ch_nghs, num_ch2_nghs, num_ch3_nghs


def update_chx_nums(num_ch_nghs_r2, num_ch2_nghs_r2, num_ch3_nghs_r2,num_ch_nghs_r3, num_ch2_nghs_r3, num_ch3_nghs_r3, num_ch_nghs_r4, num_ch2_nghs_r4, num_ch3_nghs_r4, num_ch_nghs_r5, num_ch2_nghs_r5, num_ch3_nghs_r5):
    num_ch_nghs_r3 -= num_ch_nghs_r2
    num_ch_nghs_r4 -= num_ch_nghs_r2 + num_ch_nghs_r3
    num_ch_nghs_r5 -= num_ch_nghs_r2 + num_ch_nghs_r3 + num_ch_nghs_r4

    num_ch2_nghs_r3 -= num_ch2_nghs_r2
    num_ch2_nghs_r4 -= num_ch2_nghs_r2 + num_ch2_nghs_r3
    num_ch2_nghs_r5 -= num_ch2_nghs_r2 + num_ch2_nghs_r3 + num_ch2_nghs_r4

    num_ch3_nghs_r3 -= num_ch3_nghs_r2
    num_ch3_nghs_r4 -= num_ch3_nghs_r2 + num_ch3_nghs_r3
    num_ch3_nghs_r5 -= num_ch3_nghs_r2 + num_ch3_nghs_r3 + num_ch3_nghs_r4

    return num_ch_nghs_r2, num_ch2_nghs_r2, num_ch3_nghs_r2,num_ch_nghs_r3, num_ch2_nghs_r3, num_ch3_nghs_r3, \
           num_ch_nghs_r4, num_ch2_nghs_r4, num_ch3_nghs_r4, num_ch_nghs_r5, num_ch2_nghs_r5, num_ch3_nghs_r5


def add_to_row_info(var, var_name, cs_row, cs_row_header):
    cs_row.append(var)
    cs_row_header.append(var_name)
    return cs_row, cs_row_header


def extract_couplings(G, atom_iter, couplings, proton_nghs):
    out = []
    for cs_pair in couplings:
        if cs_pair[0] in proton_nghs:
            value = cs_pair[1]
            distance = len(nx.shortest_path(G, source=atom_iter, target=cs_pair[0])) - 1  # n nodes, n-1 edges
            out.append([distance, value])
    return out


def get_distances_between_protons(curr_nx, proton_indices):
    distances = 10 * np.ones([len(proton_indices), len(proton_indices)])
    for _ in range(len(proton_indices)-1):
        for __ in range(_+1, len(proton_indices)):
            dist = nx.shortest_path_length(curr_nx, source=proton_indices[_], target=proton_indices[__])
            distances[_, __] = dist
            distances[__, _] = dist
    return distances


def parse_input_structure_file(input_path):
    mol = compound.load_sdf(input_path, "MOL")
    atoms = mol.get_atoms()
    curr_nx = mol.get_networkx()
    main_ch_groups, main_ch2_groups, main_ch3_groups = get_chx_groups(atoms, mol)
    table_out_cs = []
    table_out_cs_has_header = False
    proton_indices = []
    for atom_iter in range(len(atoms)):
        # if not proton or not assigned a ppm: continue
        if atoms[atom_iter].get_atom_name() != 'H' or \
                atoms[atom_iter].get_ppm() == -10:
            continue
        # should return a label: 3: CH3, 2: CH2, 1: CH
        base_carbon_index, chx_group_label = get_chx_group_label(mol, atom_iter, atoms, main_ch_groups, main_ch2_groups,
                                                                 main_ch3_groups)
        if base_carbon_index == -1:
            continue
        ch_groups, ch2_groups, ch3_groups = update_chx_groups(base_carbon_index, main_ch_groups, main_ch2_groups,
                                                              main_ch3_groups)

        num_total_nghs_2, nums_2, nghs_list_2 = get_info_for_a_radius(mol, curr_nx, atom_iter, curr_input=2)
        num_total_nghs_3, nums_3, nghs_list_3 = get_info_for_a_radius(mol, curr_nx, atom_iter, curr_input=3)
        num_total_nghs_4, nums_4, nghs_list_4 = get_info_for_a_radius(mol, curr_nx, atom_iter, curr_input=4)
        num_total_nghs_5, nums_5, nghs_list_5 = get_info_for_a_radius(mol, curr_nx, atom_iter, curr_input=5)

        num_total_nghs_2, nums_2, nghs_list_2, num_total_nghs_3, nums_3, nghs_list_3, num_total_nghs_4, nums_4, nghs_list_4, num_total_nghs_5, nums_5, nghs_list_5 = update_nghs_info(
            num_total_nghs_2, nums_2, nghs_list_2, num_total_nghs_3, nums_3, nghs_list_3, num_total_nghs_4,
            nums_4, nghs_list_4, num_total_nghs_5, nums_5, nghs_list_5)

        num_ch_nghs_r2, num_ch2_nghs_r2, num_ch3_nghs_r2 = get_num_chx_from_nghs_list(nghs_list_2["C"], ch_groups,
                                                                                      ch2_groups, ch3_groups)
        num_ch_nghs_r3, num_ch2_nghs_r3, num_ch3_nghs_r3 = get_num_chx_from_nghs_list(nghs_list_3["C"], ch_groups,
                                                                                      ch2_groups, ch3_groups)
        num_ch_nghs_r4, num_ch2_nghs_r4, num_ch3_nghs_r4 = get_num_chx_from_nghs_list(nghs_list_4["C"], ch_groups,
                                                                                      ch2_groups, ch3_groups)
        num_ch_nghs_r5, num_ch2_nghs_r5, num_ch3_nghs_r5 = get_num_chx_from_nghs_list(nghs_list_5["C"], ch_groups,
                                                                                      ch2_groups, ch3_groups)

        num_ch_nghs_r2, num_ch2_nghs_r2, num_ch3_nghs_r2, num_ch_nghs_r3, num_ch2_nghs_r3, num_ch3_nghs_r3, num_ch_nghs_r4, num_ch2_nghs_r4, num_ch3_nghs_r4, num_ch_nghs_r5, num_ch2_nghs_r5, num_ch3_nghs_r5 = update_chx_nums(
            num_ch_nghs_r2, num_ch2_nghs_r2, num_ch3_nghs_r2, num_ch_nghs_r3, num_ch2_nghs_r3, num_ch3_nghs_r3,
            num_ch_nghs_r4, num_ch2_nghs_r4, num_ch3_nghs_r4, num_ch_nghs_r5, num_ch2_nghs_r5, num_ch3_nghs_r5)

        cs_row = []
        cs_row_header = []
        # filling cs inputs
        cs_row, cs_row_header = add_to_row_info(chx_group_label, "chx_group_label", cs_row, cs_row_header)
        # total num nghs
        cs_row, cs_row_header = add_to_row_info(num_total_nghs_2, "num_total_nghs_2", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_total_nghs_3, "num_total_nghs_3", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_total_nghs_4, "num_total_nghs_4", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_total_nghs_5, "num_total_nghs_5", cs_row, cs_row_header)
        # num chx groups
        cs_row, cs_row_header = add_to_row_info(num_ch_nghs_r2, "num_ch_nghs_r2", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch2_nghs_r2, "num_ch2_nghs_r2", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch3_nghs_r2, "num_ch3_nghs_r2", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch_nghs_r3, "num_ch_nghs_r3", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch2_nghs_r3, "num_ch2_nghs_r3", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch3_nghs_r3, "num_ch3_nghs_r3", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch_nghs_r4, "num_ch_nghs_r4", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch2_nghs_r4, "num_ch2_nghs_r4", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch3_nghs_r4, "num_ch3_nghs_r4", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch_nghs_r5, "num_ch_nghs_r5", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch2_nghs_r5, "num_ch2_nghs_r5", cs_row, cs_row_header)
        cs_row, cs_row_header = add_to_row_info(num_ch3_nghs_r5, "num_ch3_nghs_r5", cs_row, cs_row_header)
        # num and types of different atoms
        for _ in List_of_atoms_to_consider:
            cs_row, cs_row_header = add_to_row_info(nums_2[_], "num_%s_nghs_r2" % _, cs_row, cs_row_header)
        for _ in List_of_atoms_to_consider:
            cs_row, cs_row_header = add_to_row_info(nums_3[_], "num_%s_nghs_r3" % _, cs_row, cs_row_header)
        for _ in List_of_atoms_to_consider:
            cs_row, cs_row_header = add_to_row_info(nums_4[_], "num_%s_nghs_r4" % _, cs_row, cs_row_header)
        for _ in List_of_atoms_to_consider:
            cs_row, cs_row_header = add_to_row_info(nums_5[_], "num_%s_nghs_r5" % _, cs_row, cs_row_header)
        if not table_out_cs_has_header:
            table_out_cs.append(cs_row_header)
            table_out_cs_has_header = True
        table_out_cs.append(cs_row)
        proton_indices.append(atom_iter)

    proton_distances = get_distances_between_protons(curr_nx, proton_indices)
    return table_out_cs, proton_indices, proton_distances
