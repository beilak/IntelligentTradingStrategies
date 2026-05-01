# Purpose and User Roles

[Back to Contents](README.md)

## System Purpose

ITS is designed to develop trading strategies as a set of standardized and interchangeable components. The system separates the modeler's research work from infrastructure tasks such as data loading, return-matrix preparation, test execution, report rendering, model comparison, and automatic strategy generation.

The core product idea is to turn trading algorithm development into a controlled engineering workflow. The modeler describes the mathematical and economic logic of a component, while the platform handles:

- retrieving and normalizing market data;
- registering components;
- assembling strategies into a unified pipeline;
- running robustness tests;
- storing results;
- comparing models;
- searching and evolving strategies through a genetic algorithm.

## Target Users

### Financial Modeler

The main user. Typical tasks:

- formulate market-behavior hypotheses;
- create asset selectors, signal models, and allocators;
- validate strategies on historical data;
- compare results;
- pass the best strategies to further research or a production circuit.

### Quant Researcher

Uses the system to research factor stability and portfolio rules:

- test different asset-selection regimes;
- assess stability on WalkForward windows;
- analyze overfitting risk through CPCV;
- compare return and risk metrics.

### Integration Developer

Extends the system with new data sources:

- quotes;
- instrument reference data;
- dividends;
- alternative bars;
- fundamental, event, or news-based features.

### Technical Buyer or Client

Receives the system as a platform that can be launched with one command, explored through UI, and extended through documented protocols.

## Problems Solved by the System

### 1. Data Centralization

Data Hub connects market data sources and exposes a unified API for quotes, instruments, currencies, dividends, and custom bars.

### 2. Trading Model Standardization

A strategy is represented as a sequence of components:

```text
pre-selection -> signal -> allocation
```

This structure makes models comparable, extensible, and suitable for automatic generation.

### 3. Fast Hypothesis Testing

Strategy Lab lets the user select a model, configure a test, and obtain:

- return and risk metrics;
- equity curve charts;
- WalkForward OOS curve;
- portfolio composition by rebalance date;
- sector aggregation;
- stop-loss and take-profit execution events for full trading strategies.

### 4. New Strategy Generation

GA Lab uses component alphabets as a search space. The genetic algorithm evaluates gene combinations and saves the best strategies to `its/strategies/models`.

### 5. LLM-Assisted Component Development

Because components have explicit protocols and narrow interfaces, LLMs can be used to rapidly generate new selectors, signals, and allocators. The modeler does not need to redesign the full testing pipeline for every new component.

## Design Principles

- **standardized models** - each strategy has a unified and reproducible pipeline;
- **Open-Closed Principle** - new components can be added without changing the core;
- **Interface Segregation Principle** - selectors, signals, allocators, policies, and data sources use focused interfaces;
- **verifiability** - core behavior is covered by tests and available through APIs;
- **extensibility** - new data sources, components, and GA genes have dedicated directories;
- **reproducibility** - test results are cached and GA candidates are materialized as Python files.

## User Outcomes

After working with the system, the user obtains:

- available asset and market data lists;
- assembled trading models;
- CPCV, WalkForward, and Backtesting reports;
- model rankings;
- generated strategy files;
- a software base for further scientific, product, or investment-analytical work.

