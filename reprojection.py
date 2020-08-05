import rasterio
from rasterio.plot import show, reshape_as_raster, reshape_as_image, adjust_band
from rasterio import warp
import numpy as np

def reprojectio(img, bounds, transform, projection = "epsg:4326", resolution = 0.00001):
    # Reproject
    transform, width, height = warp.calculate_default_transform( \
        aRaster.crs, {"init" : projection},
        img.shape[0], img.shape[1],
        left = bounds[0], bottom = bounds[1],
        right = bounds[2], top = bounds[3],
        resolution = resolution)
    out_array = np.ndarray((img.shape[0], height, width), dtype = img.dtype)

    warp.reproject(img, out_array, src_crs = aRaster.crs, dst_crs = {"init" : "epsg:4326"},
        src_transform = transform,
        dst_transform = transform, resampling = warp.Resampling.bilinear)

    return out_array

