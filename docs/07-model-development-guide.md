# Руководство модельера и разработчика компонентов

[К оглавлению](README.md)

Этот раздел описывает, как расширять систему новыми источниками данных, компонентами моделей, готовыми стратегиями и GA-генами.

## Общий принцип

Модельер должен описать только предметную логику:

- как отбирать активы;
- как формировать сигнал;
- как распределять веса;
- как управлять позицией.

Инфраструктурные задачи берет на себя платформа:

- загрузка данных;
- подготовка матриц;
- запуск тестов;
- построение отчетов;
- регистрация в UI;
- сравнение результатов;
- генерация новых комбинаций через GA.

## Типы компонентов

### Selector

Селектор реализует предварительную фильтрацию активов.

Базовый тип:

```text
its/strategies/core/types/selectors_types.py
```

Класс должен наследоваться от `Selectros` и реализовать `fit`. Внутри `fit` необходимо выставить:

```python
self.to_keep_ = ...
```

`to_keep_` - булевая маска активов.

### Signal

Сигнальная модель реализует дополнительный отбор после pre-selection.

Базовый тип:

```text
its/strategies/core/types/signals_types.py
```

Класс наследуется от `Siglans` и также выставляет `to_keep_`.

### Allocation

Аллокатор определяет веса портфеля. В текущей реализации используются skfolio-аллокаторы и собственные расширения:

```text
its/strategies/core/optimization
```

Аллокатор должен быть совместим с pipeline и выдавать веса через интерфейс skfolio.

## Создание нового селектора

1. Создать файл в:

```text
its/strategies/core/selectors
```

2. Реализовать класс.

Минимальная структура:

```python
import numpy as np
import sklearn.utils.validation as skv

from its.strategies.core.types.selectors_types import Selectros


class MySelector(Selectros):
    """Описание логики селектора."""

    def __init__(self, my_parameter: int = 10):
        self.my_parameter = my_parameter

    def fit(self, X, y=None):
        X = skv.validate_data(self, X, ensure_all_finite="allow-nan")
        self.to_keep_ = np.ones(X.shape[1], dtype=bool)
        return self
```

3. Добавить класс в:

```text
its/strategies/core/selectors/__init__.py
```

4. Добавить имя класса в `__all__`.

После этого Strategy Backend сможет отобразить компонент в реестре.

## Создание нового сигнала

1. Создать файл в:

```text
its/strategies/core/signals
```

2. Наследоваться от `Siglans`.
3. Реализовать `fit`.
4. Добавить импорт и `__all__` в:

```text
its/strategies/core/signals/__init__.py
```

## Создание нового аллокатора

1. Создать или расширить файл в:

```text
its/strategies/core/optimization
```

2. Если используется skfolio, желательно сохранить совместимость с `BaseOptimization`.
3. Добавить экспорт в:

```text
its/strategies/core/optimization/__init__.py
```

## Создание модели ядра стратегии

Готовые модели хранятся в:

```text
its/strategies/models
```

Модель должна наследоваться от `StrategyBuilder`.

Пример структуры:

```python
from typing import override

from its.strategies.core.optimization import EqualWeighted
from its.strategies.core.selectors import IntradayTurnoverSelector
from its.strategies.core.types.strategy_types import Pipeline, Strategy, StrategyBuilder


class MyStrategyBuilder(StrategyBuilder):
    """Краткое описание стратегии."""

    @override
    def build(self) -> Strategy:
        return Strategy(
            name="MyStrategy",
            description="Описание модели",
            pipeline=Pipeline(
                steps=[
                    (
                        "pre_selection",
                        IntradayTurnoverSelector(
                            asset_universe_prices=self._asset_universe_prices,
                            lookback_bars=10,
                            min_turnover=1_000_000,
                        ),
                    ),
                    ("allocation", EqualWeighted()),
                ]
            ),
        )
```

Регистрация:

1. Импортировать класс в `its/strategies/models/__init__.py`.
2. Добавить имя класса в `__all__`.

После этого модель появится во вкладке "Ядро торговой стратегии".

## Создание полноценной trading strategy

Полная торговая стратегия находится на уровень выше ядра: она добавляет правила жизненного цикла позиции.

Базовые типы:

```text
its/strategies_model/core/trading_strategy.py
```

Нужно наследоваться от `TradingStrategyBuilder` и реализовать:

- `name`;
- `description`;
- `build_core_strategy`;
- при необходимости `build_exit_policy`;
- при необходимости `build_metadata`.

Пример:

```python
from typing import override

from its.strategies.models.top_turnover_eq import ModelTurnoverWithEQBuilder
from its.strategies_model.core.trading_strategy import (
    FixedStopTakeProfitPolicy,
    TradingStrategyBuilder,
)


class MyTradingStrategyBuilder(TradingStrategyBuilder):
    @property
    @override
    def name(self) -> str:
        return "MyTradingStrategy"

    @property
    @override
    def description(self) -> str:
        return "Core strategy with fixed stop loss and take profit."

    @override
    def build_core_strategy(self):
        return ModelTurnoverWithEQBuilder(
            self._asset_universe_prices,
            self._assets_info,
            self._runtime_context,
            self._dividends_info,
        ).build()

    @override
    def build_exit_policy(self):
        return FixedStopTakeProfitPolicy(
            stop_loss_pct=0.01,
            take_profit_pct=0.03,
        )
```

Регистрация выполняется в:

```text
its/strategies_model/model/__init__.py
```

## Добавление компонента в GA

GA использует `GeneDefinition`.

Файл:

```text
its/ga/types.py
```

Минимальный пример гена:

```python
from its.ga.types import GeneDefinition
from its.strategies.core.signals import KeepAllSignal

GENES = [
    GeneDefinition(
        id="pass_signal",
        title="Pass-signal",
        description="Do not apply an additional signal filter.",
        group="signal",
        component=KeepAllSignal,
    )
]
```

Группы:

```text
pre_selection
signal
allocation
```

Гены размещаются в соответствующих папках:

```text
its/ga/alphabets/pre_selection
its/ga/alphabets/signal
its/ga/alphabets/allocation
```

Если компоненту нужны runtime-данные, используется `runtime_args`:

```python
GeneDefinition(
    id="DividendHistorySelector",
    title="DividendHistorySelector",
    description="Select assets with dividend history.",
    group="pre_selection",
    component=DividendHistorySelector,
    wrapper=SafeEmptySelector,
    runtime_args={"dividends_df": "dividends_info"},
)
```

## Runtime context GA

GA передает компонентам:

| Ключ | Содержимое |
| --- | --- |
| `asset_universe_prices` | длинная таблица свечей |
| `assets_info` | справочник активов |
| `dividends_info` | дивиденды |

## Рекомендации к компонентам

- Не использовать будущие данные при расчете признаков.
- Проверять входные данные и выдавать понятные ошибки.
- Использовать `SafeEmptySelector`, если компонент может выбрать ноль активов.
- Оставлять docstring: Strategy UI показывает описание из кода.
- Делать параметры явными в `__init__`.
- Не менять глобальное состояние.
- Сохранять совместимость с pandas DataFrame и sklearn/skfolio pipeline.
- Покрывать новую логику тестами.

## Тестирование новых компонентов

Тесты находятся в:

```text
tests
```

Рекомендуемые команды:

```bash
poetry run pytest
poetry run ruff check .
poetry run mypy .
```

В текущем проекте используются тесты для:

- загрузчиков данных;
- селекторов;
- сигналов;
- аллокаторов;
- стратегий;
- GA engine;
- trading strategy backtest.

