"""GitHub Actions에서 실행: 보유 종목 + USD/KRW 의 최근 1년 일별 종가 → data/history.json
+ S&P500 비교용 SPY·USD/KRW 월말 가격(10년, 배당 반영) → bench
하루에 한 번만 새로 받는다(이미 오늘 받은 파일이 있고 종목이 같으면 건너뜀)."""
import json, os, time, datetime, urllib.request

KST = datetime.timezone(datetime.timedelta(hours=9))
today = datetime.datetime.now(KST).strftime('%Y-%m-%d')
asset = json.load(open('data/asset.json', encoding='utf8'))
tickers = sorted({h['ticker'] for h in asset['holdings'] if h.get('ticker')}) + ['KRW=X']

old = {}
if os.path.exists('data/history.json'):
    try:
        old = json.load(open('data/history.json', encoding='utf8'))
    except Exception:
        old = {}
if old.get('date') == today and all(t in old.get('series', {}) for t in tickers) and old.get('bench', {}).get('spy'):
    print('오늘 받은 일별 시세가 있어 건너뜁니다.'); raise SystemExit(0)

def history(sym, rng='1y', itv='1d'):
    for attempt in range(4):
        host = 'query1' if attempt % 2 == 0 else 'query2'
        url = f'https://{host}.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={itv}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.load(r)['chart']['result'][0]
            ts = res.get('timestamp') or []
            close = res['indicators']['quote'][0].get('close') or []
            adj = (res['indicators'].get('adjclose') or [{}])[0].get('adjclose') or close
            off = res.get('meta', {}).get('gmtoffset', 0)
            d, c, a = [], [], []
            for t, cv, av in zip(ts, close, adj):
                if cv is None:
                    continue
                d.append(datetime.datetime.fromtimestamp(t + off, datetime.timezone.utc).strftime('%Y-%m-%d'))
                c.append(round(cv, 4)); a.append(round(av if av is not None else cv, 4))
            return {'d': d, 'c': c, 'a': a}
        except Exception as e:
            print(f'{sym} 실패({attempt + 1}): {e}'); time.sleep(2)
    return None

series = {}
for t in tickers:
    h = history(t)
    if h and len(h['d']) > 20:
        series[t] = h
    elif t in old.get('series', {}):
        series[t] = old['series'][t]          # 실패 시 이전 데이터 유지
    time.sleep(0.3)

bench = {}
for key, sym in (('spy', 'SPY'), ('fx', 'KRW=X')):
    h = history(sym, '10y', '1mo')
    if h and len(h['d']) > 24:
        bench[key] = h
    elif old.get('bench', {}).get(key):
        bench[key] = old['bench'][key]
    time.sleep(0.3)

os.makedirs('data', exist_ok=True)
json.dump({'date': today, 'series': series, 'bench': bench}, open('data/history.json', 'w', encoding='utf8'), separators=(',', ':'))
print(f'일별 시세 {len(series)}/{len(tickers)}개, S&P500 비교 데이터 {"OK" if bench.get("spy") and bench.get("fx") else "없음"} 저장')
