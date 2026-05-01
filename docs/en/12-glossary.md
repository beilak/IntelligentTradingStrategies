# Glossary

[Back to Contents](README.md)

## ITS

Intelligent Trading Strategies, a system for forming trading strategies.

## Data Hub

The data subsystem. It handles sources, instruments, quotes, dividends, custom bars, and data APIs.

## Strategy Lab

The model subsystem. It handles component registries, ready strategies, testing, and comparison.

## GA Lab

The subsystem for generating strategies through a genetic algorithm.

## Launchpad

The main program window with tiles for launching subsystems.

## Pre-selection

Initial asset selection before signal and allocation stages.

## Signal

A component that forms a trading signal or additional filter after pre-selection.

## Allocation

A component that calculates asset weights in the portfolio.

## Strategy Builder

A Python class that assembles the strategy core and returns a `Strategy` object.

## Trading Strategy

A full trading strategy: portfolio-model core plus execution rules such as stop-loss and take-profit.

## CPCV

Combinatorial Purged Cross-Validation, a validation method with combinatorial test folds and purging.

## WalkForward

A sequential validation method where a strategy is trained on one window and tested on a following window.

## Backtesting

Historical trading simulation with rebalancing, fees, slippage, and capital.

## Rebalance

Periodic change of portfolio weights according to the strategy.

## Equity Curve

A curve of portfolio value or cumulative return.

## Drawdown

A decline from the previous portfolio-value maximum.

## Sharpe Ratio

Risk-adjusted return measure calculated as mean return divided by standard deviation.

## Calmar Ratio

Return relative to maximum drawdown.

## CVaR

Conditional Value at Risk, an estimate of average tail loss at a confidence level.

## GA

Genetic Algorithm, an algorithm that generates and selects strategies.

## GeneDefinition

Description of a GA gene: component, parameters, wrapper, and runtime dependencies.

## Alphabet

A gene set for one group: pre-selection, signal, or allocation.

## Materialization

Creation of a Python strategy file from GA results.

## FIGI

Financial Instrument Global Identifier.

## TQBR

Russian equity class on Moscow Exchange, used by default.

## CETS

Currency-instrument class used for `GLDRUB_TOM` and custom gold bars.

## OHLCV

Candle data: open, high, low, close, volume.

## Custom Gold Bar

An alternative bar built through the value of a specified amount of gold.

