from __future__ import division, absolute_import, print_function

import os
from functools import partial
from itertools import combinations

import numpy as np
import multiprocessing as mp
from tqdm import tqdm

from .fw2_5d import dcfw2_5D
from .fw2_5d import get_2_5Dpara
from .rand_synth_model import get_rand_model
from ..utils.io_utils import read_pkl, read_urf, read_config_file, write_pkl


def prepare_for_get_2_5d_para(config_file, return_urf=False):
    config = read_config_file(config_file)

    urf = config['geometry_urf']
    Tx_id, Rx_id, RxP2_id, coord, data = read_urf(urf)
    # Collect pairs id
    if np.all(np.isnan(data)):
        C_pair = [set(i) for i in combinations(Tx_id.flatten().tolist(), 2)]
        P_pair = [set(i) for i in combinations(Rx_id.flatten().tolist(), 2)]
        CP_pair = []
        for i in range(len(C_pair)):
            for j in range(len(P_pair)):
                if C_pair[i].isdisjoint(P_pair[j]):
                    CP_pair.append(sorted(C_pair[i]) + sorted(P_pair[j]))  # use sorted to convert set to list
        CP_pair = np.array(CP_pair, dtype=np.int64)
    else:
        CP_pair = data[:, :4].astype(np.int64)

    # Convert id to coordinate
    recloc = np.hstack((coord[CP_pair[:, 2] - 1, 1:4:2],
                        coord[CP_pair[:, 3] - 1, 1:4:2]))
    recloc[:, 1:4:2] = np.abs(recloc[:, 1:4:2])  # In urf, z is positive up. In fw25d, z is positive down.
    SRCLOC = np.hstack((coord[CP_pair[:, 0] - 1, 1:4:2],
                        coord[CP_pair[:, 1] - 1, 1:4:2]))
    SRCLOC[:, 1:4:2] = np.abs(SRCLOC[:, 1:4:2])  # In urf, z is positive up. In fw25d, z is positive down.

    # Collect pairs that fit the array configuration
    if config['array_type'] != 'all_combination':
        # Check if the electrode is on the ground
        at_ground = np.logical_and(np.logical_and(SRCLOC[:, 1] == 0, SRCLOC[:, 3] == 0),
                                   np.logical_and(recloc[:, 1] == 0, recloc[:, 3] == 0))
        SRCLOC = SRCLOC[at_ground, :]
        recloc = recloc[at_ground, :]
        AM = recloc[:, 0] - SRCLOC[:, 0]
        MN = recloc[:, 2] - recloc[:, 0]
        NB = SRCLOC[:, 2] - recloc[:, 2]
        # Check that the electrode arrangement is correct
        positive_idx = np.logical_and(np.logical_and(AM > 0, MN > 0), NB > 0)
        SRCLOC = SRCLOC[positive_idx, :]
        recloc = recloc[positive_idx, :]
        AM = AM[positive_idx]
        MN = MN[positive_idx]
        NB = NB[positive_idx]
        if config['array_type'] == 'Wenner_Schlumberger':
            # Must be an integer multiple?
            row_idx = np.logical_and(AM == NB, AM % MN == 0)
            SRCLOC = SRCLOC[row_idx, :]
            recloc = recloc[row_idx, :]
        elif config['array_type'] == 'Wenner':
            row_idx = np.logical_and(AM == MN, MN == NB)
            SRCLOC = SRCLOC[row_idx, :]
            recloc = recloc[row_idx, :]
        elif config['array_type'] == 'Wenner_Schlumberger_NonInt':
            row_idx = np.logical_and(AM == NB, AM >= MN)
            SRCLOC = SRCLOC[row_idx, :]
            recloc = recloc[row_idx, :]

    srcloc, srcnum = np.unique(SRCLOC, return_inverse=True, axis=0)
    srcnum = np.reshape(srcnum, (-1, 1))  # matlab index starts from 1, python index starts from 0

    array_len = max(coord[:, 1]) - min(coord[:, 1])
    srcloc[:, [0, 2]] = srcloc[:, [0, 2]] - array_len / 2
    recloc[:, [0, 2]] = recloc[:, [0, 2]] - array_len / 2
    dx = np.ones((config['nx'], 1))
    dz = np.ones((config['nz'], 1))

    if return_urf:
        return [[srcloc, dx, dz, recloc, srcnum],
                [Tx_id, Rx_id, RxP2_id, coord, data]]
    else:
        return srcloc, dx, dz, recloc, srcnum


