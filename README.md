# Oscilloscope Waveform Viewer

A Python-based desktop application for visualizing and analyzing oscilloscope waveform data from CSV files. Built using PySide6 and pyqtgraph for high-performance interactive visualization.

![Screenshot of the Oscilloscope Viewer](screenshot.png)

## Features

- Fast loading and visualization of large CSV files (10MB+)
- Smart data decimation for smooth performance with large datasets
- Interactive waveform plotting with zoom and pan
- Movable cursors with intuitive mouse interaction:
  - Vertical cursors (red) with horizontal movement indicators
  - Horizontal cursors (green) with vertical movement indicators
- Real-time measurements:
  - Delta time (ΔT) between vertical cursors
  - Frequency calculation (1/ΔT)
  - Voltage difference (ΔV) between horizontal cursors
- Adjustable display resolution (points shown)
- Drag and drop file loading

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python oscilloscope_viewer.py
```

2. Use the interface:
   - Click "Load CSV" to open your oscilloscope data file
   - Add cursors using the buttons
   - Drag cursors by hovering over them (cursor will change to indicate movability)
   - Adjust the "Max Points" value to balance between performance and detail
   - Use mouse wheel to zoom and right-click drag to pan

## Supported File Format

The application expects CSV files in the Siglent oscilloscope format with metadata headers followed by time-voltage data pairs. Example format:

```csv
Record Length,Analog:450584,
Sample Interval,Analog:5.000000E-05,
Vertical Units,CH3:V,,
...
Second,Value
+1.240000E+01,+4.000008E-02
+1.240005E+01,+4.000008E-02
...
```
