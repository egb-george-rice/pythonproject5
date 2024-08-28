import geopandas as gpd
import pandas as pd
from pathlib import Path
import rasterio
from rasterio.mask import mask
from rasterio.features import shapes
from shapely.geometry import box
from osgeo import gdal
import sys
import os
import subprocess  # <--- This line was missing
import tkinter as tk
from tkinter import filedialog, messagebox

# Enable GDAL exceptions
gdal.UseExceptions()

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
    non_buildable_gdf = pd.concat([wetlands_data, slope_gdf], ignore_index=True)

    # Create spatial index for the original vector data and the non-buildable areas
    original_vector_sindex = original_vector.sindex
    non_buildable_sindex = non_buildable_gdf.sindex

    print("Calculating the difference between original parcels and non-buildable areas in chunks...")
    # Process in chunks to avoid memory issues
    difference_results = []

    for index, parcel in original_vector.iterrows():
        possible_matches_index = list(non_buildable_sindex.intersection(parcel['geometry'].bounds))
        possible_matches = non_buildable_gdf.iloc[possible_matches_index]

        if not possible_matches.empty:
            difference = gpd.overlay(gpd.GeoDataFrame([parcel], crs=original_vector.crs), possible_matches, how='difference')
            difference_results.append(difference)
        else:
            difference_results.append(gpd.GeoDataFrame([parcel], crs=original_vector.crs))

    difference_gdf = pd.concat(difference_results, ignore_index=True)

    print("Difference calculation complete.")
    return difference_gdf

def calculate_overlap(difference_gdf, original_vector):
    overlap_gdf = gpd.overlay(difference_gdf, original_vector, how='intersection')
    overlap_gdf['overlap_area'] = overlap_gdf.area
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
        vector_data = gpd.read_file(vector_file, dtype={'parcel_id': str})

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

        # Ensure parcel_id remains a string
        final_gdf['parcel_id'] = final_gdf['parcel_id'].astype(str)

        output_file = str(Path(vector_file).parent / (Path(vector_file).stem + "_buildable_acres.gpkg"))
        final_gdf.to_file(output_file, driver="GPKG")

        csv_output_file = str(Path(vector_file).parent / (Path(vector_file).stem + "_buildable_acres.csv"))
        final_gdf.to_csv(csv_output_file, index=False)

        print(f"Buildable acres calculated and saved to: {output_file}")
        print(f"CSV file saved to: {csv_output_file}")

        return csv_output_file  # Return the CSV file path to pass it to the scoring script

    except Exception as e:
        print(f"An error occurred: {str(e)}")

def main():
    slope_file = r"C:\Users\georg\OneDrive\Desktop\RA_pull_files\Ohio\Base maps\DEM\oh_dem_hs\dblbnd.adf"
    wetlands_file = r"C:\Users\georg\OneDrive\Desktop\RA_pull_files\Ohio\OH Base maps\OH_shapefile_wetlands\Ohio_Wetlands.shp"

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

    print(f"Vector file selected: {vector_file}")
    csv_output_file = run_analysis(vector_file, slope_file, wetlands_file)
    print("Analysis completed.")

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
            messagebox.showerror("Error", f'Error running the parcel scoring script: {str(e)}')

if __name__ == "__main__":
    main()
