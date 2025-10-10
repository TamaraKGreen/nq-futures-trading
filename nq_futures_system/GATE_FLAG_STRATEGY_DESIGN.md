# Gate/Flag Strategy System Design

## Overview

A comprehensive order-based trading strategy system for NQ futures that uses multiple conditional "gates" or "flags" to generate precise entry signals. The system emphasizes fail-fast principles and precise signal visualization for strategy refinement.

## Core Strategy Logic

The strategy triggers entry signals when ALL of the following conditions (gates) are met:

1. **Volume Profile Gate**: Price is above/below the 70% liquidity zone of the past 24 hours
2. **Session Timing Gate**: We are NOT within 30 minutes of cash opening session
3. **Order Flow Gate**: A large order (50+ contracts) appears in accordance with our position
4. **Buy/Sell Ratio Gate**: The ratio of buy/sell volume is at least 2:1

## System Architecture

### Project Structure

```
nq_futures_system/
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py           # Abstract strategy interface
│   ├── gate_flag_strategy.py      # Main strategy implementation
│   ├── gates/                     # Modular gate components
│   │   ├── __init__.py
│   │   ├── volume_profile_gate.py # 70% liquidity zone detection
│   │   ├── session_timing_gate.py # Cash opening session check
│   │   ├── order_flow_gate.py     # Large order + buy/sell ratio
│   │   └── base_gate.py           # Abstract gate interface
│   └── indicators/
│       ├── __init__.py
│       ├── volume_profile.py      # 24-hour volume profile calculator
│       ├── order_flow.py          # Buyer aggression & order analysis
│       └── session_manager.py     # Market session timing utilities
│
├── backtesting/
│   ├── __init__.py
│   ├── backtest_engine.py         # Main backtesting framework
│   ├── signal_tracker.py          # Track precise entry signals
│   ├── performance_metrics.py     # Strategy evaluation
│   ├── reports/
│   │   ├── html_report.py         # Interactive HTML reports
│   │   └── signal_visualization.py # Entry signal chart overlays
│   └── data_loader.py             # Historical data for backtesting
│
├── ui/                            # Web UI for strategy testing
│   ├── __init__.py
│   ├── app.py                     # Flask/FastAPI main app
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── charts/                # Chart.js/Plotly components
│   ├── templates/
│   │   ├── strategy_tester.html   # Main strategy testing interface
│   │   ├── signal_viewer.html     # Entry signal visualization
│   │   └── backtest_results.html  # Results dashboard
│   └── api/
│       ├── strategy_api.py        # Strategy parameter endpoints
│       ├── backtest_api.py        # Backtesting endpoints
│       └── data_api.py            # Real-time data endpoints
```

### Core Components

#### 1. Base Strategy Framework

```python
# strategies/base_strategy.py
class BaseStrategy:
    def __init__(self):
        self.gates = []
        self.signal_history = []
    
    def check_entry_signal(self, current_data) -> Tuple[bool, str]:
        """Check all gates for entry signal"""
        pass
    
    def get_signal_context(self) -> dict:
        """Return detailed context at signal time"""
        pass
```

#### 2. Gate Implementation

```python
# strategies/gates/base_gate.py
class BaseGate:
    def evaluate(self, data) -> bool:
        """Return True if gate condition is met"""
        pass
    
    def get_failure_reason(self) -> str:
        """Return why gate failed for UI display"""
        pass
    
    def get_gate_status(self) -> dict:
        """Return detailed gate status for UI"""
        pass
```

#### 3. Main Strategy Implementation

```python
# strategies/gate_flag_strategy.py
class GateFlagStrategy(BaseStrategy):
    def __init__(self):
        self.gates = [
            VolumeProfileGate(threshold_pct=70, lookback_hours=24),
            SessionTimingGate(avoid_cash_open_minutes=30),
            OrderFlowGate(min_order_size=50, buy_sell_ratio=2.0)
        ]
    
    def check_entry_signal(self, current_data):
        gate_results = []
        for gate in self.gates:
            passed = gate.evaluate(current_data)
            gate_results.append({
                'gate': gate.__class__.__name__,
                'passed': passed,
                'reason': gate.get_failure_reason() if not passed else 'OK',
                'status': gate.get_gate_status()
            })
        
        all_passed = all(result['passed'] for result in gate_results)
        return all_passed, gate_results
```

## UI Design for Precise Entry Signal Visualization

### Main Strategy Testing Interface

