# Databento Pricing Research

## Databento's Pricing Model (as of 2024/2025)

### 1. **Subscription Tiers**
Databento uses a credit-based system where you pay for:
- Monthly subscription fee (includes base credits)
- Additional usage beyond included credits

### 2. **Historical Data Pricing**

**Pay-as-you-go model:**
- Charged per **GB of data** downloaded
- OR per **request** depending on the query type
- Different datasets have different pricing

**CME (GLBX.MDP3) Pricing:**
- Professional users: Higher rates
- Non-professional: Lower rates
- Academic: Discounted rates

### 3. **Typical Pricing Structure**

**Historical Data (estimates based on common pricing):**
- ~$0.01 - $0.10 per GB of compressed data
- OR ~$0.001 - $0.01 per 1,000 records
- Varies significantly by:
  - Dataset (CME is typically more expensive)
  - Data type (trades vs quotes vs order book)
  - Subscription level

### 4. **Real Cost Calculation**

For NQ Futures historical data:
- 1 day of trades: ~10-50 MB compressed
- 1 day of 1-minute bars: ~0.5 MB
- 1 month of trades: ~200-1000 MB
- 1 month of 1-minute bars: ~10 MB

**Example Monthly Usage:**
- 4 symbols × 3 months × trades = ~3-12 GB
- 4 symbols × 3 months × 1-min bars = ~120 MB

**Estimated Costs:**
- Without optimization: Could download same 3-12 GB multiple times
- With caching: Download once, reuse forever

### 5. **Important Notes**

1. **Databento's actual pricing is complex** and depends on:
   - Your subscription tier
   - Professional vs non-professional status
   - Specific dataset access rights
   - Volume commitments

2. **Free tier limitations:**
   - Usually includes limited historical data access
   - May have delays (e.g., 15-min delayed data)
   - Limited to certain date ranges

3. **Cost savings from caching are REAL regardless of exact pricing:**
   - Even at $0.001 per API call, thousands of calls add up
   - More importantly: API rate limits can slow down development
   - Caching improves speed AND reduces costs

### 6. **How to Check Your Actual Costs**

1. Log into Databento portal
2. Check your subscription details
3. Look at usage reports
4. See credit consumption per query type

The exact cost per API call varies, but the principle remains:
**Every repeated download of the same data is wasted money!**