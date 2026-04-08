# CLAUDE.md — 네이버 부동산 매물 모니터링 봇

## 프로젝트 개요

네이버 부동산에서 사전 등록한 아파트/오피스텔의 새 매물을 주기적으로 감지하고, 새 매물 발견 시 알림(Telegram/Slack/Desktop)을 보내는 CLI 프로그램.

## 기술 스택

- **언어**: Python 3.11+
- **HTTP**: `httpx` (async) — 네이버 부동산 API 호출
- **스케줄링**: `APScheduler` (cron 기반 주기 실행)
- **알림**: `python-telegram-bot` (Telegram), `slack-sdk` (Slack), `plyer` (Desktop)
- **데이터 저장**: SQLite (`aiosqlite`) — 매물 이력 및 중복 감지
- **설정 관리**: YAML (`PyYAML`) — 모니터링 대상 및 필터 조건
- **로깅**: `loguru`

## 디렉토리 구조

```
naver-real-estate-monitor/
├── config.yaml              # 모니터링 대상 및 알림 설정
├── main.py                  # 엔트리포인트
├── monitor/
│   ├── __init__.py
│   ├── naver_api.py         # 네이버 부동산 API 클라이언트
│   ├── parser.py            # API 응답 파싱 및 매물 데이터 정규화
│   ├── detector.py          # 신규 매물 감지 (DB 비교)
│   ├── scheduler.py         # 주기 실행 스케줄러
│   └── filters.py           # 가격/층/면적 등 필터링
├── notifier/
│   ├── __init__.py
│   ├── base.py              # Notifier 추상 클래스
│   ├── telegram.py          # Telegram 알림
│   ├── slack.py             # Slack 알림
│   └── desktop.py           # Desktop 알림
├── db/
│   ├── __init__.py
│   └── store.py             # SQLite CRUD (매물 이력)
├── tests/
│   ├── test_parser.py
│   ├── test_detector.py
│   └── test_filters.py
├── requirements.txt
└── README.md
```

## 핵심 설계 원칙

### 1. 네이버 부동산 API

- 네이버 부동산 모바일/웹 내부 API 사용 (공식 API 없음)
- 핵심 엔드포인트: `https://new.land.naver.com/api/articles/complex/{complex_id}?tradeType=...&page=...`
- 요청 시 반드시 아래 헤더 포함:
  
  ```
  User-Agent: Mozilla/5.0 ...
  Referer: https://new.land.naver.com/
  Accept: application/json
  ```
- Rate limit 준수: 요청 간 최소 2초 간격, 분당 20회 이하
- complex_id는 네이버 부동산 URL에서 추출 (예: `/complexes/12345` → `12345`)

### 2. 매물 감지 로직

- 각 매물은 `article_id`로 고유 식별
- DB에 없는 `article_id` = 새 매물
- 가격 변동 감지: 기존 매물의 가격이 변경된 경우도 알림
- 매물 삭제(거래완료) 감지도 선택적으로 지원

### 3. 필터링

- `config.yaml`에 정의된 조건으로 필터링:
  - 거래유형: 매매/전세/월세
  - 가격 범위 (min/max)
  - 면적 범위 (전용면적 기준, ㎡)
  - 층수 범위
  - 방향 (남향 등)

### 4. 알림 메시지 포맷

```
🏠 새 매물 발견!
━━━━━━━━━━━━━━
📍 [단지명] [동/호]
💰 전세 4억 5,000만원
📐 전용 84㎡ / 공급 112㎡
🏢 12층 / 남향
📝 "깨끗하게 사용한 집입니다"
🔗 https://new.land.naver.com/...
━━━━━━━━━━━━━━
```

### 5. config.yaml 스키마

```yaml
targets:
  - name: "래미안 원베일리"
    complex_id: "12345"
    trade_type: "전세"          # 매매 | 전세 | 월세
    filters:
      price_min: 40000          # 만원 단위
      price_max: 80000
      area_min: 80              # ㎡
      area_max: 120
      floor_min: 5
      direction: "남"

schedule:
  interval_minutes: 10          # 모니터링 주기

notification:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
  slack:
    enabled: false
    webhook_url: "${SLACK_WEBHOOK_URL}"
  desktop:
    enabled: true
```

### 6. 에러 처리

- API 응답 에러 시 exponential backoff (최대 3회 재시도)
- 네트워크 에러 시 다음 스케줄까지 skip (크래시 방지)
- 모든 에러는 loguru로 파일 + 콘솔 로깅

### 7. DB 스키마

```sql
CREATE TABLE articles (
    article_id TEXT PRIMARY KEY,
    complex_id TEXT NOT NULL,
    trade_type TEXT,
    price TEXT,
    area_exclusive REAL,
    floor INTEGER,
    direction TEXT,
    description TEXT,
    first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    price_history TEXT,         -- JSON array of {price, date}
    is_active INTEGER DEFAULT 1
);
```

## 코딩 규칙

- 모든 I/O는 async/await 사용
- Type hints 필수
- 환경변수는 `.env` 파일 + `python-dotenv`로 관리
- 테스트는 pytest + pytest-asyncio
- 네이버 API 응답은 `tests/fixtures/`에 JSON 샘플 저장하여 모킹

## 실행 방법

```bash
# 설치
pip install -r requirements.txt

# 설정
cp config.yaml.example config.yaml
# config.yaml 편집 후

# 실행
python main.py

# 1회성 체크 (스케줄러 없이)
python main.py --once
```
