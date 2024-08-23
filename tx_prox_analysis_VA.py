import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import geopandas as gpd
from pathlib import Path
from tqdm import tqdm
from shapely.geometry import Point
import threading
import time
import subprocess
import sys
import os


class App:
    def __init__(self, root, initial_file=None):
        self.root = root
        self.root.title("Append Distance to Transmission Lines")

        # Create a frame for widgets
        self.frame = tk.Frame(self.root, padx=20, pady=20)
        self.frame.pack()

        # Add a label and button to select input file
        self.label = tk.Label(self.frame, text="Select .gpkg or .shp file:")
        self.label.grid(row=0, column=0, sticky=tk.W)

        self.file_button = tk.Button(self.frame, text="Browse", command=self.browse_file)
        self.file_button.grid(row=0, column=1, padx=10, pady=5)

        # Display selected file path/name
        self.file_label = tk.Label(self.frame, text="", wraplength=300)
        self.file_label.grid(row=1, column=0, columnspan=2, pady=10)

        # Progress bar to show script progress
        self.progress = tk.DoubleVar()
        self.progressbar = ttk.Progressbar(self.frame, length=300, variable=self.progress, mode='determinate')
        self.progressbar.grid(row=2, column=0, columnspan=2, pady=10)

        # Progress percentage label
        self.progress_label = tk.Label(self.frame, text="0%")
        self.progress_label.grid(row=3, column=0, columnspan=2, pady=10)

        # Button to start processing
        self.start_button = tk.Button(self.frame, text="Start Processing", command=self.start_processing)
        self.start_button.grid(row=4, column=0, columnspan=2, pady=10)

        # Cancel button
        self.cancel_button = tk.Button(self.frame, text="Cancel", command=self.cancel_processing, state=tk.DISABLED)
        self.cancel_button.grid(row=5, column=0, columnspan=2, pady=10)

        # Status label
        self.status_label = tk.Label(self.frame, text="")
        self.status_label.grid(row=6, column=0, columnspan=2)

        # Initialize variables
        self.input_file = initial_file
        self.output_file = None
        self.subset_file = None
        self.total_parcels = 0
        self.processed_parcels = 0
        self.script_thread = None
        self.cancel_requested = False

        if self.input_file:
            self.file_label.config(text=f"Selected file: {self.input_file}")

    def browse_file(self):
        self.input_file = filedialog.askopenfilename(filetypes=[("GeoPackage files", "*.gpkg"), ("Shapefile", "*.shp")])
        if self.input_file:
            self.file_label.config(text=f"Selected file: {self.input_file}")

    def start_processing(self):
        if not self.input_file:
            messagebox.showerror("Error", "Please select an input file.")
            return

        self.status_label.config(text="Processing...")
        self.start_button.config(state=tk.DISABLED)
        self.file_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.cancel_requested = False

        # Start a new thread to run the script
        self.script_thread = threading.Thread(target=self.run_script)
        self.script_thread.start()

        # Start periodic update of progress bar
        self.root.after(5000, self.update_progress)

    def run_script(self):
        start_time = time.time()
        try:
            self.output_file, self.subset_file = append_distance_to_transmission_lines(self.input_file,
                                                                                       self.update_progress,
                                                                                       self.is_cancel_requested)
            end_time = time.time()
            processing_time = end_time - start_time

            # Close the main window
            self.root.withdraw()

            # Ask the user if they want to perform buildable acreage analysis
            response = messagebox.askyesno("Buildable Acreage Analysis",
                                           "Would you like to perform a buildable acreage analysis on these parcels?")
            if response:
                # Call the second script (calc_bacres_VA.py) with the newly created "_2m" file
                script_path = os.path.join(os.path.dirname(__file__),
                                           'calc_bacres_VA.py')  # Update this path to the actual path of your calc_bacres_VA.py script
                subprocess.run([sys.executable, script_path, self.subset_file])

            # Show completion dialog with file paths and processing time
            self.show_completion_dialog(self.output_file, self.subset_file, processing_time)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.status_label.config(text="Error")
        finally:
            self.cancel_button.config(state=tk.DISABLED)

    def update_progress(self):
        if self.script_thread and self.script_thread.is_alive():
            if self.total_parcels > 0:
                current_progress = (self.processed_parcels / self.total_parcels) * 100
                self.progress.set(current_progress)
                self.progress_label.config(text=f"{current_progress:.2f}%")

            # Schedule next update
            self.root.after(5000, self.update_progress)

    def cancel_processing(self):
        self.cancel_requested = True

    def is_cancel_requested(self):
        return self.cancel_requested

    def show_completion_dialog(self, output_file, subset_file, processing_time):
        completion_window = tk.Toplevel(self.root)
        completion_window.title("Processing Complete")

        msg = f"Processing complete!\n\nOutput File: {output_file}\nSubset File: {subset_file}\n\nTotal Processing Time: {processing_time:.2f} seconds"
        tk.Label(completion_window, text=msg, padx=20, pady=20).pack()

        tk.Button(completion_window, text="Acknowledge", command=self.root.destroy, padx=20, pady=10).pack()


def get_utm_crs(geometry):
    lon = geometry.centroid.x
    utm_zone = int((lon + 180) / 6) + 1
    return f"EPSG:326{utm_zone if geometry.centroid.y >= 0 else utm_zone + 100}"


def append_distance_to_transmission_lines(input_file, progress_callback, cancel_callback):
    parcels = gpd.read_file(input_file)

    # Remove features where land_use_class is 'Tax Exempt'
    if 'land_use_class' in parcels.columns:
        parcels = parcels[parcels['land_use_class'] != 'Tax Exempt']

    transmission_lines_file = r"C:\Users\georg\OneDrive\Documents\GIS projects\US Electric Infra\Electric_Power_Transmission_Lines.shp"
    transmission_lines = gpd.read_file(transmission_lines_file)

    utm_crs = get_utm_crs(parcels.unary_union)
    parcels = parcels.to_crs(utm_crs)
    transmission_lines = transmission_lines.to_crs(utm_crs)

    app.total_parcels = len(parcels)

    parcels['distance_to_transmission_line_miles'] = None
    parcels['voltage_of_closest_line'] = None

    for idx, parcel in tqdm(parcels.iterrows(), total=len(parcels), desc="Processing parcels"):
        if cancel_callback():
            return None, None

        closest_line_idx = transmission_lines.distance(parcel.geometry).idxmin()
        closest_line = transmission_lines.loc[closest_line_idx]

        distance_meters = parcel.geometry.distance(closest_line.geometry)
        distance_miles = round(distance_meters * 0.000621371, 2)

        voltage = int(round(closest_line['VOLTAGE']))

        parcels.at[idx, 'distance_to_transmission_line_miles'] = distance_miles
        parcels.at[idx, 'voltage_of_closest_line'] = voltage

        # Increment processed parcels count
        app.processed_parcels += 1

        # Update progress in tqdm (not needed here, since we're using after for the GUI update)
        # tqdm.get_lock().acquire()
        # tqdm.get_lock().release()

    output_file = str(Path(input_file).parent / (Path(input_file).stem + "_dist_from_line" + Path(input_file).suffix))
    parcels.to_file(output_file)

    # Create a subset with parcels within 2 miles from the transmission line
    subset = parcels[parcels['distance_to_transmission_line_miles'] <= 2]
    subset = subset.drop_duplicates(subset='parcel_id')
    subset_file = str(Path(input_file).parent / (Path(input_file).stem + "_2m" + Path(input_file).suffix))
    subset.to_file(subset_file)

    return output_file, subset_file


if __name__ == "__main__":
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    app = App(root, initial_file)
    root.mainloop()
