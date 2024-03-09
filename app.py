import os
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests
from flask import Flask, request, redirect
import oss2
import shutil  # 用于操作临时文件和目录
import threading

# 配置信息
ACCESS_KEY_ID = os.getenv("ACCESS_KEY_ID", "your-access-key-id")
ACCESS_KEY_SECRET = os.getenv("ACCESS_KEY_SECRET", "your-access-key-secret")
ENDPOINT = os.getenv("ENDPOINT", "your-oss-endpoint")
CDN = os.getenv("CDN", "your-cdn")
BUCKET_NAME = os.getenv("BUCKET_NAME", "your-bucket-name")
BUCKET = oss2.Bucket(oss2.Auth(ACCESS_KEY_ID, ACCESS_KEY_SECRET), ENDPOINT, BUCKET_NAME)
TMP_DIR = "./tmp"  # 临时目录路径

# 确保临时目录存在
if not os.path.exists(TMP_DIR):
    os.makedirs(TMP_DIR)

# 数据库初始化
DB_FILE = "./data/sqlite.db"


def init_db():
    if not os.path.exists("./data"):
        os.makedirs("./data")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS history
                     (original_url TEXT PRIMARY KEY,
                      cached_url TEXT,
                      cache_time TIMESTAMP)"""
    )
    conn.commit()
    conn.close()


init_db()

# 缓存进行中的文件列表
caching_tasks = {}

app = Flask(__name__)


@app.route("/")
@app.route("/list")
def list_cached_images():
    offset = int(request.args.get("offset", 0))
    limit = int(request.args.get("limit", 50))

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT original_url, cached_url, cache_time FROM history ORDER BY cache_time DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    records = cursor.fetchall()

    cached_images = []
    for record in records:
        original_url, cached_url, cache_time = record
        cached_images.append(
            {
                "original_url": original_url,
                "cached_url": cached_url,
                "cache_time": cache_time,
            }
        )

    total_count = cursor.execute("SELECT COUNT(*) FROM history").fetchone()[0]

    return {"items": cached_images, "total": total_count}


@app.route("/o")
def redirect_image():
    original_url = request.args.get("url")
    plus_url = request.args.get("plus")
    print("try " + original_url)
    if not original_url:
        return "Missing url parameter", 400

    # 从数据库检查是否存在缓存记录
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT cached_url, cache_time FROM history WHERE original_url = ?",
        (original_url,),
    )
    record = cursor.fetchone()

    if record:
        cached_url, cache_time = record
        print("to " + cached_url + "?x-oss-process=image/resize,m_fill," + plus_url)
        return redirect(cached_url + "?x-oss-process=image/resize,m_fill," + plus_url)

    # 检查是否存在进行中的缓存任务
    if original_url in caching_tasks and datetime.now() - caching_tasks[
        original_url
    ] < timedelta(minutes=3):
        return redirect(original_url)
    
    # 发起后台缓存任务
    async_cache_image(original_url)

    return redirect(original_url)

def async_cache_image(original_url):
    t = threading.Thread(target=cache_image, args=(original_url,))
    t.start()

def download_image_to_tmp(url):
    """下载图片到临时目录"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            file_path = os.path.join(TMP_DIR, urlparse(url).path.split("/")[-1])
            with open(file_path, "wb") as f:
                shutil.copyfileobj(response.raw, f)
            return file_path
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
    return None 

def cache_image(original_url):
    caching_tasks[original_url] = datetime.now()
    tmp_file_path = download_image_to_tmp(original_url)
    if tmp_file_path:
        try:
            oss_path = "cache/" + urlparse(original_url).path.lstrip("/")
            with open(tmp_file_path, "rb") as f:
                BUCKET.put_object(oss_path, f)
                cached_url = f"{CDN}/{oss_path}"
                print("cached " + cached_url)
                with sqlite3.connect(DB_FILE) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO history (original_url, cached_url, cache_time) VALUES (?, ?, ?)",
                        (
                            original_url,
                            cached_url,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    conn.commit()
        except Exception as e:
            print(f"Error caching image {original_url}: {e}")
        finally:
            os.remove(tmp_file_path)  # 删除临时文件
            del caching_tasks[original_url]


if __name__ == "__main__":
    app.run(host="0.0.0.0")
