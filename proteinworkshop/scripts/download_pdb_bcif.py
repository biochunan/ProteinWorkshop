# Code source: Patrick Kunzmann
# License: BSD 3 clause

from pathlib import Path

from proteinworkshop.constants import DATA_PATH
from proteinworkshop.datasets.utils import (
    download_pdb_bcif as _download_pdb_bcif,
)


def download_pdb_bcif(create_tar: bool = True):
    _download_pdb_bcif(Path(DATA_PATH) / "pdb", create_tar=create_tar)

if __name__ == "__main__":
    download_pdb_bcif()
