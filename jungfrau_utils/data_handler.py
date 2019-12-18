import re
from collections import namedtuple
from functools import wraps

import h5py
import numpy as np
from numba import jit

from .geometry import modules_orig

try:
    import mkl
except ImportError:
    pass
else:
    mkl.set_num_threads(1)  # pylint: disable=no-member

CHIP_SIZE_X = 256
CHIP_SIZE_Y = 256

CHIP_NUM_X = 4
CHIP_NUM_Y = 2

MODULE_SIZE_X = CHIP_NUM_X * CHIP_SIZE_X
MODULE_SIZE_Y = CHIP_NUM_Y * CHIP_SIZE_Y
MODULE_SIZE = MODULE_SIZE_X * MODULE_SIZE_Y

CHIP_GAP_X = 2
CHIP_GAP_Y = 2

# 256 not divisible by 3, so we round up to 86
# 18 since we have 6 more pixels in H per gap
STRIPSEL_MODULE_SIZE_X = 1024 * 3 + 18  # = 3090
STRIPSEL_MODULE_SIZE_Y = 86


def _allow_2darray(func):
    @wraps(func)
    def wrapper(self, array, *args, **kwargs):
        if array.ndim == 2:
            is_2darray = True
            array = array[np.newaxis]
        else:
            is_2darray = False

        array = func(self, array, *args, **kwargs)

        if is_2darray:
            array = array[0]

        return array

    return wrapper


