# FilmRevive 部署指南

目标：

- 域名：`filmrevive.com`
- 前端：Netlify，访问 `https://filmrevive.com`
- 后端：Render，访问 `https://api.filmrevive.com`
- DNS：Cloudflare

## 1. 上传代码到 GitHub

1. 新建 GitHub 仓库，例如 `filmrevive`
2. 把 `FilmRevive` 文件夹里的内容作为仓库根目录上传
3. 确保仓库根目录能看到：

```text
backend/
frontend/
netlify.toml
render.yaml
README.md
```

## 2. Cloudflare 购买域名

1. 打开 Cloudflare Registrar
2. 搜索并购买 `filmrevive.com`
3. 购买完成后，在 Cloudflare DNS 页面保留这个域名

## 3. Render 部署后端

1. 打开 Render
2. New + -> Blueprint
3. 连接 GitHub 仓库
4. Render 会读取 `render.yaml`
5. 创建服务 `filmrevive-api`

如果不用 Blueprint，也可以 New + -> Web Service，手动填写：

```text
Name: filmrevive-api
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Health Check Path: /api/health
```

环境变量：

```text
CORS_ORIGINS=https://filmrevive.com,https://www.filmrevive.com,http://localhost:5173,http://127.0.0.1:5173
```

部署成功后，先记下 Render 默认域名，例如：

```text
https://filmrevive-api.onrender.com
```

## 4. Render 绑定后端域名

在 Render 的 `filmrevive-api` 服务里：

1. Settings -> Custom Domains
2. 添加：

```text
api.filmrevive.com
```

Render 会给你一个 DNS 目标，通常类似：

```text
filmrevive-api.onrender.com
```

回到 Cloudflare DNS，添加：

```text
Type: CNAME
Name: api
Target: filmrevive-api.onrender.com
Proxy status: DNS only
```

等 Render 显示证书签发成功后，后端地址就是：

```text
https://api.filmrevive.com
```

## 5. Netlify 部署前端

1. 打开 Netlify
2. Add new site -> Import an existing project
3. 选择 GitHub 仓库
4. 构建设置：

```text
Base directory: 留空
Build command: 留空
Publish directory: frontend
```

如果 Netlify 读取到了 `netlify.toml`，它会自动使用这些设置。

部署成功后，先记下 Netlify 默认域名，例如：

```text
https://xxxx.netlify.app
```

## 6. Netlify 绑定主域名

在 Netlify 站点：

1. Domain management
2. Add domain
3. 输入：

```text
filmrevive.com
www.filmrevive.com
```

Netlify 会给你 DNS 记录。

回到 Cloudflare DNS，常见设置是：

```text
Type: CNAME
Name: www
Target: 你的-netlify-域名.netlify.app
Proxy status: DNS only
```

根域名 `filmrevive.com` 按 Netlify 页面提示添加。通常 Netlify 会给 A 记录或 ALIAS/flattening 方案；在 Cloudflare 里可以使用 CNAME flattening。

## 7. 最终检查

打开：

```text
https://api.filmrevive.com/api/health
```

应该看到：

```json
{"status":"ok"}
```

打开：

```text
https://filmrevive.com
```

测试上传一张 JPG/PNG/TIFF。

如果前端能打开但处理失败，通常是 CORS 或后端域名没生效：

1. 确认 `https://api.filmrevive.com/api/health` 能打开
2. 确认 Render 环境变量 `CORS_ORIGINS` 包含 `https://filmrevive.com`
3. 修改环境变量后，在 Render 里重新部署一次

## 8. 手机安装为 App

部署到 HTTPS 后：

Android Chrome：

```text
打开 filmrevive.com -> 菜单 -> 添加到主屏幕
```

iPhone Safari：

```text
打开 filmrevive.com -> 分享 -> 添加到主屏幕
```
