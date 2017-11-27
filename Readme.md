# Description

`jungrau_utils` collects a set of scripts for operating and doing first analysis of the Jungfrau detectors. This includes:

* a python environment called `jungfrau_client`, for controllig the detector from Alvra and Bernina
* a set of scripts for calibrations (running a pedestal run, converting gain maps, ...)
* some examples (soon)

For more information about the Detector Integration Api please visit:

* https://github.com/datastreaming/detector_integration_api

# Usage

`jungfrau_utils` is provided on the Alvra, Bernina beamlines already in a conda environment. To get into the environment, execute e.g.:

```
source /sf/bernina/jungfrau/bin/jungfrau_env.sh
```


Then, to open an IPython shell already configured for the Jungfrau detector at the beamline:

```
jungfrau_console.sh
```


**Example:** starting a data acquisition with a Jungfrau 1.5M at Bernina
```
In [1]: writer_config = {"output_file": "/sf/bernina/data/raw/p16582/test.h5", "process_uid": 16582, "process_gid": 16582, "dataset_name": "jungfrau/data", "n_messages": 1000}

In [2]: detector_config = {"timing": "trigger", "exptime": 0.0001, "cycles": 1000}

In [3]: backend_config = {"n_frames": 1000, "gain_corrections_filename": "/sf/bernina/data/res/p16582/gains.h5", "gain_corrections_dataset": "gains", "pede_corrections_filename": "/sf/bernina//data/res/p16582/JF_pedestal/pedestal_20171124_1646_res.h5", "pede_corrections_dataset": 
   ...: "gains", "activate_corrections_preview": True}

In [4]:bsread_config = {'output_file': '/sf/bernina/data/raw/p16582/test_bsread.h5', 'process_uid': 16582, 'process_gid': 16582, 'channels': ['SAROP21-CVME-PBPS2:Lnk9Ch7-BG-DATA',
    ...:   'SAROP21-CVME-PBPS2:Lnk9Ch7-BG-DATA-CALIBRATED']}

In [5]: client.reset()

In [6]: client.set_config(writer_config=writer_config, backend_config=backend_config, detector_config=detector_config, bsread_config=bsread_config)

In [7]: client.start()

```

You can load a default list with `ju.load_default_channel_list()`

## Commissioning 2017-11-19

```
backend_config = {"n_frames": 100000, "pede_corrections_filename": "/sf/bernina/data/res/p16582/pedestal_20171119_1027_res.h5", "pede_corrections_dataset": "gains", "gain_corrections_filename": "/sf/bernina/data/res/p16582/gains.h5", "gain_corrections_dataset": "gains", "activate_corrections_preview": True, "pede_mask_dataset": "pixel_mask"}
detector_config = {"exptime": 0.00001, "cycles":20000, "timing": "trigger", "frames": 1} 

client.reset()
writer_config = {'dataset_name': 'jungfrau/data','output_file': '/gpfs/sf-data/bernina/raw/p16582/Bi11_pp_delayXXPP_tests.h5','process_gid': 16582,   'process_uid': 16582, "disable_processing": False};
client.set_config(writer_config=writer_config,backend_config=backend_config, detector_config=detector_config); 
client.start()

client.get_status()

## only if it is {'state': 'ok', 'status': 'IntegrationStatus.DETECTOR_STOPPED'}
client.reset()
```

## Taking a pedestal

```
# This records a pedestal run
jungfrau_run_pedestals --numberFrames 3000 --period 0.05

# This analyses and creates a pedestal correction file, in this case /sf/bernina/data/res/p16582/pedestal_20171124_1646_res.h5
jungfrau_create_pedestals -f /sf/bernina/data/raw/p16582/pedestal_20171124_1646.h5 -v 3 -o /sf/bernina/data/res/p16582/
```

## Correct data on file

One utility `jungfrau_utils` provides is a pede and gain subtraction routine. Eg.:

```
In [2]: import jungfrau_utils as ju
In [3]: f = h5py.File("/gpfs/sf-data/bernina/raw/p16582/AgBeNH_dtz60_run3.h5")
In [4]: fp = h5py.File("/sf/bernina/data/res/p16582/pedestal_20171119_0829_res_merge.h5")
In [5]: fg = h5py.File("/sf/bernina/data/res/p16582/gains.h5")
In [6]: images = f["jungfrau/data"]
In [7]: G = fg["gains"][:]
In [8]: P = fp["gains"][:]
In [9]: corrected_image = ju.apply_gain_pede(images[2], G, P, pixel_mask=fp["pixelMask"][:])

```

## Restart services

There are 4 services running on `sf-daq-1`:
* `detector_integration_api` : controls detector, backend and writer
* `detector_backend`: controls the data acquisition
* `writer`: writes data
* `detector_visualization`: controls the live visualization
* 

These services can be restarted from `sf-daq-1` with the user `dbe` with:
```
sudo systemctl stop <SERVICE_NAME>
sudo systemctl start <SERVICE_NAME>
```
where `<SERVICE_NAME>` is one of the above.



# Installation

The package is provided with a conda recipe, and uploaded on Anaconda Cloud. The easiest way to install is:

```
conda install -c paulscherrerinstitute jungfrau_utils
```

For testing, the git repo can also simply be cloned.
