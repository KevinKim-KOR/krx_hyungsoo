#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
파라미터 Grid Search 최적화
MAPS 임계값, 레짐 MA 기간, 포지션 비율 등을 자동으로 최적화
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import itertools
import json
from datetime import datetime
import logging
import pandas as pd

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """파라미터 최적화"""
    
    def __init__(self, output_dir: str = None):
        """
        Args:
            output_dir: 결과 저장 디렉토리
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "data" / "optimization"
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def define_parameter_grid(self) -> dict:
        """
        파라미터 그리드 정의
        
        Returns:
            파라미터 조합 딕셔너리
        """
        param_grid = {
            # MAPS 임계값
            'maps_threshold': [3.0, 5.0, 7.0, 10.0],
            
            # 레짐 감지 MA 기간
            'regime_ma_short': [20, 50, 100],
            'regime_ma_long': [50, 100, 200, 300],
            
            # 레짐별 포지션 비율
            'position_bull': [100, 110, 120, 130],
            'position_sideways': [60, 70, 80, 90],
            'position_bear': [30, 40, 50, 60],
            
            # 방어 모드 임계값
            'defense_confidence': [80, 85, 90, 95],
        }
        
        return param_grid
    
    def generate_combinations(self, param_grid: dict) -> list:
        """
        파라미터 조합 생성
        
        Args:
            param_grid: 파라미터 그리드
            
        Returns:
            모든 조합 리스트
        """
        # MA 기간 조합 필터링 (short < long)
        ma_combinations = []
        for short in param_grid['regime_ma_short']:
            for long in param_grid['regime_ma_long']:
                if short < long:
                    ma_combinations.append((short, long))
        
        # 나머지 파라미터 조합
        other_params = {
            k: v for k, v in param_grid.items() 
            if k not in ['regime_ma_short', 'regime_ma_long']
        }
        
        combinations = []
        for ma_short, ma_long in ma_combinations:
            for values in itertools.product(*other_params.values()):
                param_dict = dict(zip(other_params.keys(), values))
                param_dict['regime_ma_short'] = ma_short
                param_dict['regime_ma_long'] = ma_long
                combinations.append(param_dict)
        
        logger.info(f"총 {len(combinations)}개 조합 생성")
        return combinations
    
    def run_backtest_with_params(self, params: dict) -> dict:
        """
        특정 파라미터로 백테스트 실행
        
        Args:
            params: 파라미터 딕셔너리
            
        Returns:
            백테스트 결과
        """
        # TODO: 실제 백테스트 엔진 연동
        # 현재는 더미 결과 반환
        
        import random
        result = {
            'params': params,
            'cagr': random.uniform(15, 35),
            'sharpe': random.uniform(1.0, 2.0),
            'mdd': random.uniform(-25, -15),
            'total_return': random.uniform(50, 150),
            'trades': random.randint(800, 1500)
        }
        
        return result
    
    def optimize(self, max_combinations: int = 50) -> pd.DataFrame:
        """
        최적화 실행
        
        Args:
            max_combinations: 최대 테스트 조합 수
            
        Returns:
            결과 DataFrame
        """
        logger.info("=" * 60)
        logger.info("파라미터 최적화 시작")
        logger.info("=" * 60)
        
        # 파라미터 그리드 생성
        param_grid = self.define_parameter_grid()
        combinations = self.generate_combinations(param_grid)
        
        # 조합 수 제한
        if len(combinations) > max_combinations:
            import random
            combinations = random.sample(combinations, max_combinations)
            logger.info(f"조합 수 제한: {max_combinations}개")
        
        # 백테스트 실행
        results = []
        for i, params in enumerate(combinations, 1):
            logger.info(f"[{i}/{len(combinations)}] 테스트 중...")
            result = self.run_backtest_with_params(params)
            results.append(result)
        
        # DataFrame 변환
        df = pd.DataFrame(results)
        
        # 결과 저장
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f"optimization_results_{timestamp}.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        logger.info(f"✅ 결과 저장: {output_file}")
        
        # 최적 파라미터 출력
        best_idx = df['sharpe'].idxmax()
        best_result = df.iloc[best_idx]
        
        logger.info("\n" + "=" * 60)
        logger.info("최적 파라미터")
        logger.info("=" * 60)
        logger.info(f"Sharpe Ratio: {best_result['sharpe']:.2f}")
        logger.info(f"CAGR: {best_result['cagr']:.2f}%")
        logger.info(f"MDD: {best_result['mdd']:.2f}%")
        logger.info(f"\n파라미터:")
        
        params = best_result['params']
        for key, value in params.items():
            logger.info(f"  {key}: {value}")
        
        return df
    
    def save_best_params(self, df: pd.DataFrame):
        """
        최적 파라미터를 설정 파일로 저장
        
        Args:
            df: 최적화 결과 DataFrame
        """
        best_idx = df['sharpe'].idxmax()
        best_params = df.iloc[best_idx]['params']
        
        config_file = self.output_dir / "best_params.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(best_params, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 최적 파라미터 저장: {config_file}")


def main():
    """최적화 실행"""
    optimizer = ParameterOptimizer()
    
    # 최적화 실행 (테스트용 10개 조합)
    results_df = optimizer.optimize(max_combinations=10)
    
    # 최적 파라미터 저장
    optimizer.save_best_params(results_df)
    
    logger.info("✅ 최적화 완료")


if __name__ == "__main__":
    main()
