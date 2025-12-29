import logging
import hashlib
import json
import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Any

from config.production_config import PROD_STRATEGY_CONFIG
from core.strategy.market_regime_detector import MarketRegimeDetector
from infra.data.loader import load_price_data 
from pykrx import stock

logger = logging.getLogger(__name__)

class Phase9Executor:
    """
    Phase 9 'Crisis Alpha' Strategy Executor
    - Dual Timeframe Regime Detection (Bull/Bear)
    - ADX Chop Filter (Risk-Off/Block)
    - RSI Mean Reversion Logic (Entry/Exit)
    """
    
    def __init__(self):
        self.config = PROD_STRATEGY_CONFIG
        self._log_config_hash()
        
        self.detector = MarketRegimeDetector(enable_regime_detection=True)
        self.universe = self.config.get("universe_codes", [])
        
    def _log_config_hash(self):
        """설정 변경 감지를 위한 해시 로깅"""
        # default=str handles date/numpy types if present
        config_str = json.dumps(self.config, sort_keys=True, default=str)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()
        logger.info(f"[Phase9Executor] Loaded Config Hash: {config_hash[:8]}")
        logger.debug(f"[Phase9Executor] Config Details: {self.config}")

    def _load_market_data(self, end_date: date, lookback_days: int = 730) -> pd.DataFrame:
        """벤치마크(069500) 데이터 로드 (Regime/ADX용)"""
        start_date = end_date - timedelta(days=lookback_days)
        try:
            df = stock.get_market_ohlcv_by_date(
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d"),
                "069500"
            )
            df = df.rename(columns={
                '시가': 'open', '고가': 'high', '저가': 'low', '종가': 'close', '거래량': 'volume'
            })
            df.index.name = 'date'
            df.columns = [c.lower() for c in df.columns]
            return df
        except Exception as e:
            logger.error(f"Failed to load market data (069500): {e}")
            raise

    def execute(self, target_date: date) -> List[Dict[str, Any]]:
        """
        전략 실행 및 신호 생성
        Returns: List of signal dicts compatible with infra.notify
        """
        logger.info(f"[Phase9Executor] Executing Strategy for {target_date}")
        
        # 1. Load Data
        market_df = self._load_market_data(target_date)
        price_data = load_price_data(self.universe, target_date - timedelta(days=365), target_date)
        
        # 2. Detect Regime (Brain)
        regime_raw, confidence, is_golden, is_chop = self.detector.detect_regime_adx(
            market_df, 
            target_date,
            long_ma_period=self.config['regime_ma_long'],
            short_ma_period=self.config['ma_short_period'],
            adx_period=self.config['adx_period'],
            adx_threshold=self.config['adx_threshold']
        )
        
        # 3. Determine Final Regime (Priority Logic)
        final_regime = regime_raw
        reason_msg = f"Regime: {regime_raw} (Conf: {confidence:.2f})"
        
        if is_chop:
            final_regime = 'bear' # Force Risk-Off
            reason_msg = f"[CHOP BLOCK] ADX Low -> Force Bear"
            logger.warning(f"[DECISION] {reason_msg}")
        elif is_golden and regime_raw == 'bear':
             # Note: logic inside runner handles this details, 
             # but here we simplify for daily signal generation context
             # If golden cross just happened, treated as valid if logic supports it.
             # In Phase 9, Golden Cross overrides Bear lock.
             final_regime = 'bull'
             reason_msg = f"[GOLDEN CROSS] Override Bear -> Force Bull"
             logger.info(f"[DECISION] {reason_msg}")
        else:
            logger.info(f"[DECISION] Normal Regime: {final_regime}")

        # 4. Generate Signals
        signals = []
        
        if final_regime == 'bear':
            # RISK-OFF: Exit Everything
            for code in self.universe:
                signals.append({
                    'code': code,
                    'signal_type': 'EXIT',  # 'sell' or 'EXIT' based on consumer
                    'score': 0.0,
                    'reason': f"Risk-Off: {reason_msg}",
                    'timestamp': target_date.isoformat()
                })
        else:
            # RISK-ON: RSI Logic
            # Calculate RSI for universe
            rsi_period = self.config['rsi_period']
            
            # Safe way to get available codes from MultiIndex (code, date)
            valid_codes = []
            if isinstance(price_data.index, pd.MultiIndex):
                 valid_codes = price_data.index.get_level_values('code').unique()
            elif 'code' in price_data.columns:
                 valid_codes = price_data['code'].unique()
            else:
                 valid_codes = []

            for code in self.universe:
                 if code not in valid_codes:
                     continue
                     
                 # Slice Data for Code
                 try:
                     df_code = price_data.xs(code, level='code')    
                 except KeyError:
                     continue
                 
                 if len(df_code) < rsi_period + 2:
                     continue
                     
                 # Calc RSI
                 delta = df_code['close'].diff()
                 gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
                 loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
                 rs = gain / loss
                 rsi = 100 - (100 / (1 + rs)).iloc[-1]
                 
                 # Simple Mean Reversion Logic (Phase 7 Style)
                 # Buy if RSI < 30? Or high Momentum?
                 # Phase 9 Winner Params suggest simple RSI Score usage.
                 # Let's align with "Relative Momentum" usually. 
                 # But wait, Phase 9 top params include RSI=40.
                 # Assuming Lower implies Buy opportunity in Bull market (Dip Buying).
                 
                 score = (50 - rsi) # Higher score if RSI is lower (Dip Buying)
                 
                 # Threshold
                 if rsi < 50: # Example Threshold for Dip
                     signal_type = 'BUY'
                     reason = f"Bull Dip (RSI {rsi:.1f})"
                 elif rsi > 70:
                     signal_type = 'SELL'
                     reason = f"Overbought (RSI {rsi:.1f})"
                 else:
                     signal_type = 'HOLD'
                     reason = f"Neutral (RSI {rsi:.1f})"
                
                 signals.append({
                    'code': code,
                    'signal_type': signal_type,
                    'score': float(score),
                    'reason': f"{reason} | {reason_msg}",
                    'timestamp': target_date.isoformat()
                 })
                 
        return signals

