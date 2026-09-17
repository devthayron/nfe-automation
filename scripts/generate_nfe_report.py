from pathlib import Path

from excel import generate_dataframe, generate_excel
from parser.nfe_parser import NFeParser


def load_nfes(directory):
    nfes = []

    for path in sorted(Path(directory).glob("*.xml")):
        parser = NFeParser(str(path))
        parser.read_nfe()

        nfe = parser.extract_data()

        if nfe:
            nfes.append(nfe)

    return nfes


if __name__ == "__main__":
    xmls_directory = "data"

    nfes = load_nfes(xmls_directory)
    df = generate_dataframe(nfes)

    generate_excel(nfes)

    print("Excel generated successfully!")
    print(df)
