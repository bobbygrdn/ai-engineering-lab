import json
import os
import sqlite3

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from modules.logic.agentic_logic import classify_support_ticket_with_retries
from modules.auth import AuthError, AuthManager, AuthRateLimiter, RateLimitRule
from modules.schemas.type_safety import (
    AuthResponse,
    ClassifyRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    SupportAIService,
    UserProfile,
)
from modules.state import SQLiteStateStore
from modules.utils.helpers import log_invalid_output
from pydantic import ValidationError, BaseModel
from fastapi import Body
from modules.tools.engine import engine as tool_engine
from modules.tools.sql_read_only import SQL_READ_ONLY_MANIFEST, read_only_query_tool
from modules.tools.sample_tools import (
    GET_TICKET_MANIFEST,
    get_ticket_by_id,
    LIST_BY_STATUS_MANIFEST,
    list_tickets_by_status,
    SEARCH_KEYWORD_MANIFEST,
    search_tickets_keyword,
    COUNT_OPEN_BY_DEPT_MANIFEST,
    count_open_by_department,
    CREATE_TICKET_MANIFEST,
    create_ticket,
    UPDATE_STATUS_MANIFEST,
    update_ticket_status,
    ADD_NOTE_MANIFEST,
    add_ticket_note,
)
from modules.tools.hooks_builtin import rate_limit_hook_factory
from modules.tools.hooks_builtin import role_check_state_store_factory, role_check_token_per_tool_factory
from modules.logic.agentic_react import run_react_session

app = FastAPI()

DB_PATH = os.path.join("db", "app_state.db")
state_store = SQLiteStateStore(db_path=DB_PATH)
state_store.init_db()

auth_manager = AuthManager()

# register tools used by the AI (best-effort)
try:
    # register tools and per-manifest hooks for allowed_roles
    for m, fn in [
        (SQL_READ_ONLY_MANIFEST, read_only_query_tool),
        (GET_TICKET_MANIFEST, get_ticket_by_id),
        (LIST_BY_STATUS_MANIFEST, list_tickets_by_status),
        (SEARCH_KEYWORD_MANIFEST, search_tickets_keyword),
        (COUNT_OPEN_BY_DEPT_MANIFEST, count_open_by_department),
        (CREATE_TICKET_MANIFEST, create_ticket),
        (UPDATE_STATUS_MANIFEST, update_ticket_status),
        (ADD_NOTE_MANIFEST, add_ticket_note),
    ]:
        tool_engine.register_tool(m, fn)
        # register per-manifest role-check hook if manifest expresses allowed_roles
        if m.get("allowed_roles"):
            hook = role_check_token_per_tool_factory(auth_manager, state_store, m.get("allowed_roles"), m.get("name"))
            tool_engine.register_pre_invoke_hook(hook)

    # register a default rate limit hook (defense-in-depth)
    tool_engine.register_pre_invoke_hook(rate_limit_hook_factory(max_calls=1000, window_seconds=60))
    # configure engine to require access tokens for all invocations (AI will always be the caller)
    tool_engine.set_auth_manager(auth_manager)
    tool_engine.require_token_for_all_invocations(True)
except Exception:
    # best-effort: registration failures shouldn't break startup
    pass

ai_service = SupportAIService(state_store=state_store)
auth_security = HTTPBearer(auto_error=False)
auth_rate_limiter = AuthRateLimiter()

AUTH_ENDPOINT_RULES = {
    "/api/auth/register": RateLimitRule(limit=200, window_seconds=300),
    "/api/auth/login": RateLimitRule(limit=300, window_seconds=300),
    "/api/auth/refresh": RateLimitRule(limit=300, window_seconds=300),
    "/api/auth/logout": RateLimitRule(limit=300, window_seconds=300),
    "/api/auth/logout-all": RateLimitRule(limit=300, window_seconds=300),
}
AUTH_USERNAME_RULE = RateLimitRule(limit=80, window_seconds=300)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path not in AUTH_ENDPOINT_RULES:
            return await call_next(request)

        rule = AUTH_ENDPOINT_RULES[path]
        ip = request.client.host if request.client else "unknown"
        ip_key = f"auth:ip:{path}:{ip}"
        if not auth_rate_limiter.allow(ip_key, rule):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many authentication requests from this IP. Please try again later."},
            )

        username = None
        try:
            body = await request.body()
            if body:
                parsed = json.loads(body.decode("utf-8"))
                if isinstance(parsed, dict):
                    username = parsed.get("username")
        except Exception:
            username = None

        if isinstance(username, str) and username.strip():
            uname_key = f"auth:username:{path}:{username.strip().lower()}"
            if not auth_rate_limiter.allow(uname_key, AUTH_USERNAME_RULE):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many authentication attempts for this account. Please try again later."},
                )

        return await call_next(request)


app.add_middleware(AuthRateLimitMiddleware)

