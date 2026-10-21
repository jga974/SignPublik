import subprocess
from typing import Any

from app.core.logger import logger
import sys, os, io
import base64


def get_pdf_content(filename : str, base64content : str) :
    # on transforme les docx en PDF au besoin
    if filename.endswith('.docx'):
        logger.info(f"fichier DOCX dans get_pdf_content, on transforme  {filename}")
        # Décoder le contenu du fichier (supposé être en base64)
        file_bytes = base64.b64decode(base64content)

        # Utiliser BytesIO pour traiter les octets comme un fichier
        file_stream = io.BytesIO(file_bytes)

        # Enregistrer temporairement le fichier DOCX
        input_path = f"TEMP_{filename}"
        with open(input_path, 'wb') as f:
            f.write(file_stream.getvalue())

        # Définir le chemin de sortie pour le PDF
        output_path = filename.replace('.docx', '.pdf')

        # Convertir le fichier DOCX en PDF
        # SEULEMENT SUR WINDOWS OU MACOS -> convert(input_path, output_path)
        logger.info(f"Convert du fichier  {input_path} en {output_path}")
        output_path = convert_to(".", input_path)

        logger.info(f"on a converti  {filename}")
        # Lire le fichier PDF généré
        with open(output_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()
        logger.info(f"on a converti  {filename}")
        # Supprimer les fichiers temporaires
        os.remove(input_path)
        os.remove(output_path)
    else:
        # on a du PDF
        # Décoder les contenus base64
        pdf_content = base64.b64decode(base64content)
        logger.info(f"n a decode le base 64 de {filename}")
    return pdf_content


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
