# LF QuickID

本项目是一个本地照片批量处理桌面工具集。当前包含人脸分组、证件照换背景、证件照裁切、证件照排版等本地批量处理能力。

## 功能

- 选择本地照片目录
- 扫描 `.jpg`、`.jpeg`、`.png`、`.webp`、`.bmp`、`.tif`、`.tiff`
- 使用本地 InsightFace 模型做人脸检测和特征提取
- 使用聚类算法把相同/相似人物分组
- 批量抠出人像并替换为红底、蓝底、白底或自定义底色
- 换背景支持快速模式和高质量人像模式，高质量模式优先改善头发丝边缘
- 批量按常用证件照规格裁切并写入 DPI
- 将已裁切证件照按 5 寸、6 寸、A3、A4 或自定义纸张自动重复排版输出
- 在 PySide6 桌面界面中展示人物卡片、出现次数、涉及照片

## 安装

建议使用 Python 3.10、3.11 或 3.12。InsightFace/onnxruntime 通常不支持过新的 Python 版本，因此不要使用 Python 3.13+。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

首次运行人脸识别时，InsightFace 会下载本地模型文件。首次运行证件照换背景时，rembg 会下载本地抠图模型文件；切换到高质量人像模式时会额外下载 `birefnet-portrait` 模型。照片不会上传到云端。

如果模型自动下载失败，可以手动执行：

```bash
mkdir -p "$HOME/.insightface/models"
curl --http1.1 -L --retry 8 --retry-all-errors --continue-at - -o "$HOME/.insightface/models/buffalo_l.zip" "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
unzip -o "$HOME/.insightface/models/buffalo_l.zip" -d "$HOME/.insightface/models"
```

模型最终目录应为：`~/.insightface/models/buffalo_l`。

## 启动

```bash
cd "/Users/lf/Documents/lf_program/LF-QuickID-证件照处理"
source .venv/bin/activate
lf-quickid
```

或者：

```bash
python -m lf_quickid.main
```

## 打包 macOS App

```bash
scripts/build_macos_app.sh
```

打包产物会生成到 `dist/LF QuickID.app`。脚本会使用 PyInstaller 构建、ad-hoc 签名，并执行 `codesign --verify --deep --strict`。

打包后建议运行内置照片处理自检，确认 `.app` 内部的人脸识别、抠图、裁切、排版和分组导出依赖都能正常工作：

```bash
"dist/LF QuickID.app/Contents/MacOS/LF QuickID" --self-test --self-test-output /private/tmp/lf_quickid_app_selftest
```

输出 JSON 中 `"ok": true` 表示自检通过。

## 当前限制

- 第一版优先支持 macOS 本地运行。
- 当前还没有手动合并/拆分人物分组。
- 聚类阈值使用默认值，后续需要根据真实照片调优。
- 证件照换背景使用本地自动抠图模型，复杂头发、低分辨率、主体与背景颜色接近的图片仍建议人工复核。
- `.heic` 暂未启用，后续可为 macOS 单独增加支持。
