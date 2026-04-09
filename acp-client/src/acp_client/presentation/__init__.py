"""Presentation Layer (MVVM паттерн).

Модуль содержит ViewModels и Observable объекты для управления UI состоянием.
Полностью отделён от Textual и может использоваться с любым интерфейсом.

Компоненты:
- Observable: Реактивное свойство с Observer паттерном
- ObservableCommand: Команда с отслеживанием статуса выполнения
- BaseViewModel: Базовый класс для всех ViewModels
- SessionViewModel: ViewModel для управления сессиями
- ChatViewModel: ViewModel для управления чатом
- UIViewModel: ViewModel для общего UI состояния
- ViewModelFactory: Factory для регистрации ViewModels в DIContainer
"""

from acp_client.presentation.base_view_model import BaseViewModel
from acp_client.presentation.observable import Observable, ObservableCommand
from acp_client.presentation.view_model_factory import ViewModelFactory

__all__ = [
    'Observable',
    'ObservableCommand',
    'BaseViewModel',
    'ViewModelFactory',
]
