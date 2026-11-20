"""偏好的隱私規則：財務數字不寫伺服器本機檔（公開部署時所有訪客共用）。"""
import json

from twscanner.storage import cloud, preferences


def test_private_keys_never_written_locally(tmp_path, monkeypatch):
    path = tmp_path / "prefs.json"
    monkeypatch.setattr(preferences, "PREF_PATH", path)
    cloud.configure(None)
    res = preferences.save_prefs({"preset": "aggressive", "color_mode": "us",
                                  "total_capital": 3_000_000, "month_target": 20_000})
    assert res == {"local": True, "cloud": False}
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == {"preset": "aggressive", "color_mode": "us"}
    loaded = preferences.load_prefs()
    assert loaded["preset"] == "aggressive" and loaded["total_capital"] == 1_000_000   # 回到預設


def test_old_file_with_private_keys_is_scrubbed(tmp_path, monkeypatch):
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"preset": "balanced", "total_capital": 5_000_000}), encoding="utf-8")
    monkeypatch.setattr(preferences, "PREF_PATH", path)
    cloud.configure(None)
    assert preferences.load_prefs()["total_capital"] == 1_000_000
    assert "total_capital" not in json.loads(path.read_text(encoding="utf-8"))


def test_cloud_disabled_is_safe():
    cloud.configure(None)
    assert cloud.kv_get_all("me") is None and cloud.kv_versions("me") is None
    assert cloud.kv_put("me", "trades", [])["ok"] is False


def test_sync_decisions():
    from twscanner.storage.sync import decide, merge, signature
    a, b = signature([{"x": 1}]), signature([{"x": 2}])
    base = {"sig": a, "at": "t1"}
    assert decide(a, base, "t1") == "none"
    assert decide(b, base, "t1") == "push"          # 這台改了
    assert decide(a, base, "t2") == "pull"          # 別台改了
    assert decide(b, base, "t2") == "conflict"      # 兩邊都改了
    assert decide(b, {"sig": None, "at": None}, None) == "push"    # 雲端還沒有
    assert signature({"a": 1, "b": 2}) == signature({"b": 2, "a": 1})
    j1 = [{"掃描日": "d1", "股票": "2330.TW", "x": 1}]
    j2 = [{"掃描日": "d1", "股票": "2330.TW", "x": 9}, {"掃描日": "d2", "股票": "2317.TW"}]
    assert merge("journal", j1, j2) == j1 + [j2[1]]                # 日誌以（掃描日, 股票）去重
    t1, t2 = [{"賣出日": "d1", "損益": 1}], [{"賣出日": "d1", "損益": 1}, {"賣出日": "d2", "損益": 2}]
    assert merge("trades", t1, t2) == t1 + [t2[1]]                 # 交易紀錄以整筆內容去重
