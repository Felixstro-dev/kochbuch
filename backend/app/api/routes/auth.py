from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import Principal, get_optional_principal, get_principal, require_write
from app.core.config import Settings
from app.core.security import constant_time_equals, hash_password, validate_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import AuthResponse, AuthStatus, LoginRequest, PasswordChangeRequest, SetupRequest, UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(
    response: Response, token: str, csrf_token: str, settings: Settings
) -> None:
    max_age = settings.session_ttl_days * 24 * 60 * 60
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
        domain=settings.cookie_domain,
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name, path="/", domain=settings.cookie_domain
    )
    response.delete_cookie(settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)


def _check_login_rate_limit(request: Request, username: str) -> None:
    limiter = request.app.state.login_limiter
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = limiter.allow(f"{ip}:{username.strip().lower()}")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele Anmeldeversuche. Bitte kurz warten.",
            headers={"Retry-After": str(retry_after)},
        )


@router.get("/status", response_model=AuthStatus)
def auth_status(
    request: Request,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> AuthStatus:
    settings: Settings = request.app.state.settings
    user = principal.user if principal and principal.user else None
    return AuthStatus(
        setup_required=auth_service.count_users(db) == 0,
        authenticated=principal is not None and principal.is_authenticated,
        user=UserOut.model_validate(user) if user and principal and principal.is_authenticated else None,
        embed_public=settings.embed_public,
        app_name=settings.app_name,
        version=__version__,
    )


@router.post("/setup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def setup(
    payload: SetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    if auth_service.count_users(db) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Die Einrichtung wurde bereits abgeschlossen.",
        )
    _check_login_rate_limit(request, payload.username)
    try:
        user = auth_service.create_user(
            db,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name or payload.username,
            role="admin",
        )
    except auth_service.ServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings: Settings = request.app.state.settings
    token, csrf_token = auth_service.create_session(
        db, user, request, ttl_days=settings.session_ttl_days, pepper=settings.token_pepper
    )
    _set_auth_cookies(response, token, csrf_token, settings)
    auth_service.record_audit(db, action="auth.setup", user_id=user.id, request=request)
    return AuthResponse(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    _check_login_rate_limit(request, payload.username)
    user = auth_service.authenticate(db, payload.username, payload.password)
    if not user:
        auth_service.record_audit(
            db,
            action="auth.login_failed",
            request=request,
            detail={"username": payload.username[:64]},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort ist falsch.",
        )
    settings: Settings = request.app.state.settings
    token, csrf_token = auth_service.create_session(
        db, user, request, ttl_days=settings.session_ttl_days, pepper=settings.token_pepper
    )
    _set_auth_cookies(response, token, csrf_token, settings)
    request.app.state.login_limiter.reset(
        f"{(request.client.host if request.client else 'unknown')}:{payload.username}"
    )
    auth_service.record_audit(db, action="auth.login", user_id=user.id, request=request)
    return AuthResponse(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> Response:
    settings: Settings = request.app.state.settings
    if principal and principal.auth_type == "session":
        cookie = request.cookies.get(settings.csrf_cookie_name, "")
        header = request.headers.get("x-csrf-token", "")
        if not cookie or not header or not constant_time_equals(cookie, header):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF-Token fehlt oder ist ungültig.",
            )
        auth_service.revoke_session(db, principal.session_token or "", settings.token_pepper)
        auth_service.record_audit(
            db, action="auth.logout", user_id=principal.user.id if principal.user else None
        )
    _clear_auth_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(principal: Principal = Depends(get_principal)) -> UserOut:
    if not principal.user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Keine Benutzersitzung.")
    return UserOut.model_validate(principal.user)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    principal: Principal = Depends(require_write),
    db: Session = Depends(get_db),
) -> Response:
    if principal.auth_type != "session" or not principal.user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Das Passwort kann nur in der Oberfläche geändert werden.",
        )
    user = db.get(User, principal.user.id)
    if not user or not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das aktuelle Passwort ist falsch.",
        )
    problem = validate_password(payload.new_password)
    if problem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    settings: Settings = request.app.state.settings
    auth_service.revoke_user_sessions(
        db, user.id, except_token=principal.session_token, pepper=settings.token_pepper
    )
    auth_service.record_audit(db, action="auth.password_changed", user_id=user.id, request=request)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
