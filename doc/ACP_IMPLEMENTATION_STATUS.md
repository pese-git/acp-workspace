# Статус реализации ACP

Этот документ фиксирует текущее состояние соответствия ACP в репозитории.

## Матрица соответствия

| Область | Статус | Примечание |
| --- | --- | --- |
| `authenticate` | Partial | Метод реализован, `auth_required` для `session/new`/`session/load` поддержан при включенном `require_auth`; добавлены client helpers (`authenticate`) и auto-auth на WS при наличии `authMethods`, production auth-backend пока не подключен. |
| `initialize` | Done | Версия и capability negotiation реализованы; runtime-ветки запускаются только при согласованных client capabilities. |
| `session/new` | Done | Поддерживается создание сессии, `configOptions` и legacy `modes`. |
| `session/load` | Done | Поддерживается replay истории и ключевых `session/update` событий. |
| `session/list` | Done | Реализованы фильтр по `cwd`, cursor pagination и `nextCursor`. |
| `session/prompt` | Partial | Основной поток работает; marker-trigger логика удалена, остаются demo-сценарии. Structured `_meta.promptDirectives` используется как основной путь для тестовых сценариев, slash-команды сохранены как compatibility-слой; stopReason `max_tokens`, `max_turn_requests`, `refusal` поддержаны. |
| `session/cancel` | Done | Cancel-flow детерминирован для race с `session/request_permission`, включая late permission responses. |
| `session/set_config_option` | Done | Реализовано с полным возвратом состояния `configOptions`. |
| `session/request_permission` | Partial | Базовая server/client оркестрация есть; race с cancel стабилизирован и добавлена persisted policy (`allow_always`/`reject_always`) с scope по ACP tool kind (`read/edit/delete/move/search/execute/think/fetch/switch_mode/other`); decision-flow валидирует `optionId` по объявленным options и применяет policy-решения детерминированно. |
| `session/update: tool_call*` | Done | Создание/обновление/replay поддержаны. |
| `session/update: plan` | Partial | Реализовано и типизировано, пока в demo-сценарии. |
| `available_commands_update` | Done | Snapshot команд отправляется на prompt/load. |
| HTTP transport | Removed | Проект переведен в WS-only режим, HTTP endpoint удален. |
| WebSocket transport | Done | Поддержан update-поток, deferred response и agent->client RPC (permission/fs/terminal). |

## Приоритетный backlog

1. Завершить переход от demo-семантики `session/request_permission` к production policy-model (финально отвязать от fallback demo tool lifecycle и real executor integration).
2. Расширить conformance-набор до дополнительных edge-кейсов terminal/fs client-rpc (особенно race-сценарии cancel + pending client-rpc). Статус: partially done (добавлены тесты late-response после cancel для fs/read_text_file и terminal/create).
