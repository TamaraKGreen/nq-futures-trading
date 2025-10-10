# Databento API Cost Optimization Analysis

## 1. CODEBASE SCAN - Current API Usage

### Existing Components:
- **databento_client.py**: Main interface for API calls
  - `get_historical_data()`: Fetches historical data (MAIN COST DRIVER)
  - `subscribe_live()`: Live data subscription
  - `get_available_symbols()`: Symbol lookup
  - `get_continuous_contract()`: Contract resolution

### Current API Call Patterns:
1. **Every historical data request creates a new API call**
2. **No caching mechanism** - same data can be requested multiple times
3. **No local storage** - data is lost after script execution
4. **No batch optimization** - requests are made individually

## 2. COST IMPACT ANALYSIS

### What Affects Costs:
- **Number of API calls** (primary cost factor)
- **Amount of data per call** (secondary factor)
- **Frequency of redundant requests** (waste factor)

### Dependencies That Will Change:
- Data collection modules will need caching layer
- Strategy backtesting will need local data access
- Real-time systems will need efficient data management

### Side Effects:
- Storage requirements will increase
- Initial setup time will be longer
- System complexity will slightly increase

## ✅ VERIFICATION CHECKPOINT 1:
- **Deep enough?** Yes - identified all API touchpoints
- **Assumptions tested?** Need to verify Databento pricing model
- **Simplest approach?** Could be simpler - let's focus on key wins
- **Revise?** Yes - prioritize biggest cost savers

## 3. OPTIMIZED PROJECT STRUCTURE

```
nq_futures_system/
├── data/
│   ├── cache/                    # NEW: Local cache system
│   │   ├── cache_manager.py     # Manages cached data
│   │   ├── metadata.json        # Cache inventory
│   │   └── data/                # Parquet files by date/symbol
│   │       ├── NQZ5/
│   │       │   ├── 2025-10-09_trades.parquet
│   │       │   └── 2025-10-09_ohlcv-1m.parquet
│   │       └── index.json       # Quick lookup index
│   │
│   ├── collectors/
│   │   ├── databento_client.py  # MODIFIED: Add cache awareness
│   │   └── smart_collector.py   # NEW: Intelligent data fetcher
│   │
│   └── storage/
│       └── timeseries_db.py     # Local database option
```

## 4. SIMPLE OPTIMIZATION PLAN

### Priority 1: Cache Historical Data (80% cost reduction)
```python
# Before: Every backtest downloads same data
df = client.get_historical_data(symbols, start, end)  # API CALL

# After: Check cache first
df = cache.get_or_fetch(symbols, start, end)  # API CALL ONLY IF NEEDED
```

### Priority 2: Batch Requests (30% cost reduction)
```python
# Before: Multiple individual requests
for date in date_range:
    data = get_data(symbol, date)  # 30 API CALLS

# After: Single batched request  
data = get_data(symbol, start_date, end_date)  # 1 API CALL
```

### Priority 3: Smart Date Ranges (20% cost reduction)
```python
# Before: Overlapping requests
monday_data = get_data("NQ", "2025-10-07", "2025-10-07")
week_data = get_data("NQ", "2025-10-07", "2025-10-11")  # Redundant!

# After: Deduplicate and merge
week_data = get_cached_or_fetch("NQ", "2025-10-07", "2025-10-11")
monday_data = week_data[week_data.date == "2025-10-07"]  # No API call
```

## ✅ VERIFICATION CHECKPOINT 2:
- **Deep enough?** Yes - covered main optimization strategies
- **Assumptions tested?** Yes - based on typical usage patterns
- **Simplest approach?** Yes - caching is the biggest win
- **Revise?** No - plan is solid and practical

## 5. KEEPING IT SIMPLE

### Chosen Approach:
1. **Local file cache using Parquet** (efficient, fast, simple)
2. **Memory cache for session** (avoid file I/O for repeat requests)
3. **Smart request logic** (check what we have before fetching)

### Avoiding Complexity:
- ❌ NOT building complex database system
- ❌ NOT implementing distributed caching
- ❌ NOT over-engineering the solution
- ✅ Simple file-based cache with smart logic

## 6. IMPLEMENTATION STEPS

### Step 1: Create Cache Manager (2 hours)
```
- Build cache directory structure
- Implement save/load for Parquet files
- Create metadata tracking
```

### Step 2: Modify Databento Client (1 hour)
```
- Add cache checking before API calls
- Implement cache writing after API calls
- Maintain backward compatibility
```

### Step 3: Create Smart Collector (2 hours)
```
- Date range deduplication
- Batch request optimization
- Partial data merging
```

### Step 4: Test & Validate (1 hour)
```
- Verify cache hits/misses
- Measure API call reduction
- Confirm data integrity
```

## COST SAVINGS ESTIMATE

### Current Usage (Example):
- Daily backtest: 250 trading days × 4 symbols = 1,000 API calls
- Strategy development: 20 iterations = 20,000 API calls/month
- Cost: ~$200-500/month (depending on plan)

### With Optimization:
- First run: 1,000 API calls (data cached)
- Subsequent runs: ~50 API calls (only new data)
- Monthly: ~1,200 API calls (95% reduction)
- Cost: ~$10-25/month

## IMMEDIATE ACTIONS

1. **Build the cache manager first** (biggest impact)
2. **Test with your common date ranges**
3. **Monitor API usage reduction**
4. **Expand as needed**