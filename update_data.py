#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""데이터 업데이트 스크립트"""
from extensions.realtime import RealtimeDataCollector
from datetime import date, timedelta

collector = RealtimeDataCollector()
test_date = date.today() - timedelta(days=1)

print(f"데이터 수집 시작: {test_date}")
result = collector.update_latest(test_date)
print(f"결과: {'성공' if result else '실패'}")
