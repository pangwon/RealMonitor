# CLAUDE.md — 코레일 KTX 티켓 예매 매크로

## 프로젝트 개요

코레일(Korail) 웹사이트(`https://www.letskorail.com`)에서 사용자가 입력한 조건(날짜, 시간대, 출발지, 목적지)에 맞는 KTX 좌석을 자동으로 검색하고, 잔여 좌석이 있을 경우 즉시 예매(좌석 점유)까지 수행하는 CLI 매크로 프로그램.

좌석이 없으면 일정 간격으로 polling하면서 좌석이 나올 때까지 검색을 반복한다.

## 기술 스택

- **언어**: Python 3.11+
- **HTTP**: `httpx` (async) — 코레일 내부 API 호출
- **HTML 파싱**: `beautifulsoup4`, `lxml` — 응답이 HTML인 경우
- **브라우저 자동화 (옵션)**: `playwright` — 캡차/동적 페이지 우회 필요 시
- **세션/쿠키**: `httpx.AsyncClient` 의 cookie jar
- **알림**: `python-telegram-bot` (예매 성공/실패), `plyer` (Desktop)
- **CLI**: `typer` — 인자 파싱
- **설정 관리**: YAML (`PyYAML`) + `python-dotenv` (계정 정보)
- **로깅**: `loguru`
- **테스트**: `pytest`, `pytest-asyncio`, `respx` (httpx 모킹)

## 디렉토리 구조

```
korail-monitor/
├── config.yaml              # 검색/예매 조건, 알림 설정
├── .env                     # KORAIL_ID, KORAIL_PW, TELEGRAM_BOT_TOKEN 등
├── main.py                  # CLI 엔트리포인트 (typer)
├── korail/
│   ├── __init__.py
│   ├── client.py            # 코레일 API 클라이언트 (로그인/검색/예매)
│   ├── auth.py              # 로그인 및 세션 관리
│   ├── search.py            # 열차 조회
│   ├── reserve.py           # 좌석 점유/예약
│   ├── stations.py          # 역명 ↔ 역코드 매핑
│   ├── models.py            # Train, Seat, Reservation 등 dataclass
│   └── exceptions.py        # KorailError, NoSeatAvailable, LoginFailed 등
├── monitor/
│   ├── __init__.py
│   ├── poller.py            # 조건에 맞는 좌석을 polling
│   └── filters.py           # 시간대/열차종류/좌석등급 필터
├── notifier/
│   ├── __init__.py
│   ├── base.py              # Notifier 추상 클래스
│   ├── telegram.py
│   └── desktop.py
├── tests/
│   ├── fixtures/            # 코레일 API 응답 샘플 JSON/HTML
│   ├── test_client.py
│   ├── test_search.py
│   ├── test_filters.py
│   └── test_poller.py
├── requirements.txt
└── README.md
```

## 핵심 설계 원칙

### 1. 코레일 API

- 코레일은 공식 API가 없으며, 웹/모바일 내부 엔드포인트를 사용해야 한다.
- 참고할 비공식 라이브러리: `korail2` (Python), `SRTpy` 등 (구조 참고용; 그대로 사용하지 말 것 — deprecated 가능)
- 주요 엔드포인트(예시 — 실제는 코드 작성 시 검증 필요):
  - 로그인: `https://smart.letskorail.com/classes/com.korail.mobile.login.Login`
  - 열차 조회: `https://smart.letskorail.com/classes/com.korail.mobile.seatMovie.ScheduleView`
  - 좌석 선점: `https://smart.letskorail.com/classes/com.korail.mobile.certification.TicketReservation`
- 모든 요청에 모바일 앱 User-Agent 사용:
  ```
  User-Agent: Dalvik/2.1.0 (Linux; U; Android 11; SM-G991N Build/RP1A.200720.012)
  ```
- 응답 포맷은 JSON 또는 폼 인코딩된 텍스트 — `client.py`에서 통일된 dict 로 정규화한다.

### 2. 인증 및 세션

- `.env` 의 `KORAIL_ID` (회원번호 또는 이메일), `KORAIL_PW` 로 로그인
- 로그인 응답의 세션 키(`KR_JSESSIONID`, `_TK_NM` 등)를 보관 후 모든 요청에 첨부
- 세션 만료 감지 시 자동 재로그인 (1회 한정 재시도)

### 3. 검색 → 예매 플로우

1. CLI 또는 config 에서 검색 조건을 받는다:
   - 날짜 (`YYYY-MM-DD`)
   - 시간대 (`HH:MM` ~ `HH:MM`, 출발 시각 기준)
   - 출발역, 도착역
   - 열차 종류 (KTX, KTX-산천, ITX 등 — 기본 KTX)
   - 좌석 등급 (특실/일반실/입석 허용 여부)
   - 인원 (어른/어린이/경로)
2. 코레일 API 로 해당 날짜의 열차 목록을 조회
3. 시간대/좌석 등급 필터링
4. 잔여 좌석이 있는 첫 번째 열차에 대해 좌석 선점 API 호출
5. 선점 성공 시 알림 전송 후 종료 (결제는 사용자가 코레일 앱/웹에서 직접 진행 — **자동 결제 금지**)
6. 잔여 좌석이 없으면 polling 루프로 진입

