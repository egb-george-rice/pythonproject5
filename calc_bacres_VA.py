import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.features import shapes
from shapely.geometry import shape, box
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os


def clip_raster_by_extent(slope_file, vector_data):
    # Calculate the extent of the vector file
    bounds = vector_data.total_bounds
    extent = box(bounds[0], bounds[1], bounds[2], bounds[3])

    # Clip the slope raster file to the extent of the vector file
    with rasterio.open(slope_file) as src:
        out_image, out_transform = mask(src, [extent], crop=True)
        out_meta = src.meta.copy()

    # Update the metadata to reflect the new clipped area
    out_meta.update({
        "driver": "GTiff",
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform
    })

    # Save the clipped raster to a temporary file
    clipped_slope_file = str(Path(slope_file).parent / (Path(slope_file).stem + "_clipped.tif"))
    with rasterio.open(clipped_slope_file, "w", **out_meta) as dest:
        dest.write(out_image)

    return clipped_slope_file


def polygonize_raster(clipped_slope_file):
    with rasterio.open(clipped_slope_file) as src:
        image = src.read(1)
        mask = image == 0

        results = (
            {'properties': {'DN': v}, 'geometry': s}
            for i, (s, v)
            in enumerate(shapes(image, mask=mask, transform=src.transform))
        )

    polygons = list(results)

    # Create a GeoDataFrame from the polygons
    gdf = gpd.GeoDataFrame.from_features(polygons)

    # Filter by DN=0
    gdf = gdf[gdf['DN'] == 0]

    return gdf


def calculate_buildable_acres(slope_file, wetlands_file, vector_file):
    # Check if input files exist
    if not Path(slope_file).is_file():
        print(f"Error: Slope file {slope_file} does not exist.")
        return None, None
    if not Path(wetlands_file).is_file():
        print(f"Error: Wetlands file {wetlands_file} does not exist.")
        return None, None
    if not Path(vector_file).is_file():
        print(f"Error: Vector file {vector_file} does not exist.")
        return None, None

    # Load the vector file
    vector_data = gpd.read_file(vector_file)

    # Ensure the vector data is in the same CRS as the slope raster
    with rasterio.open(slope_file) as src:
        raster_crs = src.crs
        vector_data = vector_data.to_crs(raster_crs)

    # Clip the slope raster by the extent of the vector file
    clipped_slope_file = clip_raster_by_extent(slope_file, vector_data)

    # Polygonize the clipped slope raster and filter by DN=0
    slope_gdf = polygonize_raster(clipped_slope_file)

    # Load the wetlands file
    wetlands_data = gpd.read_file(wetlands_file)
    wetlands_data = wetlands_data.to_crs(raster_crs)

    # Perform a difference operation to exclude wetlands and slope DN=0 areas
    non_buildable_gdf = gpd.GeoDataFrame(pd.concat([wetlands_data, slope_gdf], ignore_index=True))
    buildable_gdf = gpd.overlay(vector_data, non_buildable_gdf, how='difference')

    # Calculate the buildable area for each parcel
    buildable_acres = []
    for idx, row in vector_data.iterrows():
        geom = row['geometry']
        buildable_geom = buildable_gdf.intersection(geom)
        buildable_area = buildable_geom.area.sum()
        buildable_acres.append(buildable_area / 4046.86)  # Convert square meters to acres

    # Convert 'acreage_calc' field to numeric type if necessary
    vector_data['acreage_calc'] = pd.to_numeric(vector_data['acreage_calc'], errors='coerce')

    # Add a new field to the vector layer for buildable acres
    vector_data['Bacres'] = (np.array(buildable_acres)).astype(int)

    # Save the updated vector layer to a new file
    output_file = str(Path(vector_file).parent / (Path(vector_file).stem + "_buildable_acres.gpkg"))
    vector_data.to_file(output_file, driver="GPKG")

    # Save the updated vector layer to a new CSV file
    csv_output_file = str(Path(vector_file).parent / (Path(vector_file).stem + "_buildable_acres.csv"))
    vector_data.to_csv(csv_output_file, index=False)

    return output_file, csv_output_file


def main():
    slope_file = r"C:\Users\georg\OneDrive\Documents\GIS projects\Elevation models\VA15percRaster\SlopeReclass.tif"
    wetlands_file = r"C:\Users\georg\OneDrive\Documents\GIS projects\Elevation models\VA15percRaster\Fixed VA wetlands.shp"

    if len(sys.argv) == 2:
        vector_file = sys.argv[1]
    else:
        root = tk.Tk()
        root.withdraw()
        vector_file = filedialog.askopenfilename(title="Select the vector file",
                                                 filetypes=[("GeoPackage files", "*.gpkg"), ("Shapefiles", "*.shp")])
        if not vector_file:
            print("No vector file selected. Exiting.")
            sys.exit(1)

    output_file, csv_output_file = calculate_buildable_acres(slope_file, wetlands_file, vector_file)
    if output_file:
        print(f"Buildable acres calculated and saved to: {output_file}")
        print(f"CSV file saved to: {csv_output_file}")

        root = tk.Tk()
        root.withdraw()
        response = messagebox.askyesno("Clean and Score CSV", "Would you like to clean and score your parcel CSV file?")
        if response:
            try:
                script_path = os.path.join(os.path.dirname(__file__), 'clean_csv.py')
                if not os.path.exists(script_path):
                    messagebox.showerror("Error", f'Script {script_path} not found.')
                    return
                subprocess.run([sys.executable, script_path, csv_output_file], check=True)
            except Exception as e:
                messagebox.showerror("Error", f'Error running the clean and score script: {str(e)}')
    else:
        print("Processing failed due to non-overlapping extents or missing files.")


if __name__ == "__main__":
    main()
