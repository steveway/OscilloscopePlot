from typing import Optional, Callable

class OscilloscopeCSVParser:
    def can_parse(self, first_lines):
        """Check if this parser can handle the CSV format based on first few lines"""
        raise NotImplementedError()
        
    def parse(self, file_path, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        """
        Parse the CSV file and return (metadata, data_frame)
        
        Args:
            file_path: Path to the CSV file
            progress_callback: Optional callback function that takes (current, total, message)
                             to report progress during parsing
        """
        raise NotImplementedError()
