# Timetable Dashboard

교육기관 시간표를 통합 관리하는 웹 캘린더 대시보드입니다.
Vertex42 엑셀 캘린더 템플릿을 업로드하면 자동으로 수업 일정을 파싱하여 FullCalendar 기반의 월간/주간 캘린더로 시각화합니다.
**직원근무표** 탭에서는 같은 템플릿으로 작성된 `직원근무표.xlsx`를 올려 사무실 근무자·외부 일정·휴가를 구성원과 공유하고 웹에서 직접 수정할 수 있습니다.

## 주요 기능

### 수업시간표 (대시보드)

- **엑셀 시간표 파싱** - Vertex42 캘린더 템플릿 자동 인식, 시트별 선택 업로드
- **복수 과정 관리** - 여러 과정을 색상별로 구분하여 하나의 캘린더에 통합 표시
- **수업 일정 추가** - 캘린더 날짜 클릭 또는 버튼으로 개별 수업 등록, 새 과정 즉시 생성 가능
- **수업 일정 수정** - 이벤트 클릭 후 상세 모달에서 수업명·강사·날짜·시간 등 수정
- **수업 일정 삭제** - 이벤트 클릭 후 상세 모달에서 개별 수업 삭제
- **수업시간 시각화** - 8시간 기준으로 긴 수업(9h, 10h)은 진한 색, 짧은 수업(4h)은 연한 색으로 자동 표시
- **강사 정보 추출** - 복수 강사명 자동 인식 (슬래시/쉼표/공백 구분)
- **공휴일 감지** - 추석, 설날, 성탄절 등 한국 공휴일 자동 인식
- **과정 통계** - 수업 일수, 총 수업시간, 강사별 수업 수, 기간 요약
- **과정 필터** - 과정별 표시/숨김 토글, 전체 해제/선택 버튼, Ctrl+클릭 단독 보기
- **색상 팔레트** - 12색 프리셋 + 커스텀 컬러피커로 자유로운 과정 색상 선택
- **빠른 날짜 선택** - 캘린더 제목 클릭 시 날짜 선택 모달 (연도 → 월 순서로 선택)
- **효율적인 네비게이션** - 기존 화살표 버튼 + 모달에서 연/월 2단계 선택으로 빠른 이동
- **도움말 가이드** - 사용 방법 안내 모달 제공
- **반응형 디자인** - 데스크톱/모바일 대응

### 직원근무표

- **근무표 엑셀 파싱** - 주 블록의 `사무실근무` 행, `노트북방문` 행, 특이사항 행(`과정명-담당자`, `담당자-과정명`, `이름 휴가`)을 자동 분류
- **월 단위 교체 업로드** - 선택한 시트(월)의 기존 항목을 통째로 교체하므로 수정된 엑셀을 다시 올리면 됨
- **월간 달력** - 담당자 1명이면 직원 색, 여러 명/없음이면 구분 색(사무실·일정·휴가·노트북·메모)으로 표시
- **주간 매트릭스** - 행=직원, 열=월~금. 한 일정에 여러 담당자가 있으면 각 행에 모두 표시
- **날짜별 요약** - 날짜 클릭 시 사이드바에 그날의 사무실 근무자 / 휴가자 / 외부 일정 / 노트북 방문 표시
- **직원·구분 필터** - 직원 칩 토글(Ctrl+클릭 단독 보기), 구분별 표시/숨김
- **웹에서 직접 수정** - 항목 추가/수정/삭제, 엑셀 원문(raw_text)과 출처 시트를 상세 모달에서 확인

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Flask 3.0, Python 3.10+ |
| Frontend | FullCalendar v6, Tailwind CSS (CDN) |
| 엑셀 파싱 | openpyxl |
| 저장소 | 로컬 JSON (기본) / Azure Cosmos DB (선택) |
| 프로덕션 서버 | Waitress (로컬) / Gunicorn (Azure) |

