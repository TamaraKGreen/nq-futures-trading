# NQ Futures Trading System

Algorithmic trading system for NQ (Nasdaq-100) futures with a gate/flag strategy design, configurable data sources, and a hierarchical processing pipeline.

## Features

- **Gate/Flag Strategy Engine** -- Multi-condition entry signals using volume profile, session timing, order flow, and buy/sell ratio gates. All gates must pass before a trade triggers.
- **Databento Integration** -- Unified interface for real-time streaming and historical market data with automatic front-month contract rolling.
- **Intelligent Caching** -- 90%+ cost reduction through layered caching of market data, with automated gap detection and backfill.
- **Production Monitoring** -- Built-in performance monitor, cost tracker, and structured logging for live operation.
- **Configurable Pipeline** -- Modular architecture where data collectors, strategies, and execution are independently swappable.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Market Data | Databento API (live + historical) |
| Data Schemas | Trades, OHLCV (1m/1h), BBO, MBP |
| Configuration | YAML + `.env` |
| Monitoring | Custom performance monitor + cost tracker |

## Quick Start

```bash
# Clone and install
git clone https://github.com/michael-abdo/nq-futures-trading.git
cd nq-futures-trading

pip install -r nq_futures_system/requirements.txt

# Configure API key
echo "DATABENTO_API_KEY=your-key-here" > nq_futures_system/config/.env

# Run the production system
python nq_futures_system/production_system.py --help

# Run tests
python nq_futures_system/test_databento_integration.py
```

## Project Structure

```
nq_futures_system/
├── production_system.py       # Main entry point / orchestrator
├── config/                    # YAML settings + .env
├── data/
│   └── collectors/            # Databento client, historical backfill
├── strategies/
│   ├── gate_flag_strategy.py  # Core strategy implementation
│   └── gates/                 # Volume profile, session timing, order flow
├── monitoring/                # Performance monitor, cost tracker
├── utils/                     # Gap detector, cache cleanup, validators
├── deployment/                # Deployment configs
├── scripts/                   # Daily update, maintenance
└── tests/                     # Test suite
```

## Gate/Flag Strategy

A trade signal fires only when **all four gates** pass simultaneously:

| Gate | Condition |
|------|-----------|
| Volume Profile | Price above/below 70% liquidity zone (24h) |
| Session Timing | Not within 30 min of cash open |
| Order Flow | Large order (50+ contracts) in trade direction |
| Buy/Sell Ratio | At least 2:1 ratio in trade direction |

See [`GATE_FLAG_STRATEGY_DESIGN.md`](nq_futures_system/GATE_FLAG_STRATEGY_DESIGN.md) for full details.

## License

MIT
