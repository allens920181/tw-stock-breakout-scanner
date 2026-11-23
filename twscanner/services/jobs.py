"""
背景與排程掃描：同一套流程給「GitHub Actions 排程」和「App 內背景掃描」用。

流程：下載一次資料 → 依序用每個策略模式評估（第二個起不必再下載）→ 把「進場／觀察」名單與摘要存到雲端
（tw_kv 的 job_scan:{模式}）→ 選擇性算出實證規則名單（job_rulebook）。App 打開時讀回最新一份，不必等掃描。
只存進場與觀察的股票（幾十檔），不存整張表，雲端用量很小。
"""
import json
import logging
import threading
import time

import pandas as pd

from twscanner.core.tz import now_tw
from twscanner.data.universe import fetch_twse_universe
from twscanner.services.rulebook import build_rulebook
from twscanner.services.runconfig import build_run_config
from twscanner.services.scan import run_scan
from twscanner.storage import cloud as store

log = logging.getLogger(__name__)

OWNER = "me"
MODES = ("breakout", "early", "ambush")
MODE_LABELS = {"breakout": "強勢突破", "early": "早期突破", "ambush": "潛伏起漲前"}
KEEP_SIGNALS = ("進場", "觀察")
MAX_ROWS = 150
SCAN_KEY = "job_scan:{mode}"
RULEBOOK_KEY = "job_rulebook"


def scan_key(mode):
    return SCAN_KEY.format(mode=mode)


def _jsonable(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, default=str))


def _records(df):
    return json.loads(df.to_json(orient="records", force_ascii=False)) if df is not None and len(df) else []


def universe_items(kind):
    uni = fetch_twse_universe(include_common=kind in ("twse", "twse-common"), include_etf=kind in ("twse", "twse-etf"))
    return [{"code": x["code"], "company_name": x["company_name"]} for x in uni]


def build_payload(result, mode, universe_kind, at=None):
    """掃描結果 → 可存進雲端的 JSON（只留進場與觀察，最多 MAX_ROWS 檔）。"""
    df = result["df"]
    keep = df[df["訊號判斷"].isin(KEEP_SIGNALS)] if "訊號判斷" in df else df.iloc[0:0]
    if "評分" in keep:
        keep = keep.sort_values("評分", ascending=False)
    return {"at": at or now_tw().isoformat(timespec="seconds"), "mode": mode, "universe": universe_kind,
            "elapsed_sec": round(float(result.get("elapsed_sec") or 0), 1),
            "n_total": int(len(df)), "n_kept": int(len(keep.head(MAX_ROWS))),
            "market_state": _jsonable(result.get("market_state")),
            "summary": _records(result.get("summary")),
            "rows": _records(keep.head(MAX_ROWS))}


def payload_to_result(payload):
    """雲端內容 → App 認得的 result（表格只有進場與觀察；沒有 K 線與重新評估用的原始資料）。"""
    summary = pd.DataFrame(payload.get("summary") or [{}])
    return {"df": pd.DataFrame(payload.get("rows") or []), "summary": summary, "failed_df": pd.DataFrame(),
            "elapsed_sec": payload.get("elapsed_sec") or 0, "market_state": payload.get("market_state"),
            "ohlc_map": {}}


def holding_codes(owner):
    try:
        recs = store.load_holdings(owner)
        return [str(c) for c in (recs["股票代號"].dropna() if recs is not None and len(recs) else [])]
    except Exception:
        return []