```
┌─ Gate/Flag Strategy Tester ──────────────────────────────────────────────┐
│ Strategy: [Custom Gate Strategy ▼]   Status: ⏸ Paused   Time: 10:15:30  │
│                                                                          │
│ ┌─ Gate Status Panel ─────────────┐  ┌─ Price Chart with Signals ─────┐  │
│ │ 🟢 Volume Profile Gate          │  │ NQZ5 | Current: 19,234.50      │  │
│ │    Above 70% liquidity: ✅      │  │                                 │  │
│ │    Zone: 19,220-19,240          │  │ 19,250 ├─70% Zone──●●●──────── │  │
│ │                                 │  │ 19,240 ├──────────────●●●───── │  │
│ │ 🟢 Session Timing Gate          │  │ 19,230 ├────ENTRY──●●●●●●──── │  │
│ │    30+ min from cash open: ✅   │  │ 19,220 ├──────────────●●●───── │  │
│ │    Next restriction: 3:25 PM    │  │ 19,210 ├─────────────────────── │  │
│ │                                 │  │        └─ 10:00 ─ 10:30 ─ 11:00 │  │
│ │ 🔴 Order Flow Gate              │  └─────────────────────────────────┘  │
│ │    Large order detected: ✅     │                                      │
│ │    Buy/Sell ratio: 1.8:1 ❌    │  ┌─ Real-time Order Flow ─────────┐  │
│ │    (Need 2.0:1 minimum)         │  │ Last 5 Minutes:                │  │
│ │                                 │  │ 10:15:30 │ 85 lots │ BUY       │  │
│ │ OVERALL: 🔴 WAITING             │  │ 10:15:15 │ 120 lots │ BUY      │  │
│ │ Next check in: 5 seconds        │  │ 10:14:45 │ 45 lots │ SELL      │  │
│ └─────────────────────────────────┘  │ 10:14:30 │ 200 lots │ BUY ⭐    │  │
│                                      │ Current Ratio: 1.8:1 (Need 2:1) │  │
│ ┌─ Entry Signal Alerts ───────────┐  └─────────────────────────────────┘  │
│ │ 🚨 ENTRY SIGNAL at 09:45:30     │                                      │
│ │    Price: 19,235.50             │  ┌─ Backtest Controls ──────────────┐  │
│ │    All gates: PASSED ✅         │  │ Mode: [Live ▼] [Backtest]        │  │
│ │    Action: BUY signal generated │  │ Speed: [1x ▼] Progress: ██░░ 60%  │  │
│ └─────────────────────────────────┘  └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Precise Signal Analysis View

```
┌─ Entry Signal Deep Dive: 09:45:30 ──────────────────────────────────────┐
│                                                                          │
│ ┌─ Signal Timeline ──────────────────────────────────────────────────────┐ │
│ │ 09:45:25  Volume Profile Gate: ✅ Price 19,235 above 70% zone         │ │
│ │ 09:45:27  Session Timing Gate: ✅ 2h 15m since cash open             │ │
│ │ 09:45:28  Order Flow: Large order detected (150 lots)                │ │
│ │ 09:45:29  Order Flow: Buy/Sell ratio reached 2.1:1 ✅                │ │
│ │ 09:45:30  🚨 ALL GATES PASSED - ENTRY SIGNAL TRIGGERED               │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ ┌─ Market Context at Signal ─────────────────────────────────────────────┐ │
│ │ Price Action:                    Order Flow Details:                   │ │
│ │ • Entry Price: 19,235.50        • Triggering Order: 150 lots @ 19,235 │ │
│ │ • 70% Liquidity Zone: 19,220    • 5-min Buy Volume: 2,340 lots       │ │
│ │ • Distance from Zone: +15.50    • 5-min Sell Volume: 1,110 lots      │ │
│ │ • Volume Profile: Breakout      • Buy/Sell Ratio: 2.11:1             │ │
│ │                                 • Large Orders (50+): 8 buy, 2 sell   │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│ [Export Signal] [Add to Strategy] [Backtest Similar] [Live Trade]        │
└──────────────────────────────────────────────────────────────────────────┘
```

## Implementation Roadmap

### Phase 1: Core Strategy Framework (Week 1)
1. Create base strategy infrastructure
2. Implement volume profile calculator
3. Build session timing gate

### Phase 2: Order Flow Analysis (Week 2)
4. Large order detection
5. Buy/sell ratio calculator
6. Complete gate implementation

### Phase 3: Backtesting Engine (Week 3)
7. Build backtesting framework
8. Performance metrics

### Phase 4: Web UI Development (Week 4)
9. Flask/FastAPI web interface
10. Signal visualization
11. Backtesting results dashboard

### Phase 5: Integration & Testing (Week 5)
12. Live trading integration
13. Comprehensive testing

## Key Implementation Details

### Volume Profile Calculation
```python
def calculate_volume_profile(data: pd.DataFrame, hours: int = 24):
    """Calculate volume profile and identify 70% liquidity zone"""
    # Group by price levels
    price_bins = pd.cut(data['price'], bins=50)
    volume_by_price = data.groupby(price_bins)['size'].sum()
    
    # Find 70% volume level
    cumsum = volume_by_price.cumsum()
    total_volume = volume_by_price.sum()
    seventy_pct_level = cumsum[cumsum >= total_volume * 0.7].index[0]
    
    return seventy_pct_level
```

### Order Flow Analysis
```python
def analyze_order_flow(ticks: List[LiveTick], window_minutes: int = 5):
    """Analyze order flow for large orders and buy/sell ratio"""
    buy_volume = sum(t.size for t in ticks if t.side == 'buy')
    sell_volume = sum(t.size for t in ticks if t.side == 'sell')
    
    ratio = buy_volume / sell_volume if sell_volume > 0 else float('inf')
    large_orders = [t for t in ticks if t.size >= 50]
    
    return {
        'buy_sell_ratio': ratio,
        'large_orders': large_orders,
        'total_buy_volume': buy_volume,
        'total_sell_volume': sell_volume
    }
```

## Benefits of This Design

1. **Modular Gate System**: Easy to add, remove, or modify gates
2. **Precise Signal Tracking**: Exact timestamps and reasons for each gate status
3. **Visual Clarity**: UI shows exactly WHERE and WHY signals trigger
4. **Backtesting Capability**: Test strategies on historical data
5. **Real-time Monitoring**: Live gate status updates
6. **Performance Analysis**: Detailed metrics for strategy evaluation

## Integration with Existing System

The design leverages the excellent existing infrastructure:
- Uses `LiveDataBuffer` for real-time tick data
- Integrates with `TradingSystem` for orchestration
- Utilizes cached historical data for backtesting
- Extends existing monitoring and alerting capabilities

## Next Steps

1. Begin with Phase 1 implementation
2. Test each gate independently
3. Build simple console output before web UI
4. Iterate based on backtesting results
5. Deploy to production with careful monitoring