class JFDataHandler:
    def __init__(self, detector_name):
        """Create an object to perform jungfrau detector data handling like pedestal correction,
        gain conversion, pixel mask, module map, etc.

        Args:
            detector_name (str): name of a detector in the form JF<id>T<nmod>V<version>
        """
        # detector_name needs to be a valid name
        if detector_name in modules_orig:
            self._detector_name = detector_name
        else:
            raise KeyError(f"Geometry for '{detector_name}' detector is not present.")

        self._gain_file = ''
        self._pedestal_file = ''

        self._gain = None
        self._pedestal = None
        self._pixel_mask = None

        self._highgain = False

        # gain and pedestal arrays to be used for the actual data conversion
        self._g_all = {True: None, False: None}
        self._p_all = {True: None, False: None}
        self._proc_func_all = {True: _correct_highgain, False: _correct}

        self._module_map = np.arange(self.detector.n_modules)

        self._mask_all = {True: None, False: None}
        self._mask_double_pixels = False

    @property
    def detector_name(self):
        """Detector name (readonly)"""
        return self._detector_name

    def is_stripsel(self):
        """Return true if detector is a stripsel"""
        return self.detector_name.startswith(("JF05", "JF11"))

    @property
    def detector(self):
        """A namedtuple of detector parameters extracted from its name (readonly)"""
        det = namedtuple('Detector', ['id', 'n_modules', 'version'])
        return det(*(int(d) for d in re.findall(r'\d+', self.detector_name)))

    @property
    def _number_active_modules(self):
        return np.sum(self.module_map != -1)

    @property
    def _shape(self):
        n_modules = self.detector.n_modules
        return MODULE_SIZE_Y * n_modules, MODULE_SIZE_X

    @property
    def _gp_shape(self):
        return (4, *self._shape)

    @property
    def _mm_shape(self):
        n_modules = self._number_active_modules
        return MODULE_SIZE_Y * n_modules, MODULE_SIZE_X

    def _get_stripsel_shape(self, geometry):
        if geometry:
            modules_orig_y, modules_orig_x = modules_orig[self.detector_name]
            shape_x = max(modules_orig_x) + STRIPSEL_MODULE_SIZE_X
            shape_y = max(modules_orig_y) + STRIPSEL_MODULE_SIZE_Y
        else:
            shape_y, shape_x = self._mm_shape

        return shape_y, shape_x

    def get_shape(self, gap_pixels, geometry):
        """Resulting image shape of a detector, based on gap_pixel and geometry flags"""
        if self.is_stripsel():
            return self._get_stripsel_shape(geometry=geometry)

        if geometry and gap_pixels:
            modules_orig_y, modules_orig_x = modules_orig[self.detector_name]
            shape_x = max(modules_orig_x) + MODULE_SIZE_X + (CHIP_NUM_X - 1) * CHIP_GAP_X
            shape_y = max(modules_orig_y) + MODULE_SIZE_Y + (CHIP_NUM_Y - 1) * CHIP_GAP_Y

        elif geometry and not gap_pixels:
            modules_orig_y, modules_orig_x = modules_orig[self.detector_name]
            shape_x = max(modules_orig_x) + MODULE_SIZE_X
            shape_y = max(modules_orig_y) + MODULE_SIZE_Y

        elif not geometry and gap_pixels:
            shape_y, shape_x = self._mm_shape
            shape_x += (CHIP_NUM_X - 1) * CHIP_GAP_X
            shape_y += (CHIP_NUM_Y - 1) * CHIP_GAP_Y * self._number_active_modules

        elif not geometry and not gap_pixels:
            shape_y, shape_x = self._mm_shape

        return shape_y, shape_x

    @property
    def gain_file(self):
        """Return gain filepath"""
        return self._gain_file

    @gain_file.setter
    def gain_file(self, filepath):
        if not filepath:
            self._gain_file = ''
            self.gain = None
            return

        if filepath == self._gain_file:
            return

        with h5py.File(filepath, 'r') as h5f:
            gains = h5f['/gains'][:]

        self._gain_file = filepath
        self.gain = gains

    @property
    def gain(self):
        """Current gain values"""
        return self._gain

    @gain.setter
    def gain(self, value):
        if value is None:
            self._gain = None
            return

        if value.ndim != 3:
            raise ValueError(
                f"Expected gain dimensions 3, provided gain dimensions {value.ndim}."
            )

        if value.shape != self._gp_shape:
            raise ValueError(
                f"Expected gain shape {self._gp_shape}, provided gain shape {value.shape}."
            )

        # convert _gain values to float32
        self._gain = value.astype(np.float32, copy=False)

        _g = 1 / self._gain

        self._g_all[True] = _g[3:]

        _g[3] = _g[2]
        self._g_all[False] = _g

    @property
    def pedestal_file(self):
        """Return pedestal filepath"""
        return self._pedestal_file

    @pedestal_file.setter
    def pedestal_file(self, filepath):
        if not filepath:
            self._pedestal_file = ''
            self.pedestal = None
            self.pixel_mask = None
            return

        if filepath == self._pedestal_file:
            return

        with h5py.File(filepath, 'r') as h5f:
            pedestal = h5f['/gains'][:]
            pixel_mask = h5f['/pixel_mask'][:]

        self._pedestal_file = filepath
        self.pedestal = pedestal
        self.pixel_mask = pixel_mask

    @property
    def pedestal(self):
        """Current pedestal values"""
        return self._pedestal

    @pedestal.setter
    def pedestal(self, value):
        if value is None:
            self._pedestal = None
            return

        if value.ndim != 3:
            raise ValueError(
                f"Expected pedestal dimensions 3, provided pedestal dimensions {value.ndim}."
            )

        if value.shape != self._gp_shape:
            raise ValueError(
                f"Expected pedestal shape {self._gp_shape}, provided pedestal shape {value.shape}."
            )

        # convert _pedestal values to float32
        self._pedestal = value.astype(np.float32, copy=False)

        _p = self._pedestal.copy()

        self._p_all[True] = _p[3:]

        _p[3] = _p[2]
        self._p_all[False] = _p

    @property
    def highgain(self):
        """Current flag for highgain"""
        return self._highgain

    @highgain.setter
    def highgain(self, value):
        if not isinstance(value, bool):
            value = bool(value)

        self._highgain = value

    @property
    def _g(self):
        return self._g_all[self.highgain]

    @property
    def _p(self):
        return self._p_all[self.highgain]

    @property
    def _proc_func(self):
        return self._proc_func_all[self.highgain]

    @property
    def pixel_mask(self):
        """Current pixel mask"""
        return self._pixel_mask

    @pixel_mask.setter
    def pixel_mask(self, value):
        if value is None:
            self._pixel_mask = None
            return

        if value.ndim != 2:
            raise ValueError(
                f"Expected pixel_mask dimensions 2, provided pixel_mask dimensions {value.ndim}."
            )

        if value.shape != self._shape:
            raise ValueError(
                f"Expected pixel_mask shape {self._shape}, provided pixel_mask shape {value.shape}."
            )

        self._pixel_mask = value.astype(np.bool, copy=False)

        self._mask_all[False] = self._pixel_mask

        mask = self._pixel_mask.copy()

        for m in range(self.detector.n_modules):
            module_mask = self._get_module_slice(mask, m)
            for n in range(CHIP_NUM_X):
                module_mask[:, CHIP_SIZE_X * n] = True
                module_mask[:, CHIP_SIZE_X * (n + 1) - 1] = True

            for n in range(CHIP_NUM_Y):
                module_mask[CHIP_SIZE_Y * n, :] = True
                module_mask[CHIP_SIZE_Y * (n + 1) - 1, :] = True

        self._mask_all[True] = mask

    def get_pixel_mask(self, gap_pixels, geometry):
        """Return pixel mask, shaped according to gap_pixel and geometry flags"""
        if self.pixel_mask is None:
            return None

        res = np.empty(self._mm_shape, dtype=self.pixel_mask.dtype)
        for i, m in enumerate(self.module_map):
            if m == -1:
                continue

            module = self._get_module_slice(self.pixel_mask, i)
            res[m * MODULE_SIZE_Y : (m + 1) * MODULE_SIZE_Y, :] = module

        res = np.invert(
            self.process(np.invert(res), conversion=False, gap_pixels=gap_pixels, geometry=geometry)
        )

        return res

    @property
    def mask_double_pixels(self):
        """Current flag for masking double pixels"""
        return self._mask_double_pixels

    @mask_double_pixels.setter
    def mask_double_pixels(self, value):
        if not isinstance(value, bool):
            value = bool(value)

        self._mask_double_pixels = value

    @property
    def _mask(self):
        return self._mask_all[self.mask_double_pixels]

    @property
    def module_map(self):
        """Current module map"""
        return self._module_map

    @module_map.setter
    def module_map(self, value):
        n_modules = self.detector.n_modules
        if value is None:
            # support legacy data by emulating 'all modules are present'
            self._module_map = np.arange(n_modules)
            return

        if len(value) != n_modules:
            raise ValueError(
                f"Expected module_map length {n_modules}, provided module_map length {len(value)}."
            )

        if min(value) < -1 or n_modules <= max(value):
            raise ValueError(
                f"Valid module_map values are integers between -1 and {n_modules-1}."
            )

        self._module_map = value

    @_allow_2darray
    def process(self, images, conversion=True, gap_pixels=True, geometry=True):
        """Perform jungfrau detector data processing like pedestal correction, gain conversion,
        applying pixel mask, module map, etc.

        Args:
            images (ndarray): image stack or single image to be processed
            conversion (bool, optional): convert to keV (apply gain and pedestal corrections).
                Defaults to True.
            gap_pixels (bool, optional): add gap pixels between detector submodules.
                Defaults to True.
            geometry (bool, optional): apply detector geometry corrections. Defaults to True.

        Returns:
            ndarray: resulting image stack or single image
        """
        image_shape = images.shape[-2:]
        if image_shape != self._mm_shape:
            raise ValueError(
                f"Expected image shape {self._mm_shape}, provided image shape {image_shape}."
            )

        if not (conversion or gap_pixels or geometry):
            # no need to continue, return unchanged images
            return images

        if conversion and not self.can_convert():
            raise RuntimeError("Gain and/or pedestal values are not set.")

        res_dtype = np.float32 if conversion else images.dtype
        res_shape = self.get_shape(gap_pixels=gap_pixels, geometry=geometry)
        res = np.zeros((images.shape[0], *res_shape), dtype=res_dtype)

        self._process(res, images, conversion, gap_pixels, geometry)

        # rotate image stack in case of alvra JF06 detector
        if geometry and self.detector_name.startswith('JF06'):
            res = np.rot90(res, axes=(1, 2)).copy()

        return res

    def can_convert(self):
        """Whether all data for gain/pedestal conversion is present"""
        return (self.gain is not None) and (self.pedestal is not None)

    def _process(self, res, image_stack, conversion, gap_pixels, geometry):
        for i, m in enumerate(self.module_map):
            if m == -1:
                continue

            if geometry:
                oy = modules_orig[self.detector_name][0][i]
                ox = modules_orig[self.detector_name][1][i]
            elif gap_pixels:
                oy = m * (MODULE_SIZE_Y + CHIP_GAP_Y)
                ox = 0
            else:
                oy = m * MODULE_SIZE_Y
                ox = 0

            module = self._get_module_slice(image_stack, m, geometry)

            if conversion:
                module_g = self._get_module_slice(self._g, i, geometry)
                module_p = self._get_module_slice(self._p, i, geometry)
                if self._mask is None:
                    module_mask = None
                else:
                    module_mask = self._get_module_slice(self._mask, i, geometry)

            if self.is_stripsel():
                if conversion:
                    module_res = np.empty(shape=module.shape, dtype=np.float32)
                    self._proc_func(module_res, module, module_g, module_p, module_mask)
                    module = module_res

                if geometry:
                    for ind in range(module.shape[0]):
                        module_res = res[
                            ind, oy : oy + STRIPSEL_MODULE_SIZE_Y, ox : ox + STRIPSEL_MODULE_SIZE_X
                        ]
                        reshape_stripsel(module_res, module[ind])
                else:
                    # gap_pixels has no effect on stripsel detectors
                    res[:, oy : oy + MODULE_SIZE_Y, ox : ox + MODULE_SIZE_X] = module
                return

            if gap_pixels:
                for j in range(CHIP_NUM_Y):
                    for k in range(CHIP_NUM_X):
                        # reading positions
                        ry_s = j * CHIP_SIZE_Y
                        rx_s = k * CHIP_SIZE_X

                        # writing positions
                        wy_s = oy + ry_s + j * CHIP_GAP_Y
                        wx_s = ox + rx_s + k * CHIP_GAP_X

                        sread = (slice(ry_s, ry_s + CHIP_SIZE_Y), slice(rx_s, rx_s + CHIP_SIZE_X))
                        swrite = (slice(wy_s, wy_s + CHIP_SIZE_Y), slice(wx_s, wx_s + CHIP_SIZE_X))

                        submod = module[(slice(None), *sread)]
                        submod_res = res[(slice(None), *swrite)]

                        if conversion:
                            submod_g = module_g[(slice(None), *sread)]
                            submod_p = module_p[(slice(None), *sread)]
                            submod_mask = module_mask[sread]
                            self._proc_func(submod_res, submod, submod_g, submod_p, submod_mask)
                        else:
                            submod_res[:] = submod

            else:
                module_res = res[:, oy : oy + MODULE_SIZE_Y, ox : ox + MODULE_SIZE_X]
                if conversion:
                    self._proc_func(module_res, module, module_g, module_p, module_mask)
                else:
                    module_res[:] = module

    @_allow_2darray
    def _get_module_slice(self, data, m, geometry=False):
        if self.detector_name == 'JF02T09V01':
            out = data[:, :, m * MODULE_SIZE_X : (m + 1) * MODULE_SIZE_X]
        else:
            out = data[:, m * MODULE_SIZE_Y : (m + 1) * MODULE_SIZE_Y, :]

        if geometry and self.detector_name in ('JF02T09V02', 'JF02T01V02'):
            out = np.rot90(out, 2, axes=(1, 2))

        return out

    def get_gains(self, images, gap_pixels, geometry):
        """Return gain values of images, shaped according to gap_pixel and geometry flags.
        """
        if images.dtype != np.uint16:
            raise TypeError(
                f"Expected image type {np.uint16}, provided data type {images.dtype}."
            )

        gains = images >> 14
        gains = self.process(gains, conversion=False, gap_pixels=gap_pixels, geometry=geometry)

        return gains

    def get_saturated_pixels(self, images, gap_pixels, geometry):
        """Return a boolean array of saturated pixels, shaped according to gap_pixel and geometry
        flags.
        """
        if images.dtype != np.uint16:
            raise TypeError(
                f"Expected image type {np.uint16}, provided data type {images.dtype}."
            )

        saturated_pixels = images == self.get_saturated_value()
        saturated_pixels = self.process(
            saturated_pixels, conversion=False, gap_pixels=gap_pixels, geometry=geometry
        )

        return saturated_pixels

    def get_saturated_value(self):
        """Get a value for saturated pixels.
        """
        if self.highgain:
            saturated_value = 0b0011111111111111  # = 16383
        else:
            saturated_value = 0b1100000000000000  # = 49152

        return saturated_value


