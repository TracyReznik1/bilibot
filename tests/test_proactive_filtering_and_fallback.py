import unittest
from unittest.mock import patch, MagicMock

import Proactive


class TestProactiveFilteringAndFallback(unittest.TestCase):
    def test_parse_tag_list(self):
        """测试多标点智能解析（支持中英文逗号、顿号、分号、空格及换行）"""
        # 1. 混合顿号与中文逗号
        raw1 = ["标签A、标签B、标签C、标签D、标签E、TagF、手书、MAD、Arrange、音MAD，综合标签"]
        res1 = Proactive.parse_tag_list(raw1)
        self.assertEqual(len(res1), 11)
        self.assertIn("标签A", res1)
        self.assertIn("综合标签", res1)
        self.assertIn("TagF", res1)

        # 2. 字符串输入与英文逗号/分号/空格
        raw2 = "科技, 游戏; 二次元 动漫；音乐\nVOCALOID"
        res2 = Proactive.parse_tag_list(raw2)
        self.assertEqual(res2, ["科技", "游戏", "二次元", "动漫", "音乐", "VOCALOID"])

        # 3. 空值与重复项自动去重
        raw3 = ["标签A", "标签A", "  ", "", "游戏", "标签A"]
        res3 = Proactive.parse_tag_list(raw3)
        self.assertEqual(res3, ["标签A", "游戏"])

    def test_match_video_filter_any_tag_match(self):
        """测试任意标签命中即通过，排除词优先拦截"""
        target_tags = ["标签A", "标签B", "综合标签"]
        exclude_keywords = ["广告", "带货"]

        # 1. 标题命中其中一个标签（任意命中）
        v1 = {"title": "【手书】标签B的日常冒险", "desc": "无特别", "tags": []}
        ok1, reason1 = Proactive.match_video_filter(v1, target_tags, exclude_keywords)
        self.assertTrue(ok1)
        self.assertIn("标签B", reason1)

        # 2. 简介中命中其中一个标签
        v2 = {"title": "普通游戏实况第1期", "desc": "本期包含综合标签同人游戏彩蛋", "tags": []}
        ok2, reason2 = Proactive.match_video_filter(v2, target_tags, exclude_keywords)
        self.assertTrue(ok2)
        self.assertIn("综合标签", reason2)

        # 3. 标签中命中其中一个标签
        v3 = {"title": "某动漫剪辑", "desc": "随手剪辑", "tags": ["MAD", "标签A"]}
        ok3, reason3 = Proactive.match_video_filter(v3, target_tags, exclude_keywords)
        self.assertTrue(ok3)
        self.assertIn("标签A", reason3)

        # 4. 未命中任何目标标签
        v4 = {"title": "纯科技开箱评测", "desc": "手机开箱", "tags": ["数码", "手机"]}
        ok4, reason4 = Proactive.match_video_filter(v4, target_tags, exclude_keywords)
        self.assertFalse(ok4)
        self.assertEqual(reason4, "未命中目标标签")

        # 5. 同时命中目标标签与排除词 -> 排除词优先拦截
        v5 = {"title": "【标签A】最新周边广告与带货专场", "desc": "买买买", "tags": ["标签A"]}
        ok5, reason5 = Proactive.match_video_filter(v5, target_tags, exclude_keywords)
        self.assertFalse(ok5)
        self.assertIn("命中排除词", reason5)

    def test_get_popular_videos_structure(self):
        """测试全站热门降级获取函数解析"""
        mock_popular_payload = {
            "code": 0,
            "data": {
                "list": [
                    {
                        "bvid": "BV1test001",
                        "title": "测试全站热门视频1",
                        "desc": "热门简介",
                        "owner": {"name": "UP主A", "mid": 10001},
                        "pubdate": 1740000000,
                        "pic": "http://example.com/pic.jpg",
                        "stat": {"view": 500000}
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_popular_payload

        with patch("requests.get", return_value=mock_resp):
            videos = Proactive.get_popular_videos(max_count=5)
            self.assertEqual(len(videos), 1)
            self.assertEqual(videos[0]["bvid"], "BV1test001")
            self.assertEqual(videos[0]["title"], "测试全站热门视频1")
            self.assertEqual(videos[0]["view"], 500000)


if __name__ == "__main__":
    unittest.main()
