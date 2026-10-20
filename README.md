# 틈새여행

조건에 맞는 왕복 항공권을 비교하는 개인용 반응형 웹앱. Python 3.12 이상, 외부 Python 패키지 불필요.

## 실행

```sh
python air_ticket/main.py
```

기본 포트는 8000이며 로컬 접속만 허용합니다. 샘플 검색은 별도 설정 없이 작동합니다. 기본 조건은 2주 후부터 1주일 사이, 3~4박, 인천–나리타입니다.

```sh
python -m unittest discover -s tests -v
```

## 실제 항공권 연결

Amadeus Self-Service의 Flight Offers Search를 사용합니다. 공식 안내: https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search

서버 실행 환경 또는 배포 서비스의 비밀 변수 설정에 아래 값을 등록하세요. `.env` 파일은 자동으로 읽지 않습니다. 키를 코드에 넣거나 브라우저에 전달하지 마세요.

- `AMADEUS_CLIENT_ID`: Amadeus API key
- `AMADEUS_CLIENT_SECRET`: Amadeus API secret
- `AMADEUS_ENV`: 기본 `test`. 실제 운임 조회는 프로덕션 권한과 키를 발급받은 후 `production` 설정

두 키가 있으면 검색 데이터 선택 메뉴에서 API 검색을 이용할 수 있습니다. 테스트 환경은 실제 최저가 검증용이 아닙니다. 서버가 OAuth 토큰을 발급받아 날짜 조합별 왕복 항공권을 조회합니다. API 한도·과금은 공급자 계약에 따릅니다. 일부 항공사와 저비용 항공사가 포함되지 않을 수 있으며 전체 시장 최저가를 보장하지 않습니다. 예약/결제와 예약 링크는 아직 제공하지 않습니다.

검색 범위는 최대 90일, 숙박은 1~30박, 성인은 1~9명입니다. 조합이 20개를 넘으면 일부만 검색하지 않고 범위를 줄이도록 안내합니다. 조합당 최대 50개 운임을 조회합니다. 중간 API 요청에 실패하면 부분 결과를 최저가로 표시하지 않습니다. 가격은 공급자의 세금 포함 grandTotal(KRW)을 사용하며 추가 수하물 등은 별도일 수 있습니다. 예산은 1인 왕복, 결과 총액은 전체 성인 기준입니다.

숙박 수는 출발 공항 기준 출발일과 귀국편 출발일의 날짜 차이입니다. 실제 호텔 숙박 수를 뜻하지 않습니다. 주말은 이 두 날짜를 포함한 기간 중 토·일 유무로 계산하며, 귀국 도착이 다음 날이면 그 날짜는 주말 필터에 포함하지 않습니다. 일정 일수는 출발일과 귀국 도착일의 현지 날짜 차이로 표시합니다.

## 배포

### Render에서 개인용으로 배포하기

저장소의 `render.yaml`은 무료 플랜의 Docker 웹 서비스와 로그인 비밀번호 자동 생성을 설정합니다. 무료 플랜 제공 여부와 제한은 Render 배포 화면에서 확인하세요.

1. https://dashboard.render.com/ 에 로그인하고 GitHub 계정을 연결합니다.
2. **New → Blueprint**에서 `jaewook718/-air-ticket` 저장소의 `main`을 선택합니다.
3. 요금제가 **Free**인지 확인한 뒤 배포합니다. 유료 플랜으로 변경하지 않아도 샘플 모드를 이용할 수 있습니다.
4. 배포가 완료되면 Render가 표시하는 HTTPS 서비스 주소로 접속합니다.
5. 로그인 이름은 `admin`입니다. 비밀번호는 Render 서비스의 **Environment → APP_PASSWORD**에서 확인하거나 원하는 값으로 변경합니다. 이 값은 채팅이나 저장소에 공유하지 마세요.

초기 배포는 샘플 검색 모드입니다. 실제 검색은 Render 서비스의 **Environment**에 `AMADEUS_CLIENT_ID`와 `AMADEUS_CLIENT_SECRET`을 비밀 값으로 추가하고 재배포합니다. 테스트 키로는 테스트 검색만 가능하며, 프로덕션 키를 발급받은 다음 `AMADEUS_ENV=production`으로 변경해야 실제 운임을 조회합니다. Codex 클라우드 변수는 Render로 자동 복사되지 않습니다.

키 발급: https://developers.amadeus.com/ 에서 계정을 만들고 **My Self-Service Workspace**에서 앱을 생성합니다. 프로덕션 전환과 과금 조건은 공급자 계정에서 확인하세요.

`/healthz`만 인증 없이 서비스 상태를 반환합니다. 검색과 화면은 비밀번호 인증으로 보호합니다. 무료 호스팅은 유휴 후 첫 접속에 시간이 걸릴 수 있습니다. 배포 주소는 배포 성공 후 Render가 발급하며, 저장소 업로드만으로 사이트가 공개되지는 않습니다.

### 직접 Docker 실행

Docker 이미지를 빌드해 HTTPS를 지원하는 컨테이너 호스팅 서비스에 배포할 수 있습니다.

```sh
docker build -t air-ticket .
# 호스트 환경에 APP_PASSWORD를 먼저 안전하게 설정한 뒤 실행
# 로그인 사용자명: admin
docker run --rm -p 8000:8000 -e APP_PASSWORD air-ticket
```

`HOST=0.0.0.0` 등 외부 바인딩 시 `APP_PASSWORD`가 필수입니다. 배포 서비스에 이를 비밀 변수로 등록하세요. HTTP Basic 인증이므로 외부 배포는 반드시 HTTPS 프록시 뒤에서 운영하세요. `PORT`로 포트를 변경할 수 있습니다. 개인용 MVP의 Python 표준 서버이며 공개 다중 사용자 서비스용 계정 관리, 분산 요청 제한, 운영 서버 구성은 별도 작업입니다.

실제 API를 배포할 때는 위 Amadeus 변수도 전달하세요. 이 저장소에는 실제 키가 포함되지 않습니다. 로컬 Docker 빌드와 컨테이너 내 인증·샘플 검색은 검증했으며 실시간 운임과 외부 호스팅 배포는 해당 환경에서 추가 검증이 필요합니다.