def run_scan_job(base_cfg, prefs, universe_kind="twse-common", modes=MODES, owner=OWNER, with_rulebook=True,
                 progress_cb=None, scan=run_scan, items_fn=universe_items, save=True):
    """
    下載一次、每個模式各評估一次、存到雲端。回 {mode: payload, "rulebook": ...}。
    prefs：這個人的設定（雲端 prefs），沒有就用預設。某個模式失敗不會影響其他模式。
    """
    def emit(pct, msg):
        log.info("[排程] %s", msg)
        if progress_cb:
            try:
                progress_cb(pct, msg)
            except Exception:
                pass

    modes = [m for m in modes if m in MODES] or ["breakout"]
    prefs = dict(prefs or {})
    emit(0.02, "讀取股票清單")
    items = items_fn(universe_kind)
    cfg = build_run_config(base_cfg, {**prefs, "strategy_mode": modes[0]})
    first = scan(cfg=cfg, items=items, progress_cb=lambda s, p, m: emit(0.05 + 0.75 * p, f"{s}：{m}"))
    results = {modes[0]: first}
    for k, mode in enumerate(modes[1:], 1):
        emit(0.8 + 0.1 * k / len(modes), f"用已下載的資料評估「{MODE_LABELS[mode]}」")
        try:
            results[mode] = scan(cfg=build_run_config(base_cfg, {**prefs, "strategy_mode": mode}),
                                 cached=first["scan_cache"])
        except Exception as e:
            log.warning("模式 %s 評估失敗：%s", mode, e)
    out = {}
    for mode, res in results.items():
        out[mode] = build_payload(res, mode, universe_kind)
        if save:
            store.kv_set(owner, scan_key(mode), out[mode])
    if with_rulebook:
        src = next((r["df"] for r in results.values() if "距一年高點%" in r["df"]), None)
        if src is not None:
            emit(0.92, "計算實證規則名單（逐檔抓月營收）")
            try:
                rb = build_rulebook(src, base_cfg["data"]["cache_dir"],
                                    holding_codes=holding_codes(owner) if save else [])
                if rb:
                    rb["at"] = now_tw().isoformat(timespec="seconds")
                    out["rulebook"] = _jsonable(rb)
                    if save:
                        store.kv_set(owner, RULEBOOK_KEY, out["rulebook"])
            except Exception as e:
                log.warning("實證規則名單失敗：%s", e)
    emit(1.0, "完成")
    return out


def run_scheduled(config_path, dsn, owner=OWNER, universe_kind="twse-common", modes=MODES, with_rulebook=True):
    """排程進入點（GitHub Actions）：連雲端、讀使用者設定、跑完存回去。沒有 DATABASE_URL 就直接失敗，不白跑。"""
    from twscanner.core.config import load_config
    if not dsn:
        raise RuntimeError("缺少 DATABASE_URL：排程掃描需要把結果存到雲端資料庫")
    store.configure(dsn)
    ok, msg = store.ping()
    if not ok:
        raise RuntimeError(f"連不上雲端資料庫：{msg}")
    base_cfg = load_config(config_path)
    prefs = store.load_prefs(owner) or {}
    return run_scan_job(base_cfg, prefs, universe_kind, modes, owner, with_rulebook)


def load_scan(owner, mode):
    return store.kv_get(owner, scan_key(mode)) if store.is_enabled() else None


def load_rulebook(owner):
    return store.kv_get(owner, RULEBOOK_KEY) if store.is_enabled() else None


# ---------- App 內背景執行：同一個伺服器行程裡開一條執行緒，離開頁面也繼續跑 ----------
class JobRunner:
    """一次只跑一個工作。狀態用鎖保護，介面用 snapshot() 讀；每個工作有遞增的 id，讓 session 認得是不是自己的。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._seq = 0
        self._state = self._idle()

    def _idle(self):
        return {"id": self._seq, "state": "idle", "pct": 0.0, "msg": "", "started": None, "finished": None,
                "error": None, "result": None, "label": "", "meta": None}

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def running(self):
        return self.snapshot()["state"] == "running"

    def start(self, label, target, meta=None):
        """target(progress_cb) → 結果。已有工作在跑就不開新的，回 None；否則回工作 id（≥ 1）。"""
        with self._lock:
            if self._state["state"] == "running":
                return None
            self._seq += 1
            jid = self._seq
            self._state = {"id": jid, "state": "running", "pct": 0.0, "msg": "準備中", "started": time.time(),
                           "finished": None, "error": None, "result": None, "label": label, "meta": meta}

        def progress(pct, msg):
            with self._lock:
                if self._state["id"] == jid:
                    self._state["pct"], self._state["msg"] = min(1.0, float(pct)), str(msg)

        def work():
            try:
                res = target(progress)
                with self._lock:
                    if self._state["id"] == jid:
                        self._state.update(state="done", pct=1.0, result=res, finished=time.time(), msg="完成")
            except Exception as e:
                log.exception("背景工作失敗")
                with self._lock:
                    if self._state["id"] == jid:
                        self._state.update(state="error", error=str(e), finished=time.time())

        threading.Thread(target=work, daemon=True, name="twscanner-job").start()
        return jid

    def release(self, jid=None):
        """結果已被取走：丟掉大物件（掃描結果含全部 K 線），保留狀態。"""
        with self._lock:
            if self._state["state"] != "running" and (jid is None or jid == self._state["id"]):
                self._state["result"] = None
