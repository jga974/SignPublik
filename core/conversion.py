import subprocess
from typing import Any

from core.logger import logger
import sys

def convert_to(folder: str, source: str, timeout: float = None) -> Any:
    args = [libreoffice_exec(), '--headless', '--convert-to', 'pdf', '--outdir', folder, source]
    logger.info(f"subprocess args = {args}")
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                             check=True, env={"HOME": '/opt/flask'})
    logger.info("process retourne")
    logger.info(process.stdout)
    #filename = re.search('-> (.*?) using filter', process.stdout.decode())
    filename = source.replace('.docx', '.pdf')
    logger.info(f"filename du fichier converti  = {filename}")
    if filename is None:
        raise LibreOfficeError(process.stdout.decode())
    else:
        logger.info(f"on a réussi a créer {filename}")
        return filename


def libreoffice_exec():
    # TODO: Provide support for more platforms
    if sys.platform == 'darwin':
        return '/Applications/LibreOffice.app/Contents/MacOS/soffice'
    if sys.platform == 'linux':
        return '/usr/bin/libreoffice'

    return 'libreoffice'

class LibreOfficeError(Exception):
    def __init__(self, output):
        self.output = output
