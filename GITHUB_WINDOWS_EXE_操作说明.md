# 用 Mac 生成 Windows EXE（不需要 Windows 电脑）

这套工具**只发布 Windows 10／11（64 位）可运行的 `BatchRenameTool.exe`**。Mac 只是上传源码，GitHub Actions 会使用 Windows 虚拟机器进行打包。

## 首次操作（使用 GitHub 网站）

1. 登录 [github.com](https://github.com) 并选择 New repository。建议选择 **Private**；仓库名称可填写 `BatchRenameTool`。
2. 在 Mac 解压本 ZIP。打开 `BatchRenameTool_v1_1_2` 文件夹。
3. 因为 `.github` 是隐藏文件夹，请在 Finder 按 `Command + Shift + .`，让隐藏文件显示出来。
4. 打开 GitHub 仓库，选择 **Add file → Upload files**，把 `BatchRenameTool_v1_1_2` **内部所有文件与文件夹**拖上去（包括 `.github`、`batchrename`、`tests`、`requirements.txt`、`main.py`）。**不要把 ZIP 原封不动上传，也不要只上传外层文件夹**；GitHub 仓库根目录必须看见 `main.py`，以及 `.github/workflows/build-windows.yml`。
5. 点击 **Commit changes** 保存。
6. 在仓库顶部点击 **Actions**，找到 **Build Windows EXE**。如果系统要求启用 Actions，请先启用。
7. 点击 **Run workflow → Run workflow**（如无手动按钮，初次 push 通常会自动启动）。
8. 在成功的执行记录中，找到 **Artifacts → BatchRenameTool-Windows-x64**，下载 ZIP，在 Mac 上解压后就能取得 `BatchRenameTool.exe`。
9. 把 `BatchRenameTool.exe` 复制给 Windows 使用者。使用者双击即可启动，不需要安装 Python。

## 注意事项

- `BatchRenameTool.exe` 是**免安装便携版**，不是拥有安装向导的 setup.exe；如果需要桌面快捷方式／卸载程序，还需要制作安装包。
- 必须在 Windows 电脑实际执行一次验收：打开、检查简体中文与高对比度文字、批量粘贴、预览、重命名及恢复。CI 的自动测试无法保证每个 Windows 环境的显示效果。
- 如果 Windows SmartScreen 提示未知发布者，这是因为此版本**没有数字签名**，不代表一定有病毒。请先确认文件来源，不要盲目忽略警告。
- GitHub Actions 的执行时间、配额与可用性取决于 GitHub 账户和仓库设置。失败时点击执行记录查看报错。
- 本 ZIP 只包含开发示例资料，**不要将真实员工姓名或薪资资料公开上传至 GitHub**。建议使用 Private 仓库。
