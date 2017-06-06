#!/usr/bin/env python

# #########################################################################
# Copyright (c) 2015, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2015. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import pdb
import os.path
import h5py
import numpy as np
from glob import glob
from mpi4py import MPI
import time
from segmentation_param import *

__author__ = "Mehdi Tondravi"
__copyright__ = "Copyright (c) 2016, UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['combine_segmented_subvols']


def combine_segmented_subvols():
    """
    Combines many segmented images created for sub-volumes into one big hdf5 for the whole volume with a 
    dataset for each segmented image class/label.
    
    Input: The segmented sub-volume image files -  files location is specified in the seg_user_param.py file.
    
    Output: The whole volume image file - its location is specified in the seg_user_param.py file. 
    """
    start_time = time.time()
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = MPI.COMM_WORLD.Get_size()
    name = MPI.Get_processor_name()
    print("Entered the function and size is %d" % size)
    # Get the list of all segmented image files . Assumes file extension is .h5
    input_files = sorted(glob(outimage_file_location + '/*subvol*.h5'))
    if not input_files:
        print("*** Did not find any file ending with .hdf5 extension  ***", hdf_subvol_files_location)
        return
    # Shape/Dimention of the volume image is available in the last sub-volume file.
    volume_ds_shape = np.zeros((3,), dtype='uint64')
    
    # Last file has the dimensions for the volume.
    f = h5py.File(input_files[-1], 'r')
    volshape = f['orig_indices']
    volume_ds_shape[0] = volshape[1]
    volume_ds_shape[1] = volshape[3]
    volume_ds_shape[2] = volshape[5]
    # Get the list of segmented datasets 
    seg_ds_list = f.keys()
    print("segmentation DS list is seg_ds_list", seg_ds_list)
    seg_ds_list.remove('orig_indices')
    print("segmentation DS list is seg_ds_list", seg_ds_list)
    seg_ds_list.remove('right_overlap')
    print("segmentation DS list is seg_ds_list", seg_ds_list)
    seg_ds_list.remove('left_overlap')
    print("segmentation DS list is seg_ds_list", seg_ds_list)
    f.close()
    
    time2 = time.time()
    # Create an hdf file to contain the whole volume segmented images for all classes
    par, name = os.path.split(outimage_file_location)
    seg_volume_file = (outimage_file_location + '/volume_' + name + '.h5')
    time3 = time.time()
    if rank == 0:
        print("seg_ds_list is ", seg_ds_list)
        print("Number of HDF5 files is %d, and Number of processes is %d" % ((len(input_files)), size))
        print("Segmented Volume file is %s" % seg_volume_file)
        print("Segmented Volume directory is %s" % outimage_file_location)
        print("Volume Shape is", volume_ds_shape[...])
    
    # Create directory for the whole volume probability maps if it does not exists.
    if rank == 0:
        if not os.path.exists(outimage_file_location):
            os.mkdir(outimage_file_location)
            print("File directory for whole segmented volume did not exist, was created")
    
    comm.Barrier()
    
    time4 = time.time()
    
    vol_map_file = h5py.File(seg_volume_file, 'w', driver='mpio', comm=comm)
    if rank == 0:
        print("Created Segmented volume file %s" % seg_volume_file)
    
    iterations = int(len(input_files) / size) + (len(input_files) % size > 0)
    print("iterations is ", iterations)
    # Combine all datasets in the subvolume into the whole volume file.
    for ds in range(len(seg_ds_list)):
        ds_time = time.time()
        vol_seg_dataset = vol_map_file.create_dataset(seg_ds_list[ds], volume_ds_shape, dtype='uint8',
                                                      chunks=(1, il_sub_vol_y, il_sub_vol_z))
        print("Working on subvolume segmented class %s" % seg_ds_list[ds])
        if rank == 0:
            print("Chunked Dataset creation time is %d Sec" % (time.time() - ds_time))
        for idx in range(iterations):
            if (rank + (size * idx)) >= len(input_files):
                print("\nBREAKING out, my rank is %d, number of files is %d, size is %d and idx is %d" %
                      (rank, len(input_files), size, idx))
                break
            subvol_file = h5py.File(input_files[rank + (size * idx)], 'r')
            # Retrieve indices into the whole volume. 
            orig_idx_ds = subvol_file['orig_indices']
            orig_idx = orig_idx_ds[...]
            
            # Retrieve overlap size to the right and left side of the sub-volume.
            right_overlapds = subvol_file['right_overlap']
            rightoverlap = right_overlapds[...]
            left_overlapds = subvol_file['left_overlap']
            leftoverlap = left_overlapds[...]
            
            start_subvol_ds = time.time()
            dataset = subvol_file[seg_ds_list[ds]]
            subvoldata = dataset[...] 
            x_dim = subvoldata.shape[0]
            y_dim = subvoldata.shape[1]
            z_dim = subvoldata.shape[2]
            print("subvol dimension, rightoverlap and leftoverlap are", subvoldata.shape, rightoverlap, leftoverlap)
            print("subvolume dataset Read time is %d Sec, rank is %d" % ((time.time() - start_subvol_ds), rank))
            vol_seg_dataset[orig_idx[0]:orig_idx[1], orig_idx[2]:orig_idx[3], orig_idx[4]:orig_idx[5]] = \
                subvoldata[leftoverlap[0] : x_dim - rightoverlap[0], 
                           leftoverlap[1] : y_dim - rightoverlap[1], 
                           leftoverlap[2] : z_dim - rightoverlap[2]]
            print("Time to read and save subvolume ds is  %d Sec and rank is %d" % ((time.time() - start_subvol_ds), rank))
            subvol_file.close()
        
        comm.Barrier()
        print("Time to combine one dataset to whole volume is %d Sec" % (time.time() - ds_time))
    
    vol_map_file.close()
    end_time = time.time()
    if rank % 1 == 0:
        print(" DONE - Volume dataset shape is", volume_ds_shape)
        print("Exec time for combine_segmented_subvols() is %d Sec and rank is %d" % ((time.time() - start_time), rank))

if __name__ == '__main__':
    combine_segmented_subvols()

