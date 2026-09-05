import os
import json
import unittest
import importlib
from unittest.mock import patch

local_chat = importlib.import_module("local-chat")


class TestUserManagementEdit(unittest.TestCase):
    def setUp(self):
        self.client = local_chat.app.test_client()

    def test_user_detail_is_owner(self):
        """测试用户详情接口正确返回 is_owner 标识"""
        mock_cfg = {"OWNER_MID": 9999001}
        with patch("config.get_raw_config", return_value=mock_cfg):
            with self.client.session_transaction() as sess:
                sess["authed"] = True

            # 测试主人 UID
            resp = self.client.get("/api/user/9999001")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("is_owner"))

            # 测试普通用户 UID
            resp = self.client.get("/api/user/8888001")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertFalse(data.get("is_owner"))

    def test_update_user_fields(self):
        """测试修改普通用户属性（不改 UID）"""
        mock_aff = {"8888001": 30}
        mock_prof = {"8888001": {"name": "旧名字", "impression": "旧印象", "tags": ["熟人"]}}

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
             patch.object(local_chat, "save_json", side_effect=mock_save), \
             patch("config.get_raw_config", return_value={"OWNER_MID": 9999001}):

            with self.client.session_transaction() as sess:
                sess["authed"] = True

            resp = self.client.post("/api/user/update", json={
                "old_uid": "8888001",
                "new_uid": "8888001",
                "name": "新名字",
                "score": 75,
                "impression": "新印象",
                "tags": ["好友", "东方同好"]
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("ok"))
            self.assertEqual(mock_aff["8888001"], 75)
            self.assertEqual(mock_prof["8888001"]["name"], "新名字")
            self.assertEqual(mock_prof["8888001"]["impression"], "新印象")
            self.assertIn("东方同好", mock_prof["8888001"]["tags"])

    def test_update_user_uid_migration(self):
        """测试修改 UID 触发全链路数据迁移（好感度、画像、记忆与推荐目标）"""
        mock_aff = {"8888001": 50}
        mock_prof = {"8888001": {"name": "迁移测试", "impression": "印象", "tags": ["好友"]}}
        mock_mem = [
            {"user_id": "8888001", "text": "消息1", "time": "2026-01-01"},
            {"user_id": "1111111", "text": "其他人的消息", "time": "2026-01-01"}
        ]

        def mock_load(path, default=None):
            if "affection.json" in path:
                return dict(mock_aff)
            if "user_profiles.json" in path:
                return dict(mock_prof)
            if "memory.json" in path:
                return list(mock_mem)
            return default if default is not None else {}

        def mock_save(path, data):
            if "affection.json" in path:
                mock_aff.clear()
                mock_aff.update(dict(data))
            elif "user_profiles.json" in path:
                mock_prof.clear()
                mock_prof.update(dict(data))
            elif "memory.json" in path:
                mock_mem.clear()
                mock_mem.extend(list(data))

        mock_cfg = {"OWNER_MID": 9999001, "PROACTIVE_MENTION_TARGETS": ["8888001", "9999001"]}

        with patch.object(local_chat, "load_json", side_effect=mock_load), \
             patch.object(local_chat, "save_json", side_effect=mock_save), \
             patch("config.get_raw_config", return_value=mock_cfg), \
             patch("config.update_config") as mock_update_cfg:

            with self.client.session_transaction() as sess:
                sess["authed"] = True

            resp = self.client.post("/api/user/update", json={
                "old_uid": "8888001",
                "new_uid": "8888002",
                "name": "迁移后名字",
                "score": 60,
                "impression": "迁移后印象",
                "tags": ["好友"]
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get("ok"))

            # 验证好感度迁移
            self.assertNotIn("8888001", mock_aff)
            self.assertEqual(mock_aff.get("8888002"), 60)

            # 验证画像迁移
            self.assertNotIn("8888001", mock_prof)
            self.assertEqual(mock_prof["8888002"]["name"], "迁移后名字")

            # 验证记忆迁移
            self.assertEqual(mock_mem[0]["user_id"], "8888002")
            self.assertEqual(mock_mem[1]["user_id"], "1111111")

            # 验证推荐目标迁移
            mock_update_cfg.assert_called_once()
            called_args = mock_update_cfg.call_args[0][0]
            self.assertEqual(called_args.get("PROACTIVE_MENTION_TARGETS"), ["8888002", "9999001"])

    def test_update_user_uid_conflict(self):
        """测试将 UID 改为已存在的其他 UID 时被拦截"""
        mock_aff = {"8888001": 30, "8888002": 40}
        mock_prof = {"8888001": {}, "8888002": {}}

        def mock_load(path, default=None):
            if "affection.json" in path:
                return dict(mock_aff)
            if "user_profiles.json" in path:
                return dict(mock_prof)
            return default if default is not None else {}

        with patch.object(local_chat, "load_json", side_effect=mock_load), \
             patch("config.get_raw_config", return_value={"OWNER_MID": 9999001}):

            with self.client.session_transaction() as sess:
                sess["authed"] = True

            resp = self.client.post("/api/user/update", json={
                "old_uid": "8888001",
                "new_uid": "8888002",
                "name": "冲突名字"
            })
            self.assertEqual(resp.status_code, 400)
            data = resp.get_json()
            self.assertFalse(data.get("ok"))
            self.assertIn("已存在", data.get("msg", ""))

    def test_owner_protection(self):
        """测试对主人 UID 的修改与删除保护机制"""
        with patch("config.get_raw_config", return_value={"OWNER_MID": 9999001}):
            with self.client.session_transaction() as sess:
                sess["authed"] = True

            # 尝试修改主人 UID
            resp = self.client.post("/api/user/update", json={
                "old_uid": "9999001",
                "new_uid": "9999002",
                "name": "企图改主人UID"
            })
            self.assertEqual(resp.status_code, 400)
            self.assertIn("主人 UID 仅可在系统基本设置中修改", resp.get_json().get("msg", ""))

            # 尝试删除主人
            resp = self.client.post("/api/user/delete", json={"uid": "9999001"})
            self.assertEqual(resp.status_code, 400)
            self.assertIn("主人不可删除", resp.get_json().get("msg", ""))

    def test_delete_regular_user(self):
        """测试删除普通用户"""
        mock_aff = {"8888001": 30, "9999001": 100}
        mock_prof = {"8888001": {"name": "待删除"}, "9999001": {"name": "主人"}}

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

        mock_cfg = {"OWNER_MID": 9999001, "PROACTIVE_MENTION_TARGETS": ["8888001", "9999001"]}

        with patch.object(local_chat, "load_json", side_effect=mock_load), \
             patch.object(local_chat, "save_json", side_effect=mock_save), \
             patch("config.get_raw_config", return_value=mock_cfg), \
             patch("config.update_config") as mock_update_cfg:

            with self.client.session_transaction() as sess:
                sess["authed"] = True

            resp = self.client.post("/api/user/delete", json={"uid": "8888001"})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.get_json().get("ok"))

            # 验证好感度与档案已删除
            self.assertNotIn("8888001", mock_aff)
            self.assertNotIn("8888001", mock_prof)
            self.assertIn("9999001", mock_aff)

            # 验证从推荐目标名单中剔除
            mock_update_cfg.assert_called_once()
            called_args = mock_update_cfg.call_args[0][0]
            self.assertEqual(called_args.get("PROACTIVE_MENTION_TARGETS"), ["9999001"])


if __name__ == "__main__":
    unittest.main()
