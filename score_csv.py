import pandas as pd
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess

class ScoreCSVApp:
    def __init__(self, root, input_file=None, output_file=None):
        self.root = root
        self.root.title("Score CSV")
        self.input_file = input_file
        self.output_file = output_file

        # Create GUI elements
        self.label_input = tk.Label(root, text="Source CSV File:")
        self.label_input.pack()

        self.entry_input = tk.Entry(root, width=50)
        self.entry_input.pack()
        if self.input_file:
            self.entry_input.insert(0, self.input_file)

        self.button_browse_input = tk.Button(root, text="Browse", command=self.browse_input_file)
        self.button_browse_input.pack()

        self.label_output = tk.Label(root, text="Save As:")
        self.label_output.pack()

        self.entry_output = tk.Entry(root, width=50)
        self.entry_output.pack()
        if self.output_file:
            self.entry_output.insert(0, self.output_file)

        self.button_browse_output = tk.Button(root, text="Browse", command=self.browse_output_file)
        self.button_browse_output.pack()

        self.button_process = tk.Button(root, text="Process CSV", command=self.process_csv)
        self.button_process.pack()

    def browse_input_file(self):
        self.input_file = filedialog.askopenfilename(title="Select the source CSV file",
                                                     filetypes=[("CSV Files", "*.csv")])
        if self.input_file:
            self.entry_input.delete(0, tk.END)
            self.entry_input.insert(0, self.input_file)

    def browse_output_file(self):
        self.output_file = filedialog.asksaveasfilename(title="Save As",
                                                        defaultextension=".csv",
                                                        filetypes=[("CSV Files", "*.csv")])
        if self.output_file:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, self.output_file)

    def process_csv(self):
        try:
            # Load the CSV file
            df = pd.read_csv(self.input_file, dtype={'parcel_id': str})  # Ensure parcel_id remains as a string

            # Example scoring process - adjust as needed
            df['score'] = df.apply(self.calculate_score, axis=1)

            # Save the processed CSV file
            df.to_csv(self.output_file, index=False)

            # Close the GUI before the next step
            self.root.withdraw()

            # Notify the user of success
            messagebox.showinfo("Success", "CSV file processed successfully.")

            # Ask if the user wants to clean the CSV
            self.ask_to_clean_csv()

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while processing the CSV file: {str(e)}")

    def ask_to_clean_csv(self):
        response = messagebox.askyesno("Clean CSV", "Would you like to clean the new CSV file?")
        if response:
            try:
                script_path = os.path.join(os.path.dirname(__file__), 'clean_csv.py')
                if not os.path.exists(script_path):
                    messagebox.showerror("Error", f'Script {script_path} not found.')
                    return
                subprocess.run([sys.executable, script_path, self.output_file], check=True)
            except Exception as e:
                messagebox.showerror("Error", f"Error running the clean CSV script: {str(e)}")
        self.root.quit()

    def calculate_score(self, row):
        score = 0

        # Extract the values from the row and handle missing values
        acreage_calc = row.get('acreage_calc', 0)
        Bacres = row.get('Bacres', 0)
        distance_to_tx_line = row.get('distance_to_transmission_line_miles', 0)
        voltage_of_closest_line = row.get('voltage_of_closest_line', 0)
        mkt_val_land = row.get('mkt_val_land', 0)

        # Calculating land value per acre
        land_value_per_acre = mkt_val_land / acreage_calc if acreage_calc != 0 else 0

        # Calculate buildable acres percentage
        buildable_acres_pc = (Bacres / acreage_calc) * 100 if acreage_calc != 0 else 0

        # Debugging output
        print(f"Processing row with acreage_calc: {acreage_calc}, Bacres: {Bacres}, distance_to_tx_line: {distance_to_tx_line}, voltage: {voltage_of_closest_line}, land_value_per_acre: {land_value_per_acre}")

        # 1. acreage_calc scoring (Weight: 3)
        if acreage_calc > 750:
            score += 9  # 3 points * weight 3
        elif 501 <= acreage_calc <= 750:
            score += 6  # 2 points * weight 3
        elif 250 <= acreage_calc <= 500:
            score += 3  # 1 point * weight 3

        # 2. Buildable acres percentage (Weight: 3)
        if buildable_acres_pc > 70:
            score += 9  # 3 points * weight 3
        elif 50 <= buildable_acres_pc <= 70:
            score += 6  # 2 points * weight 3
        elif 30 <= buildable_acres_pc <= 50:
            score += 3  # 1 point * weight 3

        # 3. Proximity to transmission line (Weight: 3)
        if distance_to_tx_line == 0:
            score += 9  # 3 points * weight 3
        elif 0 < distance_to_tx_line <= 0.5:
            score += 6  # 2 points * weight 3
        elif 0.5 < distance_to_tx_line <= 1:
            score += 3  # 1 point * weight 3

        # 4. Size of transmission line (Weight: 2)
        if voltage_of_closest_line > 500:
            score += 6  # 3 points * weight 2
        elif 235 <= voltage_of_closest_line <= 500:
            score += 4  # 2 points * weight 2
        elif 100 <= voltage_of_closest_line < 235:
            score += 2  # 1 point * weight 2

        # 5. Land value per acre (Weight: 2)
        if land_value_per_acre > 2000:
            score += 0  # 0 points * weight 2 (No points for land value per acre > $2000)
        elif 1000 <= land_value_per_acre <= 2000:
            score += 2  # 1 point * weight 2
        elif 500 <= land_value_per_acre < 1000:
            score += 4  # 2 points * weight 2
        elif 0 < land_value_per_acre < 500:
            score += 6  # 3 points * weight 2
        # Land value per acre of '0' gets 0 points added to the score
        elif land_value_per_acre == 0:
            score += 0

        print(f"Calculated score for row: {score}")
        return score

def main():
    root = tk.Tk()
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = input_file.replace(".csv", "_scored.csv")
        app = ScoreCSVApp(root, input_file=input_file, output_file=output_file)
    else:
        app = ScoreCSVApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