## 설치 및 실행

### 1. 저장소 클론

```bash
git clone <repository-url>
cd timetable
```

### 2. 가상환경 생성 및 의존성 설치

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. 환경변수 설정

`.env` 파일을 프로젝트 루트에 생성합니다.

```env
SECRET_KEY=your-secret-key
FLASK_ENV=development
PORT=5000

# Azure Cosmos DB (선택 - 미설정 시 로컬 JSON 사용)
# COSMOS_DB_ENDPOINT=https://your-account.documents.azure.com:443/
# COSMOS_DB_KEY=your-cosmos-db-key
```

### 4. 실행

```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

- **개발 모드** (`FLASK_ENV=development`): Flask 내장 서버 (자동 리로드)
- **프로덕션 모드**: Waitress WSGI 서버

## 프로젝트 구조

```
timetable/
├── app.py                    # Flask 앱 팩토리
├── config.py                 # 설정 (업로드, DB, 색상 등)
├── models.py                 # 데이터 모델 (ClassEntry, Course, RosterEntry)
├── routes.py                 # 시간표 페이지 + API 라우트
├── routes_roster.py          # 직원근무표 페이지 + /api/roster 라우트
├── requirements.txt          # Python 의존성
├── .env                      # 환경변수
│
├── services/
│   ├── excel_parser.py       # Vertex42 수업시간표 파서
│   ├── roster_parser.py      # 직원근무표 파서 (excel_parser의 블록 감지 재사용)
│   ├── cosmos_service.py     # 시간표 저장소 (Cosmos DB / 로컬 JSON)
│   ├── roster_storage.py     # 근무표 저장소 (Cosmos DB / 로컬 JSON)
│   └── calendar_service.py   # FullCalendar 이벤트 포맷 변환 (시간표 + 근무표)
│
├── static/
│   ├── css/style.css         # FullCalendar + 커스텀 스타일 (tt-week-*, tt-roster-*)
│   └── js/
│       ├── dashboard.js      # 시간표 캘린더, 과정 관리, 색상 조정
│       ├── roster.js         # 근무표 캘린더, 주간 매트릭스, 업로드/수정 모달
│       └── upload.js         # 시간표 업로드 워크플로우
│
├── templates/
│   ├── base.html             # 기본 레이아웃 (대시보드 / 직원근무표 / 업로드 탭)
│   ├── dashboard.html        # 대시보드 (캘린더 + 사이드바)
│   ├── roster.html           # 직원근무표 (캘린더 + 날짜 요약 + 모달)
│   └── upload.html           # 업로드 (3단계 위저드)
│
├── tests/
│   └── test_roster_parser.py # 근무표 파서 테스트 (직원근무표.xlsx 필요)
│
└── data/
    ├── courses.json          # 시간표 로컬 저장소 (자동 생성)
    ├── roster.json           # 근무표 로컬 저장소 (자동 생성)
    └── uploads/              # 임시 업로드 파일 (처리 후 삭제)
