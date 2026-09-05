import unittest
from unittest.mock import patch, MagicMock

import Proactive


class TestVideoFiltering(unittest.TestCase):
    def test_match_video_filter_title(self):
        """测试标题命中关键词"""
        video = {"title": "【二次元】测试角色的曲目演奏", "desc": "", "tags": []}
        ok, reason = Proactive.match_video_filter(video, ["二次元"], [])
        self.assertTrue(ok)
        self.assertIn("二次元", reason)

    def test_match_video_filter_tag(self):
        """测试标签命中关键词"""
        video = {"title": "游戏实况视频", "desc": "", "tags": ["单机游戏", "主机游戏"]}
        ok, reason = Proactive.match_video_filter(video, ["单机游戏"], [])
        self.assertTrue(ok)
        self.assertIn("单机游戏", reason)

    def test_match_video_filter_desc(self):
        """测试简介命中关键词"""
        video = {"title": "视频标题", "desc": "本视频关于测试角色的心理解析", "tags": []}
        ok, reason = Proactive.match_video_filter(video, ["测试角色"], [])
        self.assertTrue(ok)
        self.assertIn("测试角色", reason)

    def test_match_video_filter_exclude(self):
        """测试排除关键词生效"""
        video = {"title": "测试角色周边好物广告", "desc": "", "tags": ["二次元"]}
        ok, reason = Proactive.match_video_filter(video, ["测试角色"], ["广告", "带货"])
        self.assertFalse(ok)
        self.assertIn("命中排除词", reason)

    def test_match_video_filter_no_hit(self):
        """测试未命中目标标签时过滤"""
        video = {"title": "王者荣耀巅峰赛第一视角", "desc": "日常排位", "tags": ["MOBA", "手游"]}
        ok, reason = Proactive.match_video_filter(video, ["单机游戏", "二次元"], [])
        self.assertFalse(ok)
        self.assertEqual(reason, "未命中目标标签")

    def test_match_video_filter_empty_rules(self):
        """测试未设置目标标签时全部通过"""
        video = {"title": "任意视频", "desc": "简介", "tags": ["生活"]}
        ok, reason = Proactive.match_video_filter(video, [], [])
        self.assertTrue(ok)
        self.assertEqual(reason, "未限定标签")


if __name__ == "__main__":
    unittest.main()
