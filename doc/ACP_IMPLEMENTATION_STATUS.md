# Статус реализации ACP

Этот документ фиксирует текущее состояние соответствия ACP в репозитории.

## Матрица соответствия

| Область | Статус | Примечание |
| --- | --- | --- |
| `authenticate` | Done | Метод реализован, `auth_required` для `session/new`/`session/load` поддержан при включенном `require_auth`; добавлен local API key backend (`params.apiKey`) через `--auth-api-key`/`ACP_SERVER_API_KEY`, а также client helpers и auto-auth на WS при наличии `authMethods`. |
| `initialize` | Done | Версия и capability negotiation реализованы; runtime-ветки запускаются только при согласованных client capabilities. |
| `session/new` | Done | Поддерживается создание сессии, `configOptions` и legacy `modes`. |
| `session/load` | Done | Поддерживается replay истории и ключевых `session/update` событий. |
| `session/list` | Done | Реализованы фильтр по `cwd`, cursor pagination и `nextCursor`. |
| `session/prompt` | Partial | Основной WS-поток работает: prompt/update, permission-gate, fs/terminal client-rpc, deferred/cancel, replay. Structured `_meta.promptDirectives` используется как основной путь управления, slash-команды сохранены как compatibility-слой; stopReason `max_tokens`, `max_turn_requests`, `refusal` поддержаны. |
| `session/cancel` | Done | Cancel-flow детерминирован для race с `session/request_permission`, включая late permission responses. |
| `session/set_config_option` | Done | Реализовано с полным возвратом состояния `configOptions`. |
| `session/request_permission` | Done | Server/client оркестрация стабилизирована: race с cancel закрыт, persisted policy (`allow_always`/`reject_always`) scoped по ACP tool kind (`read/edit/delete/move/search/execute/think/fetch/switch_mode/other`), decision-flow валидирует `optionId` по объявленным options и применяет решения детерминированно. |
| `session/update: tool_call*` | Done | Создание/обновление/replay поддержаны. |
| `session/update: plan` | Done | Реализовано и типизировано: план публикуется по structured directives и реплеится через `session/load`; поддержан structured override `planEntries`. |
| `available_commands_update` | Done | Snapshot команд отправляется на prompt/load. |
| HTTP transport | Removed | Проект переведен в WS-only режим, HTTP endpoint удален. |
| WebSocket transport | Done | Поддержан update-поток, deferred response и agent->client RPC (permission/fs/terminal). |

## Приоритетный backlog

1. Финализировать production execution backend для `session/prompt` (убрать оставшийся in-memory executor stub и подключить реальное выполнение инструментов).
2. Продолжить расширение conformance-набора на дополнительные edge-кейсы schema/wire (terminal/fs/permission), включая редкие negative payload combinations.