```

### 테스트

```bash
python -m pytest tests/
```

> 파서 테스트는 프로젝트 루트의 `직원근무표.xlsx`를 픽스처로 사용하며, 파일이 없으면 자동으로 건너뜁니다.

## 사용 방법

### 시간표 업로드

1. 상단 **+ 시간표 업로드** 클릭
2. Vertex42 형식의 엑셀 파일(.xlsx)을 드래그앤드롭 또는 선택
3. 파싱할 시트(월)를 체크박스로 선택
4. 과정명, 색상, 수업 시작시간 설정
5. **가져오기** 클릭

### 수업 일정 직접 추가

1. 캘린더에서 **날짜를 클릭**하거나 상단 **+ 수업 추가** 버튼 클릭
2. 기존 과정을 선택하거나 **+ 새 과정 만들기**로 과정 즉시 생성
3. 수업명, 강사, 수업시간, 시작시각 등 입력
4. **추가** 클릭

### 수업 일정 삭제

1. 캘린더에서 수업 이벤트 클릭
2. 상세 모달 하단의 **수업 삭제** 버튼 클릭
3. 확인 후 삭제

### 캘린더 조회

- **월간/주간 전환** - 우측 상단 버튼 (주간은 과정별 행 × 월~금 열 매트릭스)
- **과정 필터** - 상단 과정 버튼으로 표시/숨김 토글
  - **전체 해제** — 모든 과정을 한 번에 숨김
  - **전체 선택** — 모든 과정을 한 번에 표시
  - **Ctrl+클릭** — 해당 과정만 단독으로 표시 (1클릭 단독 보기)
- **캘린더 네비게이션**
  - **◀ / ▶ 버튼** - 이전/다음 월 이동
  - **제목 클릭 ("2026년 4월")** - 날짜 선택 모달 열기 (연도 → 월 순서)
    - 연도 선택: 12개 연도 중 선택, 화살표로 10년 단위 이동
    - 월 선택: 원하는 월 클릭하면 즉시 이동 (◀ 연도 변경으로 다시 돌아가기 가능)
  - **오늘 버튼** - 현재 날짜로 이동
- **이벤트 클릭** - 수업 상세 정보 모달 (강사, 시간, 과정, 삭제)
- **마우스 호버** - 툴팁에 수업명 + 시간 표시
- **도움말** - 상단 **?** 버튼으로 사용 가이드 확인

### 색상으로 수업시간 구분

이벤트 바의 색상이 수업시간에 따라 자동으로 조정됩니다:

| 수업시간 | 색상 변화 |
|---------|----------|
| 4h | 과정 컬러보다 **연한 색** + 어두운 텍스트 |
| 8h | 과정 컬러 **기본** |
| 9h | 과정 컬러보다 **약간 진한 색** |
| 10h | 과정 컬러보다 **확실히 진한 색** |

### 직원근무표

1. 상단 **직원근무표** 탭 → 우측 **엑셀 업로드**
2. `직원근무표.xlsx`를 끌어다 놓으면 시트별로 **실제 연·월**(A1 셀 기준)이 표시됨 — 시트명(`'3월'`)과 실제 월이 달라도 정확히 매핑
3. 가져올 월 선택 (이번 달 이후가 기본 선택) → **가져오기**. 선택한 월의 기존 항목은 모두 교체됨
4. **월간**: 이벤트 클릭 → 상세(날짜·구분·담당자·메모·엑셀 원문) → 수정/삭제
5. **주간**: 행=직원, 열=요일. 셀 클릭 → 사이드바 날짜 요약, 더블클릭 → 그 직원·날짜로 항목 추가
6. 사이드바 **날짜별 요약**: 사무실 근무자 / 휴가 / 외부 일정 / 노트북 방문. **오늘** 버튼으로 복귀
7. **+ 항목 추가**: 날짜, 구분(사무실근무·일정·휴가·노트북방문·메모), 제목, 담당자(쉼표 구분, 자동완성), 메모

## API

### 과정 관리

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/courses` | 전체 과정 목록 (메타데이터) |
| `POST` | `/api/courses/quick` | 과정 빠른 생성 (이름 + 색상만) |
| `POST` | `/api/upload` | 엑셀 파싱 후 과정 저장 |
| `PUT` | `/api/courses/:id` | 과정 정보 수정 (이름, 색상, 시간) |
| `DELETE` | `/api/courses/:id` | 과정 삭제 |

### 수업 일정 관리

| Method | Endpoint | 설명 |
|--------|----------|------|
| `POST` | `/api/courses/:id/entries` | 개별 수업 일정 추가 |
| `PUT` | `/api/courses/:id/entries/:entryId` | 개별 수업 일정 수정 |
| `DELETE` | `/api/courses/:id/entries/:entryId` | 개별 수업 일정 삭제 |

