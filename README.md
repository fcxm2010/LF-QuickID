# LF QuickID

本项目是一个本地照片批量处理桌面工具集。当前 MVP 的第一个工具是“人脸分组”：选择照片目录后，在本机识别人脸并把疑似同一个人聚合到一起，方便查看某个人出现了几次。

## 功能

- 选择本地照片目录
- 扫描 `.jpg`、`.jpeg`、`.png`、`.webp`、`.bmp`、`.tif`、`.tiff`
- 使用本地 InsightFace 模型做人脸检测和特征提取
- 使用聚类算法把相同/相似人物分组
- 在 PySide6 桌面界面中展示人物卡片、出现次数、涉及照片

## 安装

建议使用 Python 3.10、3.11 或 3.12。InsightFace/onnxruntime 通常不支持过新的 Python 版本，因此不要使用 Python 3.13+。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

首次运行人脸识别时，InsightFace 会下载本地模型文件。照片不会上传到云端。

如果模型自动下载失败，可以手动执行：

```bash
mkdir -p "$HOME/.insightface/models"
curl --http1.1 -L --retry 8 --retry-all-errors --continue-at - -o "$HOME/.insightface/models/buffalo_l.zip" "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
unzip -o "$HOME/.insightface/models/buffalo_l.zip" -d "$HOME/.insightface/models"
```

模型最终目录应为：`~/.insightface/models/buffalo_l`。

## 启动

```bash
lf-quickid
```

或者：

```bash
python -m lf_quickid.main
```

## 当前限制

- 第一版优先支持 macOS 本地运行。
- 当前还没有手动合并/拆分人物分组。
- 聚类阈值使用默认值，后续需要根据真实照片调优。
- `.heic` 暂未启用，后续可为 macOS 单独增加支持。
