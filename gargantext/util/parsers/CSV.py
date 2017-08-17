from ._Parser import Parser
# from ..NgramsExtractors import *
import sys
import csv
csv.field_size_limit(sys.maxsize)
import numpy as np


class CSVParser(Parser):
    DELIMITERS = ", \t;|:"

    def detect_delimiter(self, lines, sample_size=10):
        sample = lines[:sample_size]

        # Compute frequency of each delimiter on each input line
        delimiters_freqs = {
            d: [line.count(d) for line in sample]
            for d in self.DELIMITERS
        }

        # Select delimiters with a standard deviation of zero, ie. delimiters
        # for which we have the same number of fields on each line
        selected_delimiters = [
            (d, np.sum(freqs))
            for d, freqs in delimiters_freqs.items()
            if any(freqs) and np.std(freqs) == 0
        ]

        if selected_delimiters:
            # Choose the delimiter with highest frequency amongst selected ones
            sorted_delimiters = sorted(selected_delimiters, key=lambda x: x[1])
            return sorted_delimiters[-1][0]

    def parse(self, filebuf):
        print("CSV: parsing (assuming UTF-8 and LF line endings)")

        contents = filebuf.read().decode("UTF-8").split("\n")

        # Filter out empty lines
        contents = [line for line in contents if line.strip()]

        # Delimiter auto-detection
        delimiter = self.detect_delimiter(contents, sample_size=10)

        if delimiter is None:
            raise ValueError("CSV: couldn't detect delimiter, bug or malformed data")

        print("CSV: selected delimiter: %r" % delimiter)

        # Parse CSV
        reader = csv.reader(contents, delimiter=delimiter)

        # Get first not empty row and its fields (ie. header row), or (0, [])
        first_row, headers = \
            next(((i, fields) for i, fields in enumerate(reader) if any(fields)),
                 (0, []))

        # Get first not empty column of the first row, or 0
        first_col = next((i for i, field in enumerate(headers) if field), 0)

        # Strip out potential empty fields in headers
        headers = headers[first_col:]

        # Return a generator of dictionaries with column labels as keys,
        # filtering out empty rows
        for i, fields in enumerate(reader):
            if i % 500 == 0:
                print("CSV: parsing row #%s..." % (i+1))
            if any(fields):
                yield dict(zip(headers, fields[first_col:]))
