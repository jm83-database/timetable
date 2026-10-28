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
- **수업 준비 알림** - 수업별 수신자·교육 유형을 선택하고, 수업 7일 전과 3일 전 오전 9시(한국 시간)에 개별 메일 발송. 단기교육형은 결과보고서 견본·양식 자동 첨부
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
- **엑셀처럼 편집** - 주간 뷰에서 셀 선택 후 바로 타이핑·Enter로 추가, Tab으로 옆 셀 연속 입력, 카드 더블클릭/F2 수정, 드래그 이동(Ctrl+드래그 복사), Delete 삭제, 방향키 이동
- **날짜별 요약** - 날짜 클릭 시 사이드바에 그날의 사무실 근무자 / 휴가자 / 외부 일정 / 노트북 방문 표시
- **직원·구분 필터** - 직원 칩 토글(Ctrl+클릭 단독 보기), 구분별 표시/숨김
- **웹에서 직접 수정** - 항목 추가/수정/삭제, 엑셀 원문(raw_text)과 출처 시트를 상세 모달에서 확인
- **도움말 가이드** - 탭 우측 **?** 버튼으로 구성원 누구나 볼 수 있는 사용법·단축키 안내

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
TIMETABLE_AUTH_MODE=local
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
│       │── roster.js         # 근무표 캘린더, 주간 매트릭스(인라인 편집·드래그·키보드), 업로드/수정 모달
│       └── upload.js         # 시간표 업로드 워크플로우
│
├── templates/
│   ├── base.html             # 기본 레이아웃 (대시보드 / 직원근무표 / 업로드 탭)
│   ├── dashboard.html        # 대시보드 (캘린더 + 사이드바)
│   │── roster.html           # 직원근무표 (캘린더 + 날짜 요약 + 상세/추가/업로드/도움말 모달)
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

## 리마인드 운영 구성

- 대시보드의 **수신자 관리**에서 사내외 이메일을 등록하고, 수업 상세의 **알림 설정**에서 교육 유형과 수신자를 선택하여 저장합니다. 같은 날짜의 다른 수업은 별도로 설정합니다. 수신자를 모두 해제하고 저장하면 해당 수업의 이후 알림을 중지합니다. 대시보드 **? → 사용 가이드**에서도 안내를 확인할 수 있습니다.
- **정기교육형**은 기존처럼 텍스트만 발송하며 기존 설정도 이 유형으로 처리합니다. **단기교육형**은 D-7·D-3 메일에 `결과보고서 견본.pdf`, `결과보고서_양식.docx`를 모두 첨부합니다. 이미 발송 접수된 알림은 유형 변경만으로 다시 발송하지 않습니다.
- 두 공통 파일은 [services/attachments](services/attachments)에 원본 그대로 포함되며 웹 공개 경로로 제공하지 않습니다. 첨부파일 교체 시 같은 이름의 파일을 바꾼 뒤 메일 워커도 다시 배포해야 합니다. 다운로드 폴더나 로컬 데이터 폴더에 의존하지 않으며, GitHub Actions 함수 배포 패키지에도 포함됩니다. 파일을 읽지 못하거나 비어 있으면 첨부 없는 메일을 보내지 않고 `실패`로 기록하고 서버 로그에 원인을 남깁니다.
- 발신자는 `elixirr@elixirr.co.kr`이며 수신자별로 각각 전송합니다. 휴일에는 발송하지 않습니다. 한국 시간 오전 9시 이후 시간마다 확인하므로 설정 또는 일시 장애 복구가 늦으면 같은 날 늦게 발송될 수 있습니다.
- 발송 이력의 `발송 접수`는 Microsoft Graph가 요청을 수락했다는 뜻이며 실제 전달을 보장하지 않습니다. `실패`는 요청 거절 또는 첨부파일 준비 실패로 같은 날 한 시간 후 다시 시도하고, `확인 필요`는 전송 결과가 불확실하므로 중복 방지를 위해 자동 재발송하지 않습니다.
- 로컬에서만 `TIMETABLE_AUTH_MODE=local`을 사용합니다. Azure에서는 로컬 모드가 거부되며, 인증 설정이 없으면 서비스는 닫힌 상태로 응답합니다. 로컬 미리보기는 `COSMOS_DB_ENDPOINT`와 `COSMOS_DB_KEY`를 비워 운영 데이터와 분리하세요.
- [infra/provision.bicep](infra/provision.bicep)는 전용 리소스 그룹에 Linux Consumption `Y1`, Python 3.12 함수와 Storage, Key Vault 및 모니터링을 정의합니다. [infra/cosmos-role.bicep](infra/cosmos-role.bicep)는 기존 Cosmos DB 컨테이너 범위에 데이터 접근 권한을 부여합니다. 함수는 기본적으로 비활성화되므로 인프라를 다시 배포한 뒤에는 활성 상태를 확인해야 합니다. Linux Consumption은 2028년 9월 30일 종료 예정입니다. [infra/web-auth.bicep](infra/web-auth.bicep)는 현재 앱 설정을 보안 입력으로 받아 보존하면서 인증 설정을 추가합니다. 적용 전 백업과 what-if 검토가 필요합니다.
- `REMINDER_VALIDATE_ONLY=true`일 때 워커는 Cosmos DB 읽기만 확인하고 메일 전송과 발송 이력 쓰기를 건너뜁니다. 점검 후에는 이 설정을 `false`로 바꿔야 정상 알림이 발송됩니다.
- B 테넌트에 별도의 로그인 앱과 메일 앱 등록이 필요합니다. 로그인 앱은 `https://elixirrtimetable.azurewebsites.net/.auth/login/aad/callback` 리디렉션 URI, App Service 하이브리드 로그인용 ID 토큰 발급, ID 토큰의 `acct` 선택적 클레임이 필요합니다. 로그인은 B 테넌트의 `acct=0` 구성원이면서 `@elixirr.co.kr` 사용자 이름인 경우만 허용합니다.
- 메일 앱은 Exchange Application RBAC의 `Application Mail.Send`를 `elixirr@elixirr.co.kr` 사서함으로만 제한합니다. 이 방식에서는 동일 앱에 범위 없는 Entra `Mail.Send` 애플리케이션 권한을 별도로 부여하면 제한이 무효화되므로 부여하지 않습니다. 허용 사서함과 다른 사서함을 각각 대상으로 권한을 검증합니다. 다른 앱의 권한은 재사용하거나 변경하지 않습니다. 별도 Key Vault의 `timetable-mail` 비밀에는 메일 앱 자격 증명을 넣고, 로그인 앱 비밀은 안전한 배포 입력으로 전달합니다.
- Bicep 컴파일은 실제 배포 또는 권한 검증이 아닙니다. Azure에 적용하기 전 비용, 기존 앱 설정 보존, 관리자 동의, 함수 호스트 Storage/Cosmos RBAC 및 실제 로그인·테스트 발송을 검증하세요. 신규 메일 발송은 검증 후에만 활성화합니다.
- GitHub Actions는 테스트 통과와 인증 준비 확인 후 웹앱을 배포합니다. 함수 배포는 수동 실행 시 `reminder_app`에 전용 함수 앱 이름을 입력한 경우에만 실행됩니다. Linux Python 3.12로 패키지를 빌드해 비공개 Blob에 업로드하고 함수 앱을 재시작한 뒤 트리거를 동기화합니다. 기존 OIDC 배포 주체에는 전용 함수 앱의 배포 권한과 패키지 컨테이너에 대한 Blob 데이터 쓰기 권한이 필요합니다.

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
3. 수업명, 강사, 수업시간, 시작·종료 시각 등 입력
   - 수업시간은 `4.5`처럼 소수 입력 가능 (분 단위로 집계)
   - **종료 시각**을 직접 입력하면 수업시간이 자동 계산됨 (예: 13:00~17:30 = 4시간 30분, 13:00 이전 시작 시 점심시간 13:00~14:00 제외)
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

