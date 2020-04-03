import h5py
import numpy as np
import pytest

from jungfrau_utils import File

DETECTOR_NAME = "JF01T03V01"
DATA_SHAPE = (3 * 512, 1024)
STACK_SHAPE = (10, *DATA_SHAPE)

DATA_SHAPE_WITH_GAPS = (3 * (512 + 2), 1024 + 6)
DATA_SHAPE_WITH_GEOMETRY = (1040 + 512, 0 + 1024)
DATA_SHAPE_WITH_GAPS_WITH_GEOMETRY = (1040 + 512 + 2, 0 + 1024 + 6)

IMAGE_SHAPE = DATA_SHAPE_WITH_GAPS_WITH_GEOMETRY
STACK_IMAGE_SHAPE = (3, *DATA_SHAPE_WITH_GAPS_WITH_GEOMETRY)


@pytest.fixture(name="gain_file", scope="module")
def _gain_file(tmpdir_factory):
    gain_file = tmpdir_factory.mktemp("data").join("gains.h5")

    with h5py.File(gain_file, "w") as h5f:
        h5f["/gains"] = 10 * np.ones((4, *DATA_SHAPE)).astype(np.float32)

    return gain_file


@pytest.fixture(name="pedestal_file", scope="module")
def _pedestal_file(tmpdir_factory):
    pedestal_file = tmpdir_factory.mktemp("data").join("pedestal.h5")

    with h5py.File(pedestal_file, "w") as h5f:
        h5f["/gains"] = np.ones((4, *DATA_SHAPE)).astype(np.float32)
        h5f["/pixel_mask"] = np.random.randint(2, size=DATA_SHAPE, dtype=np.uint32)

    return pedestal_file


@pytest.fixture(name="jungfrau_file", scope="module")
def _jungfrau_file(tmpdir_factory):
    jungfrau_file = tmpdir_factory.mktemp("data").join("test_jf.h5")

    with h5py.File(jungfrau_file, "w") as h5f:
        h5f["/general/detector_name"] = bytes(DETECTOR_NAME, encoding='utf-8')

        h5f[f"/data/{DETECTOR_NAME}/daq_rec"] = 3840 * np.ones((STACK_SHAPE[0], 1)).astype(np.int64)

        jf_data = np.arange(np.prod(STACK_SHAPE), dtype=np.uint16).reshape(STACK_SHAPE[::-1])
        jf_data = np.ascontiguousarray(jf_data.transpose(2, 1, 0))
        h5f[f"/data/{DETECTOR_NAME}/data"] = jf_data

    return jungfrau_file


@pytest.fixture(name="file_adapter", scope="module")
def _file_adapter(jungfrau_file, gain_file, pedestal_file):
    file_adapter = File(jungfrau_file, gain_file=gain_file, pedestal_file=pedestal_file)

    yield file_adapter


def test_file_adapter(file_adapter, gain_file, pedestal_file):
    assert file_adapter.gain_file == gain_file
    assert file_adapter.pedestal_file == pedestal_file


def test_file_get_index_image(file_adapter):
    res = file_adapter[0]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == IMAGE_SHAPE

    res = file_adapter[0, :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == IMAGE_SHAPE

    res = file_adapter[0, :, :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == IMAGE_SHAPE


def test_file_get_slice_image(file_adapter):
    res = file_adapter[:3]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE

    res = file_adapter[:3, :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE

    res = file_adapter[:3, :, :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE


def test_file_get_fancy_index_list_image(file_adapter):
    res = file_adapter[[0, 2, 4]]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE

    res = file_adapter[[0, 2, 4], :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE

    res = file_adapter[[0, 2, 4], :, :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE


def test_file_get_fancy_index_tuple_image(file_adapter):
    # this is a special case, but has the same behaviour as h5py
    res = file_adapter[(0, 2, 4)]
    assert res.dtype == np.dtype(np.float32)
    assert res.shape == ()

    res = file_adapter[(0, 2, 4), :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE

    res = file_adapter[(0, 2, 4), :, :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE


def test_file_get_fancy_index_range_image(file_adapter):
    res = file_adapter[range(0, 5, 2)]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE

    res = file_adapter[range(0, 5, 2), :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE

    res = file_adapter[range(0, 5, 2), :, :]

    assert res.dtype == np.dtype(np.float32)
    assert res.shape == STACK_IMAGE_SHAPE