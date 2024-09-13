import pandas as pd
import sys
import subprocess
import tkinter as tk
import os
from tkinter import messagebox

def calculate_score(row):
    score = 0

    # Extract the values from the row and handle missing values
    acreage_calc = row.get('acreage_calc', 0)
    Bacres = row.get('Bacres', 0)
    distance_to_tx_line = row.get('distance_to_transmission_line_miles', 0)
    voltage_of_closest_line = row.get('voltage_of_closest_line', 0)
    mkt_val_land = row.get('mkt_val_land', 0)
    acreage_adjacent_with_sameowner = row.get('acreage_adjacent_with_sameowner', 0)

    # Calculating land value per acre
    land_value_per_acre = mkt_val_land / acreage_calc if acreage_calc != 0 else 0

    # Calculate buildable acres percentage
    buildable_acres_pc = (Bacres / acreage_calc) * 100 if acreage_calc != 0 else 0

    # Calculate the new scoring criterion for adjacent acreage
    adjacent_acreage_ratio = acreage_adjacent_with_sameowner / acreage_calc if acreage_calc != 0 else 0

    # Debugging output
    print(f"Processing row with acreage_calc: {acreage_calc}, Bacres: {Bacres}, distance_to_tx_line: {distance_to_tx_line}, voltage: {voltage_of_closest_line}, land_value_per_acre: {land_value_per_acre}, adjacent_acreage_ratio: {adjacent_acreage_ratio}")

    # 1. acreage_calc scoring (Weight: 5)
    if acreage_calc > 750:
        score += 15  # 3 points * weight 5
    elif 501 <= acreage_calc <= 750:
        score += 10  # 2 points * weight 5
    elif 250 <= acreage_calc <= 500:
        score += 5  # 1 point * weight 5

    # 2. Buildable acres percentage (Weight: 5)
    if buildable_acres_pc > 70:
        score += 15  # 3 points * weight 5
    elif 50 <= buildable_acres_pc <= 70:
        score += 10  # 2 points * weight 5
    elif 30 <= buildable_acres_pc <= 50:
        score += 5  # 1 point * weight 5

    # 3. Proximity to transmission line (Weight: 3)
    if distance_to_tx_line == 0:
        score += 9  # 3 points * weight 3
    elif 0 < distance_to_tx_line <= 0.5:
        score += 6  # 2 points * weight 3
    elif 0.5 < distance_to_tx_line <= 1:
        score += 3  # 1 point * weight 3

    # 4. Size of transmission line (Weight: 1)
    if voltage_of_closest_line > 500:
        score += 3  # 3 points * weight 1
    elif 235 <= voltage_of_closest_line <= 500:
        score += 2  # 2 points * weight 1
    elif 100 <= voltage_of_closest_line < 235:
        score += 1  # 1 point * weight 1

    # 5. Land value per acre (Weight: 1)
    if land_value_per_acre > 2000:
        score += 0  # 0 points * weight 1 (No points for land value per acre > $2000)
    elif 1000 <= land_value_per_acre <= 2000:
        score += 1  # 1 point * weight 1
    elif 500 <= land_value_per_acre < 1000:
        score += 2  # 2 points * weight 1
    elif 0 < land_value_per_acre < 500:
        score += 3  # 3 points * weight 1
    # Land value per acre of '0' gets 0 points added to the score
    elif land_value_per_acre == 0:
        score += 0

    # 6. Acreage adjacent with the same owner (Weight: 5)
    if adjacent_acreage_ratio > 1:
        score += 15  # 3 points * weight 5
    elif 0.5 <= adjacent_acreage_ratio <= 1:
        score += 10  # 2 points * weight 5
    elif 0.1 <= adjacent_acreage_ratio < 0.5:
        score += 5  # 1 point * weight 5

    print(f"Calculated score for row: {score}")
    return score

def main(csv_file):
    # Read CSV file into DataFrame
    df = pd.read_csv(csv_file)

    # Apply scoring function to each row
    df['score'] = df.apply(calculate_score, axis=1)

    # Save the results to a new CSV file
    output_file = csv_file.replace('.csv', '_scored.csv')
    df.to_csv(output_file, index=False)

    print(f"Scored data saved to: {output_file}")

    # Ask the user if they want to clean the CSV file
    root = tk.Tk()
    root.withdraw()
    response = messagebox.askyesno("Clean CSV", "Do you wish to clean the CSV file?")
    if response:
        try:
            script_path = 'clean_csv.py'  # Ensure this path is correct
            if not os.path.exists(script_path):
                messagebox.showerror("Error", f'Script {script_path} not found.')
                return
            subprocess.run([sys.executable, script_path, output_file], check=True)
        except Exception as e:
            messagebox.showerror("Error", f'Error running the clean CSV script: {str(e)}')

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python score_csv.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]
    main(csv_file)
