import sys
import numpy as np
import pandas as pd
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                              QPushButton, QWidget, QFileDialog, QLabel, QSpinBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
import pyqtgraph as pg

class CursorLine(pg.InfiniteLine):
    def __init__(self, angle=90, pos=0, movable=True, label=None):
        super().__init__(angle=angle, pos=pos, movable=movable)
        self.label = label
        self.sigPositionChanged.connect(self.on_position_change)
        
        # Set cursor shape based on the angle
        if angle == 90:  # Vertical cursor
            self.setCursor(Qt.SplitHCursor)  # Horizontal split cursor for horizontal movement
        else:  # Horizontal cursor
            self.setCursor(Qt.SplitVCursor)  # Vertical split cursor for vertical movement
        
    def on_position_change(self):
        if self.label:
            self.label.setText(f"{self.value():.6f}")

def decimate_data(x, y, max_points=10000):
    """Reduce number of points using min-max decimation to preserve signal features"""
    if len(x) <= max_points:
        return x, y
        
    # Calculate the decimation factor
    decimation_factor = len(x) // (max_points // 2)
    
    # Reshape the data to perform min-max decimation
    n_chunks = len(x) // decimation_factor
    x_reshaped = x[:n_chunks * decimation_factor].reshape(-1, decimation_factor)
    y_reshaped = y[:n_chunks * decimation_factor].reshape(-1, decimation_factor)
    
    # Get min and max for each chunk
    x_decimated = x_reshaped[:, 0]  # Take first point of each chunk for x
    y_mins = y_reshaped.min(axis=1)
    y_maxs = y_reshaped.max(axis=1)
    
    # Interleave min and max values
    x_final = np.repeat(x_decimated, 2)
    y_final = np.dstack((y_mins, y_maxs)).flatten()
    
    return x_final, y_final

class OscilloscopeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Oscilloscope Waveform Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize variables
        self.vertical_cursors = []
        self.horizontal_cursors = []
        self.data = None
        self.metadata = {}
        self.raw_data = None  # Store complete dataset
        self.decimation_factor = 10000  # Default decimation points
        
        self.setup_ui()
        
    def setup_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create plot widget
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', 'Voltage (V)')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        
        # Enable antialiasing for smoother lines
        self.plot_widget.setAntialiasing(True)
        
        # Add plot to layout
        layout.addWidget(self.plot_widget)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Add buttons
        load_button = QPushButton("Load CSV")
        load_button.clicked.connect(self.load_csv)
        button_layout.addWidget(load_button)
        
        add_vcursor_button = QPushButton("Add Vertical Cursor")
        add_vcursor_button.clicked.connect(self.add_vertical_cursor)
        button_layout.addWidget(add_vcursor_button)
        
        add_hcursor_button = QPushButton("Add Horizontal Cursor")
        add_hcursor_button.clicked.connect(self.add_horizontal_cursor)
        button_layout.addWidget(add_hcursor_button)
        
        clear_cursors_button = QPushButton("Clear Cursors")
        clear_cursors_button.clicked.connect(self.clear_cursors)
        button_layout.addWidget(clear_cursors_button)
        
        # Add decimation control
        decimation_layout = QHBoxLayout()
        decimation_layout.addWidget(QLabel("Max Points:"))
        self.decimation_spinbox = QSpinBox()
        self.decimation_spinbox.setRange(100, 10000000)
        self.decimation_spinbox.setSingleStep(1000)
        self.decimation_spinbox.setValue(self.decimation_factor)
        self.decimation_spinbox.valueChanged.connect(self.update_decimation)
        decimation_layout.addWidget(self.decimation_spinbox)
        button_layout.addLayout(decimation_layout)
        
        layout.addLayout(button_layout)
        
        # Add measurement display
        measurement_layout = QHBoxLayout()
        
        # Data info label
        self.data_info_label = QLabel("No data loaded")
        self.data_info_label.setAlignment(Qt.AlignCenter)
        measurement_layout.addWidget(self.data_info_label)
        
        # Vertical cursor measurements
        self.vcursor_label = QLabel("ΔT: --- s\nFreq: --- Hz")
        self.vcursor_label.setAlignment(Qt.AlignCenter)
        measurement_layout.addWidget(self.vcursor_label)
        
        # Horizontal cursor measurements
        self.hcursor_label = QLabel("ΔV: --- V")
        self.hcursor_label.setAlignment(Qt.AlignCenter)
        measurement_layout.addWidget(self.hcursor_label)
        
        layout.addLayout(measurement_layout)
        
        # Style the plot
        self.plot_widget.getAxis('left').setPen('k')
        self.plot_widget.getAxis('bottom').setPen('k')
        self.plot_widget.getAxis('left').setTextPen('k')
        self.plot_widget.getAxis('bottom').setTextPen('k')
        
        # Connect viewbox signals for dynamic decimation
        self.plot_widget.getViewBox().sigRangeChanged.connect(self.on_view_changed)
        
    def load_csv(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open CSV File", "", "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_name:
            # Read metadata
            metadata_lines = []
            with open(file_name, 'r') as f:
                for i, line in enumerate(f):
                    if 'Second,Value' in line:
                        break
                    metadata_lines.append(line)
                    
            # Parse metadata
            self.metadata = {}
            for line in metadata_lines:
                if ',' in line:
                    key, *values = line.strip().split(',')
                    self.metadata[key] = values
            
            # Read data
            self.raw_data = pd.read_csv(file_name, skiprows=len(metadata_lines),
                                      dtype={'Second': float, 'Value': float})
            
            # Update data info label
            self.data_info_label.setText(
                f"Total points: {len(self.raw_data):,}\n"
                f"Displayed points: {self.decimation_factor:,}"
            )
            
            # Plot decimated data
            self.update_plot()
            
    def update_decimation(self, value):
        self.decimation_factor = value
        if self.raw_data is not None:
            self.update_plot()
            
    def update_plot(self):
        if self.raw_data is None:
            return
            
        # Decimate data
        x_dec, y_dec = decimate_data(
            self.raw_data['Second'].values,
            self.raw_data['Value'].values,
            max_points=self.decimation_factor
        )
        
        # Update plot
        self.plot_widget.clear()
        self.plot_widget.plot(x_dec, y_dec, pen=pg.mkPen('b', width=2))
        
        # Restore cursors
        for cursor in self.vertical_cursors + self.horizontal_cursors:
            self.plot_widget.addItem(cursor)
            
        # Update axis labels with units from metadata
        x_unit = self.metadata.get('Horizontal Units', ['s'])[0]
        y_unit = self.metadata.get('Vertical Units', ['V'])[0]
        self.plot_widget.setLabel('left', f'Voltage ({y_unit})')
        self.plot_widget.setLabel('bottom', f'Time ({x_unit})')
        
        # Update data info label
        self.data_info_label.setText(
            f"Total points: {len(self.raw_data):,}\n"
            f"Displayed points: {len(x_dec):,}"
        )
        
    def on_view_changed(self, view_box, range_):
        """Called when the view range changes (zoom/pan)"""
        if self.raw_data is not None:
            self.update_plot()
            
    def add_vertical_cursor(self):
        if len(self.vertical_cursors) >= 2:
            return
            
        # Create position label
        pos_label = QLabel()
        pos_label.setAlignment(Qt.AlignCenter)
        
        # Create cursor at center of view or at 0 if no data
        pos = 0
        if self.raw_data is not None:
            view_range = self.plot_widget.viewRange()
            pos = (view_range[0][0] + view_range[0][1]) / 2
            
        cursor = CursorLine(angle=90, pos=pos, movable=True, label=pos_label)
        cursor.setPen(pg.mkPen('r', width=2))
        self.plot_widget.addItem(cursor)
        self.vertical_cursors.append(cursor)
        
        cursor.sigPositionChanged.connect(self.update_measurements)
        self.update_measurements()
        
    def add_horizontal_cursor(self):
        if len(self.horizontal_cursors) >= 2:
            return
            
        # Create position label
        pos_label = QLabel()
        pos_label.setAlignment(Qt.AlignCenter)
        
        # Create cursor at center of view or at 0 if no data
        pos = 0
        if self.raw_data is not None:
            view_range = self.plot_widget.viewRange()
            pos = (view_range[1][0] + view_range[1][1]) / 2
            
        cursor = CursorLine(angle=0, pos=pos, movable=True, label=pos_label)
        cursor.setPen(pg.mkPen('g', width=2))
        self.plot_widget.addItem(cursor)
        self.horizontal_cursors.append(cursor)
        
        cursor.sigPositionChanged.connect(self.update_measurements)
        self.update_measurements()
        
    def clear_cursors(self):
        for cursor in self.vertical_cursors + self.horizontal_cursors:
            self.plot_widget.removeItem(cursor)
        self.vertical_cursors.clear()
        self.horizontal_cursors.clear()
        self.update_measurements()
        
    def update_measurements(self):
        # Update vertical cursor measurements
        if len(self.vertical_cursors) == 2:
            delta_t = abs(self.vertical_cursors[1].value() - self.vertical_cursors[0].value())
            freq = 1/delta_t if delta_t != 0 else float('inf')
            self.vcursor_label.setText(f"ΔT: {delta_t:.6f} s\nFreq: {freq:.2f} Hz")
        else:
            self.vcursor_label.setText("ΔT: --- s\nFreq: --- Hz")
            
        # Update horizontal cursor measurements
        if len(self.horizontal_cursors) == 2:
            delta_v = abs(self.horizontal_cursors[1].value() - self.horizontal_cursors[0].value())
            self.hcursor_label.setText(f"ΔV: {delta_v:.6f} V")
        else:
            self.hcursor_label.setText("ΔV: --- V")

def main():
    app = QApplication(sys.argv)
    
    viewer = OscilloscopeViewer()
    viewer.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
