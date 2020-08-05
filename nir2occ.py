import rasterio
from rasterio import warp
from rasterio.mask import mask
from rasterio.plot import show, reshape_as_raster, reshape_as_image, adjust_band
from shapely.geometry import box
from fiona.crs import from_epsg
import geopandas as gpd
import numpy as np
import cv2 as cv
import pycrs
from optparse import OptionParser
import matplotlib.pyplot as plt
import uuid
import os

'''
    Overview:
        raster(R, G, B, NIR, null) ---->  | naip2map | ----> raster(R, G, B, NIR, Binary Occupancy)
'''

def window_from_extent(xmin, xmax, ymin, ymax, aff):
    # Source: Loic Dutrieux
    # https://gis.stackexchange.com/a/244727
    col_start, row_start = ~aff * (xmin, ymax)
    col_stop, row_stop = ~aff * (xmax, ymin)
    return ((int(row_start), int(row_stop)), (int(col_start), int(col_stop)))

# Options
parser = OptionParser()
parser.add_option("-i", "--in_file",
                  help = "File with raster of bands (red, green, blue, NIR, null)",
                  default = "in/naip18-nc-cir-60cm_2797141_20181210.jp2")
parser.add_option("-o", "--out_file",
                  help = "File to store output raster (fifth band changed to occupancy grid)",
                  default = "out/naip18-nc-cir-60cm_2797141_20181210_occ.jp2")
parser.add_option("-p", "--out_file_plot",
                  help = "File to store output occupancy grid plot",
                  default = "out/naip18-nc-cir-60cm_2797141_20181210_occ.png")
parser.add_option("-b", "--bounds",
                  help = "Comma-separated coordinates to crop raster. Ex: 'ymin,xmin,ymax,xmax'",
                  default = "27.849235,-97.361426,27.875268,-97.325000")
parser.add_option("-n", "--band",
                  help = "Index of raster band with NIR data", type = "int",
                  default = 4)
parser.add_option("-s", "--start_coords",
                  help = "Comma-separated pair of lat,lon coords to determine accessable map area. Ex: '27.870539,-97.334531'",
                  default = None)

(options, args) = parser.parse_args()
inFile = options.in_file
outFile = options.out_file
outFilePlotOcc = options.out_file_plot
bounds = startCoords = None
nirBand = options.band
if options.bounds is not None:
    bounds = [float(b) for b in options.bounds.split(",")]
if options.start_coords is not None:
    startCoords = [float(s) for s in options.start_coords.split(",")]
    start_latlon = { "lat" : startCoords[0], "lon": startCoords[1] }

# Open NAIP raster
aRaster = rasterio.open(inFile, driver = "JP2OpenJPEG")

# Crop raster
bbox = box(bounds[1] + 0.5, bounds[0] + 0.5, bounds[3] - 0.5, bounds[2] - 0.5)
geo = gpd.GeoDataFrame({'geometry': bbox}, index=[0], crs=from_epsg(4326))
geo = geo.to_crs(crs=aRaster.crs.data)

def getFeatures(gdf):
    import json
    return [json.loads(gdf.to_json())['features'][0]['geometry']]

coords = getFeatures(geo)
out_img, out_transform = mask(aRaster, shapes = coords, crop = True, nodata = 255)
out_meta = aRaster.meta.copy()
epsg_code = int(aRaster.crs.data['init'][5:])

out_meta.update({"driver": "JP2OpenJPEG",
                 "height": out_img.shape[1],
                 "width": out_img.shape[2],
                 "transform": out_transform,
                 "crs": aRaster.crs})

tempFile = str(uuid.uuid4()) + ".jp2"
with rasterio.open(tempFile, "w", **out_meta) as dest:
    dest.write(out_img)
aRaster.close()

aRaster = rasterio.open(tempFile)
aRows, aCols = aRaster.shape

# Raster information
print("Number of bands: {n}".format(n = aRaster.count))
print("Image size: {r} rows x {c} columns".format(r = aRows, c = aCols))
print("Raster description: {desc}".format(desc = aRaster.descriptions))
print("Image projection: {proj}".format(proj = aRaster.crs))
print("Image geo-transform: {gt}".format(gt = aRaster.transform))
print("Image extent: {bounds}".format(bounds = aRaster.bounds))

# Open image
img = aRaster.read().astype(np.uint8)

# Select NIR band
nir = img[nirBand - 1, :, :]
nirRows, nirCols = nir.shape

# Filter
nir[nir > 70] = 255
nir[nir < 50] = 0

# Dilation
kernel = np.ones((5, 5), np.uint8)
dilation = cv.dilate(nir, kernel, iterations = 1)

# Final map
aMap = dilation.copy()

if startCoords is None:
    # Make new raster
    with rasterio.open(outFile, 'w', **aRaster.meta) as dst:
        # Copy existing bands
        for ID, b in enumerate([x + 1 for x in list(range(aRaster.count))], 1):
            dst.write(aRaster.read(b), ID)
            dst.set_band_description(ID, aRaster.descriptions[ID - 1])

        # Add occupancy grid band
        dst.write(aMap, aRaster.count)
        dst.set_band_description(5, 'Occupancy')

    # Save plot of occupancy grid
    if outFilePlotOcc is not None:
        fig, ax = plt.subplots(1, 1)
        ax.imshow(aMap, cmap = 'Blues_r', alpha = 0.5)
        plt.title("Occupancy Grid")
        plt.tight_layout()
        fig.savefig(outFilePlotOcc)
        plt.close()

    os.remove(tempFile)
    exit(0)

#################################################
# Limit to region accessible from a start point #
#################################################

# Convert coordinates
start_local = warp.transform({'init' : 'epsg:4326'}, aRaster.crs, [start_latlon["lon"]], [start_latlon["lat"]])
py, px = aRaster.index(start_local[0], start_local[1])

# Determine accessible region via flood fill
filled = aMap.copy()
regionMask = np.zeros((nirRows + 2, nirCols + 2), np.uint8)
cv.floodFill(filled, regionMask, (px[0], py[0]), 200, loDiff = (50, 50, 50, 50), upDiff = (50, 50, 50, 50))
regionMask = regionMask[1:1+nirRows, 1:1+nirCols]

# Convert all inaccessible areas to land
regionMaskRev = regionMask.copy()
regionMaskRev[regionMaskRev > 0] = 100
regionMaskRev[regionMaskRev == 0] = 255
regionMaskRev[regionMaskRev != 255] = aMap[regionMaskRev != 255]

# Make new raster
with rasterio.open(outFile, 'w', **aRaster.meta) as dst:
    # Copy existing bands
    for ID, b in enumerate([x + 1 for x in list(range(aRaster.count))], 1):
        dst.write(aRaster.read(b), ID)
        dst.set_band_description(ID, aRaster.descriptions[ID - 1])

    # Add occupancy grid band
    dst.write(regionMaskRev, aRaster.count)
    dst.set_band_description(5, 'Occupancy')

# Save plot
if outFilePlotOcc is not None:
    fig, axs = plt.subplots(1, 2)
    axs[0].imshow(aMap, cmap = 'Blues_r', alpha = 0.5)
    axs[0].set_title("Occupancy grid")
    axs[1].imshow(regionMaskRev, cmap = 'Blues_r', alpha = 0.5)
    axs[1].scatter(px, py, s = 5, c = 'red', marker = 'x')
    axs[1].set_title("Accessible grid")
    plt.tight_layout()
    fig.savefig(outFilePlotOcc)

os.remove(tempFile)

