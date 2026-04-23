"""Web UI сервер на базе Textual Web.

Позволяет запустить TUI клиент в браузере.
Модуль предоставляет graceful fallback если textual-web не установлен.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Флаг доступности textual-web
TEXTUAL_WEB_AVAILABLE = False
TextualWeb = None

try:
    from textual_web import TextualWeb as _TextualWeb

    TextualWeb = _TextualWeb
    TEXTUAL_WEB_AVAILABLE = True
    logger.debug("textual_web_available", version=">=0.5")
except ImportError:
    logger.debug("textual_web_not_available")


def is_web_ui_available() -> bool:
    """Проверяет доступность Web UI.
    
    Returns:
        True если textual-web установлен и доступен
    """
    return TEXTUAL_WEB_AVAILABLE


def create_web_app(server_url: str = "ws://localhost:8765/acp/ws"):
    """Создать веб-приложение для TUI.
    
    Args:
        server_url: URL WebSocket сервера для подключения
        
    Returns:
        TextualWeb instance если доступен, иначе None
        
    Raises:
        RuntimeError: если textual-web не установлен
    """
    if not TEXTUAL_WEB_AVAILABLE or TextualWeb is None:
        raise RuntimeError(
            "textual-web не установлен. "
            "Установите: pip install 'codelab[web]' или pip install textual-web"
        )
    
    # Извлекаем host и port из server_url для TUI приложения
    # Формат: ws://host:port/acp/ws
    import re
    match = re.match(r"wss?://([^:/]+):(\d+)", server_url)
    if match:
        host = match.group(1)
        port = int(match.group(2))
    else:
        host = "localhost"
        port = 8765
    
    # Фабрика для создания TUI приложения
    def app_factory():
        """Создаёт экземпляр TUI приложения для Web."""
        from codelab.client.tui.app import ACPClientApp
        return ACPClientApp(host=host, port=port)
    
    logger.info(
        "creating_web_app",
        server_url=server_url,
        host=host,
        port=port,
    )
    
    return TextualWeb(app_factory)


def get_fallback_html(host: str, port: int) -> str:
    """Возвращает HTML страницу-заглушку когда Web UI недоступен.
    
    Args:
        host: Адрес сервера
        port: Порт сервера
        
    Returns:
        HTML строка с инструкциями по установке
    """
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeLab - Web UI недоступен</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #e4e4e4;
        }}
        .container {{
            max-width: 600px;
            padding: 40px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 16px;
            color: #00d4ff;
        }}
        .status {{
            display: inline-block;
            padding: 4px 12px;
            background: #ffd700;
            color: #1a1a2e;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 24px;
        }}
        p {{
            line-height: 1.7;
            margin-bottom: 16px;
            color: #b4b4b4;
        }}
        .info-box {{
            background: rgba(0, 212, 255, 0.1);
            border-left: 4px solid #00d4ff;
            padding: 16px 20px;
            margin: 24px 0;
            border-radius: 0 8px 8px 0;
        }}
        .info-box h3 {{
            color: #00d4ff;
            margin-bottom: 8px;
        }}
        code {{
            background: rgba(255, 255, 255, 0.1);
            padding: 4px 8px;
            border-radius: 4px;
            font-family: 'Fira Code', 'Monaco', monospace;
            font-size: 0.9em;
        }}
        pre {{
            background: #0d1117;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 16px 0;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        .endpoint {{
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .endpoint h3 {{
            color: #00ff88;
            margin-bottom: 12px;
        }}
        .url {{
            font-family: 'Fira Code', monospace;
            color: #00ff88;
        }}
    </style>
</head>
<body>
    <div class="container">
        <span class="status">⚠️ Требуется установка</span>
        <h1>🔬 CodeLab Web UI</h1>
        
        <p>Web UI требует дополнительной установки пакета <code>textual-web</code>.</p>
        
        <div class="info-box">
            <h3>📦 Установка</h3>
            <pre><code>pip install 'codelab[web]'</code></pre>
            <p style="margin-bottom: 0;">Или напрямую:</p>
            <pre><code>pip install textual-web</code></pre>
        </div>
        
        <p>После установки перезапустите сервер:</p>
        <pre><code>codelab serve --port {port}</code></pre>
        
        <div class="endpoint">
            <h3>✅ WebSocket API доступен</h3>
            <p>Подключайтесь к API через TUI клиент:</p>
            <pre><code>codelab connect --host {host} --port {port}</code></pre>
            <p>WebSocket endpoint: <span class="url">ws://{host}:{port}/acp/ws</span></p>
        </div>
    </div>
</body>
</html>
"""
