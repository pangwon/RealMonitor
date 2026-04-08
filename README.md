# 네이버 부동산 매물 모니터링 봇

네이버 부동산에서 관심 아파트/오피스텔의 새 매물을 주기적으로 감지하고, Telegram/Slack/Desktop 알림을 보내는 CLI 프로그램입니다.

## 주요 기능

- 네이버 부동산 매물 자동 모니터링 (설정 가능한 주기)
- 신규 매물 감지
- 가격 변동 감지 (기존 매물의 가격 변경 추적)
- 거래 완료/삭제 감지
- 조건 필터링 (가격, 면적, 층수, 방향)
- 다중 알림 채널 (Telegram, Slack, Desktop)

## 설치

```bash
# 저장소 클론
git clone https://github.com/pangwon/RealMonitor.git
cd RealMonitor

# 의존성 설치
pip install -r requirements.txt

# 설정 파일 생성
cp config.yaml.example config.yaml
```

## 설정

### config.yaml

```yaml
targets:
  - name: "래미안 원베일리"
    complex_id: "12345"        # 네이버 부동산 단지 ID
    trade_type: "전세"          # 매매 | 전세 | 월세
    filters:
      price_min: 40000          # 만원 단위 (4억)
      price_max: 80000          # 만원 단위 (8억)
      area_min: 80              # 전용면적 ㎡
      area_max: 120
      floor_min: 5
      direction: "남"           # 부분 일치 (남 → 남향, 남서향 모두 포함)

schedule:
  interval_minutes: 10          # 모니터링 주기 (분)

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

### complex_id 찾는 방법

1. [네이버 부동산](https://new.land.naver.com/) 접속
2. 원하는 아파트 단지 검색 후 클릭
3. URL에서 숫자 부분이 `complex_id`

```
https://new.land.naver.com/complexes/12345?tradeType=...
                                    ^^^^^
                                    이 부분이 complex_id
```

### Telegram 봇 설정

1. Telegram에서 [@BotFather](https://t.me/BotFather)에게 `/newbot` 명령
2. 봇 이름과 username 설정 후 **API Token** 수령
3. 봇과 대화를 시작하거나, 봇을 그룹에 초대
4. `chat_id` 확인:
   - 봇에게 아무 메시지 전송
   - `https://api.telegram.org/bot<TOKEN>/getUpdates` 접속
   - 응답에서 `chat.id` 값 확인
5. `.env` 파일 또는 환경변수로 설정:

```bash
# .env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=987654321
```

### 환경 변수

`config.yaml`에서 `${VAR_NAME}` 형식의 값은 환경변수로 대체됩니다.
`.env` 파일을 프로젝트 루트에 생성하여 관리할 수 있습니다.

```bash
# .env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## 실행

```bash
# 스케줄러 모드 (주기적 모니터링)
python main.py

# 1회 체크 후 종료
python main.py --once

# 설정 파일 경로 지정
python main.py --config my_config.yaml
```

## 테스트

```bash
# 전체 테스트 실행
pytest

# 특정 테스트 파일 실행
pytest tests/test_parser.py
pytest tests/test_detector.py
pytest tests/test_filters.py

# 상세 출력
pytest -v
```

## 프로젝트 구조

```
RealMonitor/
├── main.py                  # 엔트리포인트 (CLI)
├── config.yaml              # 모니터링 설정
├── monitor/
│   ├── naver_api.py         # 네이버 부동산 API 클라이언트
│   ├── parser.py            # API 응답 파서
│   ├── detector.py          # 신규/가격변동/삭제 감지
│   ├── scheduler.py         # APScheduler 스케줄러
│   └── filters.py           # 매물 필터링
├── notifier/
│   ├── base.py              # Notifier 추상 클래스
│   ├── telegram.py          # Telegram 알림
│   ├── slack.py             # Slack 알림
│   └── desktop.py           # Desktop 알림
├── db/
│   └── store.py             # SQLite 매물 이력 저장소
└── tests/
    ├── fixtures/             # API 응답 샘플 JSON
    ├── test_parser.py
    ├── test_detector.py
    └── test_filters.py
```

## 주의사항

- **비공식 API**: 네이버 부동산 공식 API가 아닌 내부 웹 API를 사용합니다. API 구조가 예고 없이 변경될 수 있습니다.
- **Rate Limit**: 요청 간 최소 2초 간격, 분당 20회 이하로 제한됩니다. 과도한 요청은 IP 차단을 유발할 수 있습니다.
- **개인 용도**: 이 프로그램은 개인적인 매물 모니터링 용도로만 사용해 주세요.
- **데이터 정확성**: 매물 정보는 네이버 부동산에 등록된 내용을 기반으로 하며, 실제와 다를 수 있습니다.

## 라이선스

MIT
