# История изменений

Все значительные изменения в CodeLab документируются в этом разделе.

Полная история изменений доступна в файле [CHANGELOG.md](../../../CHANGELOG.md) в корне репозитория.

## Формат версий

Проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html):
- **MAJOR** — несовместимые изменения API
- **MINOR** — новая функциональность с обратной совместимостью
- **PATCH** — исправления ошибок

## Последние изменения

### MCP Integration (Stage 8)

Добавлена поддержка Model Context Protocol:
- Модуль интеграции с MCP серверами
- Поддержка параметра `mcpServers` в сессиях
- Transport для запуска MCP серверов через stdio
- Адаптер инструментов MCP для ToolRegistry

### Advanced Permission Management (Stage 5)

Улучшенная система управления разрешениями:
- Автоматическое восстановление политик при загрузке сессии
- Поддержка глобальных политик разрешений
- Интеграционные тесты для persistence

### Content Integration (Stage 4)

Полная поддержка типов контента ACP:
- Text, Diff, Image, Audio content
- Embedded resources и Resource links
- E2E тестирование всех типов контента

### Permission Flow (Stage 3)

Реализована система разрешений:
- Inline widgets для запроса разрешений
- Модальные окна разрешений
- Allow/Reject once и always политики

## Roadmap

### Планируется

- **Global Policy Management** — глобальные политики разрешений между сессиями
- **Plugin System** — расширяемая архитектура плагинов
- **Web UI** — полнофункциональный веб-интерфейс
- **Multi-agent** — поддержка нескольких агентов

## Обратная совместимость

CodeLab стремится поддерживать обратную совместимость:
- CLI интерфейс стабилен
- Формат сессий версионируется
- Протокол ACP следует официальной спецификации

## Как отслеживать изменения

### GitHub Releases

Следите за [релизами](https://github.com/your-org/codelab/releases) на GitHub.

### Changelog

Читайте полный [CHANGELOG.md](../../../CHANGELOG.md) для детальной истории изменений.

### Обновление

```bash
cd codelab
git pull origin main
uv sync
```

## См. также

- [CHANGELOG.md](../../../CHANGELOG.md) — полная история изменений
- [Установка](../getting-started/02-installation.md) — руководство по установке
- [Contributing](../developer-guide/06-contributing.md) — как внести вклад
