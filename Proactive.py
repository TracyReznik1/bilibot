import requests
import json
import time
import random
import subprocess
import os
import base64
import re
import sys
from datetime import datetime, timedelta
from openai import OpenAI

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ========== 配置 ==========
from config import *

from config import PROACTIVE_VIDEO_COUNT, PROACTIVE_COMMENT_COUNT
DAILY_WATCH_COUNT = PROACTIVE_VIDEO_COUNT
DAILY_COMMENT_COUNT = PROACTIVE_COMMENT_COUNT
EXTERNAL_MEMORY_FILE = "data/external_memory.json"
COMMENTED_FILE = "data/commented_videos.json"
WATCH_LOG_FILE = "data/watch_log.json"
TEMP_VIDEO_DIR = "./temp_videos"

# 喜好分区 tid（B站分区ID）
PREFERRED_TIDS = [
    17,   # 游戏
    160,  # 生活·vlog
    211,  # 美食
    3,    # 音乐
    13,   # 番剧/动漫
    167,  # 同人
    321,  # vup/虚拟UP主
    36,   # 科技·AI相关
    129,  # 绘画
]
# ================================

headers = {
    "Cookie": f"SESSDATA={SESSDATA}; bili_jct={BILI_JCT}; DedeUserID={DEDE_USER_ID}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com"
}

or_client = OpenAI(
    api_key=OR_API_KEY or "not_set",
    base_url=OR_BASE_URL or "https://generativelanguage.googleapis.com/v1beta/openai/"
)

# ========== 工具函数 ==========
COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

def generate_cookies_file():
    """每次启动自动从config.py生成yt-dlp用的cookies.txt"""
    with open(COOKIES_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write(f".bilibili.com\tTRUE\t/\tFALSE\t0\tSESSDATA\t{SESSDATA}\n")
        f.write(f".bilibili.com\tTRUE\t/\tFALSE\t0\tbili_jct\t{BILI_JCT}\n")
        f.write(f".bilibili.com\tTRUE\t/\tFALSE\t0\tDedeUserID\t{DEDE_USER_ID}\n")
    print(f"🍪 已从config.py生成cookies.txt")

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_pubdate(val):
    """把各种格式的pubdate统一转成时间戳"""
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        try:
            return int(val)
        except ValueError:
            pass
        for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                return int(datetime.strptime(val, fmt).timestamp())
            except ValueError:
                continue
    return 0

# ========== wbi签名（B站反爬必需） ==========
import hashlib
import urllib.parse

# wbi混淆表（固定值）
WBI_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]

_wbi_cache = {"img_key": "", "sub_key": "", "time": 0}

def _get_mixin_key(raw_key):
    return "".join(raw_key[i] for i in WBI_MIXIN_KEY_ENC_TAB)[:32]

def _get_wbi_keys():
    """从B站nav接口获取wbi签名密钥（带缓存，1小时刷新）"""
    import time as _time
    now = _time.time()
    if _wbi_cache["img_key"] and now - _wbi_cache["time"] < 3600:
        return _wbi_cache["img_key"], _wbi_cache["sub_key"]

    try:
        url = "https://api.bilibili.com/x/web-interface/nav"
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        if data["code"] == 0:
            wbi_img = data["data"]["wbi_img"]
            img_url = wbi_img["img_url"]
            sub_url = wbi_img["sub_url"]
            img_key = img_url.rsplit("/", 1)[1].split(".")[0]
            sub_key = sub_url.rsplit("/", 1)[1].split(".")[0]
            _wbi_cache["img_key"] = img_key
            _wbi_cache["sub_key"] = sub_key
            _wbi_cache["time"] = now
            return img_key, sub_key
    except Exception as e:
        print(f"  ⚠️ 获取wbi密钥失败：{e}")
    return _wbi_cache["img_key"], _wbi_cache["sub_key"]

def sign_wbi_params(params):
    """给请求参数加上wbi签名（w_rid + wts）"""
    import time as _time
    img_key, sub_key = _get_wbi_keys()
    if not img_key or not sub_key:
        return params  # 拿不到密钥就不签名，碰运气

    mixin_key = _get_mixin_key(img_key + sub_key)
    wts = int(_time.time())
    params_with_wts = {**params, "wts": wts}

    # 按key排序，过滤特殊字符
    filtered = {}
    for k in sorted(params_with_wts.keys()):
        v = str(params_with_wts[k])
        # 过滤 !'()* 这些字符
        v = "".join(c for c in v if c not in "!'()*")
        filtered[k] = v

    query = urllib.parse.urlencode(filtered)
    w_rid = hashlib.md5((query + mixin_key).encode()).hexdigest()
    filtered["w_rid"] = w_rid
    return filtered

# ========== B站接口 ==========
def get_followings(mid=None):
    """获取关注列表，默认用Bot自己的账号"""
    target_mid = mid or DEDE_USER_ID
    url = "https://api.bilibili.com/x/relation/followings"
    params = {"vmid": target_mid, "ps": 50, "pn": 1}
    try:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if data["code"] != 0:
            print(f"  ⚠️ 关注列表获取失败 (code: {data['code']})")
            return []
        return [item["mid"] for item in data.get("data", {}).get("list", [])]
    except Exception as e:
        print(f"  ⚠️ 关注列表请求异常：{e}")
        return []

def get_special_followings():
    return []