### 캘린더 데이터

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/events` | FullCalendar 이벤트 JSON |
| `GET` | `/api/stats` | 과정별 통계 |
| `POST` | `/api/sheets` | 엑셀 파일 업로드 후 시트 목록 반환 |

### 직원근무표

| Method | Endpoint | 설명 |
|--------|----------|------|
| `GET` | `/api/roster/entries?start=&end=` | 기간 내 근무 항목 (FullCalendar 종일 이벤트) |
| `GET` | `/api/roster/employees` | 직원 목록 + 색상, 등록된 월, 구분별 색상 |
| `GET` | `/api/roster/day?date=YYYY-MM-DD` | 해당 날짜 요약 (office / leave / out / events / laptop / memo) |
| `POST` | `/api/roster/sheets` | 엑셀 업로드 → 시트별 `{name, year, month}` |
| `POST` | `/api/roster/upload` | `{filepath, sheets}` 파싱 후 해당 월 교체 저장 |
| `POST` | `/api/roster/entries` | 항목 추가 `{date, category, title, people, note}` |
| `PUT` | `/api/roster/entries/:id` | 항목 수정 (부분 업데이트) |
| `DELETE` | `/api/roster/entries/:id` | 항목 삭제 |

`category`는 `office` · `laptop` · `event` · `leave` · `memo` 중 하나, `people`은 배열 또는 `"김철수, 이영희"` 문자열.

### 응답 예시

**GET /api/events**

```json
[
  {
    "id": "course_20250210_abc12345_2025-12-01",
    "title": "(정종현) 클라우드기반 딥러닝1",
    "start": "2025-12-01T09:00:00",
    "end": "2025-12-01T19:00:00",
    "color": "#4A90D9",
    "textColor": "#ffffff",
    "extendedProps": {
      "course_id": "course_20250210_abc12345",
      "course_name": "AI School 8",
      "entry_id": "entry_20250210_143025_a1b2c3d4",
      "instructor": "정종현",
      "hours": 9,
      "is_holiday": false
    }
  }
]
```

**GET /api/stats**

```json
{
  "success": true,
  "stats": [
    {
      "course_name": "AI School 8",
      "color": "#4A90D9",
      "total_classes": 128,
      "total_holidays": 11,
      "total_hours": 1107,
      "date_range": "2025-09-15 ~ 2026-05-29",
      "instructors": {
        "정종현": 18,
        "인선미": 13,
        "김자영": 11
      }
    }
  ]
}
```

**GET /api/roster/entries**

```json
[
  {
    "id": "roster_20261008_012631_b8fd816f",
    "title": "AI11타운홀2 · 박명균, 황소연",
    "start": "2026-10-07",
    "allDay": true,
    "color": "#F59E0B",
    "extendedProps": {
      "entry_id": "roster_20261008_012631_b8fd816f",
      "category": "event",
      "category_label": "일정",
      "title": "AI11타운홀2",
      "people": ["박명균", "황소연"],
      "note": "",
      "raw_text": "AI11타운홀2_박명균, 황소연",
      "source_sheet": "10"
    }
  }
]
```

## 엑셀 템플릿 형식

### 수업시간표

Vertex42 캘린더 템플릿 기반으로 다음 구조를 인식합니다:

```
열 배치:
  C열=월 날짜, D열=월 수업명
  E열=화 날짜, F열=화 수업명
  G열=수 날짜, H열=수 수업명
  I열=목 날짜, J열=목 수업명
  K열=금 날짜, M열=금 수업명

수업명 아래 행:
  강사명 (한글 2~4자) 또는 수업시간 (숫자 또는 "8h" 형식)
