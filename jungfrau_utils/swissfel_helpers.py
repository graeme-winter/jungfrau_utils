from datetime import timedelta
from pathlib import Path

import h5py


def locate_gain_file(file_path, verbose=True):
    """Locate gain file in default location at swissfel.

    The default gain file location is
    '/sf/<beamline>/config/jungfrau/gainMaps/<detector>/gains.h5'.

    Args:
        file_path (str or Path): File path of a jungfrau data file.
        verbose (bool, optional): Print info about located gain file.

    Returns:
        str: A path to the located gain file.
    """
    file_path = Path(file_path)
    if file_path.parts[1] != "sf":
        raise Exception(f"Gain file needs to be specified explicitly.")

    detector_name = _read_detector_name(file_path)

    gain_path = Path(*file_path.parts[:3]).joinpath("config", "jungfrau", "gainMaps")
    gain_file = gain_path.joinpath(detector_name, "gains.h5")

    if not gain_file.is_file():
        raise Exception(f"No gain file in default location: {gain_path}")

    if verbose:
        print(f"Auto-located gain file: {gain_file}")

    return gain_file.as_posix()


def locate_pedestal_file(file_path, verbose=True):
    """Locate pedestal file in default location at swissfel.

    The default processed pedestal files path for a particula p-group is
    '/sf/<beamline>/data/<p-group>/res/JF_pedestals/'.

    Args:
        file_path (str or Path): File path of a jungfrau data file.
        verbose (bool, optional): Print info about located pedestal file.

    Returns:
        str: A path to the located pedestal file.
    """
    file_path = Path(file_path)
    if file_path.parts[1] != "sf":
        raise Exception(f"Pedestal file needs to be specified explicitly.")

    detector_name = _read_detector_name(file_path)

    pedestal_path = Path(*file_path.parts[:5]).joinpath("res", "JF_pedestals")

    # find a pedestal file, which was created closest in time to the jungfrau file
    jf_file_mtime = file_path.stat().st_mtime
    closest_pedestal_file = ""
    min_mtime_diff = float("inf")
    for entry in pedestal_path.iterdir():
        if entry.is_file() and detector_name in entry.name:
            time_diff = jf_file_mtime - entry.stat().st_mtime
            if abs(time_diff) < abs(min_mtime_diff):
                min_mtime_diff = time_diff
                closest_pedestal_file = entry

    if not closest_pedestal_file:
        raise Exception(f"No pedestal file in default location: {pedestal_path}")

    if verbose:
        print(f"Auto-located pedestal file: {closest_pedestal_file}")

        mtime_diff = min_mtime_diff
        if mtime_diff < 0:
            # timedelta doesn't work nicely with negative values
            # https://docs.python.org/3/library/datetime.html#datetime.timedelta.resolution
            tdelta_str = "-" + str(timedelta(seconds=-mtime_diff))
        else:
            tdelta_str = str(timedelta(seconds=mtime_diff))
        print("    mtime difference: " + tdelta_str)

    return closest_pedestal_file.as_posix()


def _read_detector_name(file_path):
    with h5py.File(file_path, "r") as h5f:
        detector_name = h5f["/general/detector_name"][()].decode()

    return detector_name
