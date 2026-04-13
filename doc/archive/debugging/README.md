# Архив отладочных документов

**Дата архивирования:** 13 апреля 2026

Этот каталог содержит отладочные документы, которые использовались при разработке и исправлении проблем в системе ACP-протокола. Все описанные проблемы успешно решены и реализованы в текущей версии кодовой базы.

## Документы в архиве

### DEBUG_SESSION_LOAD_HISTORY.md

Документ описывал проблему с загрузкой сессий из JSON-хранилища, когда при попытке загрузить несколько сессий последовательно возникали конфликты и рассинхронизация.

**Статус решения:** ✅ РЕШЕНО

**Решение реализовано:** Архитектурный рефакторинг с внедрением системы Concurrent Receive, которая обеспечивает асинхронную обработку входящих сообщений и правильную сериализацию операций загрузки сессий.

**Связанные компоненты реализации:**
- [`acp-client/src/acp_client/infrastructure/services/background_receive_loop.py`](../../acp-client/src/acp_client/infrastructure/services/background_receive_loop.py)
- [`acp-client/src/acp_client/infrastructure/services/acp_transport_service.py`](../../acp-client/src/acp_client/infrastructure/services/acp_transport_service.py)
- [`acp-client/src/acp_client/infrastructure/services/routing_queues.py`](../../acp-client/src/acp_client/infrastructure/services/routing_queues.py)

**Связанные тесты:**
- [`acp-client/tests/test_concurrent_receive_calls.py`](../../acp-client/tests/test_concurrent_receive_calls.py)
- [`acp-client/tests/test_background_receive_loop.py`](../../acp-client/tests/test_background_receive_loop.py)

---

### DI_ANALYSIS_REPORT.md

Документ содержал результаты анализа системы внедрения зависимостей (DI) в клиентской части приложения. Была выявлена критическая проблема: 9 компонентов зависели от экземпляра эфемерных зависимостей, вызывая разрушение состояния и проблемы в многопоточности.

**Статус решения:** ✅ РЕШЕНО (все 9 проблем исправлены)

**Решение реализовано:** Полный рефакторинг контейнера внедрения зависимостей с правильной классификацией жизненных циклов компонентов (Singleton vs Transient).

**Исправленные компоненты:**
1. `ACPTransportService` - переведён на Singleton
2. `MessageRouter` - переведён на Singleton
3. `RoutingQueues` - переведён на Singleton
4. `BackgroundReceiveLoop` - переведён на Singleton
5. `SessionCoordinator` - переведён на Singleton
6. `EventBus` - переведён на Singleton
7. `DIContainer` - переведён на Singleton
8. `PluginManager` - переведён на Singleton
9. `StateRepository` - переведён на Singleton

**Связанные компоненты реализации:**
- [`acp-client/src/acp_client/infrastructure/di_container.py`](../../acp-client/src/acp_client/infrastructure/di_container.py)
- [`acp-client/src/acp_client/infrastructure/di_bootstrapper.py`](../../acp-client/src/acp_client/infrastructure/di_bootstrapper.py)

**Связанные тесты:**
- [`acp-client/tests/test_infrastructure_di_container.py`](../../acp-client/tests/test_infrastructure_di_container.py)
- [`acp-client/tests/test_di_container_integration.py`](../../acp-client/tests/test_di_container_integration.py)
- [`acp-client/tests/test_di_container_dispose.py`](../../acp-client/tests/test_di_container_dispose.py)
- [`acp-client/tests/test_di_bootstrapper.py`](../../acp-client/tests/test_di_bootstrapper.py)

---

## Связанные рефакторинги

Полная история рефакторинга и архитектурных изменений доступна в:
- [`doc/archive/refactoring/`](../refactoring/)
- [`plans/CONCURRENT_RECEIVE_ARCHITECTURE_DESIGN.md`](../../plans/CONCURRENT_RECEIVE_ARCHITECTURE_DESIGN.md)
- [`plans/HISTORY_PERSISTENCE_ARCHITECTURE.md`](../../plans/HISTORY_PERSISTENCE_ARCHITECTURE.md)
