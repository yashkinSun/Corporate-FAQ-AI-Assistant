"""
Модуль для создания и настройки Flask-приложения веб-интерфейса.
"""
import os
import logging
from flask import Flask, jsonify, render_template, send_from_directory, request
from flask_jwt_extended import JWTManager

from config import JWT_SECRET_KEY, WEB_DEBUG

logger = logging.getLogger(__name__)

def create_app():
    """
    Создает и настраивает Flask-приложение.
    
    Returns:
        Flask: Настроенное Flask-приложение
    """
    # Создаем экземпляр приложения
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # Настраиваем приложение
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
    app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    
    # Инициализируем JWT
    jwt = JWTManager(app)
    
    # Регистрируем обработчики ошибок
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'message': 'Not found'}), 404
    
    @app.errorhandler(500)
    def server_error(error):
        logger.error(f"Server error: {error}")
        return jsonify({'message': 'Internal server error'}), 500
    
    # Регистрируем blueprints
    from webapp.auth.routes import auth_bp
    from webapp.ops.routes import ops_bp
    from webapp.stats.routes import stats_bp
    
    # Эндпоинты веб-API теперь под /api/...
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(ops_bp,  url_prefix='/api/ops')
    app.register_blueprint(stats_bp, url_prefix='/api/stats')
    
    # Добавляем маршрут для API аутентификации (альтернативный)
    @app.route('/api/auth/login', methods=['POST'])
    def api_auth_login():
        # Перенаправляем запрос на обработчик в auth_bp
        from webapp.auth.routes import login
        return login()
    
    # Добавляем маршрут для проверки работоспособности
    @app.route('/health')
    def health_check():
        return jsonify({'status': 'ok'})
    
    # Временный API-индекс на /api (для тестов)
    @app.route('/api')
    def api_index():
        return jsonify({
            'message': 'FAQ Bot API',
            'version': '2.0',
            'endpoints': {
                'auth': '/api/auth',
                'operations': '/api/ops',
                'statistics': '/api/stats',
                'health': '/health'
            }
        })
    
    # Корневой маршрут — возвращает HTML UI панели операторов
    @app.route('/')
    def index():
        return render_template('tailwind/login.html')
    
    # Добавляем маршруты для веб-интерфейса
    @app.route('/login')
    def login_page():
        return render_template('tailwind/login.html')
    
    @app.route('/dashboard')
    def dashboard_page():
        return render_template('tailwind/dashboard.html')
    
    @app.route('/active-chats')
    def active_chats_page():
        return render_template('tailwind/active-chats.html')
    
    @app.route('/chat')
    def chat_page():
        return render_template('tailwind/chat.html')
    
    @app.route('/knowledge-base')
    def knowledge_base_page():
        return render_template('tailwind/knowledge-base.html')

    # Добавляем маршрут для страницы истории
    @app.route('/history')
    def history_page():
        return render_template('tailwind/history.html')

    # Добавляем маршрут для страницы статистики
    @app.route('/statistics')
    def statistics_page():
        return render_template('tailwind/statistics.html')
    
    # (Опционально) Catch-all для SPA:
    @app.route('/<path:path>')
    def static_proxy(path):
        if os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return render_template('tailwind/login.html')
    
    return app
