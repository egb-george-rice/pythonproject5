import sys
import os
import pandas as pd
import logging
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog

# Setup logging for debugging purposes
logging.basicConfig(level=logging.DEBUG, filename='clean_csv_debug.log', filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Function to sanitize the addr_number column
def sanitize_addr_number(value):
    try:
        return int(value)
    except ValueError:
        return 0

# Function to format columns as whole numbers
def format_whole_number(value):
    try:
        return int(value)
    except ValueError:
        return 0

# Function to calculate quality score
def calculate_quality_score(row):
    score = 0
    try:
        # Existing score calculations with updated weights and error handling
        if 'BAcres' in row and pd.notna(row['BAcres']):
            score += row['BAcres'] / 300
        if 'acreage_adjacent_with_sameowner' in row and pd.notna(row['acreage_adjacent_with_sameowner']):
            score += row['acreage_adjacent_with_sameowner'] / 500
        if 'mkt_val_land' in row and pd.notna(row['mkt_val_land']) and 'BAcres' in row and pd.notna(row['BAcres']) and row['BAcres'] != 0:
            score += row['mkt_val_land'] / row['BAcres'] / -10000
        if 'distance_to_transmission_line_miles' in row and pd.notna(row['distance_to_transmission_line_miles']):
            score += row['distance_to_transmission_line_miles'] / -0.5

        # Land Use Code scoring
        if 'land_use_code' in row and pd.notna(row['land_use_code']):
            if row['land_use_code'] == 9:
                score += 2
            elif row['land_use_code'] == 8:
                score += 1

        # Voltage-based scoring
        if 'voltage_of_closest_line' in row and pd.notna(row['voltage_of_closest_line']):
            voltage = row['voltage_of_closest_line']
            if voltage < 100:
                score += -2
            elif 100 <= voltage < 500:
                score += 1
            elif voltage >= 500:
                score += -1

    except Exception as e:
        raise ValueError(f"Error calculating score for row: {row}\nError details: {str(e)}")
    return score

# Function to process the CSV file
def process_csv(input_file, output_file):
    try:
        df = pd.read_csv(input_file)
        logging.info("CSV file loaded successfully.")

        # Sanitize and fill NaN values in addr_number with 0 and ensure it's an integer
        if 'addr_number' in df.columns:
            df['addr_number'] = df['addr_number'].apply(sanitize_addr_number)

        # Concatenate addr_number, addr_street_name, and addr_street_type, and format as Proper Case
        if all(col in df.columns for col in ['addr_number', 'addr_street_name', 'addr_street_type']):
            df['full_address'] = df['addr_number'].astype(str) + ' ' + df['addr_street_name'].fillna('') + ' ' + df['addr_street_type'].fillna('')
            df['full_address'] = df['full_address'].apply(lambda x: str(x).title())

        # Format specified columns as Proper Case
        columns_to_propercase = ['physcity', 'owner', 'mail_address1', 'mail_address3']
        for col in columns_to_propercase:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: str(x).title() if pd.notnull(x) else x)

        # Split mail_address3 into City, State, and Zip
        def split_mail_address(address):
            if pd.isnull(address):
                return pd.Series([None, None, None])
            parts = address.rsplit(' ', 2)  # Split from the end, assuming the last two parts are state and zip
            if len(parts) < 3:
                return pd.Series([None, None, None])
            city = parts[0]
            state = parts[1]
            zip_code = parts[2]
            return pd.Series([city, state, zip_code])

        if 'mail_address3' in df.columns:
            df[['mail_city', 'mail_state', 'mail_zip']] = df['mail_address3'].apply(split_mail_address)

        # Format the mail_state column to be all capital letters
        if 'mail_state' in df.columns:
            df['mail_state'] = df['mail_state'].apply(lambda x: str(x).upper() if pd.notnull(x) else x)

        # Format the acreage_calc and acreage_adjacent_with_sameowner columns as whole numbers
        if 'acreage_calc' in df.columns:
            df['acreage_calc'] = df['acreage_calc'].apply(format_whole_number)
        if 'acreage_adjacent_with_sameowner' in df.columns:
            df['acreage_adjacent_with_sameowner'] = df['acreage_adjacent_with_sameowner'].fillna(0).astype(int)

        # Calculate quality scores
        df['Score'] = df.apply(calculate_quality_score, axis=1)
        df['Score'] = df['Score'].round(1)

        # Select and order the specified columns, ensure 'BAcres' is next to 'county_id'
        essential_columns = [
            'owner', 'county_name', 'state_abbr', 'full_address', 'physcity', 'mail_address1',
            'mail_city', 'mail_state', 'mail_zip', 'parcel_id', 'acreage_calc', 'county_id', 'BAcres',
            'distance_to_transmission_line_miles', 'voltage_of_closest_line',
            'acreage_adjacent_with_sameowner', 'mkt_val_land', 'land_use_code',
            'latitude', 'longitude', 'land_cover', 'Score'
        ]

        # Ensure all specified columns are present in the DataFrame
        existing_essential_columns = [col for col in essential_columns if col in df.columns]

        # Get the remaining columns not specified in essential_columns
        remaining_columns = [col for col in df.columns if col not in existing_essential_columns]

        # Concatenate the essential columns with the remaining columns
        all_columns = existing_essential_columns + remaining_columns

        # Reorder DataFrame to have essential columns first, followed by remaining columns
        df_final = df[all_columns]

        # Save the adjusted DataFrame to a new CSV file
        df_final.to_csv(output_file, index=False)
        logging.info(f"File saved to {output_file}")

    except Exception as e:
        logging.error(f"Error processing CSV file: {e}")
        raise RuntimeError(f"Error processing CSV file: {e}")

