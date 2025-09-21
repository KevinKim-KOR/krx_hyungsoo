import pandas as pd

start = "20000101"
end = "20230512"

dt_s = pd.to_datetime(start)
dt_e = pd.to_datetime(end)
delta = pd.to_timedelta('730 days')
elapsed = dt_e - dt_s

while dt_s + delta < dt_e:
    print(dt_s, dt_s + delta)
    dt_s += delta + pd.to_timedelta('1 days')

if dt_s != dt_e:
    print(dt_s, dt_e)
    print("---")