def get_forward_para(config_file):
    config = read_config_file(config_file)
    srcloc, dx, dz, recloc, srcnum = prepare_for_get_2_5d_para(config)
    para_pkl = config['Para_pkl']
    num_k_g = config['num_k_g']

    if not os.path.isfile(para_pkl):
        print('Create Para for FW2_5D.')
        s = np.ones((config['nx'], config['nz']))
        Para = get_2_5Dpara(srcloc, dx, dz, s, num_k_g, recloc, srcnum)
        write_pkl(Para, para_pkl)
        config['Para'] = Para
    else:
        print('Load Para pickle file')
        Para = read_pkl(para_pkl)
        # Check if Para is in accordance with current configuration
        if 'Q' not in Para:
            print('No Q matrix in `Para` dictionary, creating a new one.')
            s = np.ones((config['nx'], config['nz']))
            Para = get_2_5Dpara(srcloc, dx, dz, s, num_k_g, recloc, srcnum)
            write_pkl(Para, para_pkl)
            config['Para'] = Para
        elif Para['Q'].shape[0] != srcnum.shape[0] \
                or Para['Q'].shape[1] != dx.size * dz.size \
                or Para['b'].shape[1] != srcloc.shape[0]:
            print('Size of Q matrix is wrong, creating a new one.')
            s = np.ones((config['nx'], config['nz']))
            Para = get_2_5Dpara(srcloc, dx, dz, s, num_k_g, recloc, srcnum)
            write_pkl(Para, para_pkl)
            config['Para'] = Para
        else:
            config['Para'] = Para

    config['srcloc'] = srcloc
    config['dx'] = dx
    config['dz'] = dz
    config['recloc'] = recloc
    config['srcnum'] = srcnum

    return config


def forward_simulation(sigma, config_file):

    config = read_config_file(config_file)
    if 'Para' not in config:
        config = get_forward_para(config)
    Para = config['Para']
    dx = config['dx']
    dz = config['dz']

    # Inputs: delta V/I (potential)
    sigma_size = (dx.size, dz.size)
    s = np.reshape(sigma, sigma_size)
    dobs, _ = dcfw2_5D(s, Para)

    return dobs.flatten()


def next_path(path_pattern, only_num=False):
    """
    Finds the next free path in an sequentially named list of files

    e.g. path_pattern = 'file-%s.txt':

    file-1.txt
    file-2.txt
    file-3.txt

    Runs in log(n) time where n is the number of existing files in sequence

    Source
    ------
    https://stackoverflow.com/questions/17984809/how-do-i-create-a-incrementing-filename-in-python
    """
    i = 1

    # First do an exponential search
    while os.path.exists(path_pattern % i):
        i = i * 2

    # Result lies somewhere in the interval (i/2..i]
    # We call this interval (a..b] and narrow it down until a + 1 = b
    a, b = (i // 2, i)
    while a + 1 < b:
        c = (a + b) // 2  # interval midpoint
        a, b = (c, b) if os.path.exists(path_pattern % c) else (a, c)

    if only_num:
        return b
    else:
        return path_pattern % b


def make_dataset(config_file):
    config = read_config_file(config_file)
    train_dir = os.path.join(config['dataset_dir'], 'train')
    valid_dir = os.path.join(config['dataset_dir'], 'valid')
    test_dir = os.path.join(config['dataset_dir'], 'test')
    num_samples_train = int(config['num_samples'] * config['train_ratio'])
    num_samples_valid = int(config['num_samples']
                            * (config['train_ratio'] + config['valid_ratio'])
                            - num_samples_train)
    num_samples_test = config['num_samples'] - num_samples_train - num_samples_valid

    config = get_forward_para(config)
    for dir_name, num_samples in ((train_dir, num_samples_train),
                                  (valid_dir, num_samples_valid),
                                  (test_dir, num_samples_test)):
        if num_samples == 0:
            pass
        else:
            os.makedirs(dir_name, exist_ok=True)
            suffix_num = next_path(os.path.join(dir_name, 'raw_data_%s.pkl'), only_num=True)

            par = partial(_make_dataset, config=config, dir_name=dir_name)
            sigma_generator = get_rand_model(config, num_samples=num_samples)
            suffix_generator = range(suffix_num, suffix_num + num_samples)
            pool = mp.Pool(processes=mp.cpu_count(), maxtasksperchild=1)
            for _ in tqdm(pool.imap_unordered(par, zip(sigma_generator, suffix_generator)),
                          total=num_samples, desc=os.path.basename(dir_name)):
                pass
            pool.close()
            pool.join()

            # Serial version
            # suffix_num = next_path(os.path.join(dir_name, 'raw_data_%s.pkl'), only_num=True)
            # for sigma in tqdm(get_rand_model(config, num_samples=num_samples),
            #                   total=num_samples, desc=os.path.basename(dir_name)):
            #     dobs = forward_simulation(sigma, config)
            #     # pickle dump/load is faster than numpy savez_compressed(or save)/load
            #     pkl_name = os.path.join(dir_name, f'raw_data_{suffix_num}.pkl')
            #     write_pkl({'inputs': dobs, 'targets': 1 / sigma}, pkl_name)
            #     suffix_num += 1


def _make_dataset(zip_item, config, dir_name):
    sigma, suffix_num = zip_item
    dobs = forward_simulation(sigma, config)
    # pickle dump/load is faster than numpy savez_compressed(or save)/load
    pkl_name = os.path.join(dir_name, f'raw_data_{suffix_num}.pkl')
    write_pkl({'inputs': dobs, 'targets': 1 / sigma}, pkl_name)
