"""로그인, 로그아웃, 현재 사용자 API와 안전한 세션 쿠키 발급 경계다."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.auth.dependencies import CurrentUser, SESSION_COOKIE_NAME
from app.auth.sessions import issue_session
from app.schemas.auth import LoginRequest, LoginResponse, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    """계정을 검증해 JavaScript가 읽을 수 없는 서명 세션 쿠키를 발급한다."""
    if len(request.app.state.auth_secret) < 32 or request.app.state.auth_secret.startswith("replace-"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="인증 서비스 설정이 준비되지 않았습니다.")
    context = request.app.state.auth_service.authenticate(body.username, body.password)
    if context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    token = issue_session(context, request.app.state.auth_secret, request.app.state.auth_expire_minutes)
    response.set_cookie(SESSION_COOKIE_NAME, token, httponly=True, secure=request.app.state.auth_cookie_secure,
                        samesite="lax", max_age=request.app.state.auth_expire_minutes * 60, path="/")
    return LoginResponse(user=UserProfile.model_validate(context))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """브라우저 세션 쿠키를 즉시 제거하여 후속 보호 요청을 차단한다."""
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", httponly=True, samesite="lax")


@router.get("/me", response_model=UserProfile)
async def me(user: CurrentUser) -> UserProfile:
    """서버가 검증한 현재 사용자 프로필과 역할별 허용 DB만 반환한다."""
    return UserProfile.model_validate(user)
