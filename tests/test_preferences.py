"""偏好的隱私規則：財務數字不寫伺服器本機檔（公開部署時所有訪客共用）。"""
import json

from twscanner.storage import cloud, preferences, trades


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


def test_trades_not_persisted_without_cloud():
    cloud.configure(None)
    assert trades.save_records([{"股票代號": "2330"}], owner="me") is False
    assert trades.load_records("me") == []
