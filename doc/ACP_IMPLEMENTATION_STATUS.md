# Статус реализации ACP

Этот документ фиксирует текущее состояние соответствия ACP в репозитории.

## Матрица соответствия

| Область | Статус | Примечание |
| --- | --- | --- |
| `initialize` | Partial | Версия и базовые capability объявляются; требуется более строгая привязка runtime-поведения к negotiated client capabilities. |
| `session/new` | Done | Поддерживается создание сессии, `configOptions` и legacy `modes`. |
| `session/load` | Done | Поддерживается replay истории и ключевых `session/update` событий. |
| `session/list` | Done | Реализованы фильтр по `cwd`, cursor pagination и `nextCursor`. |
| `session/prompt` | Partial | Основной поток работает; часть demo-логики пока остается эвристической (markers/slash). |
| `session/cancel` | Partial | Основной cancel-flow реализован; нужна дополнительная стабилизация в сложных race-сценариях. |
| `session/set_config_option` | Done | Реализовано с полным возвратом состояния `configOptions`. |
| `session/request_permission` | Partial | Базовая server/client оркестрация есть; нужно расширение до production-семантики без demo-веток. |
| `session/update: tool_call*` | Done | Создание/обновление/replay поддержаны. |
| `session/update: plan` | Partial | Реализовано и типизировано, пока в demo-сценарии. |
| `available_commands_update` | Done | Snapshot команд отправляется на prompt/load. |
| HTTP transport | Done | Рабочий запрос-ответ и совместимость с deferred turn. |
| WebSocket transport | Partial | Поддержан поток updates и deferred response; требуются дополнительные hardening-сценарии. |

## Приоритетный backlog

1. Убрать marker-based demo-триггеры как основной механизм и перейти на единый state machine prompt-turn.
2. Довести cancel/permission до полностью детерминированного поведения в гонках.
3. Привязать runtime-ветки к negotiated client capabilities после `initialize`.
4. Расширить типизацию client/server под дополнительные `session/update` payload из `doc/ACP/protocol/17-Schema.md`.
5. Подготовить отдельный conformance-тест набор для критичных ACP сценариев (prompt/cancel/permission/load replay).