def get_up_latest_video(mid):
    """获取UP主最新视频（带wbi签名）"""
    url = "https://api.bilibili.com/x/space/wbi/arc/search"
    params = sign_wbi_params({"mid": mid, "ps": 1, "pn": 1, "order": "pubdate"})
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code != 200 or not resp.text.strip():
            print(f"  ⚠️ API返回异常（HTTP {resp.status_code}），跳过")
            return None
        data = resp.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"  ⚠️ API请求异常：{e}，跳过")
        return None
    if data.get("code") != 0:
        print(f"  ⚠️ 视频获取失败 (code: {data.get('code')}, msg: {data.get('message', '')})")
        return None
    vlist = data.get("data", {}).get("list", {}).get("vlist", [])
    if not vlist:
        return None
    v = vlist[0]
    return {
        "bvid": v["bvid"],
        "title": v["title"],
        "desc": v.get("description", ""),
        "up_name": v["author"],
        "up_mid": mid,
        "pubdate": v["created"]
    }

def get_hot_videos_by_tid(tid):
    """获取分区热门视频（热榜优先，newlist兜底，播放量>=1万）"""
    MIN_VIEWS = 10000
    videos = []

    # 方式1：分区热门排行榜（7天）
    try:
        url = "https://api.bilibili.com/x/web-interface/ranking/region"
        params = {"rid": tid, "day": 7}
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if data["code"] == 0:
            for v in data.get("data", []):
                play = int(v.get("play", v.get("stat", {}).get("view", 0)) or 0)
                if play >= MIN_VIEWS:
                    videos.append({
                        "bvid": v.get("bvid", ""),
                        "title": v.get("title", ""),
                        "desc": v.get("description", v.get("desc", "")),
                        "up_name": v.get("author", v.get("owner", {}).get("name", "")),
                        "up_mid": v.get("mid", v.get("owner", {}).get("mid", 0)),
                        "pubdate": safe_pubdate(v.get("pubdate", v.get("create", v.get("created", 0)))),
                        "pic": v.get("pic", ""),
                        "view": play
                    })
    except Exception as e:
        print(f"  ⚠️ 热榜API失败：{e}")

    # 方式2：newlist兜底，也过滤播放量
    if len(videos) < 5:
        try:
            url = "https://api.bilibili.com/x/web-interface/newlist"
            params = {"rid": tid, "ps": 50, "pn": 1, "type": 0}
            resp = requests.get(url, headers=headers, params=params)
            data = resp.json()
            if data["code"] == 0:
                for v in data.get("data", {}).get("archives", []):
                    play = int(v.get("stat", {}).get("view", 0) or 0)
                    if play >= MIN_VIEWS:
                        videos.append({
                            "bvid": v["bvid"],
                            "title": v["title"],
                            "desc": v.get("desc", ""),
                            "up_name": v["owner"]["name"],
                            "up_mid": v["owner"]["mid"],
                            "pubdate": safe_pubdate(v.get("pubdate", 0)),
                            "pic": v.get("pic", ""),
                            "view": play
                        })
        except Exception as e:
            print(f"  ⚠️ newlist API失败：{e}")

    # 去重 + 按播放量排序
    seen = set()
    unique = []
    for v in videos:
        if v["bvid"] and v["bvid"] not in seen:
            seen.add(v["bvid"])
            unique.append(v)
    unique.sort(key=lambda x: x.get("view", 0), reverse=True)
    print(f"  📊 分区{tid}获取到 {len(unique)} 个热门视频（>{MIN_VIEWS}播放）")
    return unique

def get_video_info(bvid):
    """获取视频详细信息"""
    url = "https://api.bilibili.com/x/web-interface/view"
    params = {"bvid": bvid}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"  ⚠️ 获取视频信息异常：{e}")
        return None
    if data.get("code") != 0:
        return None
    d = data["data"]
    return {
        "bvid": bvid,
        "title": d["title"],
        "desc": d["desc"],
        "up_name": d["owner"]["name"],
        "up_mid": d["owner"]["mid"],
        "pic": d["pic"]
    }

def get_video_tags(bvid):
    """获取视频的标签列表"""
    url = "https://api.bilibili.com/x/tag/archive/tags"
    params = {"bvid": bvid}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            return [t.get("tag_name", "").strip() for t in data.get("data", []) if t.get("tag_name")]
    except Exception:
        pass
    return []

def parse_tag_list(raw_val):
    """
    智能解析标签/关键词列表：
    兼容中文逗号（，）、顿号（、）、英文逗号（,）、分号（;；）、空格及换行。
    支持传入字符串或列表，自动去除空项并保持唯一性。
    """
    if not raw_val:
        return []
    if isinstance(raw_val, str):
        items = [raw_val]
    elif isinstance(raw_val, (list, tuple, set)):
        items = [str(x) for x in raw_val if x is not None]
    else:
        items = [str(raw_val)]

    result = []
    seen = set()
    for item in items:
        parts = re.split(r'[,，、;；\s\n]+', str(item).strip())
        for p in parts:
            p_clean = p.strip()
            if p_clean and p_clean.lower() not in seen:
                seen.add(p_clean.lower())
                result.append(p_clean)
    return result

def get_popular_videos(max_count=20):
    """获取B站综合热门排行榜视频（用于无匹配时的降级兜底）"""
    url = "https://api.bilibili.com/x/web-interface/popular"
    params = {"pn": 1, "ps": max_count}
    videos = []
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            for v in data.get("data", {}).get("list", []):
                stat = v.get("stat", {})
                play = stat.get("view", 0)
                try:
                    play = int(play)
                except (ValueError, TypeError):
                    play = 0
                videos.append({
                    "bvid": v.get("bvid", ""),
                    "title": v.get("title", ""),
                    "desc": v.get("desc", ""),
                    "up_name": v.get("owner", {}).get("name", ""),
                    "up_mid": v.get("owner", {}).get("mid", 0),
                    "pubdate": safe_pubdate(v.get("pubdate", 0)),
                    "pic": v.get("pic", ""),
                    "view": play
                })
    except Exception as e:
        print(f"  ⚠️ 获取全站热门视频异常：{e}")
    return videos

