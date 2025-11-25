# Full new content for /home/ubuntu/bot_project/Bot_V5_0_0/webapp/ops/routes.py

import logging
import os
import time
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, g, send_from_directory
from flask_jwt_extended import get_jwt_identity # get_jwt_identity is imported but not directly used in this file. g.user['sub'] is used.
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
from bot.operator import ACTIVE_OPERATOR_SESSIONS, send_rating_request # Moved import
from services.crm_client import log_operator_action
from utils.rate_limit import web_rate_limit
from sqlalchemy import func
from sqlalchemy.exc import OperationalError, DisconnectionError

from config import DOCUMENTS_PATH
from bot.telegram_bot import bot # Moved import

# Imports for RAG indexing (Problem 2)
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

@ops_bp.route('/active-chats')
@token_required
@role_required(['admin', 'operator'])
def get_active_chats():
    try:
        with db_session() as db:
            day_ago = int((datetime.now() - timedelta(days=1)).timestamp())
            subquery = db.query(
                Message.chat_id,
                func.max(Message.timestamp).label('last_message_time')
            ).group_by(Message.chat_id).subquery()
            active_chats_query = db.query(Chat).join(
                subquery, Chat.id == subquery.c.chat_id
            ).filter(
                subquery.c.last_message_time >= day_ago,
                Chat.status == 'active'  # Original filter
            )
            active_chats = active_chats_query.all()
            
            result = []
            for chat_obj in active_chats:
                last_user_message = db.query(Message).filter(
                    Message.chat_id == chat_obj.id
                ).order_by(Message.timestamp.desc()).first()
                
                user_info = {
                    'id': chat_obj.user_id,
                    'name': f"Пользователь {chat_obj.user_id}"
                }
                
                result.append({
                    'id': chat_obj.id,
                    'user': user_info,
                    'last_message': last_user_message.message_text if last_user_message else '',
                    'last_activity': chat_obj.updated_at.isoformat() if chat_obj.updated_at else None,
                    'status': chat_obj.status,
                    'operator_id': chat_obj.operator_id
                })
            
            final_waiting_chats = [c for c in result if c['status'] == 'waiting']
            final_active_chats = [c for c in result if c['status'] == 'active' and c.get('operator_id')]

            return jsonify({
                'waiting': final_waiting_chats,
                'active': final_active_chats
            })
    except Exception as e:
        logger.error(f"Error getting active chats: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get active chats', 'details': str(e)}), 500

@ops_bp.route('/active-chats-old', methods=['GET'])  # Legacy handler
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def get_active_chats_old():
    try:
        with db_session() as db:
            active_sessions = db.query(UserSession).filter(
                UserSession.end_time.is_(None),
                UserSession.last_escalation_time.isnot(None)
            ).all()
            
            chats_list = []
            for session in active_sessions:
                if session.user_id in ACTIVE_OPERATOR_SESSIONS:
                    continue
                
                last_message = db.query(Message).filter(
                    Message.session_id == session.id
                ).order_by(Message.timestamp.desc()).first()
                
                if last_message:
                    chats_list.append({
                        'session_id': session.id,
                        'user_id': session.user_id,
                        'start_time': session.start_time.isoformat() if session.start_time else None,
                        'last_escalation_time': session.last_escalation_time.isoformat() if session.last_escalation_time else None,
                        'interface_type': session.interface_type,
                        'last_message': {
                            'text': last_message.message_text,
                            'timestamp': last_message.timestamp.isoformat() if last_message.timestamp else None
                        }
                    })
            
            return jsonify({
                'chats': chats_list,
                'count': len(chats_list)
            }), 200
    except Exception as e:
        logger.error(f"Error in get_active_chats_old: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get old active chats', 'details': str(e)}), 500

@ops_bp.route('/my-chats', methods=['GET'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def get_my_chats():
    db = None
    try:
        operator_id = g.user['sub']
        my_sessions_data = {user_id: data for user_id, data in ACTIVE_OPERATOR_SESSIONS.items()
                            if data.get("operator_id") == operator_id}
        
        with db_session() as db:
            chats_list = []
            for user_id, data in my_sessions_data.items():
                session_id = data.get("session_id")
                session = db.query(UserSession).filter(UserSession.id == session_id).first()
                
                if session:
                    last_message = db.query(Message).filter(
                        Message.session_id == session_id
                    ).order_by(Message.timestamp.desc()).first()
                    
                    chats_list.append({
                        'session_id': session_id,
                        'user_id': user_id,
                        'start_time': session.start_time.isoformat() if session.start_time else None,
                        'last_escalation_time': session.last_escalation_time.isoformat() if session.last_escalation_time else None,
                        'interface_type': session.interface_type,
                        'last_message': {
                            'text': last_message.message_text if last_message else None,
                            'timestamp': last_message.timestamp.isoformat() if last_message and last_message.timestamp else None
                        }
                    })
        
        return jsonify({
            'chats': chats_list,
            'count': len(chats_list)
        }), 200
    except Exception as e:
        logger.error(f"Error in get_my_chats: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get my chats', 'details': str(e)}), 500
    finally:
        pass

@ops_bp.route('/chat/<int:user_id>/messages', methods=['GET'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def get_chat_messages(user_id):
    db = None
    try:
        operator_id = g.user['sub']
        if user_id not in ACTIVE_OPERATOR_SESSIONS or ACTIVE_OPERATOR_SESSIONS[user_id].get("operator_id") != operator_id:
            return jsonify({'message': 'Chat not assigned to you'}), 403
        
        session_id = ACTIVE_OPERATOR_SESSIONS[user_id].get("session_id")
        with db_session() as db:
            messages_query = db.query(Message).filter(
                Message.session_id == session_id
            ).order_by(Message.timestamp).all()
        
        message_list = []
        for msg in messages_query:
            message_list.append({
                'id': msg.id,
                'user_id': msg.user_id,
                'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                'message_text': msg.message_text,
                'bot_response': msg.bot_response,
                'confidence_score': msg.confidence_score
            })
        
        return jsonify({
            'session_id': session_id,
            'user_id': user_id,
            'messages': message_list
        }), 200
    except Exception as e:
        logger.error(f"Error in get_chat_messages for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get chat messages', 'details': str(e)}), 500
    finally:
        pass

@ops_bp.route('/chat/<int:user_id>/accept', methods=['POST'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def accept_chat(user_id):
    db = None
    try:
        operator_id = g.user['sub']
        if user_id in ACTIVE_OPERATOR_SESSIONS:
            return jsonify({'message': 'Chat already accepted by another operator'}), 409
        
        with db_session() as db:
            session = db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.end_time.is_(None)
            ).first()
        
        if not session:
            return jsonify({'message': 'Active session not found'}), 404
        
        ACTIVE_OPERATOR_SESSIONS[user_id] = {
            "operator_id": operator_id,
            "session_id": session.id
        }
        log_operator_action(operator_id, "ACCEPT", user_id)
        return jsonify({
            'message': 'Chat accepted successfully',
            'session_id': session.id,
            'user_id': user_id
        }), 200
    except Exception as e:
        logger.error(f"Error accepting chat for user {user_id}: {e}", exc_info=True)
        if db: db.rollback()
        return jsonify({'error': 'Failed to accept chat', 'details': str(e)}), 500
    finally:
        pass

@ops_bp.route('/chat/<int:user_id>/message', methods=['POST'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def send_message_to_user(user_id):
    try:
        operator_id = g.user['sub']
        if user_id not in ACTIVE_OPERATOR_SESSIONS or ACTIVE_OPERATOR_SESSIONS[user_id].get("operator_id") != operator_id:
            return jsonify({'message': 'Chat not assigned to you'}), 403
        
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'message': 'Missing message text'}), 400
        
        message_text = data['text']
        
        bot.send_message(
            chat_id=user_id,
            text=f"Оператор: {message_text}"
        )
        log_operator_action(operator_id, "MESSAGE", user_id, detail=message_text)
        return jsonify({
            'message': 'Message sent successfully',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error sending message to user {user_id}: {e}", exc_info=True)
        return jsonify({'message': f'Error sending message: {str(e)}', 'details': str(e)}), 500

@ops_bp.route('/chat/<int:user_id>/end', methods=['POST'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def end_chat_with_user(user_id):
    db = None
    try:
        operator_id = g.user['sub']
        if user_id not in ACTIVE_OPERATOR_SESSIONS or ACTIVE_OPERATOR_SESSIONS[user_id].get("operator_id") != operator_id:
            return jsonify({'message': 'Chat not assigned to you'}), 403
        
        session_id = ACTIVE_OPERATOR_SESSIONS[user_id].get("session_id")
        with db_session() as db:
            end_session(db, session_id)
        
        if user_id in ACTIVE_OPERATOR_SESSIONS:
            del ACTIVE_OPERATOR_SESSIONS[user_id]
        
        class Context:
            def __init__(self, bot_instance):
                self.bot = bot_instance
        
        context = Context(bot)
        send_rating_request(context, user_id)
        
        log_operator_action(operator_id, "END_SESSION", user_id)
        return jsonify({
            'message': 'Chat ended successfully',
            'session_id': session_id,
            'user_id': user_id
        }), 200
    except Exception as e:
        logger.error(f"Error ending chat with user {user_id}: {e}", exc_info=True)
        if db: db.rollback()
        return jsonify({'message': f'Error ending chat: {str(e)}', 'details': str(e)}), 500
    finally:
        pass

# ============================
#  База знаний (Knowledge Base)
# ============================

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

@ops_bp.route('/knowledge-base', methods=['GET'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def list_documents():
    db = None
    try:
        with db_session() as db:
            # Получаем ID оператора из контекста JWT
            operator_id = g.user['sub']

            # Problem 3: Dynamic Sync for Files in DOCUMENTS_PATH (Variant B)
            synced_paths = set()
            try:
                if not os.path.exists(DOCUMENTS_PATH):
                    os.makedirs(DOCUMENTS_PATH)
                    logger.info(f"Created documents directory: {DOCUMENTS_PATH}")
                
                current_files_in_dir = os.listdir(DOCUMENTS_PATH)
                for fname in current_files_in_dir:
                    p = os.path.join(DOCUMENTS_PATH, fname)
                    abs_p = os.path.abspath(p)
                    abs_documents_path = os.path.abspath(DOCUMENTS_PATH)

                    if not abs_p.startswith(abs_documents_path):
                        logger.warning(f"Skipping file outside designated directory during sync: {p}")
                        continue  # Security: ensure we are only looking inside DOCUMENTS_PATH

                    if os.path.isfile(p):
                        synced_paths.add(p)
                        if not db.query(Document).filter(Document.path == p).first():
                            logger.info(f"Found new file '{fname}' in directory, adding to DB.")
                            doc_name = os.path.basename(p)
                            new_doc_from_fs = Document(
                                name=doc_name,
                                path=p,
                                description='Autodetected from filesystem',
                                uploaded_by=operator_id,  # ← используем операторский ID вместо current_user
                                uploaded_at=datetime.fromtimestamp(os.path.getmtime(p))
                            )
                            db.add(new_doc_from_fs)
                db.commit()  # Commit any newly added documents from filesystem scan
                logger.info(f"Filesystem sync complete. Found {len(synced_paths)} files in {DOCUMENTS_PATH}.")

                # Also, remove DB entries for files that no longer exist on disk
                all_db_docs = db.query(Document.id, Document.path).all()
                for doc_id, doc_path in all_db_docs:
                    if doc_path not in synced_paths:
                        logger.info(f"Document path '{doc_path}' (ID: {doc_id}) not found in filesystem. Removing from DB.")
                        doc_to_delete = db.query(Document).get(doc_id)
                        if doc_to_delete:
                            db.delete(doc_to_delete)
                db.commit()  # Commit deletions

            except Exception as sync_err:
                logger.error(f"Error during document directory sync: {sync_err}", exc_info=True)
                if db:
                    db.rollback()  # Rollback sync changes on error, but proceed to list what's in DB

            # Proceed to list documents from DB (now synced)
            docs_query = db.query(Document).order_by(Document.uploaded_at.desc()).all()
            result = []
            for d in docs_query:
                file_name_only, file_extension = os.path.splitext(d.name)
                ext = file_extension.lstrip('.').upper() or '—'
                result.append({
                    'id':           d.id,
                    'name':         d.name,
                    'description':  d.description or "",
                    'file_type':    ext,
                    'created_at':   d.uploaded_at.isoformat() if d.uploaded_at else None,
                    'url':          f'/api/ops/knowledge-base/download/{d.id}'
                })
            logger.info(f"Listed {len(result)} documents after sync.")
            return jsonify({'documents': result}), 200

    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list documents', 'details': str(e)}), 500

    finally:
        pass

@ops_bp.route('/knowledge-base/download/<int:doc_id>', methods=['GET'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def download_document_file(doc_id):
    db = None
    doc_instance = None
    try:
        with db_session() as db:
            doc_instance = db.query(Document).get(doc_id)
            if not doc_instance:
                logger.warning(f"Document with id {doc_id} not found for download.")
                return jsonify({'message': 'Document not found'}), 404
        
        doc_full_path = os.path.abspath(doc_instance.path)
        configured_docs_path = os.path.abspath(DOCUMENTS_PATH)

        if not doc_full_path.startswith(configured_docs_path):
            logger.error(f"Security alert: Attempt to access file outside designated documents directory. Path: {doc_full_path}, Configured Base: {configured_docs_path}")
            return jsonify({'error': 'Access to this file location is forbidden'}), 403

        filename_to_serve = os.path.basename(doc_full_path)
        
        expected_physical_path = os.path.join(configured_docs_path, filename_to_serve)
        if not os.path.isfile(expected_physical_path):
            logger.error(f"File not found at expected physical path: {expected_physical_path} for doc_id {doc_id}. Stored path was {doc_instance.path}")
            return jsonify({'error': 'File not found on server at the expected location'}), 404
        
        logger.info(f"Attempting to serve document: id={doc_id}, name='{filename_to_erve}' from directory='{configured_docs_path}'")
        return send_from_directory(configured_docs_path, filename_to_serve, as_attachment=True, download_name=doc_instance.name)
        
    except FileNotFoundError:
        logger.error(f"send_from_directory failed: File not found for document id {doc_id} at path {doc_instance.path if doc_instance else 'unknown'}", exc_info=True)
        return jsonify({'error': 'File not found on server'}), 404
    except Exception as e:
        logger.error(f"Error downloading document {doc_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to download document', 'details': str(e)}), 500
    finally:
        pass

@ops_bp.route('/knowledge-base/<int:doc_id>', methods=['DELETE'])
@token_required
@role_required(['admin', 'operator'])
@web_rate_limit
def delete_document_file(doc_id):
    db = None
    doc_instance = None
    try:
        with db_session() as db:
            doc_instance = db.query(Document).get(doc_id)
            if not doc_instance:
                logger.warning(f"Document with id {doc_id} not found for deletion.")
                return jsonify({'message': 'Document not found'}), 404

            doc_full_path = os.path.abspath(doc_instance.path)
            configured_docs_path = os.path.abspath(DOCUMENTS_PATH)

            if not doc_full_path.startswith(configured_docs_path):
                logger.error(f"Security alert: Attempt to delete file outside designated documents directory. Path: {doc_full_path}")
                return jsonify({'error': 'Access to this file location is forbidden for deletion'}), 403
            
            file_deleted_successfully = False
            if os.path.exists(doc_full_path):
                try:
                    logger.info(f"Attempting to delete file: {doc_full_path}")
                    os.remove(doc_full_path)
                    logger.info(f"Successfully deleted file: {doc_full_path}")
                    file_deleted_successfully = True
                except OSError as e_os:
                    logger.error(f"Error deleting file {doc_full_path}: {e_os}. Document record in DB will not be deleted.")
                    return jsonify({'error': f'Failed to delete file on server: {e_os}', 'details': str(e_os)}), 500
            else:
                logger.warning(f"File not found for deletion (already deleted or path issue): {doc_full_path}. Proceeding to delete DB record.")
                file_deleted_successfully = True  # If file is not there, we can still delete the DB record

            if file_deleted_successfully:
                db.delete(doc_instance)
                db.commit()
                logger.info(f"Successfully deleted document record from DB: id={doc_id}")
                # TODO: Consider if RAG index for this document should also be cleaned up.
                # This might require a function in retrieval.store to remove chunks by document path.
                return jsonify({'message': 'Document deleted successfully'}), 200
            else:
                # This case should ideally not be reached if logic above is correct
                logger.error(f"File deletion process failed for {doc_full_path}, DB record for doc_id {doc_id} was not deleted.")
                return jsonify({'message': 'File deletion failed, database record not removed.'}), 500

    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}", exc_info=True)
        if db: db.rollback()
        return jsonify({'error': 'Failed to delete document', 'details': str(e)}), 500
    finally:
        pass


