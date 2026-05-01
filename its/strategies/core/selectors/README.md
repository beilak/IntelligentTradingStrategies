# Selector checklist

Эти селекторы используются как `pre-selector` шаги в sklearn/skfolio pipeline.
Главный риск: потерять реальные тикеры из `pd.DataFrame.columns` и передать дальше
матрицу без имен активов. Ниже минимальный контракт, который нужно соблюдать при
добавлении нового селектора.

## Базовый контракт

Новый селектор должен наследоваться от `Selectros`:

```python
from its.strategies.core.types.selectors_types import Selectros


class MySelector(Selectros):
    ...
```

`Selectros` уже подключает `DataFrameSelectorMixin` и `SelectorMixin`. Поэтому
обычно не нужно писать свой `transform`: общий `transform` сам сохранит `index` и
`columns`, если `fit` подготовил корректную маску.

## Что обязательно сделать в fit

1. Валидировать вход через `validate_data(..., reset=True)`.

```python
from sklearn.utils.validation import validate_data

X_validated = validate_data(
    self,
    X,
    ensure_all_finite="allow-nan",
    reset=True,
)
```

2. Если для логики нужны имена тикеров, брать их из исходного `DataFrame`, а не из
результата `validate_data`.

```python
asset_names = X.columns if isinstance(X, pd.DataFrame) else None
```

`validate_data` возвращает numpy-массив и может потерять `columns`, поэтому не
используйте `X_validated.columns`.

3. Записать `self.to_keep_` как позиционную numpy-маску:

```python
self.to_keep_ = mask.to_numpy(dtype=bool)  # если mask это pd.Series
# или
self.to_keep_ = np.asarray(mask, dtype=bool)
```

`self.to_keep_` должен быть:

- тип: `np.ndarray`
- dtype: `bool`
- длина: `X.shape[1]`
- порядок: строго такой же, как порядок колонок в `X`

Не храните в `to_keep_` `pd.Series`, список тикеров или список индексов колонок.

## Как выбирать по тикерам

Если селектор выбирает активы по внешней таблице, сначала выровняйте результат по
`X.columns`, и только потом превращайте в numpy-маску.

```python
mask = pd.Series(False, index=X.columns)
mask.loc[mask.index.intersection(selected_tickers)] = True
self.to_keep_ = mask.to_numpy(dtype=bool)
```

Так `DataFrameSelectorMixin.transform` выполнит:

```python
return X.loc[:, mask]
```

и в результате останутся реальные имена колонок.

## Что нельзя делать

Не создавайте DataFrame из numpy без восстановления колонок, если дальше нужны
тикеры:

```python
prices = pd.DataFrame(X_validated)  # колонки станут 0, 1, 2...
```

Допустимо только если селектору не нужны имена активов. Если нужны, используйте
исходный `X`:

```python
prices = X if isinstance(X, pd.DataFrame) else pd.DataFrame(X_validated)
```

Не делайте маску из неупорядоченного набора тикеров:

```python
self.to_keep_ = np.isin(selected_tickers, X.columns)  # неверный порядок
```

Правильно:

```python
self.to_keep_ = np.isin(X.columns.astype(str), selected_tickers).astype(bool)
```

## Диагностические значения

Если селектор сохраняет score по активам, храните имена отдельно:

```python
self.asset_names_ = X.columns.to_numpy()
self.scores_ = scores.to_numpy()
```

И возвращайте диагностику с индексом тикеров:

```python
def get_scores(self):
    check_is_fitted(self)
    return pd.Series(self.scores_, index=self.asset_names_, name="scores")
```

Не пытайтесь брать индекс из `self.to_keep_`: это должна быть numpy-маска без
индекса.

## Минимальные тесты для нового селектора

Для каждого нового селектора добавьте тест, который проверяет:

1. `fit` принимает `pd.DataFrame` с тикерами в колонках.
2. `selector.to_keep_` это `np.ndarray` с `dtype == bool`.
3. `selector.transform(prices)` возвращает `pd.DataFrame`.
4. `list(transformed.columns)` равен ожидаемому списку тикеров.

Пример:

```python
def test_my_selector_preserves_dataframe_columns() -> None:
    prices = pd.DataFrame(
        {
            "AAA": [100, 101, 102],
            "BBB": [100, 99, 98],
        },
        index=pd.bdate_range("2024-01-01", periods=3),
    )

    selector = MySelector(...).fit(prices)
    transformed = selector.transform(prices)

    assert isinstance(selector.to_keep_, np.ndarray)
    assert selector.to_keep_.dtype == bool
    assert list(transformed.columns) == ["AAA"]
```

## Перед коммитом

Запустите точечные проверки:

```bash
poetry run pytest tests/strategies_model/selectors/test_new_selectors.py
poetry run ruff check its/strategies/core/selectors tests/strategies_model/selectors
```

Если селектор импортируется из `its.strategies.core.selectors`, добавьте его в
`its/strategies/core/selectors/__init__.py` и `__all__`.
