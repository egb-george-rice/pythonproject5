import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.features import shapes
from shapely.geometry import box
from shapely.ops import unary_union
import numpy as np
from osgeo import gdal
from pathlib import Path
import pandas as pd
import sys
import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

# Enable GDAL exceptions
gdal.UseExceptions()

# Disable scientific notation in Pandas
pd.set_option('display.float_format', lambda x: '%.6f' % x)

# Define a minimum threshold for area to avoid extremely small values
MIN_AREA_THRESHOLD = 1e-4  # Adjust as necessary

def clip_raster_by_mask(raster_file, mask_layer):
    with rasterio.open(raster_file) as src:
        valid_crs = src.crs.to_string()
        mask_layer = mask_layer.to_crs(valid_crs)
        out_image, out_transform = mask(src, mask_layer.geometry, crop=True)
        out_meta = src.meta.copy()

    out_meta.update({
        "driver": "GTiff",
        "height": out_image.shape[1],
        "width": out_image.shape[2],
        "transform": out_transform
    })

    clipped_raster_file = str(Path(raster_file).parent / (Path(raster_file).stem + "_clipped.tif"))
    with rasterio.open(clipped_raster_file, "w", **out_meta) as dest:
        dest.write(out_image)

    return clipped_raster_file

def calculate_difference(original_vector, slope_gdf, wetlands_file):
    print("Loading wetlands data...")
    wetlands_data = gpd.read_file(wetlands_file)

    print("Reprojecting datasets to common CRS...")
    original_vector_crs = original_vector.crs.to_string()
    wetlands_data = wetlands_data.to_crs(original_vector_crs)
    slope_gdf = slope_gdf.to_crs(original_vector_crs)

    print("Simplifying geometries to speed up processing...")
    wetlands_data['geometry'] = wetlands_data['geometry'].simplify(tolerance=0.1, preserve_topology=True)
    slope_gdf['geometry'] = slope_gdf['geometry'].simplify(tolerance=0.1, preserve_topology=True)

    print("Combining wetlands and slope data into non-buildable areas...")
    non_buildable_gdf = gpd.GeoDataFrame(pd.concat([wetlands_data, slope_gdf], ignore_index=True), crs=original_vector_crs)

    print("Calculating the difference between original parcels and non-buildable areas in chunks...")

    # Initialize spatial index on non-buildable areas to speed up operations
    non_buildable_sindex = non_buildable_gdf.sindex

    difference_gdfs = []
    for i, parcel in original_vector.iterrows():
        # Find possible overlapping geometries using spatial index
        possible_matches_index = list(non_buildable_sindex.intersection(parcel.geometry.bounds))
        possible_matches = non_buildable_gdf.iloc[possible_matches_index]

        # Calculate the actual difference
        try:
            if not possible_matches.empty:
                difference = parcel.geometry.difference(unary_union(possible_matches.geometry))
                if difference.area > MIN_AREA_THRESHOLD:  # Filter out very small differences
                    parcel.geometry = difference
                    difference_gdfs.append(parcel)
        except Exception as e:
            print(f"Error processing parcel {i}: {str(e)}")

    # Combine all the processed parcels back into a single GeoDataFrame
    if difference_gdfs:
        difference_gdf = gpd.GeoDataFrame(difference_gdfs, crs=original_vector_crs)
    else:
        difference_gdf = gpd.GeoDataFrame(columns=original_vector.columns, crs=original_vector_crs)

    print("Difference calculation complete.")
    return difference_gdf

def calculate_slope(clipped_raster_file):
    slope_file = str(Path(clipped_raster_file).parent / (Path(clipped_raster_file).stem + "_slope.tif"))
    gdal.DEMProcessing(slope_file, clipped_raster_file, 'slope', computeEdges=True, options=['-p'])
    return slope_file

def polygonize_slope(slope_file):
    with rasterio.open(slope_file) as src:
        image = src.read(1)
        results = (
            {'properties': {'DN': v}, 'geometry': s}
            for i, (s, v)
            in enumerate(shapes(image, mask=(image != 0), transform=src.transform))
        )

    polygons = list(results)
    slope_gdf = gpd.GeoDataFrame.from_features(polygons, crs=src.crs)

    slope_gdf = slope_gdf[slope_gdf['DN'] > 15]
    polygonized_slope_file = str(Path(slope_file).parent / (Path(slope_file).stem + "_polygonized.shp"))
    slope_gdf.to_file(polygonized_slope_file)

    return slope_gdf

