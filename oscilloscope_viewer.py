import sys
import numpy as np
import pandas as pd
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                              QPushButton, QWidget, QFileDialog, QLabel, QSpinBox,
                              QMessageBox, QProgressDialog, QComboBox, QDialog,
                              QFormLayout, QDoubleSpinBox, QDialogButtonBox, QCheckBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
import pyqtgraph as pg
from parsers import AVAILABLE_PARSERS

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

class BinaryImportDialog(QDialog):
    """Dialog to configure binary import settings."""
    def __init__(self, parent=None, file_path: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Binary Import Settings")
        self.file_path = file_path

        layout = QFormLayout(self)

        # Endianness
        self.endian_combo = QComboBox()
        self.endian_combo.addItems(["Little", "Big"])
        layout.addRow("Endianness", self.endian_combo)

        # Data type
        self.dtype_combo = QComboBox()
        # Common numeric formats
        self.dtype_combo.addItems([
            "int8", "uint8",
            "int16", "uint16",
            "int32", "uint32",
            "float32", "float64",
        ])
        self.dtype_combo.setCurrentText("int16")
        layout.addRow("Data Type", self.dtype_combo)

        # Header offset (bytes)
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(0, 2_147_483_647)
        self.offset_spin.setValue(0)
        layout.addRow("Header Offset (bytes)", self.offset_spin)

        # Data length (bytes, 0 = to end)
        self.length_spin = QSpinBox()
        self.length_spin.setRange(0, 2_147_483_647)
        self.length_spin.setValue(0)
        layout.addRow("Data Length (bytes)", self.length_spin)

        # Sample rate
        self.sr_spin = QDoubleSpinBox()
        self.sr_spin.setRange(1e-12, 1e12)
        self.sr_spin.setDecimals(6)
        self.sr_spin.setValue(1_000_000.0)
        layout.addRow("Sample Rate (Hz)", self.sr_spin)

        # Scale (V per unit)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(-1e12, 1e12)
        self.scale_spin.setDecimals(9)
        self.scale_spin.setValue(1.0)
        layout.addRow("Scale (V per unit)", self.scale_spin)

        # Offset (V)
        self.voffset_spin = QDoubleSpinBox()
        self.voffset_spin.setRange(-1e12, 1e12)
        self.voffset_spin.setDecimals(9)
        self.voffset_spin.setValue(0.0)
        layout.addRow("Offset (V)", self.voffset_spin)

        # Channel count (for simple interleaving support)
        self.chan_count_spin = QSpinBox()
        self.chan_count_spin.setRange(1, 128)
        self.chan_count_spin.setValue(1)
        layout.addRow("Channel Count (interleaved)", self.chan_count_spin)

        # Channel index to extract (0-based)
        self.chan_index_spin = QSpinBox()
        self.chan_index_spin.setRange(0, 127)
        self.chan_index_spin.setValue(0)
        layout.addRow("Channel Index (0-based)", self.chan_index_spin)

        # Keep channel index max synced with channel count
        def _sync_channel_index_max(val):
            self.chan_index_spin.setMaximum(max(0, val - 1))
        self.chan_count_spin.valueChanged.connect(_sync_channel_index_max)
        _sync_channel_index_max(self.chan_count_spin.value())

        # Auto-detect on load option
        self.auto_check = QCheckBox("Auto-detect header on load")
        self.auto_check.setChecked(False)
        layout.addRow(self.auto_check)

        # Tools row: Preview and Auto-detect buttons
        tools_row = QWidget()
        tools_layout = QHBoxLayout(tools_row)
        self.preview_btn = QPushButton("Preview")
        self.autodetect_btn = QPushButton("Auto-detect Now")
        tools_layout.addWidget(self.preview_btn)
        tools_layout.addWidget(self.autodetect_btn)
        layout.addRow("Tools", tools_row)

        # Preview label
        self.preview_label = QLabel("No preview yet")
        self.preview_label.setWordWrap(True)
        layout.addRow("Preview", self.preview_label)

        # Preview thumbnail plot
        self.preview_plot = pg.PlotWidget()
        self.preview_plot.setMinimumHeight(120)
        self.preview_plot.setBackground('w')
        self.preview_plot.showGrid(x=True, y=True)
        layout.addRow("Thumbnail", self.preview_plot)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Connect tool actions
        self.preview_btn.clicked.connect(self.preview_data)
        self.autodetect_btn.clicked.connect(self.auto_detect_offset)

        # Live update preview when key settings change
        self.endian_combo.currentTextChanged.connect(self.preview_data)
        self.dtype_combo.currentTextChanged.connect(self.preview_data)
        self.offset_spin.valueChanged.connect(self.preview_data)
        self.chan_count_spin.valueChanged.connect(self.preview_data)
        self.chan_index_spin.valueChanged.connect(self.preview_data)
        self.sr_spin.valueChanged.connect(self.preview_data)
        self.scale_spin.valueChanged.connect(self.preview_data)
        self.voffset_spin.valueChanged.connect(self.preview_data)

        # Initial preview
        try:
            self.preview_data()
        except Exception:
            pass

    def get_params(self):
        return {
            "endian": self.endian_combo.currentText(),
            "dtype": self.dtype_combo.currentText(),
            "offset_bytes": int(self.offset_spin.value()),
            "length_bytes": int(self.length_spin.value()),
            "sample_rate_hz": float(self.sr_spin.value()),
            "scale_v_per_unit": float(self.scale_spin.value()),
            "v_offset": float(self.voffset_spin.value()),
            "channel_count": int(self.chan_count_spin.value()),
            "channel_index": int(self.chan_index_spin.value()),
            "auto_detect": bool(self.auto_check.isChecked()),
        }

    # --- Helper methods for preview and auto-detect ---
    def _np_dtype(self):
        endian_char = '<' if self.endian_combo.currentText().lower().startswith('l') else '>'
        dtype_map = {
            'int8': 'i1', 'uint8': 'u1',
            'int16': 'i2', 'uint16': 'u2',
            'int32': 'i4', 'uint32': 'u4',
            'float32': 'f4', 'float64': 'f8',
        }
        base = dtype_map.get(self.dtype_combo.currentText())
        if base is None:
            raise ValueError(f"Unsupported data type: {self.dtype_combo.currentText()}")
        return np.dtype(endian_char + base)

    def _read_channel_samples(self, start_offset: int, items_wanted: int) -> np.ndarray:
        if not self.file_path:
            return np.array([], dtype=np.float64)
        np_dtype = self._np_dtype()
        ch_count = max(1, int(self.chan_count_spin.value()))
        ch_index = min(max(0, int(self.chan_index_spin.value())), ch_count - 1)
        sample_bytes = np_dtype.itemsize * ch_count
        eff_offset = ((int(start_offset) + sample_bytes - 1) // sample_bytes) * sample_bytes
        # For interleaved, read enough items to extract desired channel samples
        total_items = items_wanted * ch_count
        with open(self.file_path, 'rb') as f:
            if eff_offset:
                f.seek(eff_offset, 0)
            raw = np.fromfile(f, dtype=np_dtype, count=total_items)
        if raw.size == 0:
            return np.array([], dtype=np.float64)
        if ch_count > 1:
            usable = (raw.size // ch_count) * ch_count
            raw = raw[:usable].reshape(-1, ch_count)[:, ch_index]
        return raw.astype(np.float64)

    def preview_data(self):
        try:
            if not self.file_path:
                self.preview_label.setText("No file selected for preview")
                self.preview_plot.clear()
                return
            offset = int(self.offset_spin.value())
            # Compute effective aligned offset for display
            np_dtype = self._np_dtype()
            ch_count = max(1, int(self.chan_count_spin.value()))
            sample_bytes = np_dtype.itemsize * ch_count
            eff_offset = ((int(offset) + sample_bytes - 1) // sample_bytes) * sample_bytes
            window = self._read_channel_samples(offset, 4096)
            if window.size == 0:
                self.preview_label.setText("Preview: no data at current offset")
                self.preview_plot.clear()
                return
            diffs = np.diff(window)
            transitions = int(np.count_nonzero(diffs != 0))
            unique_vals = int(len(np.unique(window)))
            unique_frac = unique_vals / max(1, window.size)
            # Apply scale/offset for display
            scale = float(self.scale_spin.value())
            voffset = float(self.voffset_spin.value())
            y = window * scale + voffset
            sr = float(self.sr_spin.value())
            x = np.arange(y.size) / max(sr, 1e-12)
            # Update plot
            self.preview_plot.clear()
            self.preview_plot.plot(x, y, pen=pg.mkPen('#0077cc', width=1))

            msg = (
                f"Samples: {window.size}\n"
                f"Effective offset: {eff_offset} bytes\n"
                f"Min/Max (scaled): {np.nanmin(y):.3g} / {np.nanmax(y):.3g}\n"
                f"Mean/Std (scaled): {np.nanmean(y):.3g} / {np.nanstd(y):.3g}\n"
                f"Transitions: {transitions} ({transitions/window.size:.3%})\n"
                f"Unique values: {unique_vals} ({unique_frac:.1%})"
            )
            self.preview_label.setText(msg)
        except Exception as e:
            self.preview_label.setText(f"Preview error: {e}")
            self.preview_plot.clear()

    def auto_detect_offset(self):
        try:
            if not self.file_path:
                self.preview_label.setText("No file selected for detection")
                return
            np_dtype = self._np_dtype()
            ch_count = max(1, int(self.chan_count_spin.value()))
            ch_index = min(max(0, int(self.chan_index_spin.value())), ch_count - 1)
            best = detect_header_offset(self.file_path, np_dtype, ch_count, ch_index)
            self.offset_spin.setValue(int(best))
            self.preview_data()
        except Exception as e:
            self.preview_label.setText(f"Auto-detect error: {e}")

    def auto_detect_on_load(self) -> bool:
        return bool(self.auto_check.isChecked())

def detect_header_offset(file_path: str, np_dtype: np.dtype, channel_count: int, channel_index: int, max_scan_bytes: int = 1 << 20) -> int:
    """
    Heuristic header detector: scans the first portion of the file in aligned steps
    and returns the offset where the data appears least "random" based on low
    transition density and low unique value fraction in a window.

    Returns byte offset.
    """
    step = max(1, int(np_dtype.itemsize) * max(1, channel_count))
    file_size = Path(file_path).stat().st_size
    limit = min(max_scan_bytes, file_size)

    def window_score(arr: np.ndarray) -> float:
        if arr.size < 64:
            return float('inf')
        diffs = np.diff(arr)
        trans = np.count_nonzero(diffs != 0) / arr.size
        uniq = len(np.unique(arr)) / arr.size
        # Favor fewer transitions and fewer unique values (plateaus)
        return trans + 0.75 * uniq

    best_offset = 0
    best_score = float('inf')
    # Scan in steps; ensure we don't read too much each time
    items_per_window = 4096
    for off in range(0, int(limit), step * 8):  # hop by 8 samples worth to speed up
        # Read enough raw items to get items_per_window for the selected channel
        total_needed = items_per_window * channel_count
        with open(file_path, 'rb') as f:
            f.seek(off, 0)
            raw = np.fromfile(f, dtype=np_dtype, count=total_needed)
        if raw.size < items_per_window:
            continue
        if channel_count > 1:
            usable = (raw.size // channel_count) * channel_count
            raw = raw[:usable].reshape(-1, channel_count)[:, channel_index]
        arr = raw.astype(np.float64)
        s = window_score(arr)
        if s < best_score:
            best_score = s
            best_offset = off
    return best_offset

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

class OscilloscopeCSVParser:
    def can_parse(self, first_lines):
        """Check if this parser can handle the CSV format based on first few lines"""
        raise NotImplementedError()
        
    def parse(self, file_path, update_progress=None):
        """Parse the CSV file and return (metadata, data_frame)"""
        raise NotImplementedError()

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
        self.dark_mode = False  # Track dark mode state
        self.selected_channel: int | None = None  # Active channel (e.g., 1..4) if available
        
        # Define color schemes
        self.color_schemes = {
            'light': {
                'background': 'w',
                'foreground': 'k',
                'grid': (128, 128, 128),
                'plot': 'b',
            },
            'dark': {
                'background': '#2b2b2b',
                'foreground': 'w',
                'grid': (90, 90, 90),
                'plot': '#00a3ff',
            }
        }
        
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

        load_bin_button = QPushButton("Load Binary")
        load_bin_button.clicked.connect(self.load_binary)
        button_layout.addWidget(load_bin_button)
        
        add_vcursor_button = QPushButton("Add Vertical Cursor")
        add_vcursor_button.clicked.connect(self.add_vertical_cursor)
        button_layout.addWidget(add_vcursor_button)
        
        add_hcursor_button = QPushButton("Add Horizontal Cursor")
        add_hcursor_button.clicked.connect(self.add_horizontal_cursor)
        button_layout.addWidget(add_hcursor_button)
        
        clear_cursors_button = QPushButton("Clear Cursors")
        clear_cursors_button.clicked.connect(self.clear_cursors)
        button_layout.addWidget(clear_cursors_button)
        
        # Add dark mode toggle
        toggle_dark_mode = QPushButton("Toggle Dark Mode")
        toggle_dark_mode.clicked.connect(self.toggle_dark_mode)
        button_layout.addWidget(toggle_dark_mode)
        
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

        # Channel selector (populated when file contains multiple channels)
        channel_layout = QHBoxLayout()
        channel_layout.addWidget(QLabel("Channel:"))
        self.channel_combo = QComboBox()
        self.channel_combo.setEnabled(False)
        self.channel_combo.currentTextChanged.connect(self.on_channel_changed)
        channel_layout.addWidget(self.channel_combo)
        button_layout.addLayout(channel_layout)
        
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
            # Get file size for progress calculation
            file_size = Path(file_name).stat().st_size
            
            # Create progress dialog
            progress = QProgressDialog("Loading CSV file...", "Cancel", 0, 100, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setAutoClose(True)
            progress.setMinimumDuration(0)  # Show immediately for large files
            
            def update_progress(current: int, total: int, message: str):
                if progress.wasCanceled():
                    raise InterruptedError("File loading cancelled by user")
                progress.setLabelText(message)
                progress.setValue(int(current * 100 / total))
                QApplication.processEvents()  # Ensure UI remains responsive
            
            # Read first few lines to detect format
            with open(file_name, 'r') as f:
                first_lines = [f.readline() for _ in range(10)]
            
            # Find suitable parser
            parser = None
            for p in AVAILABLE_PARSERS:
                if p.can_parse(first_lines):
                    parser = p
                    break
                    
            if parser is None:
                progress.close()
                QMessageBox.critical(self, "Error", 
                    "Unsupported CSV format. Currently supported formats:\n" +
                    "\n".join(f"- {p.__class__.__name__.replace('CSVParser', '')}" 
                             for p in AVAILABLE_PARSERS))
                return
            
            try:
                # Parse the file with progress reporting
                self.metadata, self.raw_data = parser.parse(file_name, update_progress)
                
                # Update data info label
                self.data_info_label.setText(
                    f"Total points: {len(self.raw_data):,}\n"
                    f"Displayed points: {self.decimation_factor:,}"
                )
                
                # Populate channel selector if available
                channels = self.metadata.get('Channels')
                self.channel_combo.blockSignals(True)
                self.channel_combo.clear()
                if channels:
                    for ch in channels:
                        self.channel_combo.addItem(f"CH{ch}")
                    # Prefer CH1 if present, else first
                    if 1 in channels:
                        self.channel_combo.setCurrentText("CH1")
                        self.selected_channel = 1
                    else:
                        self.channel_combo.setCurrentIndex(0)
                        # Extract number from text
                        try:
                            self.selected_channel = int(self.channel_combo.currentText().replace('CH',''))
                        except Exception:
                            self.selected_channel = None
                    self.channel_combo.setEnabled(True)
                else:
                    self.channel_combo.setEnabled(False)
                    self.selected_channel = None
                self.channel_combo.blockSignals(False)

                # Plot decimated data
                self.update_plot()
                
            except InterruptedError:
                self.data_info_label.setText("Loading cancelled")
                return
            except Exception as e:
                progress.close()
                QMessageBox.critical(self, "Error", f"Failed to parse CSV file: {str(e)}")
                return
            finally:
                progress.close()

    def load_binary(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Binary File", "", "All Files (*)"
        )

        if not file_name:
            return

        # Ask user for binary import settings
        dlg = BinaryImportDialog(self, file_path=file_name)
        if dlg.exec() != QDialog.Accepted:
            return
        params = dlg.get_params()

        # Optionally auto-detect header on load
        if params.get("auto_detect"):
            try:
                endian_char = '<' if params['endian'].lower().startswith('l') else '>'
                dtype_map = {
                    'int8': 'i1', 'uint8': 'u1',
                    'int16': 'i2', 'uint16': 'u2',
                    'int32': 'i4', 'uint32': 'u4',
                    'float32': 'f4', 'float64': 'f8',
                }
                base = dtype_map.get(params['dtype'])
                if base is None:
                    raise ValueError(f"Unsupported data type: {params['dtype']}")
                np_dtype = np.dtype(endian_char + base)
                ch_count = max(1, int(params['channel_count']))
                ch_index = int(params['channel_index'])
                auto_offset = detect_header_offset(file_name, np_dtype, ch_count, ch_index)
                params['offset_bytes'] = int(auto_offset)
            except Exception as _e:
                # Fall back to user-provided offset if detection fails
                pass

        # Create progress dialog
        progress = QProgressDialog("Loading binary file...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setAutoClose(True)
        progress.setMinimumDuration(0)

        try:
            # Validate params
            if params["sample_rate_hz"] <= 0:
                raise ValueError("Sample rate must be > 0")

            endian_char = '<' if params['endian'].lower().startswith('l') else '>'
            dtype_map = {
                'int8': 'i1', 'uint8': 'u1',
                'int16': 'i2', 'uint16': 'u2',
                'int32': 'i4', 'uint32': 'u4',
                'float32': 'f4', 'float64': 'f8',
            }
            base = dtype_map.get(params['dtype'])
            if base is None:
                raise ValueError(f"Unsupported data type: {params['dtype']}")
            np_dtype = np.dtype(endian_char + base)

            offset = int(params['offset_bytes'])
            length_bytes = int(params['length_bytes'])

            # Align offset to sample boundary (dtype size * channel_count)
            ch_count = max(1, int(params['channel_count']))
            sample_bytes = np_dtype.itemsize * ch_count
            eff_offset = ((int(offset) + sample_bytes - 1) // sample_bytes) * sample_bytes

            # Adjust length if provided to account for alignment shift
            if length_bytes > 0:
                align_delta = max(0, eff_offset - offset)
                eff_length_bytes = max(0, length_bytes - align_delta)
            else:
                eff_length_bytes = 0

            progress.setValue(5)
            progress.setLabelText("Reading file...")
            if progress.wasCanceled():
                raise InterruptedError("File loading cancelled by user")

            # Determine number of items to read
            if eff_length_bytes > 0:
                count = eff_length_bytes // np_dtype.itemsize
            else:
                # Compute remaining bytes to end of file
                file_size = Path(file_name).stat().st_size
                remaining_bytes = max(0, file_size - eff_offset)
                count = remaining_bytes // np_dtype.itemsize

            # Read using a file handle: seek to offset then fromfile
            with open(file_name, 'rb') as f:
                if eff_offset:
                    f.seek(eff_offset, 0)
                data = np.fromfile(f, dtype=np_dtype, count=count)

            if data.size == 0:
                raise ValueError("No data samples found with the given settings")

            progress.setValue(30)
            progress.setLabelText("Processing channels...")
            if progress.wasCanceled():
                raise InterruptedError("File loading cancelled by user")

            ch_index = int(params['channel_index'])
            if ch_index < 0 or ch_index >= ch_count:
                raise ValueError("Channel index out of range")

            if ch_count > 1:
                # Assume simple interleaving by sample
                total_samples = data.size // ch_count
                if total_samples == 0:
                    raise ValueError("Not enough data for the specified channel count")
                data = data[: total_samples * ch_count]
                data = data.reshape(total_samples, ch_count)
                data = data[:, ch_index]

            progress.setValue(60)
            progress.setLabelText("Building time axis...")
            if progress.wasCanceled():
                raise InterruptedError("File loading cancelled by user")

            sr = float(params['sample_rate_hz'])
            t = np.arange(data.size, dtype=np.float64) / sr

            # Apply scaling
            scale = float(params['scale_v_per_unit'])
            voffset = float(params['v_offset'])
            y = data.astype(np.float64) * scale + voffset

            progress.setValue(80)
            progress.setLabelText("Creating DataFrame...")
            if progress.wasCanceled():
                raise InterruptedError("File loading cancelled by user")

            df = pd.DataFrame({'Second': t, 'Value': y})

            # Metadata
            metadata = {
                'format': 'Binary',
                'Horizontal Units': ['s'],
                'Vertical Units': ['V'],
                'Sample Rate (Hz)': [sr],
                'Endian': [params['endian']],
                'Data Type': [params['dtype']],
                'Requested Header Offset (bytes)': [offset],
                'Effective Header Offset (bytes)': [eff_offset],
                'Header Alignment (bytes)': [sample_bytes],
                'Data Length (bytes)': [
                    eff_length_bytes if eff_length_bytes > 0 else (Path(file_name).stat().st_size - eff_offset)
                ],
            }

            self.metadata, self.raw_data = metadata, df

            # Update UI similarly to CSV load
            self.data_info_label.setText(
                f"Total points: {len(self.raw_data):,}\n"
                f"Displayed points: {self.decimation_factor:,}"
            )

            # No multi-channel metadata for now
            self.channel_combo.blockSignals(True)
            self.channel_combo.clear()
            self.channel_combo.setEnabled(False)
            self.selected_channel = None
            self.channel_combo.blockSignals(False)

            self.update_plot()

            progress.setValue(100)
            progress.setLabelText("Done!")

        except InterruptedError:
            self.data_info_label.setText("Loading cancelled")
            return
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Error", f"Failed to parse binary file: {str(e)}")
            return
        finally:
            progress.close()

    def update_decimation(self, value):
        self.decimation_factor = value
        if self.raw_data is not None:
            self.update_plot()
            
    def update_plot(self):
        if self.raw_data is None:
            return
        
        # Determine which value column to display
        y_col = None
        if self.selected_channel is not None:
            candidate = f"Value_CH{self.selected_channel}"
            if candidate in self.raw_data.columns:
                y_col = candidate
        if y_col is None:
            # Fallback to default 'Value' if present
            if 'Value' in self.raw_data.columns:
                y_col = 'Value'
            else:
                # Last resort: pick the first Value_CHn column
                ch_cols = [c for c in self.raw_data.columns if c.startswith('Value_CH')]
                if ch_cols:
                    y_col = ch_cols[0]
        if y_col is None:
            return

        # Decimate data for selected column
        x_dec, y_dec = decimate_data(
            self.raw_data['Second'].values,
            self.raw_data[y_col].values,
            max_points=self.decimation_factor
        )
        
        # Get current color scheme
        mode = 'dark' if self.dark_mode else 'light'
        colors = self.color_schemes[mode]
        
        # Update plot
        self.plot_widget.clear()
        self.plot_widget.plot(x_dec, y_dec, pen=pg.mkPen(colors['plot'], width=2))
        
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

    def on_channel_changed(self, text: str):
        # Parse channel like "CH1" to integer 1
        try:
            if text.upper().startswith('CH'):
                ch = int(text[2:])
                self.selected_channel = ch
            else:
                self.selected_channel = None
        except Exception:
            self.selected_channel = None
        # Re-plot with the selected channel
        if self.raw_data is not None:
            self.update_plot()
        
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
            
    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        mode = 'dark' if self.dark_mode else 'light'
        colors = self.color_schemes[mode]
        
        # Update plot colors
        self.plot_widget.setBackground(colors['background'])
        self.plot_widget.getAxis('left').setPen(colors['foreground'])
        self.plot_widget.getAxis('bottom').setPen(colors['foreground'])
        self.plot_widget.getAxis('left').setTextPen(colors['foreground'])
        self.plot_widget.getAxis('bottom').setTextPen(colors['foreground'])
        
        # Update grid color
        self.plot_widget.getPlotItem().getViewBox().setBackgroundColor(colors['background'])
        
        # Update plot if data is loaded
        if self.raw_data is not None:
            self.update_plot()
            
def main():
    app = QApplication(sys.argv)
    
    viewer = OscilloscopeViewer()
    viewer.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
