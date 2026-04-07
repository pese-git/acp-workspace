# Статус реализации ACP

Этот документ фиксирует текущее состояние соответствия ACP в репозитории.

## Матрица соответствия

| Область | Статус | Примечание |
| --- | --- | --- |
| `initialize` | Done | Версия и capability negotiation реализованы; runtime-ветки запускаются только при согласованных client capabilities. |
| `session/new` | Done | Поддерживается создание сессии, `configOptions` и legacy `modes`. |
| `session/load` | Done | Поддерживается replay истории и ключевых `session/update` событий. |
| `session/list` | Done | Реализованы фильтр по `cwd`, cursor pagination и `nextCursor`. |
| `session/prompt` | Partial | Основной поток работает; marker-trigger логика удалена, но остаются demo slash-сценарии. |
| `session/cancel` | Done | Cancel-flow детерминирован для race с `session/request_permission`, включая late permission responses. |
| `session/set_config_option` | Done | Реализовано с полным возвратом состояния `configOptions`. |
| `session/request_permission` | Partial | Базовая server/client оркестрация есть; race с cancel стабилизирован и добавлена persisted policy (`allow_always`/`reject_always`) по tool kind, остаются demo-ветки. |
| `session/update: tool_call*` | Done | Создание/обновление/replay поддержаны. |
| `session/update: plan` | Partial | Реализовано и типизировано, пока в demo-сценарии. |
| `available_commands_update` | Done | Snapshot команд отправляется на prompt/load. |
| HTTP transport | Removed | Проект переведен в WS-only режим, HTTP endpoint удален. |
| WebSocket transport | Done | Поддержан update-поток, deferred response и agent->client RPC (permission/fs/terminal). |

## Приоритетный backlog

1. Завершить переход от demo-семантики `session/request_permission` к production policy-model (включая policy scope beyond tool kind `other`).
2. Расширить conformance-набор до edge-кейсов terminal/fs client-rpc и error-сценариев.
