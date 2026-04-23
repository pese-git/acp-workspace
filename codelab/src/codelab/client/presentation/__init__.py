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

from codelab.client.presentation.base_view_model import BaseViewModel
from codelab.client.presentation.file_viewer_view_model import FileViewerViewModel
from codelab.client.presentation.filesystem_view_model import FileSystemViewModel
from codelab.client.presentation.observable import Observable, ObservableCommand
from codelab.client.presentation.permission_view_model import PermissionViewModel
from codelab.client.presentation.plan_view_model import PlanViewModel
from codelab.client.presentation.terminal_log_view_model import TerminalLogViewModel
from codelab.client.presentation.terminal_view_model import TerminalViewModel
from codelab.client.presentation.view_model_factory import ViewModelFactory

__all__ = [
    'Observable',
    'ObservableCommand',
    'BaseViewModel',
    'FileSystemViewModel',
    'FileViewerViewModel',
    'PermissionViewModel',
    'PlanViewModel',
    'TerminalLogViewModel',
    'TerminalViewModel',
    'ViewModelFactory',
]