```

### 파서 동작 규칙

- **날짜**: `datetime` 형식, 2020년 이후만 인식
- **수업시간**: 숫자 셀(1~12) 우선 → 텍스트 "Xh" 합산 → 기본 8시간
- **강사명**: 한글 2~4자 이름 자동 추출, `강사` 접미사 제거
- **복수 강사**: 슬래시(`/`), 쉼표(`,`), 별도 행 모두 지원
- **공휴일**: 추석, 설날, 성탄절, 방학 등 키워드 자동 감지
- **점심시간**: 13:00~14:00 자동 포함 (8시간 수업 = 09:00~18:00)

### 직원근무표

같은 Vertex42 월간 템플릿을 사용하며, 요일 열 배치는 수업시간표와 동일합니다. 주 블록(날짜 행 R) 안의 행 의미만 다릅니다:

```
A1 셀        : 해당 월 1일 (datetime) → 시트명 대신 이 값으로 연·월 판별
R   (날짜 행) : B열 '사무실근무' 라벨, 요일별 이름 열 = 당일 사무실 근무자
R+1          : A열 '노트북방문' 라벨, 자유 텍스트 메모
R+2 ~        : 특이사항
               '숙대-최진명'            → 일정(숙대) / 담당자 최진명
               '이대건-마산대'          → 일정(마산대) / 담당자 이대건  (방향 자동 판별)
               'AI11타운홀2_박명균, 황소연' → 일정 / 담당자 2명
               '황소연 휴가', '최진명-휴가' → 휴가
               '김해예정' ↵ '강형주,황소연,최진명' → 이름만 있는 다음 행은 직전 일정의 담당자로 병합
               '최진명(프로젝트안내)'   → 괄호 안은 메모
```

- **직원 명단**: 1차 패스에서 `사무실근무` 행의 단일 이름을 수집하고, `X-Y`처럼 양쪽이 모두 이름 형태일 때 알려진 직원이 있는 쪽을 담당자로 판별
- **노이즈 제거**: `8h` 같은 템플릿 잔재, `메모`, Vertex42 푸터, 해당 월이 아닌 날짜(다음달 첫 주)는 무시
- **이름 오인식 방지**: `벡스코`, `숙대`, `마산대`, `타운홀`, `대체휴일` 등 2~4자 한글이지만 이름이 아닌 단어는 제외 (`services/roster_parser.py`의 `NOT_NAME`)
- 자동 분류가 틀린 항목은 상세 모달의 **원문**을 보고 웹에서 수정할 수 있습니다

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SECRET_KEY` | (랜덤 자동 생성) | Flask 시크릿 키 |
| `FLASK_ENV` | - | `development` 설정 시 디버그 모드 |
| `PORT` | `5000` | 서버 포트 |
| `COSMOS_DB_ENDPOINT` | - | Azure Cosmos DB 엔드포인트 (선택) |
| `COSMOS_DB_KEY` | - | Azure Cosmos DB 키 (선택) |

> Cosmos DB 환경변수가 미설정이면 `data/courses.json`(시간표)과 `data/roster.json`(근무표)에 로컬 저장됩니다.

### Cosmos DB 문서 구조

데이터베이스 `TimetableDashboardDB` / 컨테이너 `ScheduleData` 하나를 공유하며, 파티션 키는 `/type`입니다. 컨테이너는 앱 시작 시 `create_container_if_not_exists`로 자동 생성되므로 별도 스키마 작업이 필요 없습니다.

| `type` | 용도 | 주요 필드 |
|--------|------|-----------|
| `course` | 과정 메타데이터 | `name`, `color`, `default_start_time`, `entry_count` |
| `entry` | 수업 일정 | `course_id`, `date`, `class_name`, `instructor`, `hours` |
| `roster_entry` | 근무표 항목 | `date`, `category`, `title`, `people[]`, `note`, `raw_text`, `source_sheet` |
| `roster_upload` | 근무표 업로드 이력 | `file_name`, `uploaded_at`, `months[]`, `entry_count` |

## 배포

### Azure Web App (GitHub Actions)

