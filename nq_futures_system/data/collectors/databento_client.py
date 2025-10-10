"""
Databento integration for NQ futures - both live and historical data.
Provides a unified interface for accessing market data.
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Callable
import pandas as pd
import databento as db
from dotenv import load_dotenv
import logging

# Import typed exceptions
from nq_futures_system.utils.validators import ConfigurationError, APIValidationError

# Helper function for UTC now that works in all Python versions
def utc_now():
    """Get current UTC time in a way that works for all Python versions."""
    try:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    except AttributeError:
        return datetime.utcnow()

logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../config/.env')
load_dotenv(env_path, override=True)  # Override existing env vars
logger.info(f"Loading .env from: {env_path}")


class DatabentoClient:
    """Unified client for both live and historical Databento data."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Databento client.
        
        Args:
            api_key: Optional API key. If not provided, uses environment variable.
        """
        self.api_key = api_key or os.getenv('DATABENTO_API_KEY')
        if not self.api_key:
            raise ConfigurationError("No Databento API key found. Set DATABENTO_API_KEY environment variable.")
        logger.info(f"Using API key: {self.api_key[:10]}... (total length: {len(self.api_key)})")
        
        self._live_client = None
        self._hist_client = None
        self._subscribers = {}
        
    @property
    def live(self):
        """Lazy-load live client."""
        if self._live_client is None:
            self._live_client = db.Live(key=self.api_key)
        return self._live_client
    
    @property
    def historical(self):
        """Lazy-load historical client."""
        if self._hist_client is None:
            self._hist_client = db.Historical(self.api_key)
        return self._hist_client
    
    # Live Data Methods
    async def subscribe_live(self, 
                           symbols: List[str],
                           schema: str = "trades",
                           callback: Optional[Callable] = None,
                           dataset: str = "GLBX.MDP3") -> str:
        """
        Subscribe to live data feed.
        
        Args:
            symbols: List of symbols to subscribe to (e.g., ['NQZ24', 'NQH25'])
            schema: Data schema (trades, bbo, mbp-1, etc.)
            callback: Function to call with each data update
            dataset: Databento dataset (default: GLBX.MDP3 for CME)
            
        Returns:
            subscription_id: ID for managing this subscription
        """
        try:
            # Map schema names to Databento schema objects
            schema_map = {
                "trades": db.Schema.TRADES,
                "bbo": db.Schema.BBO_1M,
                "mbp-1": db.Schema.MBP_1,
                "ohlcv-1m": db.Schema.OHLCV_1M,
                "ohlcv-1h": db.Schema.OHLCV_1H,
            }
            
            db_schema = schema_map.get(schema, db.Schema.TRADES)
            
            # Subscribe to live data
            self.live.subscribe(
                dataset=dataset,
                schema=db_schema,
                symbols=symbols,
                stype_in=db.SType.RAW_SYMBOL,
                start=utc_now(),
            )
            
            # Store subscription info
            sub_id = f"{dataset}_{schema}_{'_'.join(symbols)}"
            self._subscribers[sub_id] = {
                'symbols': symbols,
                'schema': schema,
                'callback': callback,
                'dataset': dataset
            }
            
            logger.info(f"Subscribed to live data: {symbols} with schema {schema}")
            return sub_id
            
        except Exception as e:
            logger.error(f"Failed to subscribe to live data: {e}")
            raise
    
    async def start_live_feed(self):
        """Start processing live data feed."""
        try:
            async for record in self.live:
                # Route to appropriate callbacks
                for sub_id, sub_info in self._subscribers.items():
                    if sub_info['callback']:
                        await sub_info['callback'](record)
                        
        except Exception as e:
            logger.error(f"Error in live feed: {e}")
            raise
    
    def stop_live_feed(self):
        """Stop all live data subscriptions."""
        if self._live_client:
            self._live_client.stop()
            logger.info("Stopped live data feed")
    
    # Historical Data Methods
    def get_historical_data(self,
                          symbols: List[str],
                          start: datetime,
                          end: datetime,
                          schema: str = "trades",
                          dataset: str = "GLBX.MDP3") -> pd.DataFrame:
        """
        Fetch historical data for given symbols and time range.
        
        Args:
            symbols: List of symbols (e.g., ['NQZ24', 'NQH25'])
            start: Start datetime
            end: End datetime
            schema: Data schema (trades, ohlcv-1m, etc.)
            dataset: Databento dataset
            
        Returns:
            DataFrame with historical data
        """
        try:
            data = self.historical.timeseries.get_range(
                dataset=dataset,
                symbols=symbols,
                schema=schema,
                start=start,
                end=end,
                stype_in="raw_symbol"
            )
            
            df = data.to_df()
            logger.info(f"Retrieved {len(df)} historical records for {symbols}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get historical data: {e}")
            raise
    
    def get_available_symbols(self, 
                            pattern: str = "NQ",
                            date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get available symbols matching pattern.
        
        Args:
            pattern: Symbol pattern to match (e.g., "NQ" for all NQ futures)
            date: Date to check availability (default: today)
            
        Returns:
            List of symbol information dictionaries
        """
        try:
            if date is None:
                # Use yesterday to ensure data is available
                date = utc_now() - timedelta(days=1)
            
            # Ensure we're not requesting future data
            end_date = min(date + timedelta(days=1), utc_now() - timedelta(hours=1))
            
            # Get symbol definitions
            data = self.historical.timeseries.get_range(
                dataset="GLBX.MDP3",
                symbols=pattern,
                schema="definition",
                start=date,
                end=end_date,
                stype_in="raw_symbol"
            )
            
            df = data.to_df()
            symbols = []
            
            for _, row in df.iterrows():
                symbol_info = {
                    'symbol': row.get('symbol', row.get('raw_symbol', '')),
                    'exchange': row.get('exchange', ''),
                    'instrument_class': row.get('instrument_class', ''),
                    'expiration': row.get('expiration', ''),
                    'strike': row.get('strike_price', None),
                    'option_type': row.get('option_type', None)
                }
                symbols.append(symbol_info)
            
            logger.info(f"Found {len(symbols)} symbols matching pattern '{pattern}'")
            return symbols
            
        except Exception as e:
            logger.error(f"Failed to get available symbols: {e}")
            raise
    
    # Utility Methods
    def get_continuous_contract(self, 
                              base_symbol: str = "NQ",
                              dataset: str = "GLBX.MDP3") -> str:
        """
        Get the front-month continuous contract symbol.
        
        Args:
            base_symbol: Base symbol (e.g., "NQ")
            dataset: Databento dataset
            
        Returns:
            Current front-month symbol (e.g., "NQZ24")
        """
        try:
            # Get all available NQ futures
            symbols = self.get_available_symbols(pattern=base_symbol)
            
            # Filter for futures only (not options)
            futures = [s for s in symbols if s['instrument_class'] == 'FUTURE']
            
            # Sort by expiration and get the front month
            futures.sort(key=lambda x: x['expiration'])
            
            if futures:
                return futures[0]['symbol']
            else:
                raise APIValidationError(f"No futures contracts found for {base_symbol}")
                
        except Exception as e:
            logger.error(f"Failed to get continuous contract: {e}")
            raise
    
    def close(self):
        """Clean up client connections."""
        self.stop_live_feed()
        logger.info("Databento client closed")


# Example callback function for live data
async def print_trade(record):
    """Example callback to print trade data."""
    if hasattr(record, 'price') and hasattr(record, 'size'):
        print(f"Trade: {record.symbol} @ {record.price/1e9:.2f} x {record.size}")


if __name__ == "__main__":
    # Example usage
    client = DatabentoClient()
    
    # Get current front-month contract
    try:
        front_month = client.get_continuous_contract("NQ")
        print(f"Current front-month NQ contract: {front_month}")
        
        # Get some historical data
        end = datetime.now()
        start = end - timedelta(days=1)
        
        df = client.get_historical_data(
            symbols=[front_month],
            start=start,
            end=end,
            schema="ohlcv-1m"
        )
        
        print(f"\nHistorical data sample:")
        print(df.head())
        
    except Exception as e:
        print(f"Error: {e}")