> 탭 우측 **?** 버튼을 누르면 같은 내용을 화면에서 바로 볼 수 있습니다.

#### 엑셀 업로드

1. 상단 **직원근무표** 탭 → 우측 **엑셀 업로드**
2. `직원근무표.xlsx`를 끌어다 놓으면 시트별로 **실제 연·월**(A1 셀 기준)이 표시됨 — 시트명(`'3월'`)과 실제 월이 달라도 정확히 매핑. 한글 파일명 그대로 올려도 됨
3. 가져올 월 선택 (이번 달 이후가 기본 선택) → **가져오기**. 선택한 월의 기존 항목은 모두 교체됨(웹에서 수정한 내용 포함)

#### 보기

- **월간**: 이벤트 클릭 → 상세(날짜·구분·담당자·메모·엑셀 원문) → 수정/삭제
- **주간**: 행=직원, 열=월~금. 맨 아래 **담당자 없음** 행에는 메모 등 사람이 없는 항목이 모임
- 사이드바 **날짜별 요약**: 사무실 근무자 / 휴가 / 외부 일정 / 노트북 방문. **오늘** 버튼으로 복귀
- **직원 칩** 클릭으로 표시/숨김, **Ctrl+클릭**은 한 사람만 보기. **구분 칩**으로 사무실·일정·휴가·노트북·메모 필터

#### 주간 보기에서 엑셀처럼 편집

셀을 클릭해 선택한 뒤 글자를 바로 입력하면 그 직원·날짜에 항목이 만들어집니다. 입력 내용에 `휴가`/`연차`/`반차`가 있으면 휴가, `사무실`이면 사무실근무, `노트북`이면 노트북방문, 그 외는 외부 일정으로 자동 분류됩니다.

| 동작 | 결과 |
|------|------|
| 셀 클릭 | 셀 선택 + 사이드바 날짜 요약 |
| 글자 입력 / Enter / 더블클릭 | 셀 안에 입력창 → Enter로 저장 |
| Tab / Shift+Tab | 저장 후 옆 셀로 이동하며 연속 입력 |
| 카드 더블클릭 / F2 | 제목 수정 (사무실근무 카드는 메모 수정). 비우고 Enter → 삭제 |
| 카드 드래그 → 다른 셀 | 날짜·담당자 변경. **Ctrl+드래그**는 복사 |
| Delete | 선택한 카드 삭제 |
| 방향키 / Esc | 셀 이동 / 입력 취소·선택 해제 |
| 카드의 `⋯` | 상세 모달 (구분 변경, 담당자 여러 명, 엑셀 원문 확인) |

