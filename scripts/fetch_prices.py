"""GitHub Actions에서 실행: data/asset.json의 티커 시세 + USD/KRW 환율을 받아 data/prices.json 생성."""
import json, time, urllib.request, datetime

def quote(sym):
    for attempt in range(4):
        host = 'query1' if attempt % 2 == 0 else 'query2'
        url = f'https://{host}.finance.yahoo.com/v8/finance/chart/{sym}?range=1d&interval=1d'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                m = json.load(r)['chart']['result'][0]['meta']
            return {'price': m['regularMarketPrice'],
                    'prevClose': m.get('previousClose') or m.get('chartPreviousClose'),
                    'currency': m.get('currency'),
                    'marketTime': m.get('regularMarketTime')}
        except Exception as e:
            print(f'{sym} 실패({attempt + 1}): {e}'); time.sleep(2)
    return None

asset = json.load(open('data/asset.json', encoding='utf8'))
tickers = sorted({h['ticker'] for h in asset['holdings'] if h.get('ticker')})
quotes = {t: q for t in tickers if (q := quote(t))}
fx = quote('KRW=X')
out = {'updatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
       'fx': {'USDKRW': fx} if fx else {}, 'quotes': quotes}
json.dump(out, open('data/prices.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(f'{len(quotes)}/{len(tickers)} 종목, 환율 {fx and fx["price"]}')
