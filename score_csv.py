import sys
import os
import pandas as pd
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog

class CSVProcessorGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Clean and Score your CSV')

        # Introductory message
        self.intro_label = QLabel(
            "This module will clean and score a CSV file downloaded from QGIS."
            "Before running this module, you must calculate the buildable acres for each parcel."
        )
        self.intro_label.setWordWrap(True)

        # Input file browser
        self.input_label = QLabel('Select input CSV file:', self)
        self.input_path = QLineEdit(self)
        self.input_browse = QPushButton('Browse', self)
        self.input_browse.clicked.connect(self.browse_input_file)

        # Output file browser
        self.output_label = QLabel('Select output file:', self)
        self.output_path = QLineEdit(self)
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

    def browse_input_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Select input CSV file", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_name:
            self.input_path.setText(file_name)

    def browse_output_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Select output CSV file", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_name:
            self.output_path.setText(file_name)

    def process_csv(self):
        input_file = self.input_path.text()
        output_file = self.output_path.text()

        if not input_file or not output_file:
            QMessageBox.warning(self, "Input/Output Error", "Both input and output files must be specified.")
            return

        try:
            df = pd.read_csv(input_file)

            # Example scoring logic, replace with your logic
            df['Score'] = df['Bacres'] * 100 / df['acreage_calc']
            df.to_csv(output_file, index=False)
            QMessageBox.information(self, "Success", "CSV processed and saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while processing the CSV: {str(e)}")

def main():
    app = QApplication(sys.argv)
    gui = CSVProcessorGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