한 일정에 담당자가 여러 명이면 각 직원 행에 모두 보이며, 드래그는 그 행의 직원만 바꿉니다.

#### 항목 추가 버튼

**+ 항목 추가**(또는 날짜 요약 아래 **+ 이 날짜에 항목 추가**)로 날짜, 구분(사무실근무·일정·휴가·노트북방문·메모), 제목, 담당자(쉼표 구분, 자동완성), 메모를 한 번에 입력할 수 있습니다.

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
| `POST` | `/api/courses/:id/entries` | 개별 수업 일정 추가 (`hours` 소수 허용, `end_time`을 주면 시작~종료로 분 단위 계산) |
| `PUT` | `/api/courses/:id/entries/:entryId` | 개별 수업 일정 수정 (동일) |
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

`category`는 `office` · `laptop` · `event` · `leave` · `memo` 중 하나, `people`은 배열 또는 `"홍길동, 전우치"` 문자열.

### 응답 예시

**GET /api/events**

```json
[
  {
    "id": "course_20250210_abc12345_2025-12-01",
    "title": "(홍길동) 데이터분석 기초1",
    "start": "2025-12-01T09:00:00",
    "end": "2025-12-01T19:00:00",
    "color": "#4A90D9",
    "textColor": "#ffffff",
    "extendedProps": {
      "course_id": "course_20250210_abc12345",
      "course_name": "A과정 1기",
      "entry_id": "entry_20250210_143025_a1b2c3d4",
      "instructor": "홍길동",
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
      "course_name": "A과정 1기",
      "color": "#4A90D9",
      "total_classes": 128,
      "total_holidays": 11,
      "total_hours": 1107,
      "date_range": "2025-09-15 ~ 2026-05-29",
      "instructors": {
        "홍길동": 18,
        "성춘향": 13,
        "이몽룡": 11
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
    "title": "A과정 설명회 · 전우치, 심청이",
    "start": "2026-10-07",
    "allDay": true,
    "color": "#F59E0B",
    "extendedProps": {
      "entry_id": "roster_20261008_012631_b8fd816f",
      "category": "event",
      "category_label": "일정",
      "title": "A과정 설명회",
      "people": ["전우치", "심청이"],
      "note": "",
      "raw_text": "A과정 설명회_전우치, 심청이",
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
- **수업시간**: 숫자 셀(0 초과~12, `4.5` 소수 허용) 우선 → 텍스트 "Xh"/"X.5h" 합산 → 기본 8시간 (분 단위로 반올림)
- **강사명**: 한글 2~4자 이름 자동 추출, `강사` 접미사 제거
- **복수 강사**: 슬래시(`/`), 쉼표(`,`), 별도 행 모두 지원
- **공휴일**: 추석, 설날, 성탄절, 방학 등 키워드 자동 감지
- **점심시간**: 13:00~14:00 자동 포함 (8시간 수업 = 09:00~18:00, 13:00 이후 시작은 미포함 → 4.5시간 = 13:00~17:30)

### 직원근무표

같은 Vertex42 월간 템플릿을 사용하며, 요일 열 배치는 수업시간표와 동일합니다. 주 블록(날짜 행 R) 안의 행 의미만 다릅니다:

```
A1 셀        : 해당 월 1일 (datetime) → 시트명 대신 이 값으로 연·월 판별
R   (날짜 행) : B열 '사무실근무' 라벨, 요일별 이름 열 = 당일 사무실 근무자
R+1          : A열 '노트북방문' 라벨, 자유 텍스트 메모
R+2 ~        : 특이사항
               '외부강의-임꺽정'        → 일정(외부강의) / 담당자 임꺽정
               '장보고-출장'            → 일정(출장) / 담당자 장보고  (방향 자동 판별)
               'A과정 설명회_전우치, 심청이' → 일정 / 담당자 2명
               '심청이 휴가', '임꺽정-휴가' → 휴가
               '출장예정' ↵ '이순신,심청이,임꺽정' → 이름만 있는 다음 행은 직전 일정의 담당자로 병합
               '임꺽정(프로젝트안내)'   → 괄호 안은 메모
```

- **직원 명단**: 1차 패스에서 `사무실근무` 행의 단일 이름을 수집하고, `X-Y`처럼 양쪽이 모두 이름 형태일 때 알려진 직원이 있는 쪽을 담당자로 판별
- **노이즈 제거**: `8h` 같은 템플릿 잔재, `메모`, Vertex42 푸터, 해당 월이 아닌 날짜(다음달 첫 주)는 무시
- **이름 오인식 방지**: `전시장`, `세미나`, `타운홀`, `대체휴일`처럼 2~4자 한글이지만 이름이 아닌 장소·행사명은 제외 (`services/roster_parser.py`의 `NOT_NAME` 목록에 추가)
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
