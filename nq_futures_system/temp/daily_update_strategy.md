# Daily Data Update Strategy for Cached System

## The Challenge
- Markets generate new data every trading day
- Need to keep cache current without complexity
- Must be simple and automatic

## Solution: Smart Incremental Updates

### 1. **Simple Daily Update Pattern**

```python
def update_daily_data(self):
    """Run this once per day (e.g., 6 PM after market close)"""
    
    # Get today's date
    today = datetime.now().date()
    
    # Check what's the latest data we have cached
    latest_cached_date = self.get_latest_cached_date()
    
    # If we're missing today's data, fetch it
    if latest_cached_date < today:
        print(f"📅 Fetching new data for {today}")
        
        # Only fetch the NEW data (1 day)
        new_data = self.get_historical_data(
            symbols=["NQZ5"],
            start=today,
            end=today,
            schema="trades"
        )
        # This automatically caches it
        
        print(f"✅ Daily update complete. Cache is current.")
    else:
        print(f"✅ Cache already up to date")
```

### 2. **Automatic Gap Filling**

```python
def get_historical_data_smart(self, symbols, start, end, schema):
    """Automatically fills any gaps in cached data"""
    
    # Check what we have cached
    cached_ranges = self.get_cached_date_ranges(symbols, schema)
    
    # Find gaps
    missing_ranges = self.find_missing_dates(start, end, cached_ranges)
    
    if not missing_ranges:
        # Everything is cached!
        return self.load_from_cache(symbols, start, end, schema)
    
    # Fetch only the missing pieces
    all_data = []
    for gap_start, gap_end in missing_ranges:
        print(f"📡 Fetching missing data: {gap_start} to {gap_end}")
        new_data = super().get_historical_data(symbols, gap_start, gap_end, schema)
        all_data.append(new_data)
    
    # Combine with cached data
    cached_data = self.load_partial_cache(symbols, start, end, schema)
    all_data.append(cached_data)
    
    # Merge and return
    return pd.concat(all_data).sort_index()
```

## Real-World Usage Examples

### Example 1: Daily Trading System
```python
# Run this each trading day at 6 PM
client = CachedDatabentoClient()

# Fetch today's data (only if not cached)
today_data = client.get_historical_data(
    ["NQZ5"], 
    datetime.now().date(),
    datetime.now().date(),
    "trades"
)
# First time: API call (costs ~$0.20)
# Rest of day: Cache hit (free)
```

### Example 2: Rolling Window Analysis
```python
# Get last 30 days (smart caching)
end = datetime.now()
start = end - timedelta(days=30)

data = client.get_historical_data(["NQZ5"], start, end, "ohlcv-1m")
# Day 1: Fetches all 30 days
# Day 2: Only fetches 1 new day
# Day 3: Only fetches 1 new day
# etc...
```

### Example 3: Weekend/Holiday Handling
```python
def smart_daily_update(self):
    """Handles weekends and holidays intelligently"""
    
    last_cached = self.get_latest_cached_date()
    today = datetime.now().date()
    
    # Find all missing trading days
    missing_days = []
    current = last_cached + timedelta(days=1)
    
    while current <= today:
        if is_trading_day(current):  # Skip weekends/holidays
            missing_days.append(current)
        current += timedelta(days=1)
    
    # Batch fetch all missing days at once
    if missing_days:
        print(f"📥 Updating {len(missing_days)} missing days")
        self.get_historical_data(
            ["NQZ5"],
            missing_days[0],
            missing_days[-1],
            "trades"
        )
```

## Automation Options

### Option 1: Manual Daily Update (Simplest)
```bash
# Add to your daily routine
python update_market_data.py
```

### Option 2: Cron Job (Automatic)
```bash
# Run every weekday at 6 PM
0 18 * * 1-5 python /path/to/update_market_data.py
```

### Option 3: Smart Update on First Use
```python
class AutoUpdatingClient(CachedDatabentoClient):
    def get_historical_data(self, symbols, start, end, schema):
        # Auto-update if requesting recent data
        if end.date() == datetime.now().date():
            self.ensure_data_current()
        
        return super().get_historical_data(symbols, start, end, schema)
```

## Cost Analysis for Daily Updates

### Without Smart Caching:
- Backtest requests 30 days: $5
- Run backtest 10 times/day: $50/day ❌

### With Smart Caching:
- Initial 30 days: $5 (one time)
- Daily update: $0.20
- Run backtest 100 times: $0
- **Total daily cost: $0.20** ✅

### Monthly Costs:
- Initial cache build: ~$20 (one time)
- Daily updates: $0.20 × 20 days = $4/month
- Unlimited backtests: $0
- **Total: $4/month** (vs $1000+/month without caching)

## Simple Implementation

```python
# Your daily workflow becomes:
client = CachedDatabentoClient()

# 1. Update today's data (automatic)
client.update_daily_data()  # Only fetches if needed

# 2. Run your analysis (uses cache)
data = client.get_historical_data(
    ["NQZ5"], 
    datetime.now() - timedelta(days=30),
    datetime.now(),
    "trades"
)

# 3. Cache handles everything!
```

## Bottom Line

Adding new daily data is **EASY**:
1. Fetch only the new day's data (small, fast, cheap)
2. Cache handles merging with historical data
3. Total overhead: ~30 seconds and $0.20/day
4. Everything else uses the cache

The beauty is that you're only paying for each day's data ONCE, no matter how many times you use it!