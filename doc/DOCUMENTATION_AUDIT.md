# Аудит документации проекта ACP Protocol

**Дата аудита:** 2026-04-24  
**Контекст:** Проект унифицирован — весь код находится в `codelab/`, директории `acp-client/` и `acp-server/` устарели.

---

## 1. Инвентаризация документов

### 1.1 Корневые документы

| Файл | Статус | Описание | Рекомендация |
|------|--------|----------|--------------|
| `README.md` | 🔴 УСТАРЕЛ | Описывает монорепозиторий с acp-client и acp-server | Переписать для codelab/ |
| `AGENTS.md` | ✅ АКТУАЛЕН | Инструкции для AI ассистентов, корректно описывает codelab/ | Оставить |
| `CHANGELOG.md` | 🟡 ЧАСТИЧНО | Содержит историю, но ссылки на acp-server/acp-client | Обновить пути |
| `Makefile` | ⚠️ ПРОВЕРИТЬ | Возможно содержит устаревшие targets | Проверить совместимость |

### 1.2 Документация codelab/

| Файл | Статус | Описание |
|------|--------|----------|
| `codelab/README.md` | ✅ АКТУАЛЕН | Основная документация унифицированного проекта |

### 1.3 doc/ - Основная документация

#### Референсный протокол (НЕ МЕНЯТЬ!)

| Путь | Статус |
|------|--------|
| `doc/Agent Client Protocol/get-started/` | 🔒 РЕФЕРЕНС |
| `doc/Agent Client Protocol/protocol/` | 🔒 РЕФЕРЕНС |

#### Документы верхнего уровня

| Файл | Статус | Описание | Рекомендация |
|------|--------|----------|--------------|
| `doc/ACP_IMPLEMENTATION_STATUS.md` | 🔴 УСТАРЕЛ | Статус реализации, ссылки на acp-server/acp-client | Обновить пути на codelab/ |
| `doc/TOOL_CALLS_TESTING_GUIDE.md` | ⚠️ ПРОВЕРИТЬ | Гайд по тестированию tool calls | Проверить актуальность путей |

#### doc/architecture/ - Архитектурные документы