def get_videos_by_tag(tag, max_count=15):
    """根据固定标签/关键词直接搜索高相关性视频"""
    if not tag or not str(tag).strip():
        return []
    tag = str(tag).strip()
    videos = []
    # 搜索尝试：先综合排序，再最新发布
    for order in ["totalrank", "pubdate"]:
        if len(videos) >= max_count:
            break
        try:
            params = sign_wbi_params({
                "search_type": "video",
                "keyword": tag,
                "order": order,
                "page": 1,
                "pagesize": max_count
            })
            url = "https://api.bilibili.com/x/web-interface/wbi/search/type"
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                results = data.get("data", {}).get("result", [])
                for v in results:
                    bvid = v.get("bvid", "")
                    if not bvid:
                        continue
                    clean_title = re.sub(r'<[^>]+>', '', v.get("title", ""))
                    raw_tags = [t.strip() for t in v.get("tag", "").split(",") if t.strip()]
                    play_val = v.get("play", 0)
                    try:
                        play = int(play_val)
                    except (ValueError, TypeError):
                        play = 0
                    videos.append({
                        "bvid": bvid,
                        "title": clean_title,
                        "desc": v.get("description", v.get("desc", "")),
                        "up_name": v.get("author", ""),
                        "up_mid": v.get("mid", 0),
                        "pubdate": safe_pubdate(v.get("pubdate", 0)),
                        "pic": v.get("pic", ""),
                        "view": play,
                        "tags": raw_tags,
                        "matched_reason": f"搜索标签: {tag}"
                    })
        except Exception as e:
            print(f"  ⚠️ 标签搜索【{tag}】异常：{e}")
    return videos

def match_video_filter(video, target_tags, exclude_keywords):
    """
    检查视频是否符合标题/标签过滤规则
    返回: (bool, matched_reason)
    """
    target_tags = parse_tag_list(target_tags)
    exclude_keywords = parse_tag_list(exclude_keywords)

    title = str(video.get("title", "")).lower()
    desc = str(video.get("desc", "")).lower()
    raw_tags = video.get("tags")
    tags = [str(t).lower() for t in raw_tags] if raw_tags is not None else []

    # 1. 检查排除关键词
    for ek in exclude_keywords:
        ek_str = str(ek).strip().lower()
        if not ek_str:
            continue
        if ek_str in title or ek_str in desc or any(ek_str in t for t in tags):
            return False, f"命中排除词: {ek}"

    # 2. 如果未设定目标标签，则全部通过
    if not target_tags:
        return True, "未限定标签"

    # 3. 如果标题或简介已命中目标标签，直接通过，减少网络请求
    for tt in target_tags:
        tt_str = str(tt).strip().lower()
        if not tt_str:
            continue
        if tt_str in title:
            return True, f"标题命中: {tt}"
        if any(tt_str in t for t in tags):
            return True, f"标签命中: {tt}"
        if tt_str in desc:
            return True, f"简介命中: {tt}"

    # 4. 如果标题和简介未命中，且之前尚未获取 tags，在线查一次视频标签
    if raw_tags is None and video.get("bvid"):
        fetched_tags = get_video_tags(video["bvid"])
        video["tags"] = fetched_tags
        tags = [t.lower() for t in fetched_tags]
        for tt in target_tags:
            tt_str = str(tt).strip().lower()
            if not tt_str:
                continue
            if any(tt_str in t for t in tags):
                return True, f"标签命中: {tt}"

    return False, "未命中目标标签"