@app.get("/api/heartbeat")
def heartbeat():
    return {"status": "ok"}


def _request_meta(req: Request) -> dict[str, str]:
    return {
        "ip_address": req.client.host if req.client else "unknown",
        "user_agent": req.headers.get("user-agent", "unknown"),
    }


def _issue_auth_response(user: UserProfile, req: Request) -> AuthResponse:
    access_token = auth_manager.create_access_token(user_id=user.id, username=user.username)
    refresh_token = auth_manager.create_refresh_token(user_id=user.id, username=user.username)
    payload = auth_manager.decode_token(refresh_token, expected_type="refresh")

    state_store.persist_refresh_token(
        user_id=user.id,
        token_jti=payload["jti"],
        expires_at=auth_manager.refresh_expiry_iso(),
        ip_address=_request_meta(req)["ip_address"],
        user_agent=_request_meta(req)["user_agent"],
    )
    return AuthResponse(access_token=access_token, refresh_token=refresh_token, user=user)


def _user_profile_from_id(user_id: int) -> UserProfile:
    user = state_store.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return UserProfile(id=user.id, username=user.username, email=user.email)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(auth_security)) -> UserProfile:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")

    try:
        payload = auth_manager.decode_token(credentials.credentials, expected_type="access")
        user_id = int(payload.get("sub", "0"))
    except (AuthError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid access token")

    return _user_profile_from_id(user_id)


@app.post("/api/auth/register", response_model=AuthResponse)
def register(payload: RegisterRequest, request: Request):
    if "@" not in payload.email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    try:
        password_hash = auth_manager.hash_password(payload.password)
        created_user = state_store.create_user(
            username=payload.username,
            email=payload.email,
            password_hash=password_hash,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    profile = UserProfile(id=created_user.id, username=created_user.username, email=created_user.email)
    state_store.record_interaction(
        event_type="auth_register",
        payload={"username": created_user.username},
        user_id=created_user.id,
        **_request_meta(request),
    )
    return _issue_auth_response(profile, request)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request):
    user = state_store.get_user_by_username(payload.username)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if state_store.is_user_locked(payload.username):
        raise HTTPException(status_code=423, detail="Account temporarily locked due to failed login attempts")

    if not auth_manager.verify_password(payload.password, user["password_hash"]):
        state_store.mark_login_failure(payload.username)
        state_store.record_interaction(
            event_type="auth_login_failed",
            payload={"username": payload.username},
            user_id=int(user["id"]),
            **_request_meta(request),
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user_id = int(user["id"])
    state_store.clear_login_failures(user_id)
    state_store.record_interaction(
        event_type="auth_login_success",
        payload={"username": payload.username},
        user_id=user_id,
        **_request_meta(request),
    )
    profile = UserProfile(id=user_id, username=user["username"], email=user["email"])
    return _issue_auth_response(profile, request)


@app.post("/api/auth/refresh", response_model=AuthResponse)
def refresh_token(payload: RefreshRequest, request: Request):
    try:
        decoded = auth_manager.decode_token(payload.refresh_token, expected_type="refresh")
        user_id = int(decoded.get("sub", "0"))
        token_jti = str(decoded.get("jti", ""))
    except (AuthError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if not state_store.is_refresh_token_active(user_id=user_id, token_jti=token_jti):
        raise HTTPException(status_code=401, detail="Refresh token expired or revoked")

    state_store.revoke_refresh_token(user_id=user_id, token_jti=token_jti)
    user_profile = _user_profile_from_id(user_id)
    state_store.record_interaction(
        event_type="auth_token_refreshed",
        payload={"jti": token_jti},
        user_id=user_id,
        **_request_meta(request),
    )
    return _issue_auth_response(user_profile, request)


@app.post("/api/auth/logout")
def logout(payload: LogoutRequest, request: Request):
    try:
        decoded = auth_manager.decode_token(payload.refresh_token, expected_type="refresh")
        user_id = int(decoded.get("sub", "0"))
        token_jti = str(decoded.get("jti", ""))
    except (AuthError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Idempotent revocation: always revoke if token record exists.
    state_store.revoke_refresh_token(user_id=user_id, token_jti=token_jti)
    state_store.record_interaction(
        event_type="auth_logout",
        payload={"jti": token_jti},
        user_id=user_id,
        **_request_meta(request),
    )
    return {"status": "ok"}


@app.post("/api/auth/logout-all")
def logout_all(request: Request, current_user: UserProfile = Depends(get_current_user)):
    state_store.revoke_all_refresh_tokens(user_id=current_user.id)
    state_store.record_interaction(
        event_type="auth_logout_all",
        payload={"scope": "all_sessions"},
        user_id=current_user.id,
        **_request_meta(request),
    )
    return {"status": "ok"}


@app.get("/api/auth/me")
def me(current_user: UserProfile = Depends(get_current_user)):
    try:
        roles = state_store.get_roles_for_user_id(current_user.id)
    except Exception:
        roles = []
    return {"user": current_user, "roles": roles}

@app.post("/api/classify")
def classify(request: ClassifyRequest):
    try:
        ticket, metadata = classify_support_ticket_with_retries(request.email_text)
        if ticket is None:
            raise HTTPException(status_code=500, detail="Failed to classify the support ticket.")
        return {"ticket": ticket.model_dump(), "metadata": metadata.model_dump()}
    except ValueError as e:
        try:
            log_invalid_output(request.email_text, None, str(e))
        except Exception as log_error:
            print(f"Logging error: {log_error}")
        raise HTTPException(status_code=500, detail=str(e))
    except ValidationError as e:
        try:
            log_invalid_output(request.email_text, None, "Validation Error")
        except Exception as log_error:
            print(f"Logging error: {log_error}")
        raise HTTPException(status_code=500, detail="Failed to classify the support ticket.")
    except Exception as e:
        try:
            log_invalid_output(request.email_text, None, f"Unexpected error: {str(e)}")
        except Exception as log_error:
            print(f"Logging error: {log_error}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/api/handle")
def handle(request: ClassifyRequest, http_request: Request, current_user: UserProfile = Depends(get_current_user)):
    def event_generator():
        try:
            for event in ai_service.handle_ticket(
                request.email_text,
                user_id=current_user.id,
                request_meta=_request_meta(http_request),
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            try:
                log_invalid_output(request.email_text, None, f"Streaming error: {str(e)}")
            except Exception as log_error:
                print(f"Logging error: {log_error}")

            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/agentic")
def agentic(request: ClassifyRequest, http_request: Request, current_user: UserProfile = Depends(get_current_user)):
    def event_generator():
        try:
            for event in run_react_session(
                request.email_text,
                user_id=current_user.id,
                request_meta=_request_meta(http_request),
                tool_engine=tool_engine,
                state_store=state_store,
                auth_manager=auth_manager,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            try:
                log_invalid_output(request.email_text, None, f"Agentic streaming error: {str(e)}")
            except Exception as log_error:
                print(f"Logging error: {log_error}")

            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/interactions")
def interactions(
    event_type: str | None = None,
    limit: int = 100,
    current_user: UserProfile = Depends(get_current_user),
):
    safe_limit = max(1, min(limit, 500))
    return {
        "items": state_store.search_interactions(
            user_id=current_user.id,
            event_type=event_type,
            limit=safe_limit,
        )
    }


@app.get("/api/messages")
def messages(limit: int = 200, session_id: str | None = None, current_user: UserProfile = Depends(get_current_user)):
    safe_limit = max(1, min(limit, 2000))
    if session_id:
        msgs = state_store.get_messages_by_session(user_id=current_user.id, session_id=session_id, limit=safe_limit)
    else:
        msgs = state_store.get_recent_messages(user_id=current_user.id, limit=safe_limit)
    return {"items": msgs}


class MessageCreate(BaseModel):
    session_id: str | None = None
    role: str
    content: str
    token_count: int | None = 0


@app.post("/api/messages")
def post_message(payload: MessageCreate, current_user: UserProfile = Depends(get_current_user)):
    try:
        m = state_store.add_message(
            user_id=current_user.id,
            role=payload.role,
            content=payload.content,
            token_count=payload.token_count or 0,
            session_id=payload.session_id,
        )
        return {"status": "ok", "message_id": m}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions")
def create_session(payload: dict = Body(None), current_user: UserProfile = Depends(get_current_user)):
    import uuid
    sid = str(uuid.uuid4())
    title = None
    try:
        if payload and isinstance(payload, dict):
            title = payload.get('title')
        state_store.create_session(user_id=current_user.id, session_id=sid, title=title)
        return {"status": "ok", "session_id": sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SessionUpdate(BaseModel):
    title: str


@app.patch("/api/sessions/{session_id}")
def update_session_title(session_id: str, payload: SessionUpdate, current_user: UserProfile = Depends(get_current_user)):
    try:
        updated = state_store.update_session_title(user_id=current_user.id, session_id=session_id, title=payload.title)
        if not updated:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
def list_sessions(limit: int = 100, current_user: UserProfile = Depends(get_current_user)):
    safe_limit = max(1, min(limit, 1000))
    try:
        items = state_store.list_sessions(user_id=current_user.id, limit=safe_limit)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str, request: Request, current_user: UserProfile = Depends(get_current_user)):
    try:
        # attempt deletion
        deleted = state_store.delete_session(user_id=current_user.id, session_id=session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")

        # audit log the deletion for traceability
        try:
            state_store.add_audit_log(
                user_id=current_user.id,
                event_type="session_deleted",
                payload={"session_id": session_id},
                ip_address=_request_meta(request).get("ip_address"),
                user_agent=_request_meta(request).get("user_agent"),
            )
        except Exception:
            # non-fatal: don't prevent deletion if audit logging fails
            pass

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))