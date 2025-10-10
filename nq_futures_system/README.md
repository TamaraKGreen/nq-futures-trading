# NQ Futures Trading System

A comprehensive trading system for NQ futures with Databento integration for real-time and historical market data.

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Test Databento integration:**
```bash
python test_databento_integration.py
```

## Databento Integration

The system provides a unified interface for both live and historical NQ futures data:

### Features

- **Live Data Streaming**: Real-time trades, quotes, and order book data
- **Historical Data Access**: Retrieve past market data for backtesting
- **Automatic Contract Rolling**: Get current front-month contract automatically
- **Multiple Data Schemas**: Support for trades, OHLCV, BBO, and more

### Usage Example

```python
from data.collectors.databento_client import DatabentoClient

# Initialize client (uses API key from .env file)
client = DatabentoClient()

# Get current front-month NQ contract
front_month = client.get_continuous_contract("NQ")
print(f"Current contract: {front_month}")

# Get historical data
from datetime import datetime, timedelta

end = datetime.now()
start = end - timedelta(days=5)

df = client.get_historical_data(
    symbols=[front_month],
    start=start,
    end=end,
    schema="ohlcv-1m"  # 1-minute bars
)

# Subscribe to live data (market hours only)
async def handle_trade(record):
    print(f"Trade: {record.symbol} @ {record.price/1e9:.2f}")

await client.subscribe_live(
    symbols=[front_month],
    schema="trades",
    callback=handle_trade
)

await client.start_live_feed()
```

### Available Data Schemas

- **trades**: Individual trade records
- **ohlcv-1m**: 1-minute OHLCV bars
- **ohlcv-1h**: 1-hour OHLCV bars
- **bbo**: Best bid/offer quotes
- **mbp-1**: Market by price (1 level)

## Project Structure

```
nq_futures_system/
├── data/
│   ├── collectors/        # Data collection modules
│   │   └── databento_client.py
│   ├── storage/          # Data persistence (coming soon)
│   └── processors/       # Data analysis (coming soon)
├── strategies/           # Trading strategies (coming soon)
├── backtesting/         # Backtesting engine (coming soon)
├── execution/           # Order execution (coming soon)
└── config/              # Configuration files
    └── .env            # API keys (not in git)
```

## Configuration

Create a `config/.env` file with your Databento API key:
```
DATABENTO_API_KEY=your-api-key-here
```

**Important**: Never commit the `.env` file to git!

## Development Status

- ✅ Databento integration (live & historical)
- ⏳ Volume profile calculator
- ⏳ Buyer aggression detector
- ⏳ Backtesting framework
- ⏳ Strategy engine
- ⏳ Order execution integration

## Trading Hours

CME NQ Futures trading hours:
- Sunday 6:00 PM - Friday 5:00 PM ET
- Daily break: 5:00 PM - 6:00 PM ET

Live data is only available during market hours.