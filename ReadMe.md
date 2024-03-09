# 提示词工程师的一天：让AI编写一个图片CDN分发器



本文创作于 [OPENAI GPT4](https://twoapi-ui.qiangtu.com/chat/base/13/11) | 图片绘制 [Midjourney](https://twoapi-ui.qiangtu.com/log/draw/mj) | 编撰 [Odin](https://odin.mblog.club/)



我们的[AI 演示站点](https://twoapi-ui.qiangtu.com/chat/base/0/99)中有很多画的美美的[AI创作成品](https://twoapi-ui.qiangtu.com/log/draw/mj)，但是总是因为加载速度慢，文件太大太多等问题让查看的体验变得很差，今天是周六了，要不我们今天就行动起来，扮演一个提示词工程师，让AI来创作一个小程序，解决这个问题。

解决当前问题的思路是，减少图片大小、使用CDN进行加速；这个时候阿里云的OSS其实就是一个不错的选择，除开价格贵点之外，其他都是优点。 想下我的图片一共也没多少，应该花不了多少钱，就这么办吧。

让我们开动，编写提示词，让AI给我们编码！顺便也让大家了解一下，提示词工程师是如何写程序的，以及在这种水平的提示词编写能力要求下，你是否能够轻松胜任。



## 一、编写Prompts:

### 核心配置信息：

- 阿里云OSS的相关配置信息 ( 可以被环境变量覆盖 )
- 阿里云OSS配置信息

```
ACCESS_KEY_ID = os.getenv('ACCESS_KEY_ID', 'your-access-key-id')
ACCESS_KEY_SECRET = os.getenv('ACCESS_KEY_SECRET', 'your-access-key-secret')
ENDPOINT = os.getenv('ENDPOINT', 'your-oss-endpoint')
CDN = os.getenv('CDN', 'your-cdn')
BUCKET_NAME = os.getenv('BUCKET_NAME', 'your-bucket-name')
```



### 主要解决问题

- 部分网络图片加载速度过慢，在我的网页上直接链接这些图片会导致网页卡顿



### 解决方案

- 在所有的图片链接上加一个分发器
- （原图片地址） http://a.com/1.jpg 
- 修改后的图片地址 http://分发器.com/o?url=http://a.com/1.jpg
  - 新的（缓存后的AliyunOSS中的图片地址）会作为img 的 src 添加到网页中
  - 分发器.com 会做一个简单的逻辑判断
    - 已缓存 -> 跳转缓存后的文件地址
    - 未缓存 -> 跳转原始地址



### 需要实现的内容

- 语言采用Python

- 对象定义：

  - （原图片地址）：作为参数传入的原始图片地址
  - （缓存后的AliyunOSS中的图片地址）：缓存后的AliyunOSS中的图片地址
    - AliyunOSS 中的存储路径定义  cache/{原图片地址去掉https:// 和 http:// 的其他部分}
  - （缓存时间）： 缓存任务发起的时间

- 数据库采用sqlite  `./data/sqlite.db` 

  - 检查数据库文件和目录是否存在，不存在则创建，并初始化数据库
  - 在数据库中创建 history 表，用于存储 （原图片地址），（缓存后的AliyunOSS中的图片地址），（缓存时间）

- 文件存放到 Aliyun OSS , 配置信息在文件头部预定义，可以被覆盖未缓存变量中传入的值

- 编写这样的分发器

  - 定义一个变量，用于存储 （缓存进行中的文件列表），包含（原图片地址）和（缓存时间）

  - 提供接口 / 和 /list ，支持 offset 和 limit 参数用于翻页，用时间倒序排列列表，功能是用于以json的格式返回当前已缓存的文件列表。 默认50条每页(limit =50)， 在返回的结果对象里面有一个 total 用于返回总数, item 用于返回列表

    ```
    {
    	"items":[],
    	"total":0
    }
    ```

  - 提供接口 /o?url=，

    - 获取被请求的地址的当前 host 之外的所有内容（原图片地址）
      - 比如 http://分发器.com/o?url=http://a.com/1.jpg ， 获取到http://a.com/1.jpg 
    - 从sqlite 中检查是否存在缓存成功记录
      - 存在3分钟之前的缓存记录
        - 跳转（缓存后的AliyunOSS中的图片地址）
      - 未存在缓存成功记录
        - 检查变量  （缓存进行中的文件列表），是否存在3分钟内发起的缓存任务。
          - 存在
            - 跳过检查，返回 （原图片地址）
          - 不存在
            - 返回 （原图片地址）， 
            - 后台发起一项任务
              - 在变量 （缓存进行中的文件列表） 中添加当前任务信息【（原图片地址），（缓存时间）】
              - 检查（原图片地址）的图片文件大小，
                - 大于20M直接跳过，并移出掉 （缓存进行中的文件列表）的任务。
                - 小于等于20M
                  - 下载图片，并把文件存放在一个临时目录 ./tmp
                  - 将下载好的图片从临时目录上传到OSS, 并得到 （缓存后的AliyunOSS中的图片地址）
                    - 把（原图片地址），（缓存后的AliyunOSS中的图片地址），（缓存时间） 添加到sqlite



### 请依据以上需求，编写Python代码 app.py 

请勿使用redis, 缓存直接用全部变量

直接返回我完整代码，请勿省略任何内容

 

## 二、生成代码

把以上提示词贴给ChatGPT, 得到如下代码：

### 1. Python 代码

```python
import os
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests
from flask import Flask, request, redirect
import oss2
import shutil  # 用于操作临时文件和目录

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
        "SELECT original_url, cached_url, cache_time FROM history LIMIT ? OFFSET ?",
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
        if datetime.strptime(
            cache_time, "%Y-%m-%d %H:%M:%S"
        ) > datetime.now() - timedelta(minutes=3):
            print("to " + cached_url + "?x-oss-process=image/resize,m_fill," + plus_url)
            return redirect(cached_url + "?x-oss-process=image/resize,m_fill," + plus_url)

    # 检查是否存在进行中的缓存任务
    if original_url in caching_tasks and datetime.now() - caching_tasks[
        original_url
    ] < timedelta(minutes=3):
        return redirect(original_url)

    # 发起后台缓存任务
    cache_image(original_url)
    return redirect(original_url)


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
    app.run(debug=False)

```

### 2. 然后依据Python代码让它生成 Dockerfile :

```dockerfile
# 使用官方Python基础镜像
FROM python:3.9-slim-buster

# 设置工作目录
WORKDIR /app

# 复制requirements.txt到工作目录
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序代码到工作目录
COPY . .

# 创建临时目录
RUN mkdir -p tmp

# 创建数据目录
RUN mkdir -p data

# 暴露应用程序端口(根据实际情况修改)
EXPOSE 5000

# 运行应用程序
CMD ["python", "app.py"]
```

### 3. requirements.txt 文件的内容

```
Flask
oss2
requests
```

### 4. 作为docker的发布需求，编写一个 deploy.yaml 文件

```
version: '3'
services:
  img2oss:
    image: odinluo/img2oss:latest
    ports:
      - 5000:5000
      - 7081:80
      - 7082:8080
    environment:
      - ACCESS_KEY_ID=
      - ACCESS_KEY_SECRET=
      - BUCKET_NAME=
      - ENDPOINT=oss-cn-hangzhou.aliyuncs.com
      - CDN=https://file.domainname.com
      - REGION=cn-hangzhou
    deploy:
      resources:
        limits:
          memory: 300m
    volumes:
      - /www/img2oss:/app/data
```



## 三、发布

### 发布完成：

配置好OSS信息，发布到服务器上测试一下，果然随便就跑通了，真离谱。



![image-20240309202326472](https://memosfile.qiangtu.com/picgo/assets/2024/03/09202403_09202326.png)

指了一个域名过来，反向代理到这个服务。

![image-20240309202400228](https://memosfile.qiangtu.com/picgo/assets/2024/03/09202403_09202400.png)

当然，我的核心需求，其实是减少页面加载的文件大小，比如 midjourney 的生成结果，一个就是5-10M, 我的一个页面就有21个这样的图片，100-200M 的流量就这样没了，关键加载还能慢。

这个时候使用OSS的好处也就来了。

完整图片：[网页中查看](https://twoapi-ui.qiangtu.com/log/draw/mj)
![](https://memosfile.qiangtu.com/cache/cdn/download/20240309/KPr1bX0Ddic7mToHiqVPAcIWDSmf0w.png)

添加缩小参数后图片：[网页中查看](https://twoapi-ui.qiangtu.com/log/draw/mj)

![](https://memosfile.qiangtu.com/cache/cdn/download/20240309/KPr1bX0Ddic7mToHiqVPAcIWDSmf0w.png?x-oss-process=image/resize,m_fill,w_500)

在显示图片的时候，指定一下图片的宽度，这样就可以避免居多的流量被浪费。

### Docker成品：

从上文大家也看到了，我发布的docker镜像的地址是 `odinluo/img2oss:latest` 。

如果你拥有OSS, 且只是想体验成品带来的便利的话，那你也可以直接使用他哦； 



当前代码基于AI 创建，作为编写人，我指定的是MIT协议，请随意。



## 四、结论

#### 提示词工程师轻松高薪何来？

扯，所谓的提示词工程师可以很轻松？ 在我看来还是企业对这个东西的认知差异吧。 一个好的提示词工程师能替代的是整个工程体系的一套小班子，所谓的出纳、会计、保安、收银、客服、保洁、产品经理、设计师、程序员、测试、IT 通通都是你！如果从这个角度来说，未来提示词工程师确实价值很高那确实是事实，因为这就是一个AI赋能的万精油嘛，成为这样的人，你可能得都干过才行。



#### 回到技术话题：

在网页中插入图片的时候，采用以下格式，能节省很多用户流量，加快页面访问速度。

```
https://{domain}/o?plus=w_500&url={imageurl}
```

![image-20240309202040655](https://memosfile.qiangtu.com/picgo/assets/2024/03/09202403_09202040.png)



这也是今天我的[工作内容](https://twoapi-ui.qiangtu.com/log/draw/gpt-4-dalle)啦，增加一个被动的CDN转发服务，用来把网页内的图片备份到CDN保护下的OSS, 用来提高网页的访问速度和解决网页图片加载不出来的问题。因为这个东西的应用领域比较狭窄，估计也就个人站点级别的站长们会有需求，所有上文出现的诸多操作流程，就没有细述了哈，毕竟连源代码都在上面了，看懂源码很多事情都不需要解释。实在有问题，你就来问我吧。



#### 如果你有任何问题，可以在我的[博客页面](https://odin.mblog.club/)扫码添加我的个人微信，我会尽量回复你。

如果你对我们的[AI产品](https://github.com/520hacker/two-api)感兴趣的话，添加我微信，我也可以拉你加入我们的[AI技术群](https://h5.clewm.net/?url=qr61.cn%2FoRUvxf%2FqyT8mJT)哦。



**注：** 上文提示词和生成代码**非一次生成**，为逐步迭代测试逐步完成，其中更有手改代码环节，请勿对当前各版本AI有过高期待。
