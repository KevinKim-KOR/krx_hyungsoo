# -*- coding: utf-8 -*-
"""
extensions/backtest/validation.py
백테스트 검증 프레임워크
"""
from typing import Tuple, Optional
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

def simple_train_test_split(
    start_date: date,
    end_date: date,
    train_ratio: float = 0.7
) -> Tuple[Tuple[date, date], Tuple[date, date]]:
    """
    기간을 Train(학습)과 Test(검증)로 단순 분할
    
    Args:
        start_date: 전체 시작일
        end_date: 전체 종료일
        train_ratio: 학습 데이터 비율 (0.0 ~ 1.0)
        
    Returns:
        ((train_start, train_end), (test_start, test_end))
    """
    if not (0 < train_ratio < 1):
        raise ValueError(f"train_ratio는 0과 1 사이여야 합니다: {train_ratio}")
        
    total_days = (end_date - start_date).days
    if total_days < 10:
        raise ValueError(f"기간이 너무 짧습니다: {total_days}일")
        
    train_days = int(total_days * train_ratio)
    
    train_start = start_date
    train_end = start_date + timedelta(days=train_days)
    
    test_start = train_end + timedelta(days=1)
    test_end = end_date
    
    logger.info(f"데이터 분할 (Ratio: {train_ratio:.2f})")
    logger.info(f"Train: {train_start} ~ {train_end} ({train_days}일)")
    logger.info(f"Test : {test_start} ~ {test_end} ({(test_end - test_start).days}일)")
    
    return (train_start, train_end), (test_start, test_end)
