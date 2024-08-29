import sys
import requests
import geopandas as gpd
from shapely import wkt
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QLineEdit, QMessageBox, QFileDialog
import os
import logging
import subprocess

# Setup logging for debugging purposes
logging.basicConfig(level=logging.DEBUG, filename='debug.log', filemode='w',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# API and authentication details
client_key = 'RqMXhNFKlQ'  # Replace with your actual client token
api_version = '9'  # API version
api_url = "https://reportallusa.com/api/parcels"

# Mapping of County_ID prefixes to states
STATE_MAPPING = {
    '39': 'OH',  # Ohio
    '51': 'VA',  # Virginia
    # Add more states here as needed
}

class ReportAllParcelSearch(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('ReportAll Parcel Search')

        # Input fields for new query option
        self.county_id_label = QLabel('County ID:', self)
        self.county_id_input = QLineEdit(self)
        self.owner_label = QLabel('Owner (optional):', self)
        self.owner_input = QLineEdit(self)
        self.parcel_id_label = QLabel('Parcel ID (optional):', self)
        self.parcel_id_input = QLineEdit(self)
        self.calc_acreage_min_label = QLabel('Minimum Acreage (optional):', self)
        self.calc_acreage_min_input = QLineEdit(self)

        # Run and Exit buttons
        self.run_button = QPushButton('Run', self)
        self.run_button.clicked.connect(self.run_action)
        self.exit_button = QPushButton('Exit', self)
        self.exit_button.clicked.connect(self.close)

        # Layout
        vbox = QVBoxLayout()
        vbox.addWidget(QLabel("Enter the query details:"))
        vbox.addWidget(self.county_id_label)
        vbox.addWidget(self.county_id_input)
        vbox.addWidget(self.owner_label)
        vbox.addWidget(self.owner_input)
        vbox.addWidget(self.parcel_id_label)
        vbox.addWidget(self.parcel_id_input)
        vbox.addWidget(self.calc_acreage_min_label)
        vbox.addWidget(self.calc_acreage_min_input)
        hbox = QVBoxLayout()
        hbox.addWidget(self.run_button)
        hbox.addWidget(self.exit_button)
        vbox.addLayout(hbox)

        self.setLayout(vbox)
        self.show()

    def run_action(self):
        county_id = self.county_id_input.text().strip()
        owner = self.owner_input.text().strip()
        parcel_id = self.parcel_id_input.text().strip()
        calc_acreage_min = self.calc_acreage_min_input.text().strip()

        if not county_id:
            QMessageBox.warning(self, 'Error', 'County ID is required for a new query.')
            return

        self.run_new_query(county_id, owner, parcel_id, calc_acreage_min)

    def run_new_query(self, county_id, owner, parcel_id, calc_acreage_min):
        params = {
            'client': client_key,
            'v': api_version,
            'county_id': county_id,
            'owner': owner,
            'parcel_id': parcel_id,
            'calc_acreage_min': calc_acreage_min,
            'returnGeometry': 'true',
            'f': 'geojson',
            'page': 1
        }
        all_results = []
        try:
            while True:
                response = requests.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()

                if 'results' in data and data['results']:
                    all_results.extend(data['results'])
                    if data['count'] > len(all_results):
                        params['page'] += 1
                        continue
                    else:
                        break
                else:
                    break

            if all_results:
                geometries = [wkt.loads(res['geom_as_wkt']) for res in all_results if 'geom_as_wkt' in res]
                gdf = gpd.GeoDataFrame(all_results, geometry=geometries)
                gdf.crs = "EPSG:4326"
                self.display_results(gdf)
            else:
                QMessageBox.warning(self, 'No Results', 'No parcels found for the specified query.')
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, 'Error', f'Error querying the API: {str(e)}')
            logging.error(f'Error querying the API with URL: {api_url}, params: {params}, error: {str(e)}')

    def display_results(self, gdf):
        if not gdf.empty:
            self.close()  # Close the initial dialog before showing the "Save As" dialog
            options = QFileDialog.Options()
            options |= QFileDialog.DontUseNativeDialog
            desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
            save_path, _ = QFileDialog.getSaveFileName(self, "Save GeoPackage", desktop_path,
                                                       "GeoPackage Files (*.gpkg);;All Files (*)", options=options)
            if save_path:
                if not save_path.endswith('.gpkg'):
                    save_path += '.gpkg'
                gdf.to_file(save_path, driver='GPKG')
                QMessageBox.information(self, 'Success', f'GeoPackage saved to {save_path}')
                self.ask_for_proximity_analysis(save_path, gdf)
            else:
                QMessageBox.information(self, 'Cancelled', 'Save operation cancelled.')
                self.close_application()
        else:
            QMessageBox.warning(self, 'No Data', 'There is no data to save.')
            self.close_application()

    def ask_for_proximity_analysis(self, save_path, gdf):
        response = QMessageBox.question(self, 'Transmission Line Proximity Analysis',
                                        "Would you like to run a Transmission Line Proximity Analysis?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if response == QMessageBox.Yes:
            self.run_proximity_analysis(save_path, gdf)
        else:
            self.close_application()

    def determine_state_from_county_id(self, gdf):
        if 'county_id' not in gdf.columns:
            raise ValueError("The input data does not contain a 'county_id' field.")

        county_id_prefix = gdf['county_id'].astype(str).str[:2].iloc[0]
        state_code = STATE_MAPPING.get(county_id_prefix)

        if state_code is None:
            raise ValueError(f"Unrecognized County_ID prefix: {county_id_prefix}. Please update the state mapping.")

        return state_code

    def run_proximity_analysis(self, save_path, gdf):
        try:
            state_code = self.determine_state_from_county_id(gdf)
            script_name = f'tx_prox_analysis_{state_code}.py'
            script_path = os.path.join(os.path.dirname(__file__), script_name)
            if not os.path.exists(script_path):
                QMessageBox.critical(self, 'Error', f'Script {script_path} not found.')
                return
            subprocess.run([sys.executable, script_path, save_path], check=True)
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Error running the proximity analysis: {str(e)}')
            logging.error(f'Error running the proximity analysis with script: {script_path}, error: {str(e)}')
        finally:
            self.close_application()

    def close_application(self):
        self.close()  # Close the QWidget
        QApplication.quit()  # Quit the application completely


def main():
    app = QApplication(sys.argv)
    gui = ReportAllParcelSearch()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