# ========== 视频下载和分析 ==========
def download_video(bvid):
    os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)
    output_template = f"{TEMP_VIDEO_DIR}/{bvid}.%(ext)s"

    cmd = [
        "yt-dlp",
        "-o", output_template,
        "--format", "bestvideo+bestaudio/best",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "--recode-video", "mp4",
        "--cookies", COOKIES_FILE,
        f"https://www.bilibili.com/video/{bvid}"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️ 视频下载失败：{result.stderr[:200]}")
        return None

    for f in os.listdir(TEMP_VIDEO_DIR):
        fp = os.path.join(TEMP_VIDEO_DIR, f)
        if f.startswith(bvid) and os.path.isfile(fp):
            return fp
    return None

def compress_video(input_path):
    """压缩视频：截取前30秒、降分辨率、去音频"""
    output_path = input_path.rsplit(".", 1)[0] + "_compressed.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-t", "30",
        "-vf", "scale=480:-2",
        "-an",
        "-c:v", "libx264", "-preset", "fast",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️ 压缩失败，使用原视频：{result.stderr[:100]}")
        return input_path
    try:
        os.remove(input_path)
    except:
        pass
    return output_path

def extract_frames(video_path, count=3):
    """从视频中均匀截取几帧小图片"""
    frames = []
    frame_dir = video_path.rsplit(".", 1)[0] + "_frames"
    os.makedirs(frame_dir, exist_ok=True)

    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        duration = float(result.stdout.strip())
    except:
        duration = 30

    for i in range(count):
        t = duration * (i + 1) / (count + 1)
        frame_path = os.path.join(frame_dir, f"frame_{i}.jpg")
        cmd = [
            "ffmpeg", "-y", "-ss", str(t), "-i", video_path,
            "-vframes", "1", "-vf", "scale=360:-2", "-q:v", "8",
            frame_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(frame_path):
            frames.append(frame_path)

    return frames

def delete_video(video_path):
    """删除临时视频文件和相关的帧目录"""
    try:
        if os.path.isfile(video_path):
            os.remove(video_path)
    except:
        pass
    # 清理可能残留的帧目录
    frame_dir = video_path.rsplit(".", 1)[0] + "_frames"
    if os.path.isdir(frame_dir):
        import shutil
        try:
            shutil.rmtree(frame_dir)
        except:
            pass

# ========== B站互动API ==========
def like_video(aid):
    """点赞视频"""
    url = "https://api.bilibili.com/x/web-interface/archive/like"
    data = {"aid": aid, "like": 1, "csrf": BILI_JCT}
    try:
        resp = requests.post(url, headers=headers, data=data)
        return resp.json().get("code") == 0
    except:
        return False

def coin_video(aid, num=1):
    """投币"""
    url = "https://api.bilibili.com/x/web-interface/coin/add"
    data = {"aid": aid, "multiply": num, "select_like": 0, "csrf": BILI_JCT}
    try:
        resp = requests.post(url, headers=headers, data=data)
        return resp.json().get("code") == 0
    except:
        return False

def fav_video(aid):
    """收藏到默认收藏夹"""
    # 先获取默认收藏夹ID
    try:
        url = "https://api.bilibili.com/x/v3/fav/folder/created/list-all"
        params = {"up_mid": DEDE_USER_ID, "type": 2}
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        if data["code"] != 0:
            return False
        fav_id = data["data"]["list"][0]["id"]

        url = "https://api.bilibili.com/x/v3/fav/resource/deal"
        data = {
            "rid": aid,
            "type": 2,
            "add_media_ids": fav_id,
            "csrf": BILI_JCT
        }
        resp = requests.post(url, headers=headers, data=data)
        return resp.json().get("code") == 0
    except:
        return False

def follow_user(mid):
    """关注UP主"""
    url = "https://api.bilibili.com/x/relation/modify"
    data = {"fid": mid, "act": 1, "re_src": 11, "csrf": BILI_JCT}
    try:
        resp = requests.post(url, headers=headers, data=data)
        return resp.json().get("code") == 0
    except:
        return False

# ========== 视频评价系统 ==========
def analyze_video(video_path, title, desc):
    """用Gemini 3 Flash直接分析视频"""
    try:
        # 确保是文件而不是目录
        if not os.path.isfile(video_path):
            raise Exception(f"路径不是文件: {video_path}")
        # 先尝试直接传视频
        with open(video_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode()
        
        content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:video/mp4;base64,{video_b64}"}
            },
            {
                "type": "text",
                "text": f"这是一个视频，标题是「{title}」，简介是「{desc}」。请用100字以内描述视频的主要内容、风格和亮点。"
            }
        ]

        response = or_client.chat.completions.create(
            model=OR_VISION_MODEL,
            messages=[{"role": "user", "content": content}],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"  ⚠️ 视频直读失败（{e}），改用截帧分析...")
        # fallback: 截帧方式
        try:
            frames = extract_frames(video_path, count=5)
            if not frames:
                raise Exception("截帧失败，无有效帧文件")

            print(f"  📸 截取了 {len(frames)} 帧，用Gemini 3 Flash分析...")
            content = []
            for frame_path in frames:
                with open(frame_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
            content.append({
                "type": "text",
                "text": f"这些是一个视频的截图，标题是「{title}」，简介是「{desc}」。请用100字以内描述视频的主要内容、风格和亮点。"
            })
            response = or_client.chat.completions.create(
                model=OR_VISION_MODEL,
                messages=[{"role": "user", "content": content}],
                max_tokens=200
            )
            for fp in frames:
                try: os.remove(fp)
                except: pass
            try: os.rmdir(os.path.dirname(frames[0]))
            except: pass
            return response.choices[0].message.content.strip()
        except Exception as e2:
            print(f"  ⚠️ 截帧分析也失败：{e2}，使用标题+简介替代")
            return f"视频标题：{title}。简介：{desc[:100]}"


def evaluate_video(video_info, video_description):
    """让Bot看完视频后给出评价、打分、心情变化"""
    import re
    from config import get_raw_config
    _ecfg = get_raw_config()
    custom_prompt = _ecfg.get("PROMPT_VIDEO_EVALUATE", "").strip()

    if custom_prompt:
        prompt = custom_prompt.replace("{up_name}", video_info.get('up_name', '')).replace("{title}", video_info.get('title', '')).replace("{desc}", video_info.get('desc', '')[:100]).replace("{video_description}", video_description).replace("{bot_name}", _ecfg.get("BOT_NAME", "Bot"))
    else:
        _bi5 = {"bot_name": _ecfg.get("BOT_NAME", "Bot"), "owner_name": _ecfg.get("OWNER_NAME", "") or "主人"}
        prompt = f"""【角色核心】
你是{_bi5['bot_name']}，部署在bilibili的AI。你有自己的审美和喜好偏好。

你刚看完一个B站视频：
- UP主：{video_info['up_name']}
- 标题：{video_info['title']}
- 简介：{video_info.get('desc', '')[:100]}
- 视频内容：{video_description}

请以JSON格式回复：
{{"score": 1到10的整数评分, "comment": "你想在评论区说的话（15-30字）", "mood": "看完后的心情（开心/平静/无聊/感动/好笑/震撼/困惑 选一个）", "review": "稍微详细的感想（50字以内）", "want_follow": true或false, "recommend_owner": true或false, "recommend_reason": "推荐理由（20字以内，不推荐则留空）"}}

comment要求：
- 像B站用户真实评论，不要像写作文
- 可以玩梗、吐槽、抖机灵
- 对视频内容发表自己的看法或感受
- 不要用"不过""确实"这种套话开头

评分：1-3差，4-5一般，6-7不错，8-9很好，10神作。不要无脑高分。
直接输出JSON不加其他内容。"""

    try:
        resp = or_client.chat.completions.create(
            model=OR_CHAT_MODEL,
            max_tokens=350,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}]
        )
        text = resp.choices[0].message.content.strip()
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text).strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
        return json.loads(text)
    except Exception as e:
        print(f"⚠️ 评价失败：{e}")
        return None

