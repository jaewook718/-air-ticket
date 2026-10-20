"""Personal airfare finder. Python 3.12+, no third-party dependencies."""
import base64
import hashlib
import hmac
import json
import os
import re
import threading
from datetime import date, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

STATIC = Path(__file__).parent / 'static'
SEARCH_LOCK = threading.BoundedSemaphore(2)
MAX_PAIRS = 20


def search_dates(data):
    try:
        origin, destination = str(data['origin']).upper(), str(data['destination']).upper()
        start, end = date.fromisoformat(data['start']), date.fromisoformat(data['end'])
        low, high = int(data['min_nights']), int(data['max_nights'])
        adults, budget = int(data['adults']), int(data['budget'])
        weekend = data.get('weekend', 'any')
    except (KeyError, TypeError, ValueError):
        raise ValueError('날짜, 숙박 일수, 인원과 예산을 확인해 주세요.') from None
    if not re.fullmatch('[A-Z]{3}', origin) or not re.fullmatch('[A-Z]{3}', destination) or origin == destination:
        raise ValueError('서로 다른 출발·도착 공항 코드(영문 3자)를 입력해 주세요.')
    if start < date.today() or end < start or (end - start).days > 90:
        raise ValueError('오늘 이후 최대 90일 범위로 여행 가능 기간을 지정해 주세요.')
    if not 1 <= low <= high <= 30 or not 1 <= adults <= 9 or not 1 <= budget <= 100_000_000:
        raise ValueError('숙박은 1~30박, 성인은 1~9명, 예산은 1~1억 원으로 입력해 주세요.')
    if weekend not in ('any', 'include', 'exclude') or not isinstance(data.get('direct', False), bool):
        raise ValueError('주말 또는 직항 조건이 올바르지 않습니다.')
    pairs = []
    for offset in range((end - start).days + 1):
        depart = start + timedelta(days=offset)
        for nights in range(low, high + 1):
            back = depart + timedelta(days=nights)
            if back > end:
                continue
            has_weekend = any((depart + timedelta(days=i)).weekday() >= 5 for i in range(nights + 1))
            if weekend == 'include' and not has_weekend or weekend == 'exclude' and has_weekend:
                continue
            pairs.append((depart.isoformat(), back.isoformat(), nights, has_weekend))
    if len(pairs) > MAX_PAIRS:
        raise ValueError(f'날짜 조합이 {len(pairs)}개입니다. 전체 조합을 비교할 수 있도록 기간이나 숙박 범위를 좁혀 {MAX_PAIRS}개 이하로 설정해 주세요.')
    return origin, destination, adults, budget, pairs


def sample_offers(origin, destination, adults, pair):
    depart, back, nights, weekend = pair
    seed = int(hashlib.sha256(f'{origin}{destination}{depart}{back}'.encode()).hexdigest()[:8], 16)
    return [dict(id=f'{depart}-{back}-{i}', departure=depart, return_date=back, nights=nights,
                 weekend=weekend, price=(110000 + seed % 290000 + i * 37000) * adults,
                 carrier=f'샘플 항공사 {i + 1}', stops=i % 2, duration='샘플',
                 arrival=depart, trip_days=nights + 1) for i in range(3)]


