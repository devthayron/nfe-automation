from pathlib import Path

from excel import generate_dataframe, generate_excel
from parser.nfe_parser import NFeParser


# Run with: python -m scripts.generate_nfe_report
def load_nfes(directory):
    nfes = []

    for path in sorted(Path(directory).glob("*.xml")):
        parser = NFeParser(str(path))
        parser.read_nfe()

        nfe = parser.extract_data()

        if nfe:
            nfes.append(nfe)

    return nfes


def get_xmls_directory():
    directory = Path("data")
    directory.mkdir(exist_ok=True)

    if not list(directory.glob("*.xml")):
        print('No XML files found in the "data" directory.')
        print('Add XML files to the "data" directory and run the script again.')
        raise SystemExit

    return directory


if __name__ == "__main__":
    xmls_directory = get_xmls_directory()

    nfes = load_nfes(xmls_directory)
    df = generate_dataframe(nfes)

    generate_excel(nfes)

    print("Excel generated successfully!")
    print(df)
