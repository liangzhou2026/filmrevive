# FilmRevive MVP

FilmRevive 是一个本地运行的网页 Demo，用于把手机拍摄的彩色负片照片转换成正片预览。

第一版处理流程：

1. 上传彩色负片照片
2. 显示原图预览
3. 点击“自动转正片”
4. FastAPI 后端使用 OpenCV 做反相、简单去橙色罩、自动白平衡、自动对比度
5. 返回 JPG 正片
6. 页面显示 before / after 对比
7. 下载处理后的图片
8. 一键去色罩：片基颜色估计、RGB 补偿、自动色阶、灰点/肤色校正

## 项目结构

```text
FilmRevive/
  backend/
    main.py
    requirements.txt
  frontend/
    index.html
    package.json
    tsconfig.json
    vite.config.ts
    src/
      main.tsx
      styles.css
  README.md
```

## 后端启动

最简单方式：双击 `start-backend.bat`。

建议使用 Python 3.10 及以上版本。如果你的默认 `python` 太新或装包失败，可以换成本机已安装的稳定版本，例如 `py -3.12`。

```bash
cd FilmRevive/backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

健康检查：

```bash
curl http://127.0.0.1:8001/api/health
```

## 前端启动

最简单方式：双击 `start-frontend.bat`。

另开一个终端：

```bash
cd FilmRevive/frontend
npm install
npm run dev
```

如果本机没有 npm，也可以用 Node 直接启动静态前端：

```bash
cd FilmRevive/frontend
node dev-server.mjs
```

前端已经把 React/ReactDOM 运行时放在 `frontend/public/vendor/`，静态启动不需要联网加载 CDN。

打开：

```text
http://127.0.0.1:5173
```

## PWA App

前端已经支持 PWA：

- `manifest.webmanifest`
- App 图标
- Service Worker
- 手机添加到主屏幕

部署到 HTTPS 网页后，用手机浏览器打开站点，即可添加到主屏幕作为 FilmRevive App 使用。本地 `127.0.0.1` 也可以测试 PWA 安装能力。

## API

`POST /api/convert`

- 请求：`multipart/form-data`，字段名为 `file`
- 响应：`image/jpeg`

示例：

```bash
curl -X POST http://127.0.0.1:8001/api/convert \
  -F "file=@negative.jpg" \
  --output positive.jpg
```

## 上传格式

常规图片：

- JPG / JPEG
- PNG
- WEBP
- BMP
- TIFF / TIF

RAW 文件例如 `.fff`、`.3fr`、`.dng` 暂不支持。建议先用 Hasselblad Phocus、Lightroom 或 Capture One 导出为 TIFF/JPG 后再上传。

线上 Render 免费实例使用云端安全模式：

- 上传文件限制：25MB
- 处理前自动缩小到最长边 2400px
- 这样可以避免 OpenCV 处理大图时超过云服务器内存

## 一键去色罩

一键去色罩会按顺序执行：

- 估计橙色片基颜色
- 按 RGB 通道做片基补偿
- 反相为正片
- 自动黑场 / 高光 / 色阶
- 自动白平衡
- 灰点校正
- 自然肤色校正：参考 Portra 400 的柔和肤色倾向，曝光不足时局部提亮肤色
- 清透自然人像调性：低反差、柔和高光、轻微提亮暗部、克制饱和度

附加可选处理：

- 去噪点：用保守强度的 OpenCV 彩色降噪降低噪声，同时混合原图保留细节

## 当前算法说明

后端暂时不使用 AI 模型，只做基础 OpenCV 图像处理：

- `255 - pixel` 反相
- 按通道均值拉平，粗略抵消橙色片基
- Gray World 白平衡
- 按百分位裁剪的自动对比度

这是一个 MVP 级基线算法，适合快速验证交互链路。后续可以加入胶片边框检测、曝光估计、色彩曲线、扫描仪风格 LUT 或 AI 色彩恢复。
