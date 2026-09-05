import unittest
from unittest.mock import patch, MagicMock

import ai


class TestEnhancedReplies(unittest.TestCase):
    def test_send_reply_nested_comment(self):
        """测试楼中楼二级/多级评论回复：root为根评论ID，parent为子评论ID"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "message": "0"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            # 5个参数调用: oid, root_id, parent_id, content_type, reply_text
            res = ai.send_reply(oid=12345, root_id=99999, parent_id_or_type=88888, content_type_or_reply=1, reply_text="楼中楼测试回复")
            self.assertTrue(res)
            mock_post.assert_called_once()
            _, kwargs = mock_post.call_args
            data = kwargs.get("data", {})
            self.assertEqual(data.get("oid"), 12345)
            self.assertEqual(data.get("root"), 99999)
            self.assertEqual(data.get("parent"), 88888)
            self.assertEqual(data.get("type"), 1)
            self.assertEqual(data.get("message"), "楼中楼测试回复")

    def test_send_reply_top_level_comment(self):
        """测试一级评论回复：root和parent均为当前评论ID"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "message": "0"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            res = ai.send_reply(oid=12345, root_id=77777, parent_id_or_type=77777, content_type_or_reply=1, reply_text="根楼层测试回复")
            self.assertTrue(res)
            _, kwargs = mock_post.call_args
            data = kwargs.get("data", {})
            self.assertEqual(data.get("root"), 77777)
            self.assertEqual(data.get("parent"), 77777)

    def test_send_reply_backward_compatibility(self):
        """测试旧版4参数调用方式兼容性"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 0, "message": "0"}

        with patch("requests.post", return_value=mock_resp) as mock_post:
            # 旧版4参数: (oid, rpid, content_type, reply_text)
            res = ai.send_reply(12345, 66666, 1, "旧版兼容回复")
            self.assertTrue(res)
            _, kwargs = mock_post.call_args
            data = kwargs.get("data", {})
            self.assertEqual(data.get("root"), 66666)
            self.assertEqual(data.get("parent"), 66666)
            self.assertEqual(data.get("type"), 1)
            self.assertEqual(data.get("message"), "旧版兼容回复")

    def test_get_new_ats_parsing(self):
        """测试 @我的 消息解析功能"""
        mock_payload = {
            "code": 0,
            "data": {
                "items": [
                    {
                        "user": {"nickname": "B站测试用户", "mid": 10001},
                        "item": {
                            "source_id": 50001,
                            "subject_id": 112233,
                            "root_id": 40001,
                            "business_id": 1,
                            "source_content": "你好 @AI机器人 请问今天天气怎么样"
                        }
                    },
                    {
                        "user": {"nickname": "另一个用户", "mid": 10002},
                        "item": {
                            "source_id": 50002,
                            "target_id": 334455,
                            "root_id": 0,
                            "business_id": 17,
                            "source_content": "@AI机器人 动态评论@测试"
                        }
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_payload

        with patch("requests.get", return_value=mock_resp):
            ats = ai.get_new_ats()
            self.assertEqual(len(ats), 2)

            # 楼中楼中的@消息
            self.assertEqual(ats[0]["rpid"], 50001)
            self.assertEqual(ats[0]["thread_id"], 40001)  # root_id
            self.assertEqual(ats[0]["oid"], 112233)
            self.assertEqual(ats[0]["username"], "B站测试用户")
            self.assertTrue(ats[0]["is_at"])

            # 顶级楼层的@消息 (root_id=0，thread_id应等于source_id)
            self.assertEqual(ats[1]["rpid"], 50002)
            self.assertEqual(ats[1]["thread_id"], 50002)
            self.assertEqual(ats[1]["oid"], 334455)
            self.assertTrue(ats[1]["is_at"])


if __name__ == "__main__":
    unittest.main()
