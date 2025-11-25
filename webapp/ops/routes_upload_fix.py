import logging
import os
import time
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g, send_from_directory
from flask_jwt_extended import get_jwt_identity
from werkzeug.utils import secure_filename

from webapp.auth.jwt_auth import token_required, role_required
from storage.database_unified import (
    db_session,
    UserSession,
    Message,
    Chat,
    Document,
    end_session
)
from bot.operator import ACTIVE_OPERATOR_SESSIONS, send_rating_request
from services.crm_client import log_operator_action
from utils.rate_limit import web_rate_limit
from sqlalchemy import func
from sqlalchemy.exc import OperationalError, DisconnectionError

from config import DOCUMENTS_PATH
from bot.telegram_bot import bot

# Imports for RAG indexing
from retrieval.doc_parser import parse_document
from retrieval.store import store_document_chunks

logger = logging.getLogger(__name__)

ops_bp = Blueprint('ops', __name__)

def retry_db_operation(operation, max_retries=3, delay=1):
    """
    Выполняет операцию с базой данных с повторными попытками при ошибках соединения.
    
    Args:
        operation: Функция для выполнения
        max_retries: Максимальное количество попыток
        delay: Задержка между попытками в секундах
    
    Returns:
        Результат операции или None при неудаче
    """
    for attempt in range(max_retries):
        try:
            return operation()
        except (OperationalError, DisconnectionError) as e:
            logger.warning(f"Database connection error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))  # Увеличиваем задержку с каждой попыткой
                continue
            else:
                logger.error(f"All {max_retries} database retry attempts failed")
                raise
        except Exception as e:
            logger.error(f"Non-retryable database error: {e}")
            raise

@ops_bp.route('/knowledge-base/upload', methods=['POST'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def upload_document():
    """
    Загрузка документа с улучшенной обработкой ошибок и retry логикой.
    """
    db = None
    dest_path = None
    file_saved = False
    
    try:
        # Валидация файла
        if 'file' not in request.files:
            logger.warning("Upload attempt with no file part.")
            return jsonify({'message': 'No file part'}), 400

        uploaded_file = request.files['file']
        if not uploaded_file.filename:
            logger.warning("Upload attempt with no selected file (empty filename).")
            return jsonify({'message': 'No selected file'}), 400

        filename = secure_filename(uploaded_file.filename)
        if not filename:
            logger.warning(f"Upload attempt with an invalid/empty secured filename from original: {uploaded_file.filename}")
            return jsonify({'message': 'Invalid filename after securing.'}), 400

        # Подготовка пути для сохранения
        os.makedirs(DOCUMENTS_PATH, exist_ok=True)
        dest_path = os.path.join(DOCUMENTS_PATH, filename)
        
        abs_dest_path = os.path.abspath(dest_path)
        abs_documents_path = os.path.abspath(DOCUMENTS_PATH)
        if not abs_dest_path.startswith(abs_documents_path):
            logger.error(
                f"Security alert: Attempt to save file outside designated documents directory. "
                f"Path: {abs_dest_path}, Base: {abs_documents_path}"
            )
            return jsonify({'error': 'Invalid file path for saving. Directory traversal attempt?'}), 400
        
        # Сохранение файла
        if os.path.exists(dest_path):
            logger.info(f"File '{filename}' already exists at {dest_path}. It will be overwritten.")

        uploaded_file.save(dest_path)
        file_saved = True
        logger.info(f"File '{filename}' saved to {dest_path}.")

        uploader_id = g.user['sub']
        logger.info(f"User {uploader_id} starts upload of file '{filename}' to '{dest_path}'")

        # Попытка записи в базу данных с retry логикой
        doc_to_return = None
        db_success = False
        
        def db_operation():
            nonlocal doc_to_return, db_success
            with db_session() as db:
                try:
                    existing_doc = db.query(Document).filter(Document.path == dest_path).first()
                    if existing_doc:
                        logger.info(f"Updating existing document record for path {dest_path}")
                        existing_doc.name = filename
                        existing_doc.description = request.form.get('description', existing_doc.description)
                        existing_doc.uploaded_by = uploader_id
                        existing_doc.uploaded_at = datetime.utcnow()
                        doc_to_return = existing_doc
                    else:
                        logger.info(f"Creating new document record for path {dest_path}")
                        new_doc = Document(
                            name=filename,
                            path=dest_path,
                            description=request.form.get('description', ''),
                            uploaded_by=uploader_id,
                            uploaded_at=datetime.utcnow()
                        )
                        db.add(new_doc)
                        doc_to_return = new_doc
                    
                    db.commit()
                    db.refresh(doc_to_return)
                    db_success = True
                    logger.info(
                        f"Document record for '{filename}' (id: {doc_to_return.id}) "
                        f"saved/updated in DB by user {uploader_id}."
                    )
                    return doc_to_return
                finally:
                    pass

        try:
            retry_db_operation(db_operation)
        except Exception as db_error:
            logger.error(f"Failed to save document to database after retries: {db_error}")
            # Создаем фиктивный объект для ответа, если БД недоступна
            doc_to_return = type('Document', (), {
                'id': 'temp',
                'name': filename,
                'path': dest_path
            })()

        # Индексация документа (независимо от успеха БД операции)
        indexing_success = False
        try:
            logger.info(f"Parsing and indexing document: {dest_path}")
            content = parse_document(dest_path)
            if content:
                store_document_chunks(content, dest_path)
                indexing_success = True
                logger.info(f"Successfully indexed {len(content)} chunks for {dest_path}")
            else:
                logger.warning(f"No content parsed from {dest_path}, skipping indexing.")
        except Exception as idx_err:
            logger.error(f"Indexing failed for {dest_path}: {idx_err}", exc_info=True)

        # Формирование ответа
        response_data = {
            'name': doc_to_return.name,
            'path': doc_to_return.path,
            'file_saved': file_saved,
            'db_saved': db_success,
            'indexed': indexing_success
        }
        
        if hasattr(doc_to_return, 'id') and doc_to_return.id != 'temp':
            response_data['id'] = doc_to_return.id

        if db_success and indexing_success:
            response_data['message'] = 'Document uploaded and indexed successfully'
            return jsonify(response_data), 201
        elif file_saved and indexing_success:
            response_data['message'] = 'Document uploaded and indexed, but database save failed'
            response_data['warning'] = 'Document may not appear in web interface until database is restored'
            return jsonify(response_data), 201
        elif file_saved:
            response_data['message'] = 'Document uploaded but indexing failed'
            response_data['error'] = 'Document will not be searchable by bot'
            return jsonify(response_data), 500
        else:
            return jsonify({'message': 'Upload failed completely'}), 500

    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        
        # Если файл был сохранен, но произошла ошибка, попробуем хотя бы проиндексировать
        if file_saved and dest_path:
            try:
                logger.info(f"Attempting emergency indexing for {dest_path}")
                content = parse_document(dest_path)
                if content:
                    store_document_chunks(content, dest_path)
                    logger.info(f"Emergency indexing successful for {dest_path}")
                    return jsonify({
                        'message': 'Upload partially successful',
                        'warning': 'File saved and indexed, but database error occurred',
                        'name': filename,
                        'path': dest_path
                    }), 201
            except Exception as emergency_err:
                logger.error(f"Emergency indexing also failed: {emergency_err}")
        
        return jsonify({'message': 'Upload failed', 'error': str(e)}), 500

@ops_bp.route('/knowledge-base/reindex', methods=['POST'])
@token_required
@role_required(['admin'])
@web_rate_limit
def reindex_documents():
    """
    Принудительная переиндексация всех документов.
    """
    try:
        if not os.path.exists(DOCUMENTS_PATH):
            return jsonify({'message': 'Documents directory not found'}), 404
        
        files = os.listdir(DOCUMENTS_PATH)
        indexed_count = 0
        failed_count = 0
        
        for filename in files:
            file_path = os.path.join(DOCUMENTS_PATH, filename)
            if os.path.isfile(file_path):
                try:
                    logger.info(f"Reindexing document: {file_path}")
                    content = parse_document(file_path)
                    if content:
                        store_document_chunks(content, file_path)
                        indexed_count += 1
                        logger.info(f"Successfully reindexed {file_path}")
                    else:
                        logger.warning(f"No content parsed from {file_path}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Failed to reindex {file_path}: {e}")
                    failed_count += 1
        
        return jsonify({
            'message': 'Reindexing completed',
            'total_files': len(files),
            'indexed': indexed_count,
            'failed': failed_count
        }), 200
        
    except Exception as e:
        logger.error(f"Error during reindexing: {e}", exc_info=True)
        return jsonify({'message': 'Reindexing failed', 'error': str(e)}), 500