class CSVProcessorGUI(QWidget):
    def __init__(self, initial_file=None):
        super().__init__()
        self.init_ui(initial_file)

    def init_ui(self, initial_file):
        self.setWindowTitle('Clean your CSV')

        # Introductory message
        self.intro_label = QLabel(
            "This module will 'clean' a CSV file downloaded from QGIS so that the data can be imported into the CRM. "
            "Before running this module, you must calculate the buildable acres for each parcel by using the BAcres calculator plug-in in QGIS.",
            self
        )
        self.intro_label.setWordWrap(True)

        # Input file browser
        self.input_label = QLabel('Select input CSV file:', self)
        self.input_path = QLineEdit(self)
        if initial_file:
            self.input_path.setText(initial_file)
            suggested_output = os.path.join(os.path.dirname(initial_file), os.path.basename(initial_file).replace('.csv', '_clean.csv'))
            self.output_path = QLineEdit(suggested_output)
        else:
            self.output_path = QLineEdit()
        self.input_browse = QPushButton('Browse', self)
        self.input_browse.clicked.connect(self.browse_input_file)

        # Output file browser
        self.output_label = QLabel('Select output file:', self)
        self.output_browse = QPushButton('Browse', self)
        self.output_browse.clicked.connect(self.browse_output_file)

        # Process button
        self.process_button = QPushButton('Process CSV', self)
        self.process_button.clicked.connect(self.process_csv)

        # Layout
        vbox = QVBoxLayout()
        vbox.addWidget(self.intro_label)
        vbox.addWidget(self.input_label)
        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.input_path)
        hbox1.addWidget(self.input_browse)
        vbox.addLayout(hbox1)
        vbox.addWidget(self.output_label)
        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.output_path)
        hbox2.addWidget(self.output_browse)
        vbox.addLayout(hbox2)
        vbox.addWidget(self.process_button)

        self.setLayout(vbox)
        self.show()

    def browse_input_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Input CSV File", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_path:
            self.input_path.setText(file_path)
            # Suggest output file name
            suggested_output = os.path.join(os.path.dirname(file_path), os.path.basename(file_path).replace('.csv', '_clean.csv'))
            self.output_path.setText(suggested_output)

    def browse_output_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Select Output File", self.output_path.text(), "CSV Files (*.csv);;All Files (*)", options=options)
        if file_path:
            self.output_path.setText(file_path)

    def process_csv(self):
        input_file = self.input_path.text()
        output_file = self.output_path.text()

        if not input_file or not output_file:
            QMessageBox.warning(self, 'Error', 'Please specify both input and output file paths.')
            return

        try:
            process_csv(input_file, output_file)
            QMessageBox.information(self, 'Success', f'CSV file has been processed and saved to {output_file}')
            self.close()  # Close the main window after the message box is acknowledged
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'An error occurred while processing the CSV file: {e}')
            self.close()  # Close the main window after the error message box is acknowledged

def main():
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    app = QApplication(sys.argv)
    gui = CSVProcessorGUI(initial_file)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
