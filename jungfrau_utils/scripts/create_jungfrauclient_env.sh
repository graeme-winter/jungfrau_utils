#!/bin/bash

if [ $# != 1  ]; then
    echo "Usage: $0 [alvra|bernina]"
    exit 1
fi
    
dest=$1

echo "Loading psi-python34"
module load psi-python34

echo "Creating jungfrau_client Conda env"
conda create -c paulscherrerinstitute -p /sf/${dest}/jungfrau/envs/jungfrau_client detector_integration_api ipython setuptools h5py numpy dask matplotlib