def calculate_overlap(difference_gdf, original_vector):
    overlap_gdf = gpd.overlay(difference_gdf, original_vector, how='intersection')
    overlap_gdf['overlap_area'] = overlap_gdf.area

    # Handle small areas that could cause issues by setting them to zero
    overlap_gdf['overlap_area'] = np.where(overlap_gdf['overlap_area'] < MIN_AREA_THRESHOLD, 0, overlap_gdf['overlap_area'])

    overlap_gdf['overlap_pc'] = (overlap_gdf['overlap_area'] / original_vector.area) * 100

    return overlap_gdf

def calculate_bacres(overlap_gdf, original_vector):
    original_vector['overlap_pc'] = pd.to_numeric(overlap_gdf['overlap_pc'], errors='coerce')
    original_vector['acreage_calc'] = pd.to_numeric(original_vector['acreage_calc'], errors='coerce')

    original_vector['overlap_pc'].fillna(0, inplace=True)
    original_vector['acreage_calc'].fillna(0, inplace=True)

    original_vector['Bacres'] = (original_vector['overlap_pc'] * original_vector['acreage_calc']) / 100
    return original_vector

def run_analysis(vector_file, slope_file, wetlands_file):
    try:
        vector_data = gpd.read_file(vector_file)

        print("Step 1: Clipping raster by mask layer")
        clipped_raster_file = clip_raster_by_mask(slope_file, vector_data)

        print("Step 2: Calculating slope of clipped raster")
        slope_file = calculate_slope(clipped_raster_file)

        print("Step 3: Polygonizing slope raster")
        slope_gdf = polygonize_slope(slope_file)

        print("Step 5: Calculating difference between wetlands layer and filtered polygonized layer")
        difference_gdf = calculate_difference(vector_data, slope_gdf, wetlands_file)

        print("Step 6: Calculating overlap of difference layer and original _2m layer")
        overlap_gdf = calculate_overlap(difference_gdf, vector_data)

        print("Step 7: Calculating Bacres")
        final_gdf = calculate_bacres(overlap_gdf, vector_data)

        output_file = str(Path(vector_file).parent / (Path(vector_file).stem + "_buildable_acres.gpkg"))
        final_gdf.to_file(output_file, driver="GPKG")

        csv_output_file = str(Path(vector_file).parent / (Path(vector_file).stem + "_buildable_acres.csv"))
        final_gdf.to_csv(csv_output_file, index=False)

        print(f"Buildable acres calculated and saved to: {output_file}")
        print(f"CSV file saved to: {csv_output_file}")

        return csv_output_file

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

def prompt_for_scoring(csv_output_file):
    root = tk.Tk()
    root.withdraw()
    response = messagebox.askyesno("Parcel Scoring", "Do you want to run a parcel_score on the file?")
    if response:
        try:
            script_path = os.path.join(os.path.dirname(__file__), 'score_csv.py')
            if not os.path.exists(script_path):
                messagebox.showerror("Error", f'Script {script_path} not found.')
                return
            subprocess.run([sys.executable, script_path, csv_output_file], check=True)
        except Exception as e:
            messagebox.showerror("Error", f'Error running the scoring script: {str(e)}')

def main():
    slope_file = r"C:\Users\georg\OneDrive\Desktop\RA_pull_files\Ohio\Base maps\DEM\oh_dem_hs\dblbnd.adf"
    wetlands_file = r"C:\Users\georg\OneDrive\Desktop\RA_pull_files\Ohio\OH Base maps\OH_shapefile_wetlands\Ohio_Wetlands.shp"

    if len(sys.argv) >= 2:
        vector_file = sys.argv[1]
    else:
        root = tk.Tk()
        root.withdraw()
        vector_file = filedialog.askopenfilename(title="Select the vector file",
                                                 filetypes=[("GeoPackage files", "*.gpkg"), ("Shapefiles", "*.shp")])
        if not vector_file:
            print("No vector file selected. Exiting.")
            sys.exit(1)

    print(f"Vector file selected: {vector_file}")
    csv_output_file = run_analysis(vector_file, slope_file, wetlands_file)
    if csv_output_file:
        prompt_for_scoring(csv_output_file)
    print("Analysis complete.")

if __name__ == "__main__":
    main()
