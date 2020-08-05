import rasterio
from rasterio.features import shapes
from shapely.geometry import shape
import geopandas as gpd
import numpy as np
from optparse import OptionParser
import matplotlib.pyplot as plt

# Options
parser = OptionParser()
parser.add_option("-i", "--in_file",
                  help = "File with raster containing occupancy grid band",
                  default = "out/naip18-nc-cir-60cm_2797141_20181210_occ.jp2")
parser.add_option("-o", "--out_file",
                  help = "File to store output shapefile with obstacle polygons",
                  default = "out/naip18-nc-cir-60cm_2797141_20181210_poly.shp")
parser.add_option("-p", "--out_file_plot",
                  help = "File to store plot of polygons",
                  default = "out/naip18-nc-cir-60cm_2797141_20181210_poly.png")
parser.add_option("-b", "--band",
                  help = "Index of raster band with occupancy grid", type = "int",
                  default = 5)
(options, args) = parser.parse_args()

inFile = options.in_file
outFile = options.out_file
outFilePlot = options.out_file_plot
occBand = options.band

with rasterio.open(inFile, 'r') as src:
    # Read occupancy grid band
    occgrid = src.read(occBand).astype('uint16')

    # Only want polygons of obstacles
    mask = occgrid > 225

    # Store each polygon
    results = (
        {'properties': {'raster_val': v}, 'geometry': s}
        for i, (s, v)
        in enumerate(
            shapes(occgrid, mask = mask, transform = src.transform)
        )
    )
    geoms = list(results)

# Convert polygons to shapely and geopandas formats
gdf = gpd.GeoDataFrame()
count = 0 # Track number of polygons
shapes = []
for geom in geoms:
    # Convert to shapely
    shape_ = shape(geom['geometry'])
    # Simplify shape boundary (since raster artificially blocky)
    shape_ = shape_.simplify(0.005, preserve_topology=False)
    # Grow shape
    shape_ = shape_.buffer(1.0)
    # If smoothing too aggressive, may loose obstacles!
    if shape_.is_empty:
        print ("  Warning! shape lost in simplifying.")
        continue
    shapes.append(shape_)
    gdf.loc[count, 'geometry'] = shape_

    count += 2

# Visualize
if outFilePlot is not None:
    gdf.plot(cmap='OrRd')
    plt.title("Marine environment obstacles")
    plt.savefig(outFilePlot)

# Save shapefile
gdf.to_file(driver = 'ESRI Shapefile', filename = outFile)