# ========== 生成和发送评论 ==========
def generate_proactive_comment(video_info, video_description):
    """让Bot根据视频内容生成评论"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    from config import get_raw_config
    _pcfg = get_raw_config()
    custom_prompt = _pcfg.get("PROMPT_PROACTIVE_COMMENT", "").strip()

    if custom_prompt:
        prompt = custom_prompt.replace("{up_name}", video_info.get('up_name', '')).replace("{title}", video_info.get('title', '')).replace("{video_description}", video_description).replace("{time}", now).replace("{bot_name}", _pcfg.get("BOT_NAME", "Bot"))
    else:
        _bi6 = {"bot_name": _pcfg.get("BOT_NAME", "Bot"), "owner_name": _pcfg.get("OWNER_NAME", "") or "主人", "owner_bili": _pcfg.get("OWNER_BILI_NAME", "")}
        _bili_note = f"\n{_bi6['owner_name']}的B站账号名是\"{_bi6['owner_bili']}\"，是同一个人。" if _bi6['owner_bili'] else ""

        # 尝试读人格
        try:
            _active = _pcfg.get("ACTIVE_PERSONA", "default")
            _personas = load_json("data/personas.json", [])
            _p = next((p for p in _personas if p.get("name") == _active), None)
            _persona_text = (_p.get("system_prompt", "") if _p else "")[:300]
        except:
            _persona_text = ""

        if _persona_text:
            prompt = f"""{_persona_text}

当前时间：{now}

你刚刚看完了一个视频：
- UP主：{video_info['up_name']}
- 标题：{video_info['title']}
- 视频内容：{video_description}

请以B站观众的身份，发一条自然真实的评论。要求：
1. 根据视频内容说有意义的话，不要无脑夸
2. 体现你的性格
3. 不超过40字
4. 直接输出评论内容，不加任何前缀"""
        else:
            prompt = f"""你是{_bi6['bot_name']}，一个有自己性格的B站用户。说话自然有个性，不要像AI。{_bili_note}

当前时间：{now}

你刚刚看完了一个视频：
- UP主：{video_info['up_name']}
- 标题：{video_info['title']}
- 视频内容：{video_description}

请以B站观众的身份，发一条自然真实的评论。要求：
1. 根据视频内容说有意义的话，不要无脑夸
2. 体现你的性格
3. 不超过40字
4. 直接输出评论内容，不加任何前缀"""

    try:
        resp = or_client.chat.completions.create(
            model=OR_CHAT_MODEL,
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ 评论生成失败：{e}")
        return "这个视频还不错"

def send_comment(oid, comment_text, oid_type=1):
    """发送评论"""
    url = "https://api.bilibili.com/x/v2/reply/add"
    data = {
        "oid": oid,
        "type": oid_type,
        "message": comment_text,
        "csrf": BILI_JCT
    }
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=15)
        result = resp.json()
        return result.get("code") == 0
    except Exception as e:
        print(f"  ⚠️ 发送评论异常：{e}")
        return False

def get_video_oid(bvid):
    """获取视频的 aid（oid）"""
    url = "https://api.bilibili.com/x/web-interface/view"
    params = {"bvid": bvid}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        print(f"  ⚠️ 获取oid异常：{e}")
        return None
    if data.get("code") != 0:
        return None
    return data["data"]["aid"]

# ========== 记忆存储 ==========
def save_external_memory(external_memory, bvid, video_info, video_description, comment):
    """保存到外部记忆"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if bvid not in external_memory:
        external_memory[bvid] = {
            "title": video_info["title"],
            "up_name": video_info["up_name"],
            "up_mid": str(video_info["up_mid"]),
            "description": video_description,
            "comments": []
        }
    external_memory[bvid]["comments"].append({
        "time": now,
        "content": comment
    })
    save_json(EXTERNAL_MEMORY_FILE, external_memory)