@jit(nopython=True, cache=True)
def _correct(res, image, gain, pedestal, mask):
    num, size_y, size_x = image.shape
    for i1 in range(num):
        for i2 in range(size_y):
            for i3 in range(size_x):
                if mask is not None and mask[i2, i3]:
                    res[i1, i2, i3] = 0
                else:
                    gm = image[i1, i2, i3] >> 14
                    val = image[i1, i2, i3] & 0x3FFF
                    res[i1, i2, i3] = (val - pedestal[gm, i2, i3]) * gain[gm, i2, i3]


@jit(nopython=True, cache=True)
def _correct_highgain(res, image, gain, pedestal, mask):
    num, size_y, size_x = image.shape
    for i1 in range(num):
        for i2 in range(size_y):
            for i3 in range(size_x):
                if mask is not None and mask[i2, i3]:
                    res[i1, i2, i3] = 0
                else:
                    val = image[i1, i2, i3] & 0x3FFF
                    res[i1, i2, i3] = (val - pedestal[0, i2, i3]) * gain[0, i2, i3]


@jit(nopython=True, cache=True)
def reshape_stripsel(res, image):
    # first we fill the normal pixels, the gap ones will be overwritten later
    for yin in range(256):
        for xin in range(1024):
            ichip = xin // 256
            xout = (ichip * 774) + (xin % 256) * 3 + yin % 3
            # 774 is the chip period, 256*3+6
            yout = yin // 3
            res[yout, xout] = image[yin, xin]

    # now the gap pixels
    for igap in range(3):
        for yin in range(256):
            yout = (yin // 6) * 2

            # first the left side of gap
            xin = igap * 64 + 63
            xout = igap * 774 + 765 + yin % 6
            res[yout, xout] = image[yin, xin]
            res[yout + 1, xout] = image[yin, xin]

            # then the right side is mirrored
            xin = igap * 64 + 63 + 1
            xout = igap * 774 + 765 + 11 - yin % 6
            res[yout, xout] = image[yin, xin]
            res[yout + 1, xout] = image[yin, xin]
            # if we want a proper normalization (the area of those pixels is double, so they see 2x
            # the signal)
            # res[yout, xout] = res[yout, xout] / 2

    return res
