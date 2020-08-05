import rasterio
from rasterio.mask import mask
from rasterio.plot import reshape_as_raster, reshape_as_image, adjust_band, show
import geopandas as gpd
import numpy as np
from sklearn.cluster import KMeans, DBSCAN
import matplotlib.pyplot as plt
from optparse import OptionParser
from skimage.transform import resize

def color_stretch(image, index):
    colors = image[:, :, index].astype(np.float64)
    for b in range(colors.shape[2]):
        colors[:, :, b] = rasterio.plot.adjust_band(colors[:, :, b])
    return colors

# Options
parser = OptionParser()
parser.add_option("-i", "--in_file",
    help = "File with raster of bands (red, green, blue, NIR, ???)",
    default = "naip18-nc-cir-60cm_2797141_20181210_occ.jp2")
parser.add_option("-o", "--out_file",
    help = "File to store raster, sixth added band is cluster IDs",
    default = "naip18-nc-cir-60cm_2797141_20181210_occ_cluster.jp2")
parser.add_option("-m", "--masked", action = "store_true",
    help = "Input raster's fifth band is occupancy grid",
    default = False)
(options, args) = parser.parse_args()

inFile = options.in_file
outFile = options.out_file
masked = options.masked

# Load NAIP raster
full_dataset = rasterio.open(inFile, driver = "JP2OpenJPEG")
img_rows, img_cols = full_dataset.shape
img_bands = full_dataset.count
print(full_dataset.shape)
print(full_dataset.count)

# Read image
img = full_dataset.read() #[:, 100:2600, 2000:14000]
bands, rows, cols = img.shape
print(bands, rows, cols)

# If masked, apply it
if masked:
    for b in range(bands):
        img[b, :, :][img[4, :, :] == 255] = 255

# Remove map band
img = img[:4, :, :]

#scaled_img = resize(img, (int(scale * float(rows)), int(scale * float(cols))))

# reshape into long 2d array (nrow * ncol, nband) for classification
reshaped_img = reshape_as_image(img)

# Kmeans
k = 8
kmeans_predictions = KMeans(n_clusters=k, random_state=0, algorithm='full').fit(reshaped_img.reshape(-1, 4))
kmeans_predictions_2d = kmeans_predictions.labels_.reshape(rows, cols)

# Visualize

rgb = img[0:3]
rgb_norm = adjust_band(rgb) # normalize bands to range between 1.0 to 0.0
rgb_reshaped = reshape_as_image(rgb_norm) # reshape to [rows, cols, bands]

fig, axs = plt.subplots(2, 1, figsize=(10, 20))
show(rgb_norm, ax=axs[1])
axs[1].set_title("RGB")

axs[0].imshow(kmeans_predictions_2d)
axs[0].set_title("KMEANS")

plt.show()
