"""
登入方式：Google 登入（記住這台裝置）＋ 密碼（備援）。

- Google 登入用 Streamlit 內建的 st.login（OpenID Connect）。登入後 Streamlit 會在瀏覽器存一個
  身分 cookie（約 30 天），重新整理、關掉再開都不用重新登入。
- 這是單人 App：只有 secrets 裡 ALLOWED_EMAILS 列出的 Google 帳號能讀寫雲端資料；
  它們都對應到同一個雲端空間（owner = "me"），和密碼登入看到的是同一份資料。
- 沒設定 [auth] 時，設定頁只顯示密碼登入，行為和以前一樣。
設定步驟見 docs/雲端設定.md。
"""
import streamlit as st

OWNER = "me"


def _secrets():
    try:
        return st.secrets
    except Exception:
        return {}


def _auth_section():
    try:
        sec = _secrets().get("auth")
        return dict(sec) if sec else None
    except Exception:
        return None


def provider():
    """[auth] 底下若有 [auth.google] 這類子區塊，回它的名字；單一供應商寫在 [auth] 裡就回 None。"""
    sec = _auth_section() or {}
    subs = [k for k, v in sec.items() if hasattr(v, "keys")]
    return "google" if "google" in subs else (subs[0] if subs else None)


def google_configured():
    sec = _auth_section()
    if not sec or not sec.get("redirect_uri") or not sec.get("cookie_secret"):
        return False
    p = provider()
    conf = sec.get(p) if p else sec
    return bool(conf and conf.get("client_id") and conf.get("client_secret") and conf.get("server_metadata_url"))


def allowed_emails():
    raw = _secrets().get("ALLOWED_EMAILS", [])
    if isinstance(raw, str):
        raw = raw.replace(";", ",").split(",")
    return {str(e).strip().lower() for e in raw if str(e).strip()}


def is_allowed(email, allowed):
    """純函式：email 是否在允許名單（不分大小寫）。名單空的時候一律不允許（安全預設）。"""
    return bool(email) and bool(allowed) and email.strip().lower() in allowed


def google_email():
    """目前用 Google 登入的 email；沒登入回 None。"""
    try:
        if google_configured() and st.user.is_logged_in:
            return str(st.user.get("email") or "").lower() or None
    except Exception:
        return None
    return None


def decide_login(email, allowed, owner, method):
    """
    純函式：Google 登入狀態 → 這個 session 該怎麼做。
    "login"：進入雲端空間；"deny"：不在名單（若原本是用 Google 進來的就退出）；
    "drop"：Google 已登出（cookie 過期或在別處登出），原本用 Google 進來的要退出；"none"：不用動。
    用密碼登入的 session 不受 Google 狀態影響。
    """
    if not email:
        return "drop" if method == "google" else "none"
    if not is_allowed(email, allowed):
        return "deny"
    return "login" if owner != OWNER else "none"


def apply_login():
    """每次執行開頭（同步之前）：Google 已登入且在允許名單 → 進入雲端空間，不用再輸入密碼。"""
    ss = st.session_state
    email = google_email()
    action = decide_login(email, allowed_emails(), ss.get("cloud_owner"), ss.get("auth_method"))
    if action != "deny":
        ss.pop("_auth_denied", None)
    if action == "login":
        ss["cloud_owner"] = OWNER
        ss["auth_method"] = "google"
        ss.pop("_cloud_loaded", None)                 # 讓同步在這次執行把雲端資料載回來
    elif action == "deny":
        ss["_auth_denied"] = email
        if ss.get("auth_method") == "google":
            from twscanner.ui import sync
            sync.logout()
            ss.pop("auth_method", None)
    elif action == "drop":
        from twscanner.ui import sync
        sync.logout()                                 # 一併清掉個人資料（共用電腦）
        ss.pop("auth_method", None)


def login_with_password(passcode, typed):
    if passcode and typed == passcode:
        st.session_state["cloud_owner"] = OWNER
        st.session_state["auth_method"] = "password"
        st.session_state.pop("_cloud_loaded", None)
        return True
    return False


def start_google_login():
    p = provider()
    st.login(p) if p else st.login()


def sign_out():
    """清掉這個分頁的個人資料；用 Google 登入的也一併登出 Google（否則下次執行又會自動登入）。"""
    from twscanner.ui import sync

    was_google = st.session_state.get("auth_method") == "google" or google_email()
    sync.logout()
    st.session_state.pop("auth_method", None)
    if was_google:
        st.logout()
