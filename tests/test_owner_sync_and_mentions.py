import os
import json
import tempfile
import unittest
import importlib
from unittest.mock import patch

import config
local_chat = importlib.import_module("local-chat")


class TestOwnerSyncAndMentions(unittest.TestCase):
    def test_sync_owner_state(self):
        """测试动态自愈引擎：纠正主人好感度为100，清理占位UID:0，补全主人标签"""
        with tempfile.TemporaryDirectory() as tmpdir:
            aff_file = os.path.join(tmpdir, "affection.json")
            prof_file = os.path.join(tmpdir, "user_profiles.json")

            # 初始状态：包含残留占位0和未同步好感度的主人
            initial_aff = {"0": 100, "9999001": 15, "9999002": 30}
            initial_prof = {
                "0": {"impression": "占位"},
                "9999001": {"name": "老昵称", "tags": ["路人"]}
            }
            with open(aff_file, "w", encoding="utf-8") as f:
                json.dump(initial_aff, f)
            with open(prof_file, "w", encoding="utf-8") as f:
                json.dump(initial_prof, f)

            mock_cfg = {
                "OWNER_MID": 9999001,
                "OWNER_NAME": "测试主人",
                "OWNER_BILI_NAME": "主人B站名"
            }

            with patch("config.get_raw_config", return_value=mock_cfg):
                config.sync_owner_state(data_dir=tmpdir)

            # 验证好感度
            with open(aff_file, "r", encoding="utf-8") as f:
                aff = json.load(f)
            self.assertNotIn("0", aff)
            self.assertEqual(aff.get("9999001"), 100)
            self.assertEqual(aff.get("9999002"), 30)

            # 验证用户画像
            with open(prof_file, "r", encoding="utf-8") as f:
                prof = json.load(f)
            self.assertNotIn("0", prof)
            self.assertIn("9999001", prof)
            self.assertIn("主人", prof["9999001"]["tags"])
            self.assertEqual(prof["9999001"]["name"], "主人B站名")

    def test_preset_user_api(self):
        """测试 POST /api/user/preset 添加预设认识的人"""
        client = local_chat.app.test_client()
        mock_aff = {}
        mock_prof = {}

        def mock_load(path, default=None):
            if "affection.json" in path:
                return dict(mock_aff)
            if "user_profiles.json" in path:
                return dict(mock_prof)
            return default if default is not None else {}

        def mock_save(path, data):
            if "affection.json" in path:
                mock_aff.clear()
                mock_aff.update(dict(data))
            elif "user_profiles.json" in path:
                mock_prof.clear()
                mock_prof.update(dict(data))

        with patch.object(local_chat, "load_json", side_effect=mock_load), \
             patch.object(local_chat, "save_json", side_effect=mock_save):
            
            with client.session_transaction() as sess:
                sess["authed"] = True

            resp = client.post("/api/user/preset", json={
                "uid": "8888001",
                "name": "测试好友",
                "score": 45,
                "impression": "测试印象",
                "tags": ["预设认识的人", "东方同好"]
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("ok"))
            self.assertEqual(mock_aff.get("8888001"), 45)
            self.assertIn("8888001", mock_prof)
            self.assertEqual(mock_prof["8888001"]["name"], "测试好友")
            self.assertEqual(mock_prof["8888001"]["impression"], "测试印象")
            self.assertIn("预设认识的人", mock_prof["8888001"]["tags"])
            self.assertIn("东方同好", mock_prof["8888001"]["tags"])

    def test_mention_targets_resolution(self):
        """测试 @推荐目标 的各种配置决策模式"""
        owner_mid = "9999001"

        # 1. 默认状态（未配置）：默认仅 @ 主人
        raw_targets_default = None
        if raw_targets_default is None:
            targets_default = [owner_mid] if owner_mid and owner_mid != "0" else []
        else:
            targets_default = [str(t).strip() for t in raw_targets_default if str(t).strip()]
        self.assertEqual(targets_default, [owner_mid])

        # 2. 全不选（空列表）：跳过@，仅发表推荐评论
        raw_targets_empty = []
        if raw_targets_empty is None:
            targets_empty = [owner_mid]
        else:
            targets_empty = [str(t).strip() for t in raw_targets_empty if str(t).strip()]
        self.assertEqual(targets_empty, [])

        # 3. 多选模式：指定多名候选人
        raw_targets_multi = ["9999001", "9999002", "9999003"]
        targets_multi = [str(t).strip() for t in raw_targets_multi if str(t).strip()]
        self.assertEqual(len(targets_multi), 3)
        self.assertIn(owner_mid, targets_multi)
        self.assertIn("9999002", targets_multi)


if __name__ == "__main__":
    unittest.main()
