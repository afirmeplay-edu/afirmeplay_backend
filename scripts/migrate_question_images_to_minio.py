"""
Migra imagens de questões de base64 (no banco) para MinIO.

- Localiza questões que tenham question.images com campo "data" (base64).
- Faz upload de cada imagem para o bucket question-images no MinIO.
- Atualiza question.images (remove "data", adiciona minio_bucket e minio_object_name).
- Substitui no formatted_text e formatted_solution o src base64 por:
  /questions/{question_id}/images/{image_id}

Idempotente: se o objeto já existir no MinIO, não reenvia.
Commit em lotes pequenos. Log de progresso.

Uso:
    cd c:\\Users\\Artur Calderon\\Documents\\Programming\\innovaplay_backend
    python scripts/migrate_question_images_to_minio.py
"""

import os
import sys
import re
import base64
import logging

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def mime_to_ext(mime):
    m = (mime or "").lower()
    if "png" in m:
        return "png"
    if "jpeg" in m or "jpg" in m:
        return "jpg"
    if "gif" in m:
        return "gif"
    if "webp" in m:
        return "webp"
    return "png"


def run():
    from app import create_app
    from app.models.question import Question
    from app import db
    from app.services.storage.minio_service import MinIOService

    app = create_app()
    with app.app_context():
        minio = MinIOService()
        bucket_name = MinIOService.BUCKETS["QUESTION_IMAGES"]

        # Questões com pelo menos uma imagem que tenha "data" (base64)
        questions = Question.query.filter(Question.images.isnot(None)).all()
        to_migrate = [q for q in questions if q.images and any(
            isinstance(img, dict) and img.get("data") for img in q.images
        )]
        total = len(to_migrate)
        logger.info("Questões com imagens em base64: %s (de %s com images)", total, len(questions))
        if total == 0:
            logger.info("Nada a migrar.")
            return

        processed = 0
        errors = 0
        for i, question in enumerate(to_migrate):
            try:
                images = list(question.images or [])
                new_images = []
                formatted_text = question.formatted_text or ""
                formatted_solution = question.formatted_solution or ""

                for img in images:
                    if not isinstance(img, dict):
                        new_images.append(img)
                        continue
                    data_b64 = img.get("data")
                    if not data_b64:
                        new_images.append(img)
                        continue

                    image_id = img.get("id")
                    if not image_id:
                        new_images.append(img)
                        continue

                    try:
                        image_bytes = base64.b64decode(data_b64)
                    except Exception as e:
                        logger.warning("Questão %s imagem %s: decode base64 falhou: %s", question.id, image_id, e)
                        new_images.append(img)
                        continue

                    mime = img.get("type") or "image/png"
                    ext = mime_to_ext(mime)
                    image_name = f"{image_id}.{ext}"
                    object_name = f"{question.id}/{image_name}"

                    if minio.file_exists(bucket_name, object_name):
                        logger.debug("Já existe no MinIO: %s", object_name)
                    else:
                        result = minio.upload_question_image(question.id, image_bytes, image_name)
                        if not result:
                            logger.warning("Upload falhou questão %s imagem %s", question.id, image_id)
                            new_images.append(img)
                            continue

                    new_meta = {
                        "id": image_id,
                        "type": mime,
                        "width": img.get("width"),
                        "height": img.get("height"),
                        "minio_bucket": bucket_name,
                        "minio_object_name": object_name,
                    }
                    new_images.append(new_meta)

                    old_src = f"data:{mime};base64,{data_b64}"
                    api_url = f"/questions/{question.id}/images/{image_id}"
                    if old_src in formatted_text:
                        formatted_text = formatted_text.replace(old_src, api_url, 1)
                    if old_src in formatted_solution:
                        formatted_solution = formatted_solution.replace(old_src, api_url, 1)

                question.images = new_images
                question.formatted_text = formatted_text
                question.formatted_solution = formatted_solution
                processed += 1
                if (i + 1) % BATCH_SIZE == 0:
                    db.session.commit()
                    logger.info("Commit lote: %s questões processadas", i + 1)

            except Exception as e:
                errors += 1
                logger.exception("Erro na questão %s: %s", question.id, e)
                db.session.rollback()

        if processed > 0 and (len(to_migrate) % BATCH_SIZE != 0 or len(to_migrate) == 0):
            db.session.commit()
        logger.info("Concluído: %s questões migradas, %s erros.", processed, errors)


if __name__ == "__main__":
    run()
