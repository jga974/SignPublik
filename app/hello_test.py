import datetime

from fastapi import FastAPI, Header, File, UploadFile, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse, Response

import io
import os

import json

import base64
from .core.ImageUtils import creer_image_texte_manuscrit_avance
from .core.utilities import file_chunk_generator
from .core.logger import logger
from .core.utilities import get_image_size_in_points, slugify, storeImage
from app.core.signature import sign_pdf_content
from .core.conversion import convert_to, get_pdf_content
from .core.rib import extract_text_from_pdf_stream, extract_ibans, parse_french_rib
from .core.constants import SIGN_PATH

from pypdf import PdfReader
import pymupdf

from .models.files import (ImageRequest, SignBasePDFRequest, InfoSearchPDFRequest, SimplePDFPublik,
                           SignBasePDFRequestName, RudaPdfPublik)
from app.config import API_KEY, SHARED_SECRET

def verify_api_key(api_key: str = Header(...)):
    logger.debug(f"header : {api_key}")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden - Invalid API Key")
    return api_key



app = FastAPI(root_path="https://projet.ac-corse.fr/api", version="0.3",
              servers=[
                  {"url": "https://projet.ac-corse.fr/api", "description": "Production server"},
                  {"url": "https://preprod.ac-corse.fr/api", "description": "Staging server"},
                  {"url": "http://localhost:8000", "description": "Local development server"},
              ],

              )

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello, {name}!"}

@app.get("/helloSP/{name}")
async def say_hellosp(name: str, x_api_key: str = Header(...)):
    if x_api_key != SHARED_SECRET:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return {"message": f"Hello,SECURE  {name}!"}