def api_json(url, data=None, token=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
            return json.load(response)
    except HTTPError as exc:
        messages = {401: '항공권 API 인증에 실패했습니다. 서버의 키를 확인해 주세요.',
                    429: '항공권 API 요청 한도에 도달했습니다. 잠시 후 다시 시도해 주세요.'}
        raise RuntimeError(messages.get(exc.code, f'항공권 제공 서비스 오류({exc.code})입니다. 조건 또는 API 설정을 확인해 주세요.')) from None
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise RuntimeError('항공권 제공 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.') from None


def live_offers(origin, destination, adults, pairs, direct):
    key, secret = os.getenv('AMADEUS_CLIENT_ID'), os.getenv('AMADEUS_CLIENT_SECRET')
    if not key or not secret:
        raise ValueError('실시간 검색에는 서버의 AMADEUS_CLIENT_ID와 AMADEUS_CLIENT_SECRET 설정이 필요합니다. 지금은 샘플 검색을 이용할 수 있습니다.')
    production = os.getenv('AMADEUS_ENV') == 'production'
    base = 'https://api.amadeus.com' if production else 'https://test.api.amadeus.com'
    auth = api_json(base + '/v1/security/oauth2/token', urlencode(dict(grant_type='client_credentials', client_id=key, client_secret=secret)).encode())
    results = []
    for depart, back, nights, weekend in pairs:
        query = urlencode(dict(originLocationCode=origin, destinationLocationCode=destination,
                               departureDate=depart, returnDate=back, adults=adults,
                               currencyCode='KRW', nonStop=str(direct).lower(), max=50))
        payload = api_json(base + '/v2/shopping/flight-offers?' + query, token=auth['access_token'])
        carriers = payload.get('dictionaries', {}).get('carriers', {})
        for offer in payload.get('data', []):
            legs = offer['itineraries']
            first, last = legs[0]['segments'][0], legs[-1]['segments'][-1]
            airline = first['carrierCode']
            results.append(dict(id=f'{depart}-{back}-{offer["id"]}', departure=first['departure']['at'],
                                return_date=legs[-1]['segments'][0]['departure']['at'],
                                arrival=last['arrival']['at'], nights=nights, weekend=weekend,
                                trip_days=(date.fromisoformat(last['arrival']['at'][:10]) - date.fromisoformat(depart)).days + 1,
                                price=int(Decimal(offer['price']['grandTotal']).to_integral_value(rounding='ROUND_CEILING')),
                                carrier=carriers.get(airline, airline), stops=max(len(leg['segments']) - 1 for leg in legs),
                                duration=' / '.join(leg['duration'].removeprefix('PT').lower() for leg in legs)))
    return results


def search(data):
    origin, destination, adults, budget, pairs = search_dates(data)
    mode = data.get('mode', 'sample')
    if mode not in ('sample', 'live'):
        raise ValueError('지원하지 않는 검색 모드입니다.')
    if mode == 'sample':
        offers = [offer for pair in pairs for offer in sample_offers(origin, destination, adults, pair)]
        source = 'sample'
    else:
        offers = live_offers(origin, destination, adults, pairs, data.get('direct', False)) if pairs else []
        source = 'production' if os.getenv('AMADEUS_ENV') == 'production' else 'test'
    offers = sorted((o for o in offers if o['price'] <= budget * adults and (not data.get('direct') or o['stops'] == 0)), key=lambda o: o['price'])
    return dict(offers=offers, source=source, searched_dates=len(pairs), adults=adults, origin=origin, destination=destination)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        password = os.getenv('APP_PASSWORD')
        if not password:
            return True
        expected = 'Basic ' + base64.b64encode(('admin:' + password).encode()).decode()
        if hmac.compare_digest(self.headers.get('Authorization', '').encode(), expected.encode()):
            return True
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="Air Ticket", charset="UTF-8"')
        self.end_headers()
        return False

    def do_GET(self):
        if self.path == '/healthz':
            return self.respond(200, {'status': 'ok'})
        if not self.authorized():
            return
        route = self.path.split('?')[0]
        if route == '/api/status':
            return self.respond(200, dict(live_available=bool(os.getenv('AMADEUS_CLIENT_ID') and os.getenv('AMADEUS_CLIENT_SECRET')), production=os.getenv('AMADEUS_ENV') == 'production'))
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if route not in files:
            return self.respond(404, {'error': '페이지를 찾을 수 없습니다.'})
        name, mime = files[route]
        self.respond(200, (STATIC / name).read_bytes(), mime)

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != '/api/search':
            return self.respond(404, {'error': '페이지를 찾을 수 없습니다.'})
        if not SEARCH_LOCK.acquire(blocking=False):
            return self.respond(429, {'error': '검색이 진행 중입니다. 잠시 후 다시 시도해 주세요.'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                raise ValueError('요청 크기가 올바르지 않습니다.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('검색 조건을 확인해 주세요.')
            self.respond(200, search(data))
        except (ValueError, TypeError):
            # Only explicit validation errors are exposed, never provider payloads or credentials.
            import sys
            error = sys.exception()
            message = str(error) if type(error) is ValueError else '검색 조건 형식이 올바르지 않습니다.'
            self.respond(400, {'error': message})
        except RuntimeError as error:
            self.respond(502, {'error': str(error)})
        except Exception:
            self.respond(502, {'error': '응답을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.'})
        finally:
            SEARCH_LOCK.release()


def main():
    host, port = os.getenv('HOST', '127.0.0.1'), int(os.getenv('PORT', '8000'))
    if host not in ('127.0.0.1', 'localhost', '::1') and not os.getenv('APP_PASSWORD'):
        raise SystemExit('외부 접속을 허용하려면 APP_PASSWORD를 설정하세요. 로그인 이름은 admin입니다.')
    server = ThreadingHTTPServer((host, port), Handler)
    print(f'Air Ticket listening on port {port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    main()
