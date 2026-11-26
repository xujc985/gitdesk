# GitDesk

**轻量级原生桌面 Git 客户端**——基于 **Python + PySide6（Qt Widgets）**，复刻 PyCharm 的主要 Git 图形化工作流。不是 Electron，不包含 WebView 或常驻浏览器进程。

![GitDesk 应用图标](assets/gitdesk.png)

所有 Git 操作直接调用本机 `git`，与你的全局配置、凭据管理器、SSH 代理兼容。

![GitDesk Qt 历史图](docs/screenshot-qt.png)
![GitDesk Qt 变更与差异](docs/screenshot-qt-changes.png)

## 为什么改用 Qt

旧版 tkinter 前端已全部移除，当前只有一套 Qt 前端：

- 更现代的深色主题、抗锯齿彩色分支图、原生高 DPI 支持。
- 真正的分支/标签徽标、清晰的层级与间距、平滑的矢量连线。
- 列表虚拟化、可见区域绘图、差异预览限量，控制大仓库前端资源开销。
- 只使用 `PySide6-Essentials` 的 Qt Widgets，**不安装 QtWebEngine**。

> Qt 比 tkinter 多一些基础运行库开销，不等于“零内存”。Windows 实测参考：欢迎页约 **110 MB**，打开 200 个提交的仓库约 **117 MB**（含 Python/Qt 运行库；机器和 Qt 版本会影响结果）。未采用 Electron，避免额外浏览器进程。

## 功能

| 模块 | 覆盖能力 |
|------|----------|
| **仓库管理** | 打开、克隆、初始化、最近仓库、子目录自动定位根目录 |
| **变更 / 暂存 / 差异** | 分组展示、暂存、取消暂存、回滚、未跟踪文件预览、语法高亮差异 |
| **提交** | 提交信息、Amend、无暂存时提交全部、Ctrl+Enter 提交 |
| **历史** | 真实拓扑的彩色分支图、分支徽标、标签徽标、过滤、提交详情、文件差异 |
| **分支** | 新建、检出、重命名、删除、合并、变基、上游领先/落后 |
| **远程同步** | fetch、pull（可选 rebase）、push、远程仓库管理 |
| **Stash** | 贮藏、预览、apply、pop、drop |
| **标签** | 轻量/附注标签、指定提交、检出、推送、删除 |
| **历史与合并操作** | Cherry-pick、Revert、Reset、Merge、Rebase、继续/中止变基 |

## 运行环境

- Windows / macOS / Linux
- Python 3.10+
- Git 已安装并在 `PATH` 中
- PySide6 Essentials（`requirements.txt`）

## 启动

```bash
# 安装依赖（仅第一次）
python -m pip install -r requirements.txt

# 启动
python main.py [仓库路径]
# 或双击
gitdesk.pyw
```

Windows 可直接双击 `run.bat` 或执行 `.\run.ps1 [仓库路径]`，脚本会自动检查并安装缺失的 Qt 依赖。

- **Windows 桌面图标**：`powershell -ExecutionPolicy Bypass -File .\install-windows.ps1`
- **Linux 启动/菜单**：`sh run.sh`、`sh install-linux.sh`
- **macOS 启动**：`sh run.sh` 或 `./run-macos.command`

详见 [多平台安装与兼容说明](docs/多平台安装.md)。

## 打包发布

已提供 **Windows 原生 Setup 安装程序、Linux AppImage、macOS .app/DMG**，并保留便携 ZIP 供不需要安装的用户使用：

- Windows：`GitDesk-1.0.0-windows-x64-setup.exe`，支持安装路径、开始菜单/桌面图标和卸载。
- Linux：`GitDesk-1.0.0-linux-x64.AppImage`，赋予执行权限后双击运行。
- macOS：`GitDesk-1.0.0-macos.dmg`，打开后将 `GitDesk.app` 拖入应用程序目录。

下载地址：https://github.com/xujc985/gitdesk/releases/tag/v1.0.0

```powershell
# Windows（生成本机可独立运行的 exe 与便携 ZIP）
powershell -ExecutionPolicy Bypass -File .\packaging\build-windows.ps1
```

```sh
# Linux：AppDir + tar.gz
sh packaging/build-linux.sh
# macOS：.app + DMG
sh packaging/build-macos.sh
```

详细产物、签名、公证和发布步骤见 [打包发布文档](docs/打包发布.md)。

## 轻量策略

- **单一 Qt 工作线程**：后台任务顺序执行，不随视图数量创建线程。
- **虚拟化提交表格**：默认加载 200 条，需要时每次再加载 200 条。
- **可见区域绘图**：200 条历史实测约 38 个绘图对象，而非几百条长期驻留的连线。
- **大差异限量**：最多显示约 1.2 MB、5 万个文本块，避免超大差异撑高内存。
- **纯 Qt 原生控件**：无 WebView、无前端 Node 服务、无浏览器进程。

## 测试

```bash
# 后端与历史拓扑测试
python -m unittest tests.test_backend tests.test_graph -v

# Qt 真实组件集成测试（无头模式）
python -m unittest tests.test_qt -v

# 全部 61 项
python -m unittest discover -s tests -v
```

Linux 无显示服务器可使用 `QT_QPA_PLATFORM=offscreen`；正常启动需桌面环境。

## 项目结构

```
gitdesk/
├── main.py             # Qt 启动入口
├── gitdesk.pyw         # Windows 无控制台入口
├── run.bat / run.ps1   # 自动依赖检查与启动
├── requirements.txt    # 仅 PySide6-Essentials
├── git_backend.py      # 本机 Git 封装与后台基础工具
├── graph_layout.py     # 真实父提交彩色轨道布局
├── ui_qt/
│   ├── main.py         # 主窗口与工作流调度
│   ├── theme.py        # 现代深色 Qt 主题
│   ├── tasks.py        # 单线程后台任务与 GUI 信号派发
│   ├── history_graph.py# QGraphics 可见区域彩色分支图
│   ├── widgets.py      # 通用表单/差异/高亮组件
│   ├── changes.py      # 变更、暂存、提交
│   ├── log.py          # 历史与提交详情
│   └── pages.py        # 分支、Stash、标签
├── tests/              # 后端、拓扑、Qt 集成测试
└── docs/               # 中文文档与真实界面截图
```

详细操作见 [使用指南](docs/使用指南.md)，技术取舍见 [Qt 前端优化说明](docs/Qt前端优化.md)。

## 许可

MIT
