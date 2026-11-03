# Render 배포 가이드

`render.yaml`(Blueprint)로 PostgreSQL, 백엔드 API, 프론트엔드 정적 사이트를 한 번에 만듭니다.
모두 무료 플랜이며 주소는 `https://<서비스 이름>.onrender.com` 형태로 고정됩니다.

| 서비스 | 저장소 / 브랜치 | 역할 |
|---|---|---|
| `placed-db` | - | PostgreSQL |
| `placed-api` | nqo4/Placed `db-update` | Django API (gunicorn) |
| `placed-web` | tjsals021127-wq/Placed `master` | React 빌드 결과 |

## 0. 준비

- Render 계정에 GitHub를 연결하고, **두 저장소 모두** Render GitHub 앱이 접근할 수 있게 허용합니다.
  프론트엔드 저장소는 소유자(tjsals021127-wq) 계정에서 허용해야 할 수 있습니다.
- Gemini API 키, NAVER API HUB Client ID/Secret을 준비합니다.

## 1. Blueprint 생성

1. Render 대시보드 > **New > Blueprint** > `nqo4/Placed` 선택, 브랜치는 `db-update`.
2. 입력란이 나오면 값을 넣습니다. 서비스 주소는 아직 모르므로 우선 예상 주소를 넣습니다.
   - `CORS_ALLOWED_ORIGINS`: `https://placed-web.onrender.com`
   - `REACT_APP_API_URL`: `https://placed-api.onrender.com`
   - `GEMINI_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 발급받은 값
3. **Apply**를 누르면 DB 생성 → API 빌드(마이그레이션 포함) → 프론트엔드 빌드가 진행됩니다.

## 2. 실제 주소 확인

이름이 이미 쓰이고 있으면 Render가 `placed-api-abcd.onrender.com`처럼 뒤에 문자를 붙입니다.
각 서비스 화면 상단의 주소를 확인하고, 1단계에서 넣은 값과 다르면 고칩니다.

- `placed-api` > Environment > `CORS_ALLOWED_ORIGINS` = 프론트엔드 실제 주소 (끝에 `/` 없이)
- `placed-web` > Environment > `REACT_APP_API_URL` = API 실제 주소 (끝에 `/` 없이)
- 프론트엔드 값을 바꾸면 **Manual Deploy > Clear build cache & deploy**로 다시 빌드해야 반영됩니다.

## 3. 로컬 데이터 옮기기 (선택)

빈 DB로 시작하지 않으려면 로컬 PostgreSQL 데이터를 옮깁니다.
`placed-db` > Connect > **External Database URL**을 복사해 아래 `<EXTERNAL_URL>` 자리에 넣습니다.
이 주소에는 비밀번호가 들어 있으니 저장소나 채팅에 올리지 마세요.

```bash
pg_dump --no-owner --no-acl -Fc -h localhost -U postgres -d placed -f placed.dump
pg_restore --no-owner --no-acl --clean --if-exists -d "<EXTERNAL_URL>" placed.dump
```

확장(extension) 관련 경고가 몇 줄 나와도 테이블이 복원되면 정상입니다.
로컬 회원 계정(비밀번호 해시 포함)도 함께 옮겨집니다.

## 4. 관리자 계정

무료 플랜은 Render 셸을 쓸 수 없으므로 로컬에서 원격 DB에 직접 만듭니다.
3단계에서 데이터를 옮겼다면 기존 관리자 계정을 그대로 쓸 수 있습니다.

```bash
DATABASE_URL="<EXTERNAL_URL>" python manage.py createsuperuser
```

## 5. 확인

- `https://<web 주소>`에서 회원가입, 로그인, 검색, 장소 상세가 되는지 확인합니다.
- 다른 기기(휴대폰 등)에서도 같은 주소로 접속해 봅니다.

## 무료 플랜 제약

- API 서버는 15분 동안 요청이 없으면 잠들고, 다음 첫 요청에 약 1분이 걸립니다.
  발표나 시연 직전에는 미리 한 번 접속해 깨워 두세요.
- 무료 PostgreSQL은 생성 후 일정 기간(현재 30일)이 지나면 만료됩니다. 대시보드의 만료일을 확인하세요.
- 서버 디스크는 재배포 때 초기화됩니다. 관리자가 업로드한 장소 이미지(`media/`)는 남지 않고,
  `DEBUG=False`에서는 제공되지도 않습니다. 네이버에서 수집한 외부 이미지 주소는 문제없습니다.
- Gemini 키는 서버에서만 쓰이며, AI 관련 API는 분당 10회로 제한되어 있습니다.