아래 단계를 따라 GitHub Actions를 통해 Azure Web App으로 배포합니다.

#### 1단계: Azure Cosmos DB 생성

1. [Azure Portal](https://portal.azure.com) → **Azure Cosmos DB** → **만들기**
2. API: **NoSQL** 선택
3. 용량 모드: **서버리스** (소규모 트래픽에 적합)
4. 리소스 그룹, 계정 이름 설정 후 생성
5. 생성 완료 후 **키** 메뉴에서 **URI**와 **PRIMARY KEY** 복사

#### 2단계: Azure Web App 생성

1. Azure Portal → **App Services** → **만들기**
2. 설정:
   - 런타임 스택: **Python 3.11**
   - OS: **Linux**
   - 요금제: **F1 (무료)** 또는 **B1**
3. **배포** 탭에서 **GitHub Actions** 활성화
   - GitHub 계정 연결
   - 조직 / 리포지토리 / 브랜치 선택
4. **만들기** → 자동으로 `.github/workflows/` 에 워크플로우 파일 생성

#### 3단계: 시작 명령 설정

Azure Portal → Web App → **구성** → **일반 설정** → **시작 명령**:

```
gunicorn --bind=0.0.0.0 --timeout 600 app:app
```

#### 4단계: 환경변수 설정

Azure Portal → Web App → **구성** → **애플리케이션 설정**에서 추가:

| 이름 | 값 |
|------|-----|
| `SECRET_KEY` | 프로덕션용 시크릿 키 (랜덤 문자열) |
| `COSMOS_DB_ENDPOINT` | 1단계에서 복사한 URI |
| `COSMOS_DB_KEY` | 1단계에서 복사한 PRIMARY KEY |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

> `SCM_DO_BUILD_DURING_DEPLOYMENT=true`를 설정해야 Azure가 배포 시 `pip install -r requirements.txt`를 자동 실행합니다.

#### 5단계: 배포

```bash
git add .
git commit -m "Deploy to Azure"
git push origin main
```

GitHub Actions가 자동으로 빌드 및 배포를 실행합니다.
**Actions** 탭에서 배포 진행 상황을 확인할 수 있습니다.

#### 구조 요약

```
GitHub Push → GitHub Actions → Azure Web App (Gunicorn) → Cosmos DB
```

`app.py`의 `app = create_app()` 전역 인스턴스가 Gunicorn과 Azure Web App에 호환됩니다.

## 보안

### 적용된 보안 조치

| 항목 | 설명 |
|------|------|
| **Path Traversal 차단** | 파일 업로드 경로가 업로드 폴더 내부인지 `os.path.realpath`로 검증 |
| **XSS 방지** | 클라이언트에서 서버 데이터를 `innerHTML`에 삽입 시 `escapeHtml()` 적용 |
| **보안 헤더** | `X-Content-Type-Options`, `X-Frame-Options`, `CSP`, `Referrer-Policy` 등 설정 |
| **에러 메시지 보호** | 내부 시스템 경로·스택 트레이스가 API 응답에 노출되지 않음 |
| **SECRET_KEY** | 환경변수 미설정 시 `secrets.token_hex(32)`로 랜덤 생성 |
| **세션 쿠키** | `HttpOnly=True`, `SameSite=Lax` 설정 |
| **파일 업로드 검증** | 확장자 검사 + `openpyxl`로 실제 엑셀 파일 여부 이중 검증 |
| **파일명 보안** | `werkzeug.utils.secure_filename`으로 안전한 파일명 변환 |

### 주의사항

- `.env` 파일은 `.gitignore`에 포함되어 있으므로 GitHub에 커밋되지 않습니다.
- 프로덕션 배포 시 Azure Portal의 **애플리케이션 설정**에서 `SECRET_KEY`를 별도로 설정하세요.
- Cosmos DB 키는 환경변수로만 관리하고 코드에 하드코딩하지 마세요.
