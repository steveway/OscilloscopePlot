class OscilloscopeCSVParser:
    def can_parse(self, first_lines):
        """Check if this parser can handle the CSV format based on first few lines"""
        raise NotImplementedError()
        
    def parse(self, file_path):
        """Parse the CSV file and return (metadata, data_frame)"""
        raise NotImplementedError()
