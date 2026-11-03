# 배포 가이드 (백엔드 Render + 프론트엔드 Vercel)

| 서비스 | 위치 | 저장소 / 브랜치 | 주소 예시 |
|---|---|---|---|
| PostgreSQL `placed-db` | Render | - | - |
| Django API `placed-api` | Render | nqo4/Placed `db-update` | `https://placed-api.onrender.com` |
| React 사이트 | Vercel | tjsals021127-wq/Placed `master` | `https://placed.vercel.app` |

이름이 이미 쓰이고 있으면 두 서비스 모두 주소 뒤에 문자가 붙습니다. 아래 순서대로 실제 주소를 확인하며 진행합니다.

## 0. 준비

- Render와 Vercel 계정에 GitHub를 연결합니다.
  Render는 `nqo4/Placed`, Vercel은 `tjsals021127-wq/Placed`에 접근할 수 있어야 합니다.
  프론트엔드 저장소는 소유자(tjsals021127-wq) 계정에서 허용해야 할 수 있습니다.
- Gemini API 키, NAVER API HUB Client ID/Secret을 준비합니다.

## 1. 백엔드 (Render)

1. Render 대시보드 > **New > Blueprint** > `nqo4/Placed` 선택, 브랜치는 `db-update`.
2. 입력란에 값을 넣습니다.
   - `CORS_ALLOWED_ORIGINS`: 아직 프론트 주소를 모르므로 우선 `https://placed.vercel.app`
   - `GEMINI_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 발급받은 값
3. **Apply** → DB 생성, API 빌드(마이그레이션 포함)가 진행됩니다.
4. `placed-api` 화면 상단의 주소(예: `https://placed-api.onrender.com`)를 복사해 둡니다.
   브라우저로 `<API 주소>/admin/login/`이 열리면 백엔드는 정상입니다.

## 2. 프론트엔드 (Vercel)

1. Vercel 대시보드 > **Add New > Project** > `tjsals021127-wq/Placed` Import.
2. Framework Preset은 Create React App으로 자동 인식됩니다. 빌드 설정은 저장소의 `vercel.json`이 정합니다.
3. **Environment Variables**에 추가합니다.
   - `REACT_APP_API_URL` = 1단계의 API 주소 (끝에 `/` 없이)
4. **Deploy**. 완료 후 나오는 주소(예: `https://placed.vercel.app`)를 확인합니다.

`REACT_APP_API_URL`은 빌드할 때 들어가므로, 나중에 값을 바꾸면 **Redeploy**해야 반영됩니다.

## 3. 주소 맞추기

Vercel 주소가 1단계에서 넣은 값과 다르면 Render `placed-api` > Environment >
`CORS_ALLOWED_ORIGINS`를 실제 Vercel 주소로 고칩니다(끝에 `/` 없이, 저장하면 자동 재배포).
여러 주소를 허용하려면 쉼표로 구분합니다.

Vercel은 커밋마다 `placed-git-xxx.vercel.app` 같은 미리보기 주소도 만듭니다. 이 주소들은
CORS에 넣지 않았으므로 로그인·검색이 실패하는 것이 정상이며, 고정 주소(Production)로 접속하면 됩니다.

## 4. 로컬 데이터 옮기기 (선택)

`placed-db` > Connect > **External Database URL**을 복사해 `<EXTERNAL_URL>` 자리에 넣습니다.
이 주소에는 비밀번호가 들어 있으니 저장소나 채팅에 올리지 마세요.

```bash
pg_dump --no-owner --no-acl -Fc -h localhost -U postgres -d placed -f placed.dump
pg_restore --no-owner --no-acl --clean --if-exists -d "<EXTERNAL_URL>" placed.dump
```

확장(extension) 관련 경고가 몇 줄 나와도 테이블이 복원되면 정상입니다.
로컬 회원 계정(비밀번호 해시 포함)도 함께 옮겨집니다.

## 5. 관리자 계정

무료 플랜은 Render 셸을 쓸 수 없으므로 로컬에서 원격 DB에 직접 만듭니다.
4단계에서 데이터를 옮겼다면 기존 관리자 계정을 그대로 쓸 수 있습니다.

```bash
DATABASE_URL="<EXTERNAL_URL>" python manage.py createsuperuser
```

## 6. 확인

- Vercel 주소에서 회원가입, 로그인, 검색, 장소 상세가 되는지 확인합니다.
- 다른 기기(휴대폰 등)에서도 같은 주소로 접속해 봅니다.

## 무료 플랜 제약

- Render API 서버는 15분 동안 요청이 없으면 잠들고, 다음 첫 요청에 약 1분이 걸립니다.
  화면(Vercel)은 바로 뜨지만 데이터가 늦게 옵니다. 시연 직전에는 API 주소를 미리 한 번 열어 깨워 두세요.
- 무료 PostgreSQL은 생성 후 일정 기간(현재 30일)이 지나면 만료됩니다. 대시보드의 만료일을 확인하세요.
- Render 서버 디스크는 재배포 때 초기화됩니다. 관리자가 업로드한 장소 이미지(`media/`)는 남지 않고,
  `DEBUG=False`에서는 제공되지도 않습니다. 네이버에서 수집한 외부 이미지 주소는 문제없습니다.
- Vercel 무료(Hobby) 플랜은 비상업용입니다.
- Gemini 키는 서버에서만 쓰이며, AI 관련 API는 분당 10회로 제한되어 있습니다.
