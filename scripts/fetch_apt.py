"""GitHub Actions에서 하루 1회 실행: 국토교통부 아파트 매매 실거래가 → data/apt.json

필요한 GitHub Secrets (공개 로그에 단지 정보가 찍히지 않도록 이름/지역은 출력하지 않음)
  APT_API_KEY  공공데이터포털 인증키 (Encoding/Decoding 어느 쪽이든 가능)
  APT_LAWD_CD  시군구 코드 5자리 (예: 11680)
  APT_NAME     단지명 (실거래 자료에 표기된 이름의 일부만 써도 됨)
  APT_AREA     전용면적 m² (예: 84.97)
  APT_DONG     (선택) 법정동 이름 - 같은 이름의 단지가 여럿일 때
"""
import os, sys, json, time, statistics, datetime, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

KEY = os.environ.get('APT_API_KEY', '').strip()
LAWD = os.environ.get('APT_LAWD_CD', '').strip()
NAME = os.environ.get('APT_NAME', '').replace(' ', '')
DONG = os.environ.get('APT_DONG', '').replace(' ', '')
try:
    AREA = float(os.environ.get('APT_AREA', '0'))
except ValueError:
    AREA = 0.0
MONTHS = 6          # 최근 몇 개월 거래를 볼지
RECENT_N = 3        # 최근 몇 건의 중앙값을 추정가로 쓸지
URL = 'https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade'

if not (KEY and LAWD and NAME and AREA):
    print('아파트 설정(Secrets)이 없어 건너뜁니다.'); sys.exit(0)

key_q = KEY if '%' in KEY else urllib.parse.quote(KEY, safe='')

def months_back(n):
    d = datetime.date.today().replace(day=1)
    out = []
    for _ in range(n):
        out.append(d.strftime('%Y%m'))
        d = (d - datetime.timedelta(days=1)).replace(day=1)
    return out

def txt(item, *tags):
    for t in tags:
        el = item.find(t)
        if el is not None and el.text and el.text.strip():
            return el.text.strip()
    return ''

deals, errors = [], 0
for ym in months_back(MONTHS):
    page = 1
    while True:
        url = f'{URL}?serviceKey={key_q}&LAWD_CD={LAWD}&DEAL_YMD={ym}&numOfRows=1000&pageNo={page}'
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print(f'{ym} 요청 실패: {type(e).__name__}'); errors += 1; break
        code = (root.findtext('.//resultCode') or '').strip()
        if code not in ('', '00', '000'):
            print(f'{ym} API 오류 코드 {code}: {(root.findtext(".//resultMsg") or "").strip()}'); errors += 1; break
        items = root.findall('.//item')
        for it in items:
            if NAME not in txt(it, 'aptNm', '아파트').replace(' ', ''):
                continue
            if DONG and DONG not in txt(it, 'umdNm', '법정동').replace(' ', ''):
                continue
            try:
                area = float(txt(it, 'excluUseAr', '전용면적'))
            except ValueError:
                continue
            if abs(area - AREA) > 1.0:
                continue
            if txt(it, 'cdealType', '해제여부').upper() == 'O':   # 해제된 거래 제외
                continue
            try:
                amount = int(txt(it, 'dealAmount', '거래금액').replace(',', '')) * 10000
                y, m, d = int(txt(it, 'dealYear', '년')), int(txt(it, 'dealMonth', '월')), int(txt(it, 'dealDay', '일'))
            except ValueError:
                continue
            deals.append({'date': f'{y:04d}.{m:02d}.{d:02d}', 'price': amount})
        total = int(root.findtext('.//totalCount') or 0)
        if page * 1000 >= total:
            break
        page += 1
        time.sleep(0.3)

print(f'조건에 맞는 거래 {len(deals)}건 (요청 오류 {errors}회)')
if not deals:
    print('거래가 없어 기존 값을 유지합니다.'); sys.exit(0)

deals.sort(key=lambda x: x['date'], reverse=True)
recent = deals[:RECENT_N]
out = {
    'updatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
    'estimate': int(statistics.median(d['price'] for d in recent)),
    'latest': deals[0],
    'count': len(deals),
    'window': f'최근 {MONTHS}개월',
    'basis': f'최근 {len(recent)}건 중앙값',
}
os.makedirs('data', exist_ok=True)
json.dump(out, open('data/apt.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print('data/apt.json 저장 완료')