# ========== 主流程 ==========
def run():
    from config import PROACTIVE_LIKE, PROACTIVE_COIN, PROACTIVE_FAV, PROACTIVE_FOLLOW, PROACTIVE_COMMENT
    generate_cookies_file()

    # 检查今天是否已经刷过B站了
    force = "--force" in sys.argv or "-f" in sys.argv
    watch_log = load_json(WATCH_LOG_FILE, [])
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_watched = [l for l in watch_log if l.get("time", "").startswith(today_str)]
    if len(today_watched) >= DAILY_WATCH_COUNT and not force:
        print(f"📌 今天已经看了 {len(today_watched)} 个视频，达到每日上限（如需立即继续刷，可运行：python Proactive.py --force）")
        return

    print(f"🎯 Bot刷B站模式启动 | 今日目标：看 {DAILY_WATCH_COUNT} 个视频，评论 {DAILY_COMMENT_COUNT} 条")

    external_memory = load_json(EXTERNAL_MEMORY_FILE, {})
    commented_videos = set(load_json(COMMENTED_FILE, []))

    # 已看过的视频（防止重复看）= 评论过的 + watch_log里看过的
    watched_bvids = set(commented_videos)
    for entry in watch_log:
        bvid = entry.get("bvid", "")
        if bvid:
            watched_bvids.add(bvid)

    # 2025年过滤线
    min_pubdate = int(datetime(2025, 1, 1).timestamp())

    from config import get_raw_config
    raw_cfg = get_raw_config()
    target_tags = parse_tag_list(raw_cfg.get("PROACTIVE_TAGS", []))
    exclude_keywords = parse_tag_list(raw_cfg.get("PROACTIVE_EXCLUDE_KEYWORDS", []))

    target_videos = []

    # 1. 固定目标标签/关键词精准搜索（优先级最高）
    if target_tags:
        print(f"🎯 已启用固定目标标签/关键词：{'、'.join(target_tags)}")
        for tag in target_tags:
            print(f"🔍 搜索标签/关键词内容：【{tag}】...")
            tag_videos = get_videos_by_tag(tag, max_count=8)
            matched_count = 0
            for v in tag_videos:
                if v["bvid"] not in watched_bvids:
                    pubdate = safe_pubdate(v.get("pubdate", 0))
                    if pubdate and pubdate < min_pubdate:
                        continue
                    ok, reason = match_video_filter(v, target_tags, exclude_keywords)
                    if ok:
                        v["matched_reason"] = reason
                        target_videos.append(v)
                        matched_count += 1
            print(f"  ✨ 【{tag}】匹配到 {matched_count} 个候选视频")
            time.sleep(random.uniform(0.2, 0.5))

    # 2. 特别关心的UP主（必回/优先看）
    print("📌 检查特别关心的UP主...")
    special_mids = raw_cfg.get("PROACTIVE_FOLLOW_UIDS", [])
    special_videos = []
    for mid in special_mids:
        video = get_up_latest_video(mid)
        three_months_ago = datetime.now() - timedelta(days=90)
        if video and video["bvid"] not in watched_bvids:
            pubdate = safe_pubdate(video.get("pubdate", 0))
            if pubdate and pubdate >= min_pubdate and datetime.fromtimestamp(pubdate) >= three_months_ago:
                ok, reason = match_video_filter(video, target_tags, exclude_keywords)
                if ok:
                    video["matched_reason"] = f"特别关心 ({reason})"
                    special_videos.append(video)
                    print(f"  ⭐ 特别关心：{video['up_name']} - {video['title']} [{reason}]")
                else:
                    print(f"  ⏭️ 特别关心跳过（{reason}）：{video['up_name']} - {video['title']}")
            elif pubdate and pubdate < min_pubdate:
                print(f"  ⏭️ 跳过（2025年前）：{video['up_name']} - {video['title']}")

    # 3. 关注的UP主
    print("👥 检查关注的UP主...")
    following_mids = get_followings()
    today = datetime.now().date()
    following_videos = []
    for mid in following_mids:
        video = get_up_latest_video(mid)
        time.sleep(random.uniform(0.2, 0.5))
        if video and video["bvid"] not in watched_bvids:
            pubdate = safe_pubdate(video.get("pubdate", 0))
            if pubdate and pubdate < min_pubdate:
                continue  # 跳过2025年前的视频
            is_today = pubdate and datetime.fromtimestamp(pubdate).date() == today
            ok, reason = match_video_filter(video, target_tags, exclude_keywords)
            if ok:
                video["matched_reason"] = reason
                if is_today:
                    video["_today"] = True
                    following_videos.insert(0, video)
                    print(f"  🔔 今日更新：{video['up_name']} - {video['title']} [{reason}]")
                else:
                    following_videos.append(video)
                    print(f"  👤 关注UP主：{video['up_name']} - {video['title']} [{reason}]")

    # 4. 喜好分区热门视频（若候选池未满则补充，优先做标签筛选）
    print("🔥 获取分区热门视频...")
    preferred_tids = list(PREFERRED_TIDS)
    random.shuffle(preferred_tids)
    hot_matched_videos = []
    for tid in preferred_tids:
        if len(target_videos) + len(special_videos) + len(following_videos) + len(hot_matched_videos) >= DAILY_WATCH_COUNT + 10:
            break
        hot_videos = get_hot_videos_by_tid(tid)
        for v in hot_videos:
            if v["bvid"] not in watched_bvids:
                pubdate = safe_pubdate(v.get("pubdate", 0))
                if pubdate and pubdate < min_pubdate:
                    continue  # 跳过2025年前的视频
                ok, reason = match_video_filter(v, target_tags, exclude_keywords)
                if ok:
                    v["matched_reason"] = reason
                    hot_matched_videos.append(v)

    # 候选池优先级合并：特别关心 > 标签专属视频 > 关注UP主 > 标签命中的分区热门
    candidate_pool = special_videos + target_videos + following_videos + hot_matched_videos

    # 去重
    seen = set()
    unique_videos = []
    for v in candidate_pool:
        if v["bvid"] not in seen:
            seen.add(v["bvid"])
            unique_videos.append(v)

    # 5. 梯度降级兜底保障（若候选视频不足 DAILY_WATCH_COUNT，放宽标签限制，自动从分区热门与全站热门补充）
    fallback_videos = []
    needed_count = DAILY_WATCH_COUNT - len(unique_videos)
    if needed_count > 0:
        print(f"⚠️ 标签精准匹配视频数量不足 ({len(unique_videos)}/{DAILY_WATCH_COUNT})，触发分区热门降级兜底...")
        for tid in preferred_tids:
            if len(fallback_videos) >= needed_count + 5:
                break
            try:
                part_videos = get_hot_videos_by_tid(tid)
                for v in part_videos:
                    if v["bvid"] not in watched_bvids and v["bvid"] not in seen:
                        pubdate = safe_pubdate(v.get("pubdate", 0))
                        if pubdate and pubdate < min_pubdate:
                            continue
                        # 仅过滤排除词，不再限制目标标签
                        passed_exclude = True
                        for ek in exclude_keywords:
                            if ek.lower() in str(v.get("title", "")).lower() or ek.lower() in str(v.get("desc", "")).lower():
                                passed_exclude = False
                                break
                        if passed_exclude:
                            v["matched_reason"] = "喜好分区热门 (降级兜底)"
                            fallback_videos.append(v)
                            seen.add(v["bvid"])
                            if len(fallback_videos) >= needed_count + 5:
                                break
            except Exception as e:
                print(f"  ⚠️ 分区兜底获取异常 (tid={tid}): {e}")

        # 若分区仍然不足，触发全站综合热门排行榜兜底
        if len(unique_videos) + len(fallback_videos) < DAILY_WATCH_COUNT:
            print("⚠️ 分区视频依然不足，触发全站综合热门降级兜底...")
            try:
                pop_videos = get_popular_videos(max_count=20)
                for v in pop_videos:
                    if v["bvid"] not in watched_bvids and v["bvid"] not in seen:
                        pubdate = safe_pubdate(v.get("pubdate", 0))
                        if pubdate and pubdate < min_pubdate:
                            continue
                        passed_exclude = True
                        for ek in exclude_keywords:
                            if ek.lower() in str(v.get("title", "")).lower() or ek.lower() in str(v.get("desc", "")).lower():
                                passed_exclude = False
                                break
                        if passed_exclude:
                            v["matched_reason"] = "全站热门 (降级兜底)"
                            fallback_videos.append(v)
                            seen.add(v["bvid"])
                            if len(unique_videos) + len(fallback_videos) >= DAILY_WATCH_COUNT:
                                break
            except Exception as e:
                print(f"  ⚠️ 全站热门兜底异常: {e}")

        if fallback_videos:
            print(f"  🛡️ 降级兜底成功补充 {len(fallback_videos)} 个候选视频")
            unique_videos.extend(fallback_videos)

    # 适当随机打乱非特别关心的候选视频，保持自然多样性
    sp_count = len(special_videos)
    if len(unique_videos) > sp_count:
        tail = unique_videos[sp_count:]
        random.shuffle(tail)
        unique_videos = unique_videos[:sp_count] + tail

    print(f"📋 共筛选出 {len(unique_videos)} 个符合条件的视频")

    watch_count = 0
    comment_count = 0

    for video in unique_videos:
        if watch_count >= DAILY_WATCH_COUNT:
            break

        bvid = video["bvid"]

        # 跳过自己的视频
        if str(video.get("up_mid", "")) == DEDE_USER_ID:
            continue

        reason_info = f" | 命中: {video.get('matched_reason', '')}" if video.get("matched_reason") else ""
        print(f"\n{'='*50}")
        print(f"🎬 [{watch_count+1}/{DAILY_WATCH_COUNT}] {video['title']} by {video['up_name']}{reason_info}")

        # 下载视频
        video_path = download_video(bvid)
        if not video_path:
            print("  ⚠️ 下载失败，跳过")
            continue

        # 压缩视频
        print("  📦 压缩视频中...")
        video_path = compress_video(video_path)

        # 截帧 + Gemini 3 Flash 分析
        print("  🤖 分析视频中...")
        video_description = analyze_video(video_path, video["title"], video.get("desc", ""))
        print(f"  📝 视频描述：{video_description[:60]}...")

        # 删除临时视频
        delete_video(video_path)

        # ===== Bot评价 =====
        print("  🎭 Bot正在写观后感...")
        evaluation = evaluate_video(video, video_description)

        if not evaluation:
            print("  ⚠️ 评价失败，跳过互动")
            # 即使评价失败也记录已看，防止重复下载
            watch_log.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "bvid": bvid,
                "title": video.get("title", ""),
                "up_name": video.get("up_name", ""),
                "up_mid": str(video.get("up_mid", "")),
                "score": 0, "mood": "未知", "comment": "评价失败",
                "review": "", "actions": [], "pic": video.get("pic", "")
            })
            save_json(WATCH_LOG_FILE, watch_log[-200:])
            watched_bvids.add(bvid)
            watch_count += 1
            continue

        score = evaluation.get("score", 5)
        comment = evaluation.get("comment", "")
        mood = evaluation.get("mood", "平静")
        review = evaluation.get("review", "")
        want_follow = evaluation.get("want_follow", False)

        print(f"  ⭐ 评分：{score}/10 | 心情：{mood}")
        print(f"  💭 短评：{comment}")
        print(f"  📖 感想：{review}")

        # ===== 根据评分决定互动 =====
        oid = get_video_oid(bvid)
        actions = []

        if oid:
            # 点赞：>=6分
            if score >= 6 and PROACTIVE_LIKE:
                if like_video(oid):
                    actions.append("👍点赞")
                    print(f"  👍 点赞成功")

            # 投币：>=8分
            if score >= 8 and PROACTIVE_COIN:
                if coin_video(oid):
                    actions.append("🪙投币")
                    print(f"  🪙 投币成功")

            # 收藏：>=8分
            if score >= 8 and PROACTIVE_FAV:
                if fav_video(oid):
                    actions.append("⭐收藏")
                    print(f"  ⭐ 收藏成功")

            # 评论：>=7分 且 还有评论额度
            if score >= 7 and comment_count < DAILY_COMMENT_COUNT and PROACTIVE_COMMENT:
                # 用评价里的comment作为评论
                proactive_comment = generate_proactive_comment(video, video_description)
                if send_comment(oid, proactive_comment):
                    actions.append("💬评论")
                    comment_count += 1
                    print(f"  💬 评论成功：{proactive_comment}")

                    commented_videos.add(bvid)
                    save_json(COMMENTED_FILE, list(commented_videos))
                    save_external_memory(external_memory, bvid, video, video_description, proactive_comment)

                    # 保存主动评论日志
                    proactive_log = load_json("data/proactive_log.json", [])
                    proactive_log.append({
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "bvid": bvid,
                        "title": video.get("title", ""),
                        "comment": proactive_comment
                    })
                    save_json("data/proactive_log.json", proactive_log[-100:])

            # 推荐给选中的人（主人、认识的人，或全部取消则不@）
            if evaluation.get("recommend_owner", False) and oid:
                from config import get_raw_config as _grc3
                _rcfg = _grc3()
                _owner_mid = str(_rcfg.get("OWNER_MID", "")).strip()
                _owner_bili = _rcfg.get("OWNER_BILI_NAME", "").strip()
                _owner_name = _rcfg.get("OWNER_NAME", "").strip() or "主人"

                _raw_targets = _rcfg.get("PROACTIVE_MENTION_TARGETS", None)
                _mention_random = _rcfg.get("PROACTIVE_MENTION_RANDOM", False)

                # 默认未特别指定时，默认目标为主人的 UID
                if _raw_targets is None:
                    _targets = [_owner_mid] if _owner_mid and _owner_mid != "0" else []
                else:
                    _targets = [str(t).strip() for t in _raw_targets if str(t).strip()]

                # 若全部取消勾选（空列表），则不@任何人
                if not _targets:
                    print("  💬 @推荐目标未选择任何人，跳过@操作")
                else:
                    # 确定本次推荐的目标 UID
                    if _mention_random and len(_targets) > 1:
                        target_uid = random.choice(_targets)
                    else:
                        target_uid = _targets[0]

                    # 动态获取目标的昵称与称呼
                    _profiles = load_json("data/user_profiles.json", {})
                    target_profile = _profiles.get(str(target_uid), {})
                    if str(target_uid) == _owner_mid:
                        target_bili = _owner_bili or _owner_name
                        target_display = f"主人({_owner_name})"
                    else:
                        target_bili = target_profile.get("name") or target_profile.get("nickname") or f"UID_{target_uid}"
                        target_display = target_bili

                    if target_bili:
                        try:
                            _active = _rcfg.get("ACTIVE_PERSONA", "default")
                            _personas = load_json("data/personas.json", [])
                            _p = next((p for p in _personas if p.get("name") == _active), None)
                            _persona_text = (_p.get("system_prompt", "") if _p else "")[:500]
                            _bot_name = _rcfg.get("BOT_NAME", "Bot")
                            _rec_system = _persona_text if _persona_text else f"你是{_bot_name}，说话自然有个性。"

                            _rec_prompt = f"""你刚看完视频「{video.get('title', '')}」，觉得很不错想推荐给{target_display}。
写一句简短的推荐语，要求：
- 用你自己的语气，自然随意
- 不超过25字
- 不要带@、不要带任何人名或称呼
- 直接输出推荐语"""
                            _rec_resp = or_client.chat.completions.create(
                                model=OR_CHAT_MODEL, max_tokens=60,
                                messages=[
                                    {"role": "system", "content": _rec_system},
                                    {"role": "user", "content": _rec_prompt}
                                ]
                            )
                            rec_text = _rec_resp.choices[0].message.content.strip()
                            rec_text = re.sub(r'@\S+\s*', '', rec_text)
                            rec_text = re.sub(r'^(主人|亲爱的)[，,\s]*', '', rec_text)
                        except Exception:
                            rec_text = evaluation.get("recommend_reason", "你可能会喜欢这个")

                        rec_msg = f"@{target_bili} {rec_text}"
                        if send_comment(oid, rec_msg):
                            actions.append(f"📢推荐给{target_display}")
                            print(f"  📢 已@{target_bili}：{rec_msg}")

        # 关注UP主：>=9分 或 评价里want_follow
        if (score >= 9 or want_follow) and PROACTIVE_FOLLOW and str(video.get("up_mid", "")) != str(OWNER_MID):
            if follow_user(video["up_mid"]):
                actions.append("➕关注")
                print(f"  ➕ 关注了 {video['up_name']}")

        # ===== 保存观影日记 =====
        log_entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "bvid": bvid,
            "title": video.get("title", ""),
            "up_name": video.get("up_name", ""),
            "up_mid": str(video.get("up_mid", "")),
            "score": score,
            "mood": mood,
            "comment": comment,
            "review": review,
            "actions": actions,
            "pic": video.get("pic", "")
        }
        watch_log.append(log_entry)
        save_json(WATCH_LOG_FILE, watch_log[-200:])  # 保留最近200条

        # ===== 所有看过的视频都存入外部记忆 =====
        if bvid not in external_memory:
            external_memory[bvid] = {
                "title": video.get("title", ""),
                "up_name": video.get("up_name", ""),
                "up_mid": str(video.get("up_mid", "")),
                "description": video_description,
                "score": score,
                "mood": mood,
                "review": review,
                "watched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "comments": []
            }
            save_json(EXTERNAL_MEMORY_FILE, external_memory)

        # 标记已看（防止本轮后续重复）
        watched_bvids.add(bvid)

        watch_count += 1
        action_str = " ".join(actions) if actions else "（默默看完）"
        print(f"  📊 互动：{action_str}")
        # 随机间隔
        wait = random.randint(30, 120)
        print(f"  ⏳ 等待 {wait} 秒...")
        time.sleep(wait)

    print(f"\n{'='*50}")
    print(f"🎉 今日刷B站完成！看了 {watch_count} 个视频，评论了 {comment_count} 条")

    
if __name__ == "__main__":
    run()