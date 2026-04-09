# Стратегия тестирования acp-client

Документация по подходам, инструментам и практикам тестирования в проекте acp-client.

## Содержание

1. [Введение](#введение)
2. [Инструменты и фреймворки](#инструменты-и-фреймворки)
3. [Структура тестов](#структура-тестов)
4. [Unit тесты](#unit-тесты)
5. [MVVM тесты](#mvvm-тесты)
6. [Integration тесты](#integration-тесты)
7. [Fixtures и моки](#fixtures-и-моки)
8. [Асинхронное тестирование](#асинхронное-тестирование)
9. [Coverage и метрики](#coverage-и-метрики)
10. [Best Practices](#best-practices)
11. [Запуск тестов](#запуск-тестов)
12. [Отладка тестов](#отладка-тестов)
13. [CI/CD интеграция](#cicd-интеграция)
14. [Типичные проблемы и решения](#типичные-проблемы-и-решения)

---

## Введение

### Философия тестирования

acp-client следует принципам чистой архитектуры и многоуровневого тестирования:

- **Unit тесты** - тестируют отдельные компоненты в изоляции
- **Integration тесты** - тестируют взаимодействие между компонентами
- **MVVM тесты** - тестируют связку UI компонента с ViewModel
- **E2E тесты** (интеграция с реальным сервером) - полный workflow

### Test Pyramid

```
         /\
        /  \  E2E (интеграция с сервером)
       /----\
      /      \  Integration
     /--------\
    /          \  Unit
   /____________\
```

### Цели тестирования

1. **Гарантия корректности** - код работает как ожидается
2. **Регрессионная защита** - новые изменения не ломают старый функционал
3. **Документирование** - тесты документируют поведение кода
4. **Упрощение рефакторинга** - быстрое обнаружение проблем при изменениях
5. **Изоляция слоев** - валидация архитектуры (domain ≠ infrastructure)

---

## Инструменты и фреймворки

### Основные зависимости

Все зависимости для тестирования указаны в `pyproject.toml`:

```toml
[dependency-groups]
dev = [
  "pytest>=8.3.5",
  "pytest-asyncio>=0.24.0",
  "ruff>=0.11.4",
  "ty>=0.0.1a11",
]
```

### pytest

Основной фреймворк для запуска тестов.

**Особенности:**
- Автоматическое обнаружение тестов по паттерну `test_*.py`
- Встроенная система fixtures
- Подробные отчёты о сбоях
- Параллельное выполнение тестов

### pytest-asyncio

Расширение для тестирования асинхронного кода.

**Использование:**
```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result == expected_value
```

### unittest.mock

Встроенный модуль Python для создания моков и патчей.

```python
from unittest.mock import Mock, MagicMock, patch

# Создание простого мока
mock_obj = Mock()
mock_obj.some_method.return_value = "value"

# Проверка вызовов
assert mock_obj.some_method.called
assert mock_obj.some_method.call_count == 1
```

### pytest-cov (coverage)

Инструмент для измерения покрытия кода тестами.

```bash
# Запуск с отчётом о покрытии
pytest --cov=acp_client --cov-report=html
```

---

## Структура тестов

### Организация файлов

Тесты расположены в директории `acp-client/tests/`:

```
tests/
├── conftest.py                          # Общие fixtures
├── test_domain_*.py                     # Тесты Domain Layer
├── test_application_*.py                # Тесты Application Layer
├── test_infrastructure_*.py             # Тесты Infrastructure Layer
├── test_presentation_*.py               # Тесты Presentation Layer
├── test_tui_*.py                        # Тесты TUI компонентов
├── test_tui_*_mvvm.py                   # MVVM тесты (View + ViewModel)
├── test_navigation_*.py                 # Тесты NavigationManager
├── test_integration_*.py                # Integration тесты
└── test_cli.py                          # Тесты CLI
```

### Naming Conventions

| Тип | Паттерн | Пример |
|-----|---------|--------|
| Test файл | `test_<module>.py` | `test_domain_entities.py` |
| Test класс | `Test<Component>` | `TestSession` |
| Test метод | `test_<scenario>` | `test_session_create` |
| Fixture | `<name>_fixture` или просто `<name>` | `mock_transport` |

### Категории тестов

#### 1. Unit тесты Domain Layer
- **Файлы:** `test_domain_*.py`
- **Тестируют:** entities, events, domain logic
- **Характеристика:** быстрые, изолированные, no mocks

#### 2. Unit тесты Application Layer
- **Файлы:** `test_application_*.py`
- **Тестируют:** use cases, state machine, application services
- **Характеристика:** тестируют бизнес-логику с моками инфраструктуры

#### 3. Unit тесты Infrastructure Layer
- **Файлы:** `test_infrastructure_*.py`
- **Тестируют:** DI container, event bus, transport, repositories
- **Характеристика:** могут использовать real компоненты или моки

#### 4. Unit тесты Presentation Layer
- **Файлы:** `test_presentation_*.py`
- **Тестируют:** ViewModels, Observable pattern
- **Характеристика:** тестируют reactive логику, подписки на события

#### 5. MVVM тесты
- **Файлы:** `test_tui_*_mvvm.py`
- **Тестируют:** компонент View + его ViewModel
- **Характеристика:** интеграционные тесты UI слоя

#### 6. Integration тесты
- **Файлы:** `test_integration_*.py`
- **Тестируют:** полный workflow с реальным/mock сервером
- **Характеристика:** медленные, но проверяют реальные сценарии

---

## Unit тесты

### AAA Pattern (Arrange-Act-Assert)

Все unit тесты следуют AAA паттерну:

```python
def test_some_functionality() -> None:
    # ARRANGE - подготовка
    obj = SomeClass()
    expected = "result"
    
    # ACT - выполнение
    actual = obj.do_something()
    
    # ASSERT - проверка
    assert actual == expected
```

---

## MVVM тесты

### Что такое MVVM тесты

MVVM тесты тестируют взаимодействие между:
- **View** - UI компонент (Textual Widget)
- **ViewModel** - логика презентации с Observable свойствами

### Тестирование Observable уведомлений

```python
def test_observable_notifies_on_change() -> None:
    """Проверить что Observable уведомляет подписчиков при изменении значения."""
    obs = Observable(1)
    changes = []
    
    obs.subscribe(lambda x: changes.append(x))
    obs.value = 2
    obs.value = 3
    
    assert changes == [2, 3]
```

---

## Integration тесты

### Что тестируем

Integration тесты проверяют:
- Взаимодействие нескольких компонентов
- Полные workflow сценарии
- Интеграцию с mock/real сервером

---

## Fixtures и моки

### Best Practices для Fixtures

1. **Изолированные fixtures** - каждый тест получает свой экземпляр
   ```python
   @pytest.fixture
   def fresh_container() -> DIContainer:
       """Создать новый DI контейнер для каждого теста."""
       return DIContainer()
   ```

2. **Fixtures с cleanup** - использовать yield
   ```python
   @pytest.fixture
   async def database() -> AsyncGenerator[DB, None]:
       db = await DB.connect()
       yield db
       await db.disconnect()  # cleanup
   ```

3. **Scope fixtures** - переиспользовать в пределах scope
   ```python
   @pytest.fixture(scope="session")
   def mock_server():
       """Запустить mock сервер один раз на всю сессию тестов."""
       return MockServer()
   ```

---

## Асинхронное тестирование

### pytest-asyncio

Для тестирования асинхронного кода используется декоратор `@pytest.mark.asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation() -> None:
    """Тест асинхронной операции."""
    result = await some_async_function()
    assert result == expected_value
```

---

## Coverage и метрики

### Запуск с coverage

```bash
# Базовый отчёт
pytest --cov=acp_client

# HTML отчёт
pytest --cov=acp_client --cov-report=html
# Открыть: htmlcov/index.html

# Терминальный отчёт с подробностями
pytest --cov=acp_client --cov-report=term-missing
```

### Целевые метрики

| Компонент | Целевое покрытие | Обоснование |
|-----------|-----------------|-------------|
| Domain | 95%+ | Критичная бизнес-логика |
| Application | 90%+ | Важные use cases |
| Infrastructure | 85%+ | Может использовать real компоненты |
| Presentation | 85%+ | Observable паттерны сложнее тестировать |
| TUI компоненты | 70%+ | Визуальное тестирование сложно |

---

## Best Practices

### 1. Arrange-Act-Assert (AAA)

Все тесты должны следовать этому паттерну:

```python
def test_something() -> None:
    # ARRANGE - подготовка данных и объектов
    obj = SomeClass()
    input_data = {"key": "value"}
    
    # ACT - выполнение проверяемого кода
    result = obj.process(input_data)
    
    # ASSERT - проверка результата
    assert result["status"] == "success"
    assert result["data"] is not None
```

### 2. Один тест = одна проверка

❌ **Плохо:**
```python
def test_user_operations() -> None:
    user = User.create("John")
    assert user.name == "John"  # Проверка 1
    user.set_email("john@example.com")
    assert user.email == "john@example.com"  # Проверка 2
    user.mark_active()
    assert user.is_active is True  # Проверка 3
```

✅ **Хорошо:**
```python
def test_user_creation() -> None:
    user = User.create("John")
    assert user.name == "John"

def test_user_email_setting() -> None:
    user = User.create("John")
    user.set_email("john@example.com")
    assert user.email == "john@example.com"

def test_user_activation() -> None:
    user = User.create("John")
    user.mark_active()
    assert user.is_active is True
```

### 3. Изоляция тестов

Каждый тест должен быть независимым и не зависеть от порядка выполнения.

### 4. Моки vs Реальные объекты

| Случай | Использовать |
|--------|--------------|
| External dependencies (HTTP, DB) | Моки или fixtures |
| Pure logic | Реальные объекты |
| Async операции | Моки с side_effect |
| Тяжёлые операции | Моки |

### 5. Naming Conventions

❌ **Плохо:**
```python
def test_1() -> None:
    ...
```

✅ **Хорошо:**
```python
def test_session_creation_with_valid_parameters() -> None:
    ...
```

---

## Запуск тестов

### Все тесты

```bash
# Из корня репозитория
uv run --directory acp-client python -m pytest

# Или с полным путём
uv run --directory acp-client python -m pytest tests/
```

### Конкретный файл

```bash
uv run --directory acp-client python -m pytest tests/test_domain_entities.py
uv run --directory acp-client python -m pytest tests/test_tui_chat_view_mvvm.py
```

### Конкретный тест

```bash
uv run --directory acp-client python -m pytest \
  tests/test_domain_entities.py::TestSession::test_session_create
```

### Фильтрация по имени

```bash
# Запустить тесты содержащие "session" в имени
uv run --directory acp-client python -m pytest -k "session"

# Запустить тесты НЕ содержащие "slow"
uv run --directory acp-client python -m pytest -k "not slow"
```

### С coverage

```bash
# Терминальный отчёт
uv run --directory acp-client python -m pytest --cov=acp_client

# HTML отчёт
uv run --directory acp-client python -m pytest \
  --cov=acp_client \
  --cov-report=html
# Открыть acp-client/htmlcov/index.html
```

### Verbose режим

```bash
# Вывод на уровне каждого теста
uv run --directory acp-client python -m pytest -v

# С выводом print statements
uv run --directory acp-client python -m pytest -v -s
```

---

## Отладка тестов

### pytest -v -s (вывод print)

```bash
uv run --directory acp-client python -m pytest -v -s tests/test_something.py
```

### pytest --pdb (интерактивный debugger)

```bash
# Остановиться в debugger при ошибке теста
uv run --directory acp-client python -m pytest --pdb tests/test_something.py
```

### pytest -x (остановиться на первой ошибке)

```bash
# Остановиться после первого failing теста
uv run --directory acp-client python -m pytest -x tests/
```

---

## CI/CD интеграция

### Проверка в Makefile

```bash
# Из acp-client/ директории:
make test              # Запустить тесты
make test-coverage     # Тесты с coverage
make test-verbose      # Verbose вывод
```

---

## Типичные проблемы и решения

### Проблема 1: Async тесты не работают

❌ **Ошибка:**
```
RuntimeError: no running event loop
```

✅ **Решение:** Использовать декоратор `@pytest.mark.asyncio`

```python
@pytest.mark.asyncio
async def test_async_operation() -> None:
    result = await some_async_function()
    assert result == expected
```

### Проблема 2: Observable tests не уведомляют

❌ **Проблема:**
```python
obs = Observable([1, 2, 3])
changes = []
obs.subscribe(lambda x: changes.append(x))

obs.value = [1, 2, 3]  # Одинаковое значение
assert len(changes) == 1  # Провалится, будет 0
```

✅ **Решение:** Observable не уведомляет если значение не изменилось

```python
obs = Observable([1, 2, 3])
changes = []
obs.subscribe(lambda x: changes.append(x))

obs.value = [1, 2, 3, 4]  # Другое значение
assert len(changes) == 1  # ✓
```

### Проблема 3: Невозможно импортировать модули из src

❌ **Ошибка:**
```
ModuleNotFoundError: No module named 'acp_client'
```

✅ **Решение:** pyproject.toml должен содержать

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "../acp-server/src"]
```

---

## Заключение

Тестирование в acp-client следует многоуровневому подходу:

1. **Unit тесты** - быстрые, изолированные, по слоям
2. **MVVM тесты** - тестирование связки UI + логики
3. **Integration тесты** - проверка workflows с реальным сервером

Все тесты:
- Следуют AAA паттерну (Arrange-Act-Assert)
- Имеют понятные имена и docstrings
- Используют fixtures для изоляции
- Проверяют одно логическое действие

Для запуска и разработки используйте:

```bash
# Все тесты
uv run --directory acp-client python -m pytest

# С coverage
uv run --directory acp-client python -m pytest --cov=acp_client -v

# С отладкой
uv run --directory acp-client python -m pytest -v -s --tb=short
```
