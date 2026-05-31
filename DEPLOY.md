# FilmRevive 部署指南

目标：

- 域名：`filmrevive.app`
- 前端：Netlify，访问 `https://filmrevive.app`
- 后端：Render，访问 `https://api.filmrevive.app`
- DNS：Cloudflare

## 1. GitHub

项目已上传到：

```text
https://github.com/liangzhou2026/filmrevive
```

仓库根目录应包含：

```text
backend/
frontend/
netlify.toml
render.yaml
README.md
DEPLOY.md
```

## 2. Render 后端

Render 会读取仓库根目录的 `render.yaml`。

服务配置：

```text
Name: filmrevive-api
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Health Check Path: /api/health
```

环境变量：

```text
CORS_ORIGINS=https://filmrevive.app,https://www.filmrevive.app,https://filmrevive.netlify.app,http://localhost:5173,http://127.0.0.1:5173
```

Render 默认后端地址：

```text
https://filmrevive-api.onrender.com
```

测试：

```text
https://filmrevive-api.onrender.com/api/health
```

应该看到：

```json
{"status":"ok"}
```

## 3. Render 绑定后端域名

在 Render 的 `filmrevive-api` 服务里：

```text
Settings -> Custom Domains -> Add Custom Domain
```

添加：

```text
api.filmrevive.app
```

Render 要求在 Cloudflare DNS 添加：

```text
Type: CNAME
Name: api
Target: filmrevive-api.onrender.com
Proxy status: DNS only
TTL: Auto
```

验证成功后测试：

```text
https://api.filmrevive.app/api/health
```

## 4. Netlify 前端

Netlify 会读取仓库根目录的 `netlify.toml`。

部署设置：

```text
Build command: echo 'No build needed'
Publish directory: frontend
Branch: main
```

Netlify 默认前端地址：

```text
https://filmrevive.netlify.app
```

## 5. Netlify 绑定前端域名

在 Netlify：

```text
Domain management -> Add a domain
```

添加：

```text
filmrevive.app
www.filmrevive.app
```

在 Cloudflare DNS 添加或确认：

```text
Type: A
Name: @
Target: Netlify 提供的 A 记录 IP
Proxy status: DNS only
TTL: Auto
```

以及：

```text
Type: CNAME
Name: www
Target: filmrevive.netlify.app
Proxy status: DNS only
TTL: Auto
```

如果 Netlify 给出不同 DNS 指引，以 Netlify 页面为准。

## 6. 最终测试

后端：

```text
https://api.filmrevive.app/api/health
```

前端：

```text
https://filmrevive.app
```

上传一张 JPG/PNG/TIFF 测试一键去色罩。

## 7. 手机安装为 App

Android Chrome：

```text
打开 filmrevive.app -> 菜单 -> 添加到主屏幕
```

iPhone Safari：

```text
打开 filmrevive.app -> 分享 -> 添加到主屏幕
```
