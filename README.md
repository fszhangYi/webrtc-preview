# webrtc-preview

多站 WebRTC 预览上位机：从主站拉 **preview catalog**，再对各站 `signaling_url` **直连** offer/answer 显示画面；同连接上接收 **DataChannel `sensors-preview`** 的全传感器 latest 遥测（允许丢，仅 HUD）。

规格与阶段：[sensors-dcs/docs/preview-catalog-webrtc.md](../sensors-dcs/docs/preview-catalog-webrtc.md) · [webrtc-preview-agent.md](../sensors-dcs/docs/webrtc-preview-agent.md)  
壳与风格：[computer-configuration-scan/pyqt-web-software-style](../computer-configuration-scan/pyqt-web-software-style/README.md)（硬性 H1/H2/H3）

```text
主站 GET /api/preview/catalog  →  stations[] + streams[]
预览页 ──POST──▶ 各站 /api/webrtc/preview/offer   （不经 Peer）
         ◀── 相机流：VideoTrack → LIVE 视频格
         ◀── 传感器流：每 agent 一条 DataChannel → LIVE 同格可视化（关节条 / 夹爪量等）
```

「连接所选」会**按勾选同步**：未勾的已连接流会断开；LIVE 只显示当前 peers。

## 硬性功能（pyqt-web-software-style）

| # | 要求 | 本仓库落地 |
|---|------|------------|
| **H1** | 安全关闭 | 顶栏「安全关闭」→ `POST /api/shutdown`；异步停 uvicorn + `os._exit`；关 PyQt 窗 / Ctrl+C 同源 |
| **H2** | 重启后端 | 顶栏「重启后端」→ `POST /api/runtime/apply-config`（`path` = catalog URL）→ 写 active 指针 → `os.execv`；前端轮询 `/api/health` 再 reload |
| **H3** | win-win 打包 bat | 根目录 `win-win-build.bat` |

本应用无硬件发布环；H2 的「配置」是主站 **catalog URL**（非 YAML）。校验失败不重启。

## 启动

```bat
pip install -e .
start_web.bat          :: 只起后端，不打开浏览器
start_web_open.bat     :: 起后端并打开系统浏览器（可选）
start_desktop.bat      :: PyQt WebEngine 壳
```

默认监听 `http://127.0.0.1:7050/`（绑定 `0.0.0.0`）。查询参数：

```text
?catalog=http://192.168.1.10:7011/api/preview/catalog
```

或在页面填主站 catalog URL / `http://host:viz_port`（自动补 `/api/preview/catalog`）。

环境变量：

| 变量 | 含义 |
|------|------|
| `WEBRTC_PREVIEW_HOST` | 绑定地址，默认 `0.0.0.0` |
| `WEBRTC_PREVIEW_PORT` | 端口，默认 `7050` |
| `WEBRTC_PREVIEW_CATALOG` | 启动时默认 catalog URL |

CLI：`python -m webrtc_preview_app web [--open] [--catalog …]`；`--open` 才开浏览器。`start_web.bat` **不带** `--open`。

DCS「打开预览软件」会先确保本后端在跑（必要时由 DCS 拉起 `python -m webrtc_preview_app web`），再打开浏览器并带上 `?catalog=...`（`POST /api/preview/open`）。后端地址可配：DCS YAML `runtime.preview_app_url`、环境变量 `WEBRTC_PREVIEW_URL`，或 DCS 设置页「预览软件」。

## 鉴权 / CORS

Catalog 与 WebRTC offer 在 DCS 侧按公开前缀放行（`/api/preview/`、`/api/webrtc/preview/`），并启用 CORS，便于跨端口预览。Catalog **不含**驱动密钥字段。勿把 DCS viz 端口暴露到不可信网络。

## 打包（Windows → Windows）

```bat
win-win-build.bat
```

- 官方 embeddable CPython → `build/packvenv`（拒绝 Miniconda）
- 优先单文件 `dist\WebRTCPreview-YYYYMMDD-HHMMSS.exe`
- WebEngine 单文件不通则打成无 `_internal` 的 onedir，再压 zip
- 打包产物默认：双击 exe / `start_web.bat` → 后台服务 + 系统浏览器；`start_desktop.bat` / `exe --ui` → PyQt 壳

目标机不需要 Python / Node / Qt。

## 目录

```text
src/webrtc_preview_app/
  cli.py / desktop_entry.py / paths.py / service.py / reexec.py
  web/server.py
  web/static/index.html
packaging/
  build_windows.ps1 · webrtc-preview.spec · rthook_dll.py · make_icon.py
win-win-build.bat
start_web.bat / start_web_open.bat / start_desktop.bat
```
