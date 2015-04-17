from .RisFileParser import RisFileParser



class IsiFileParser(RisFileParser):
    
    def __init__(self):
        super(RisFileParser, self).__init__()
        self._parameters = {
            b"ER":  {"type": "delimiter"},
            b"TI":  {"type": "metadata", "key": "title", "separator": " "},
            b"AU":  {"type": "metadata", "key": "authors", "separator": ", "},
            b"DI":  {"type": "metadata", "key": "doi"},
            b"PY":  {"type": "metadata", "key": "publication_year"},
            b"PD":  {"type": "metadata", "key": "publication_month"},
            b"LA":  {"type": "metadata", "key": "language_fullname"},
            b"AB":  {"type": "metadata", "key": "abstract", "separator": " "},
            b"WC":  {"type": "metadata", "key": "fields"},
        }

        self._begin = 3
