# zcountry

국가별 거래일 캘린더 파일을 저장하는 폴더입니다.

현재 런타임에서는 `pandas_market_calendars`를 직접 사용하지 않고, 아래 파일만 읽습니다.

- `zcountry/kor/market_calendars.json`
- `zcountry/au/market_calendars.json`
- `zcountry/us/market_calendars.json`

## 현재 범위

- 시작일: `CACHE_START_DATE`
- 종료일: `2026-12-31`

## 2027년 이후 갱신 방법

2027년이 되면 `market_calendars.json` 파일을 다시 생성해서 범위를 늘려야 합니다.

권장 절차:

1. 임시로 `pandas_market_calendars`를 설치합니다.
2. 한국(`XKRX`), 호주(`XASX`) 거래일을 새 종료일까지 계산합니다.
3. 기존 파일을 덮어써서 `start_date`, `end_date`, `updated_at`, `trading_days`를 함께 갱신합니다.

## 파일 형식

```json
{
  "country_code": "kor",
  "source": "pandas_market_calendars",
  "start_date": "2020-01-01",
  "end_date": "2026-12-31",
  "updated_at": "2026-04-08T22:39:30",
  "trading_days": ["2020-01-02", "2020-01-03"]
}
```

## 주의

- 파일이 없으면 `get_trading_days()`는 즉시 에러를 발생시킵니다.
- 요청 구간이 파일의 `start_date ~ end_date` 범위를 벗어나도 즉시 에러를 발생시킵니다.
