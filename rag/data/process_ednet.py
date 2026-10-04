import zipfile
from pathlib import Path

ZIP_PATH = Path("rag/data/raw/ednet/EdNet-KT1.zip")
OUTPUT_DIR = Path("rag/data/processed/ednet_sample")

MAX_STUDENTS = 1000


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Opening EdNet ZIP...")
    
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        csv_files = [
            name for name in z.namelist()
            if name.endswith(".csv")
        ]

        print(f"Total CSV files found: {len(csv_files)}")

        selected_files = csv_files[:MAX_STUDENTS]

        print(f"Extracting {len(selected_files)} student files...")

        for i, file_name in enumerate(selected_files, start=1):
            z.extract(file_name, OUTPUT_DIR)

            if i % 100 == 0:
                print(f"Extracted {i}/{len(selected_files)} files")

    print("EdNet sample extraction completed!")


if __name__ == "__main__":
    main()