### 4. Polling 정책

- 기본 polling 간격: **30초** (config 로 조정 가능, 최소 10초)
- Jitter 추가 (±5초) — 서버 패턴 감지 회피 및 부하 분산
- **Rate limit 엄수**: 분당 6회 이하, 동일 IP 에서 동시 다중 요청 금지
- 특정 시간(예: 명절 예매 오픈 09:00) 까지 sleep 후 시작하는 모드 지원
- 최대 polling 시간 / 최대 시도 횟수 옵션 (기본: 무제한, Ctrl+C 종료)

### 5. 좌석 선점의 의미와 윤리적 제약

- "예매" = 좌석을 10분간 점유 (코레일 정책상 결제 전 임시 점유 시간이 존재)
- 본 매크로는 **좌석 점유까지만** 수행하고 결제는 사용자가 직접 한다.
- **금지 사항**:
  - 동일 계정으로 동시에 다수의 좌석을 점유 (코레일 약관 위반)
  - 결제 자동화 (이용약관 위반 가능성 + 결제 정보 보관 위험)
  - 헤더/IP 위조를 통한 차단 우회
- 상업적 재판매 목적 사용 금지 (README 에 고지)

### 6. 알림 메시지 포맷

```
🚄 KTX 좌석 예매 성공!
━━━━━━━━━━━━━━
🗓 2026-05-15 (금)
🚉 서울 → 부산
🕐 KTX 045 | 09:00 → 11:38
💺 일반실 3호차 7A
👤 어른 1명
⏰ 결제 마감: 2026-05-07 14:32 (10분 후)
🔗 코레일 앱/웹에서 결제하세요
━━━━━━━━━━━━━━
```

### 7. config.yaml 스키마

```yaml
search:
  date: "2026-05-15"
  departure: "서울"            # 역명 (한글)
  arrival: "부산"
  time_from: "08:00"           # 출발 시각 범위 시작
  time_to: "12:00"             # 출발 시각 범위 끝
  train_types:                 # 허용 열차 종류
    - "KTX"
    - "KTX-산천"
  seat_class: "일반실"          # 일반실 | 특실
  allow_standing: false        # 입석 허용 여부
  passengers:
    adult: 1
    child: 0
    senior: 0

polling:
  interval_seconds: 30
  jitter_seconds: 5
  max_attempts: 0              # 0 = 무제한
  start_at: null               # "2026-05-07 09:00:00" 형식, null 이면 즉시
  stop_at: null                # 종료 시각 (예매 마감)

reservation:
  auto_reserve: true           # false 면 알림만 보내고 점유 안함
  max_seats_per_attempt: 1

notification:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
  desktop:
    enabled: true
```

### 8. 에러 처리

- 모든 코레일 응답 코드를 `exceptions.py` 의 예외로 매핑
  - 로그인 실패 → `LoginFailed`
  - 좌석 없음 → `NoSeatAvailable` (polling 계속)
  - 세션 만료 → `SessionExpired` (재로그인 후 재시도)
  - Rate limit / 차단 → `RateLimited` (지수 백오프 후 재시도, 최대 3회)
  - 네트워크 에러 → 다음 polling 까지 skip
- 예외는 모두 loguru 로 파일 + 콘솔 로깅
- Polling 중 치명적 에러 발생 시 텔레그램으로 즉시 통보

### 9. CLI 사용법 (typer)

```bash
# 설정 파일 기반 실행
python main.py run --config config.yaml

# CLI 인자만으로 실행
python main.py run \
  --date 2026-05-15 \
  --from 서울 --to 부산 \
  --time-from 08:00 --time-to 12:00 \
  --adult 1

# 1회만 검색 (polling 안함)
python main.py search --date 2026-05-15 --from 서울 --to 부산

# 역 코드 조회
python main.py stations --search 서울

# 로그인 테스트
python main.py login-test
```

## 코딩 규칙

- 모든 I/O 는 async/await
- Type hints 필수 (`from __future__ import annotations`)
- 비밀 정보(`KORAIL_ID/PW`)는 절대 코드/로그에 출력 금지 (loguru 필터로 마스킹)
- 코레일 API 응답은 `tests/fixtures/` 에 익명화된 샘플 저장 후 `respx` 로 모킹
- 모든 외부 호출은 timeout 설정 (기본 10초)
- `client.py` 는 코레일 endpoint 변경에 대비해 URL/필드명을 모듈 상수로 분리

## 보안 / 운영 메모

- `.env` 는 `.gitignore` 필수
- 같은 계정으로 다중 인스턴스 실행 금지 (lock 파일로 방지)
- 운영 중 `KR_JSESSIONID` 같은 토큰을 stdout 에 절대 출력하지 않음
- 본 도구는 개인 사용 목적이며, 매크로 사용에 따른 약관 위반 책임은 사용자에게 있음을 README 에 명시