@app.post("/image-size/")
async def get_image_size_and_store(request:  ImageRequest ): # = File(...)):
    logger.debug("Paramètres POST : %s", request)

    try:
        width, height =  get_image_size_in_points(request.image.content)
        save_result_filename = False
        # selon le parametre, on peut sauvegarder dans un chemon spécifique
        if request.store :
            save_result_filename = storeImage(request.image.content, request.image.filename)

        return {
            "width": width,
            "height": height,
            "save" : save_result_filename,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors du traitement sauvegarde de l'image : {str(e)}")


@app.post("/upload-pdf/", dependencies=[Depends(verify_api_key)])
async def upload_pdf(file: UploadFile = File(..., description="Téléversez un fichier PDF")):
    if file.content_type != "application/pdf":
        return JSONResponse(status_code=400, content={"message": "Le fichier doit être un PDF"})

    # Lire le fichier PDF uploadé
    #pdf_content = await file.read()
    pdf_content = sign_pdf(
        #input_pdf="document.pdf",
        input_pdf=file_content,
        output_pdf="document_signe.pdf",
        cert_pem="cert.pem",
        key_pem="private_key.pem",
        tsa_url="http://tsa.swisssign.net/",
        logo_path="../logo.png",
        passphrase=None  # None si clé non protégée
    )

    # Retourner le fichier PDF en tant que réponse
    return Response(content=pdf_content, media_type="application/pdf")


@app.post("/upload-and-download-pdf/")
async def upload_and_download_pdf(file: UploadFile = File(...)):
    """
    Endpoint pour accepter un fichier PDF en entrée et le renvoyer en streaming.
    :param file: Fichier PDF uploadé.
    :return: Flux de réponse contenant le fichier PDF.
    """
    # Vérifier que le fichier est un PDF
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF.")

    # Lire le contenu du fichier en streaming
    file_like = io.BytesIO(await file.read())

    # Renvoyer le fichier en streaming par morceaux
    return StreamingResponse(
        file_chunk_generator(file_like),
        media_type="application/pdf",
        headers={"Content-Disposition$": f"attachment; filename={file.filename}"}
    )


@app.post("/getInfo-PDF", dependencies=[Depends(verify_api_key)])
async def getInfo(file: InfoSearchPDFRequest):
    """
    donne l'info sur un document pdf ou word : nombre de page et endroit ou se trouve la signature dans le document
    :param file:
    :return:
    """
    logger.info(f"on est sur getinfo {file.fichier.filename}")
    try:
        if file.fichier.filename.endswith('.docx'):
            logger.info(f"Info sur fichier DOCX, on transforme  {file.fichier.filename}")
            # Décoder le contenu du fichier (supposé être en base64)
            file_bytes = base64.b64decode(file.fichier.content)

            # Utiliser BytesIO pour traiter les octets comme un fichier
            file_stream = io.BytesIO(file_bytes)

            # Enregistrer temporairement le fichier DOCX
            input_path = f"TEMP_{file.fichier.filename}"
            with open(input_path, 'wb') as f:
                f.write(file_stream.getvalue())

            # Définir le chemin de sortie pour le PDF
            output_path = file.fichier.filename.replace('.docx', '.pdf')

            # Convertir le fichier DOCX en PDF
            # SEULEMENT SUR WINDOWS OU MACOS -> convert(input_path, output_path)
            logger.info(f"Convert du fichier  {input_path} en {output_path}")
            output_path = convert_to(".", input_path)

            logger.info(f"on a converti pour calculer page {file.fichier.filename}")
            # Lire le fichier PDF généré
            with open(output_path, 'rb') as pdf_file:
                pdf_bytes = pdf_file.read()

            # Supprimer les fichiers temporaires
            os.remove(output_path)
            os.remove(input_path)
        else:
            # on a du PDF
            # Décoder les contenus base64
            logger.info(f"on a recu du PDF")
            pdf_bytes = base64.b64decode(file.fichier.content)

        # Utiliser BytesIO pour traiter les octets comme un fichier
        pdf_stream = io.BytesIO(pdf_bytes)

        # Lire le PDF avec PyPDF2
        lecteur_pdf = PdfReader(pdf_stream)

        nombre_de_pages = len(lecteur_pdf.pages)
        logger.info(f"on a {nombre_de_pages} pages")

        # taille : on prend celle de la premiere page (ou mediabox)
        cropbox = lecteur_pdf.pages[0].cropbox

        # le json avec les numeros de page pour colibris//publik dans une liste
        items = []
        # Parcourir les nombres de 1 à n
        for i in range(1, nombre_de_pages + 1):
            # ? page = pdf_stream[i]
            # Créer un dictionnaire pour chaque nombre
            item = {
                "id": str(i),
                "text": str(i)
            }
            # Ajouter le dictionnaire à la liste
            items.append(item)

        # on recherche la chaine pour avoir la position dans le PDF
        texte_recherche = file.recherche
        # ne plus utiliser le raccourci fitz à la place de pymupdf, sinon bug
        docFitzMuPDF = pymupdf.open(stream=pdf_stream, filetype="pdf")
        logger.info(f"on recherche  {file.recherche}")
        # la valeur renvoyée par defaut si le texte n'est pas trouve
        texte_coordinates = {
            "x1": -1,
            "y1": -1,
            "x2": -1,
            "y2": -1
        }
        page_text_found = -1
        for page_num in range(len(docFitzMuPDF)):
            page = docFitzMuPDF[page_num]
            logger.debug(f"Recherche dans page de taille H: {page.bound().height} W: {page.bound().width}")
            text_instances = page.search_for(texte_recherche)
            if text_instances:
                logger.info(f"Texte '{texte_recherche}' trouvé à la page {page_num + 1}")
                for inst in text_instances:
                    texte_coordinates = {
                        "x1": str(inst.x0),
                        "y1": str(inst.y0),
                        "x2": str(inst.x1),
                        "y2": str(inst.y1)
                    }
                    logger.info(  f"Coordos : x={inst.x0}, y={inst.y0}, largeur={inst.x1 - inst.x0}, hauteur={inst.y1 - inst.y0}")
                    page_text_found = page_num + 1
                    break
            else:
                logger.debug(f"Texte '{texte_recherche}' non trouvé à la page {page_num + 1}")

        # Exemple : Lire les métadonnées
        metadonnees = lecteur_pdf.metadata
        logger.info(f"on va retourner {file.fichier.filename} {nombre_de_pages} {metadonnees} {str(int(cropbox.width))} {str(int(cropbox.height))}")
        return {
            "filename": file.fichier.filename,
            "nombre_de_pages": nombre_de_pages,
            "metadonnees": metadonnees,
            "json_page" : json.dumps(items),
            "signature_page": page_text_found,
            "signature_coords": texte_coordinates,
            "pagesize": { "width" : str(int(cropbox.width)), "height":  str(int(cropbox.height))}
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la lecture des infos: {str(e)}")



@app.post("/read-rib", dependencies=[Depends(verify_api_key)])
async def get_rib_information(request: SimplePDFPublik):
    pdf_bytes = base64.b64decode(request.fichier.content)

    # Utiliser BytesIO pour traiter les octets comme un fichier
    pdf_stream = io.BytesIO(pdf_bytes)

    text = extract_text_from_pdf_stream(pdf_stream)
    logger.info(f"Text lu")
    ibans,bics = extract_ibans(text)
    logger.info(f"BICS {bics}")

    resultats = []
    for iban in ibans:
        rib = parse_french_rib(iban) if iban.startswith('FR') else None
        bic = bics[0] if bics else None
        #print(f"{iban} -> RIB  : {rib['code_guichet']} {rib['code_banque']}")
        resultats.append({'iban': iban, 'rib': rib, 'bic': bic})
    # on envoie que la premiere ligne
    if ibans :
        logger.info(f"on retourne {resultats[0]} {resultats[0]['iban']}  {resultats[0].get('rib', 'Inconnu')}****")
    else:
        logger.warn(f"pas de données iban trouvées dans le fichier")

    return resultats[0] if resultats else None


from app.core.omogen import envoi_tt_pdf_ruda, envoi_pdf_ruda_arretes, supp_doc_ruda


@app.get("/delete-ruda/{uuid}", dependencies=[Depends(verify_api_key)])
async def delete_ruda_uuid(uuid: str):
    try:
        response = supp_doc_ruda(uuid)
    except Exception as e:
        print(json.dumps({
            "statut": "erreur",
            "code_http": response.status_code,
            "message": f"EXCEPTION : Échec suppression document {uuid}.",
            "details": response.text
        }, indent=2, ensure_ascii=False))

    if response.status_code != 200 and response.status_code != 201 :
        return json.dumps({
            "statut": "erreur",
            "code_http": response.status_code,
            "message": f"Échec de suppression du document {uuid}.",
            "details": response.text
        }, indent=2, ensure_ascii=False)

    return response.json()

@app.post("/send-ruda", dependencies=[Depends(verify_api_key)])
async def send_ruda_teletravail(parametres: RudaPdfPublik):
    pdf_bytes = base64.b64decode(parametres.fichier.content)

    # Utiliser BytesIO pour traiter les octets comme un fichier
    pdf_stream = io.BytesIO(pdf_bytes)

    try :
     response = envoi_tt_pdf_ruda(pdf_stream,parametres.numen, parametres.libelle)
    except Exception as e:
        print(json.dumps({
            "statut": "erreur",
            "code_http": response.status_code,
            "message": "EXCEPTION : Échec de l'envoi du document.",
            "details": response.text
        }, indent=2, ensure_ascii=False))

    print(f"{response.status_code} {response}")
    if response.status_code != 200 and response.status_code != 201 :
        return json.dumps({
            "statut": "erreur",
            "code_http": response.status_code,
            "message": "Échec de l'envoi du document.",
            "details": response.text
        }, indent=2, ensure_ascii=False)

    try:
        data = response.json()
        logger.debug(data)
    except UnicodeDecodeError as e:
        logger.error("Erreur de décodage : mauvaise encodage (UTF-8 attendu).")
        logger.error("Tu peux essayer de forcer response.encoding ou lire response.content brut.")


    return response.json()

from app.core.omogen import envoi_pdf_ruda
@app.post("/send-ruda-pdf-arrete", dependencies=[Depends(verify_api_key)])
async def send_ruda_pdf_arrete(parametres: RudaPdfPublik):

    logger.debug(parametres.nature)

    if parametres.nature is None or not parametres.nature :
        raise HTTPException(
            status_code=400,
            detail="Le paramètre 'nature' est obligatoire et ne peut pas être nul."
        )

    pdf_bytes = base64.b64decode(parametres.fichier.content)

    # Utiliser BytesIO pour traiter les octets comme un fichier
    pdf_stream = io.BytesIO(pdf_bytes)

    try :
     response = envoi_pdf_ruda_arretes(pdf_stream,parametres.numen, parametres.libelle, parametres.nature)
    except Exception as e:
        print(json.dumps({
            "statut": "erreur",
            "code_http": response.status_code,
            "message": "EXCEPTION : Échec de l'envoi du document.",
            "details": response.text
        }, indent=2, ensure_ascii=False))

    print(f"{response.status_code} {response}")
    if response.status_code != 200 and response.status_code != 201 :
        erreur_json =  json.dumps({
            "statut": "erreur",
            "code_http": response.status_code,
            "message": "Échec de l'envoi du document.",
            "details": response.text
        }, indent=2, ensure_ascii=False)
        logger.error(f"erreur appel send ruda arrete {parametres.nature} pour {parametres.numen}")
        logger.error(erreur_json)
        return erreur_json

    try:
        data = response.json()
        logger.debug(data)
    except UnicodeDecodeError as e:
        logger.error("Erreur de décodage : mauvaise encodage (UTF-8 attendu).")
        logger.error("Tu peux essayer de forcer response.encoding ou lire response.content brut.")


    return response.json()

@app.post("/sign-simple-name", dependencies=[Depends(verify_api_key)])
async def sign_pdf_name_image(request: SignBasePDFRequestName):
    try:
        logger.info(f"simple sign name {request.filedef1.filename} for {request.signername} et {request.signermail} ")

        pdf_content = get_pdf_content(request.filedef1.filename, request.filedef1.content)

        try:
            # emplacement de la signature : transfo de string a tuple
            box_tuple = tuple(int(val.strip()) for val in request.signature_box.split(','))
        except ValueError:
            logger.info(f"Erreur conversion signax_box valeur par defaut de box_tuple pour {request.signature_box}")
            box_tuple = (350, 120, 550, 220)  # (120, 520, 20, 300)

        try:
            # Convertir la chaîne en entier le maximum entre le nombre et 0
            page_a_signer = max(int(request.page) - 1, 0)
        except ValueError:
            logger.info(f"valeur par defaut de page a signer {request.page}")
            #  premiere page 0 si la conversion échoue
            page_a_signer = 0

        # le fichier signature PNG
        """ ancienne version 
        signature_img_file = creer_signature_png_transparente(texte=request.signername,
                                                       nom_fichier_sortie=slugify(request.signername)+'.png',
                                                              taille_police=16,
                                                              taille_image=(113, 85))
                                                              # OK taille_image=(250, 170))
        """
        nom_fichier_img = f"{slugify(request.signername)}.png"
        signature_img_file = creer_image_texte_manuscrit_avance(
            texte=request.signername,
            taille_image=(226, 170),
            nom_fichier=os.path.join(SIGN_PATH, nom_fichier_img),
            horodatage=datetime.datetime.now().strftime("le %d/%m/%Y à %Hh%M:%S")
        )

        logger.info(f"on signe avec page : {page_a_signer}  et {box_tuple} et image {signature_img_file}")

        # la signature  electronique du flux PDF
        fichier_signe = sign_pdf_content(pdf_content, box_tuple,
                                         page_a_signer,
                                         signature_img_file,
                                         mail_signer = request.signermail)

        logger.debug(f"on retourne la réponse {fichier_signe}")

        # Retourner le PDF signé
        return StreamingResponse(
            file_chunk_generator(fichier_signe),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=signed_{request.filedef1.filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la signature SIMPLE: {str(e)}")




@app.post("/sign-basePDF64", dependencies=[Depends(verify_api_key)])
async def sign_pdf_base64_ok(request: SignBasePDFRequest):
    try:
        logger.info(f"Traitement du fichier  {request.filedef1.filename}")

        # on transforme les docx en PDF
        if request.filedef1.filename.endswith('.docx'):
            logger.info(f"fichier DOCX, on transforme  {request.filedef1.filename}")
            # Décoder le contenu du fichier (supposé être en base64)
            file_bytes = base64.b64decode(request.filedef1.content)

            # Utiliser BytesIO pour traiter les octets comme un fichier
            file_stream = io.BytesIO(file_bytes)

            # Enregistrer temporairement le fichier DOCX
            input_path = f"TEMP_{request.filedef1.filename}"
            with open(input_path, 'wb') as f:
                f.write(file_stream.getvalue())

            # Définir le chemin de sortie pour le PDF
            output_path = request.filedef1.filename.replace('.docx', '.pdf')

            # Convertir le fichier DOCX en PDF
            # SEULEMENT SUR WINDOWS OU MACOS -> convert(input_path, output_path)
            logger.info(f"Convert du fichier  {input_path} en {output_path}")
            output_path = convert_to(".", input_path)

            logger.info(f"on a converti  {request.filedef1.filename}")
            # Lire le fichier PDF généré
            with open(output_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            logger.info(f"on a converti  {request.filedef1.filename}")
            # Supprimer les fichiers temporaires
            os.remove(input_path)
            os.remove(output_path)
        else:
            # on a du PDF
            # Décoder les contenus base64
            pdf_content = base64.b64decode(request.filedef1.content)
            print("on a decode le base 64")

        try:
            # emplacement de la signature : transfo de string a tuple
            box_tuple = tuple(int(val.strip()) for val in request.signature_box.split(','))
        except ValueError:
            logger.info(f"Erreur conversion signax_box valeur par defaut de box_tuple pour {request.signature_box}")
            box_tuple = (350, 120, 550, 220) #(120, 520, 20, 300)

        
        try:
            # Convertir la chaîne en entier le maximum entre le nombre et 0
            page_a_signer = max(int(request.page) - 1, 0)
        except ValueError:
            logger.info(f"valeur par defaut de page a signer {request.page}")
            #  premiere page 0 si la conversion échoue
            page_a_signer = 0

        # le fichier signature PNG
        signature_img_file = os.path.join(SIGN_PATH, "signature_signe_noBG.png")

        logger.info(f"on signe avec page : {page_a_signer}  et {box_tuple} et image {signature_img_file}")

        # la signature  electronique du flux PDF
        fichier_signe = sign_pdf_content(pdf_content, box_tuple, page_a_signer, signature_img_file)

        logger.debug(f"on retourne la réponse {fichier_signe}")

        # Retourner le PDF signé
        return StreamingResponse(
            file_chunk_generator(fichier_signe),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=signed_{request.filedef1.filename}"}
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la signature: {str(e)}")


#@app.post("/sign-pdf/")
async def sign_pdf(pdf_file: UploadFile = File(...)):
    # Vérifier que le fichier est un PDF
    if pdf_file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Le fichier doit être un PDF.")

    # Vérifier que le fichier n'est pas vide
    if not pdf_file.filename:
        raise HTTPException(status_code=400, detail="Le nom du fichier est manquant.")

    try:
        # Lire le fichier PDF
        pdf_content = await pdf_file.read()

        file_like = sign_pdf_content(pdf_content, (350, 120, 550, 220), 0)

        logger.error("on a recu l retour fonction ")

        # Retourner le PDF signé
        return StreamingResponse(
            app.core.utilities.file_chunk_generator(file_like),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=signed_{pdf_file.filename}"}
        )

    except Exception as e:
        # exc_type, exc_obj, exc_tb = sys.exc_info()
        # fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        # print(exc_type, fname, exc_tb.tb_lineno)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la signature: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    print(pymupdf.__doc__)
    uvicorn.run(hello_test.app, host="0.0.0.0", port=8000, log_level="trace")