| Файл | Статус | Рекомендация |
|------|--------|--------------|
| `ADVANCED_PERMISSION_MANAGEMENT_ANALYSIS_REPORT.md` | 🟡 ЧАСТИЧНО | Содержит ценные диаграммы, обновить пути |
| `ADVANCED_PERMISSION_MANAGEMENT_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Архитектура permissions |
| `AGENT_PLAN_GENERATION_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Генерация планов |
| `CLIENT_METHODS_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | RPC методы клиента |
| `CLIENT_PERMISSION_HANDLING_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Обработка разрешений |
| `CONTENT_INTEGRATION_E2E_TESTING_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | E2E тестирование |
| `CONTENT_TYPES_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Типы контента |
| `INLINE_PERMISSION_WIDGET_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | UI виджет разрешений |
| `MCP_INTEGRATION_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Интеграция MCP |
| `PERMISSION_FLOW_SEQUENCE_DIAGRAMS.md` | 🟡 ЧАСТИЧНО | Sequence диаграммы |
| `PERMISSION_RESPONSE_FIX_SUMMARY.md` | 🔴 УСТАРЕЛ | Исторический документ |
| `PERMISSION_RESPONSE_HANDLING_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Обработка ответов |
| `PROMPT_TURN_CONTENT_INTEGRATION_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Интеграция контента |
| `SERVER_PERMISSION_INTEGRATION_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Серверная интеграция |
| `TOOL_CALLS_INTEGRATION_ARCHITECTURE.md` | 🟡 ЧАСТИЧНО | Tool calls |

#### doc/analysis/ - Отчёты отладки

| Файл | Статус | Рекомендация |
|------|--------|--------------|
| `INLINE_PERMISSION_WIDGET_DEBUG_REPORT.md` | 🔴 УСТАРЕЛ | Архивировать |
| `PERMISSION_MODAL_DEBUG_REPORT.md` | 🔴 УСТАРЕЛ | Архивировать |
| `PERMISSION_RESPONSE_WEBSOCKET_DISCONNECT_ANALYSIS.md` | 🔴 УСТАРЕЛ | Архивировать |
| `TOOL_PERMISSION_FLOW_ANALYSIS.md` | 🔴 УСТАРЕЛ | Архивировать |
| `TOOL_PERMISSION_FLOW_LOG_ANALYSIS.md` | 🔴 УСТАРЕЛ | Архивировать |

#### doc/archive/ - Уже архивировано

| Путь | Статус | Описание |
|------|--------|----------|
| `archive/analysis/` | ✅ АРХИВ | Старые анализы |
| `archive/debugging/` | ✅ АРХИВ | Отладочные сессии |
| `archive/diagrams/` | ✅ АРХИВ | Устаревшие диаграммы |
| `archive/integration/` | ✅ АРХИВ | Планы интеграции |
| `archive/refactoring/` | ✅ АРХИВ | Планы рефакторинга |

### 1.4 plans/ - Планы разработки

| Файл | Статус | Описание | Рекомендация |
|------|--------|----------|--------------|
| `ACP_IMPROVEMENT_PLAN.md` | ⚠️ ПРОВЕРИТЬ | План улучшений | Проверить статус |
| `ARCHITECTURE_COMPARISON.md` | 🔴 УСТАРЕЛ | Сравнение архитектур | Архивировать |
| `ARCHITECTURE_DOCUMENTATION_COMPLETION.md` | 🔴 УСТАРЕЛ | Завершение документации | Архивировать |
| `CODELAB_UNIFICATION_PLAN.md` | 🔴 ВЫПОЛНЕН | Унификация завершена | Архивировать |
| `CONCURRENT_RECEIVE_ARCHITECTURE_DESIGN.md` | ⚠️ ПРОВЕРИТЬ | Concurrent receive | Проверить |
| `HISTORY_PERSISTENCE_ARCHITECTURE.md` | ⚠️ ПРОВЕРИТЬ | Persistence истории | Проверить |
| `LLM_LOOP_ARCHITECTURE.md` | ⚠️ ПРОВЕРИТЬ | LLM loop | Проверить |
| `MCP_INTEGRATION_PLAN.md` | 🔴 ВЫПОЛНЕН | MCP интегрирован | Архивировать |
| `PRODUCTION_EXECUTION_FIX_PLAN.md` | 🔴 УСТАРЕЛ | Исправления | Архивировать |
| `RPC_WITHOUT_TIMEOUT_ARCHITECTURE.md` | ⚠️ ПРОВЕРИТЬ | RPC без таймаутов | Проверить |
| `SLASH_COMMANDS_IMPLEMENTATION_PLAN.md` | ⚠️ ПРОВЕРИТЬ | Slash commands | Проверить |
| `WEBSOCKET_CONNECTION_ANALYSIS.md` | 🔴 УСТАРЕЛ | Анализ WebSocket | Архивировать |

### 1.5 acp-client/docs/ - УСТАРЕВШАЯ директория

| Путь | Статус | Рекомендация |
|------|--------|--------------|
| `developer-guide/ARCHITECTURE.md` | 🔴 УСТАРЕЛ | Перенести в codelab/ или doc/ |
| `developer-guide/DEVELOPING.md` | 🔴 УСТАРЕЛ | Перенести |
| `developer-guide/NAVIGATION_MANAGER.md` | 🔴 УСТАРЕЛ | Перенести |
| `developer-guide/TESTING.md` | 🔴 УСТАРЕЛ | Перенести |
| `roadmap/UI_UX_IMPROVEMENTS.md` | 🔴 УСТАРЕЛ | Перенести |
| `archive/` | 🔴 УСТАРЕЛ | Удалить |

### 1.6 acp-server/docs/ - УСТАРЕВШАЯ директория

| Путь | Статус | Рекомендация |
|------|--------|--------------|
| `ARCHITECTURE.md` | 🔴 УСТАРЕЛ | Перенести в codelab/ или doc/ |
| `archive/refactoring/` | 🔴 УСТАРЕЛ | Удалить |

### 1.7 acp-server/ корневые документы - УСТАРЕВШИЕ

| Файл | Статус | Рекомендация |
|------|--------|--------------|
| `acp-server/README.md` | 🔴 УСТАРЕЛ | Удалить после миграции |
| `acp-server/CONFIGURATION.md` | 🔴 УСТАРЕЛ | Перенести в codelab/ |
| `acp-server/TOOL_CALLS_DIAGNOSTIC_REPORT.md` | 🔴 УСТАРЕЛ | Архивировать |
| `acp-server/TOOL_CALLS_FIX_ARCHITECTURE.md` | 🔴 УСТАРЕЛ | Архивировать |
| `acp-server/BUGFIX_OPENAI_TOOL_CALLS.md` | 🔴 УСТАРЕЛ | Архивировать |

### 1.8 acp-client/ корневые документы - УСТАРЕВШИЕ

| Файл | Статус | Рекомендация |
|------|--------|--------------|
| `acp-client/README.md` | 🔴 УСТАРЕЛ | Удалить после миграции |

---

## 2. Анализ проблем

### 2.1 Устаревшие пути

**Проблема:** Большинство документов ссылаются на `acp-server/` и `acp-client/`, которые более не актуальны.

**Масштаб:** ~30 документов требуют обновления путей.

### 2.2 Дублирование информации

| Тема | Дублируется в |
|------|---------------|
| Архитектура клиента | `acp-client/docs/developer-guide/ARCHITECTURE.md`, `acp-client/README.md` |
| Архитектура сервера | `acp-server/docs/ARCHITECTURE.md`, `acp-server/README.md` |
| Разработка | `acp-client/docs/developer-guide/DEVELOPING.md`, множество README |
| Тестирование | `acp-client/docs/developer-guide/TESTING.md`, корневой README |

### 2.3 Пробелы в документации

Для продуктовой документации не хватает:

1. **Пользовательская документация**
   - Руководство пользователя (Getting Started)
   - FAQ
   - Примеры использования

2. **Техническая документация**
   - API Reference (автогенерация из docstrings)
   - Конфигурационный справочник
   - Руководство по деплою

3. **Для разработчиков**
   - Contributing Guide
   - Code Style Guide
   - Release Process

---

## 3. Рекомендации

### 3.1 Немедленные действия (Critical)

1. **Переписать корневой README.md**
   - Описать проект как единый codelab/
   - Обновить инструкции по установке и запуску
   - Удалить упоминания acp-server/acp-client как отдельных проектов

2. **Архивировать выполненные планы**
   - Переместить `plans/CODELAB_UNIFICATION_PLAN.md` в `doc/archive/plans/`
   - Переместить `plans/MCP_INTEGRATION_PLAN.md` в `doc/archive/plans/`

3. **Архивировать debug-отчёты**
   - Переместить `doc/analysis/*` в `doc/archive/debugging/`

### 3.2 Краткосрочные действия

1. **Консолидировать документацию клиента и сервера**
   - Объединить `acp-client/docs/developer-guide/` и `acp-server/docs/` 
   - Создать `codelab/docs/` или `doc/developer-guide/`

2. **Обновить CHANGELOG.md**
   - Исправить пути с acp-server/ на codelab/src/codelab/server/
   - Исправить пути с acp-client/ на codelab/src/codelab/client/

3. **Обновить ACP_IMPLEMENTATION_STATUS.md**
   - Актуализировать пути модулей
   - Обновить статусы реализации

### 3.3 Структура продуктовой документации

Рекомендуемая структура для сайта документации:

```
doc/
├── Agent Client Protocol/     # 🔒 РЕФЕРЕНС (не менять!)
│
├── getting-started/           # Для пользователей
│   ├── introduction.md
│   ├── installation.md
│   ├── quick-start.md
│   └── configuration.md
│
├── guides/                    # Руководства
│   ├── user-guide.md
│   ├── deployment.md
│   └── troubleshooting.md
│
├── developer/                 # Для разработчиков
│   ├── architecture.md        # Консолидация из acp-client/acp-server docs
│   ├── contributing.md
│   ├── testing.md
│   └── code-style.md
│
├── reference/                 # Справочники
│   ├── cli.md
│   ├── api.md
│   └── config.md
│
├── internals/                 # Внутренние архитектурные документы
│   ├── permission-system.md
│   ├── content-types.md
│   └── mcp-integration.md
│
└── archive/                   # Исторические документы
    ├── plans/
    ├── debugging/
    └── analysis/
```

### 3.4 Документы для удаления

После переноса полезного контента можно удалить:

- `acp-client/` — вся директория (код перенесён в codelab/)
- `acp-server/` — вся директория (код перенесён в codelab/)

**ВНИМАНИЕ:** Перед удалением убедиться, что:
1. Весь код в codelab/ работает
2. Полезная документация перенесена
3. Тесты проходят

---

## 4. Список документов для сайта (Missing)

| Раздел | Документ | Приоритет |
|--------|----------|-----------|
| Getting Started | Introduction | HIGH |
| Getting Started | Installation Guide | HIGH |
| Getting Started | Quick Start Tutorial | HIGH |
| Guides | User Guide | HIGH |
| Guides | Deployment Guide | MEDIUM |
| Reference | CLI Reference | HIGH |
| Reference | Configuration Reference | HIGH |
| Reference | Environment Variables | MEDIUM |
| Developer | Contributing Guide | MEDIUM |
| Developer | Testing Guide | MEDIUM |
| FAQ | Common Issues | MEDIUM |

---

## 5. Резюме

### Статистика

| Категория | Количество |
|-----------|------------|
| ✅ Актуальных документов | 3 |
| 🟡 Частично устаревших | ~15 |
| 🔴 Устаревших | ~25 |
| 🔒 Референсных (не менять) | 17 |

### Приоритеты

1. **P0 (Critical):** Корневой README.md — первое что видят пользователи
2. **P1 (High):** Удаление/архивирование устаревших директорий acp-client/, acp-server/
3. **P2 (Medium):** Обновление путей в архитектурных документах
4. **P3 (Low):** Создание продуктовой документации для сайта
