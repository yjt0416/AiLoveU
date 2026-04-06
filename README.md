# 🤖 AiLoveU - 离线语音对话助手

AiLoveU 是一个偏重本地体验与可定制交互的语音对话项目，支持命令行、Tkinter、PyQt6（含 Live2D）三种使用方式。

## ✨ 当前功能

- 💬 **多轮对话**：基于 DeepSeek API，包含系统人设与上下文记忆
- 🎤 **语音输入**：离线 ASR（优先 Vosk，兼容 Whisper）
- 🔊 **语音输出**：edge-tts，自然语音合成
- 🙂 **情绪识别**：OpenCV + 情绪模型，支持根据情绪触发提示回复
- 🖥️ **三种入口**：
  - `main.py`（命令行）
  - `gui.py`（Tkinter）
  - `gui_beautiful.py`（PyQt6 + Live2D）
- 🧩 **PyQt6 增强特性**：
  - Live2D 模型递归扫描与一键切换
  - 模型缩放（滑块）与位置拖动（`Shift + 左键`）
  - 语音角色切换
  - AI 昵称可修改（运行时生效）
  - `Ctrl + Enter` 快捷发送
  - 语音播放时口型同步（简易）

## 🛠️ 技术栈

- **LLM**：DeepSeek API
- **TTS**：edge-tts
- **ASR**：Vosk / Whisper
- **音频录制**：sounddevice
- **键盘事件**：keyboard
- **GUI**：Tkinter / PyQt6
- **Live2D**：`live2d.v2`
- **CV**：OpenCV

## 📋 环境要求

- Python 3.8+
- Windows（当前交互设计优先适配 Windows）

## 🚀 快速开始

### 1) 克隆项目

```bash
git clone https://github.com/yjt0416/AiLoveU.git
cd AiLoveU
```

### 2) 安装依赖

```bash
pip install -r requirements.txt
```

### 3) 准备 `.env`

复制 `.env.example` 为 `.env`，并填写：

```env
API_KEY=your_deepseek_api_key_here
API_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-chat
TEMPERATURE=0.8
AI_NAME=AiLoveU
```

> 说明：`AI_NAME` 为默认昵称。PyQt 美化版里也可以在界面运行时直接修改。

### 4) 下载离线语音识别模型（可选但推荐）

```bash
# 下载：https://alphacephei.com/vosk/models
# 例如：vosk-model-small-cn-0.22
# 解压到项目根目录
```

### 5) 运行

```bash
# 命令行版
python main.py

# Tkinter 版
python gui.py

# PyQt6 + Live2D 美化版
python gui_beautiful.py
```

## 🐰 Live2D 使用说明（PyQt6）

1. 将模型放入 `live2d_models/` 下（支持多层目录）
2. 模型入口文件支持：
   - `index.json`
   - `*.model.json`
   - `*.model3.json`
   - `model.json`
3. 启动后可在左侧下拉框切换模型
4. 可用“大小”滑块调节模型尺寸（每个模型单独记忆）
5. 可按住 `Shift + 左键` 拖动模型显示位置

## ⌨️ 交互说明

### 命令行版 / Tkinter

- 语音模式录音触发：按住 `Ctrl`（依据 `voice.py` 当前实现）
- 可输入：`语音` / `文字` / `表情` / `退出`

### PyQt6 美化版

- 发送快捷键：`Ctrl + Enter`
- 语音模式录音触发：按住 `Ctrl`，松开结束
- 支持在界面中：
  - 修改 AI 昵称
  - 切换 TTS 声音
  - 切换 Live2D 模型与调节显示

## 📁 项目结构

```text
AiLoveU/
├── main.py
├── gui.py
├── gui_beautiful.py
├── config/
│   └── settings.py
├── src/
│   ├── chat_bot.py
│   ├── voice.py
│   ├── api_client.py
│   └── face_emotion.py
├── live2d_models/          # 本地模型目录（已在 .gitignore）
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 📦 大文件与 Git 说明

以下内容默认不上传：

- `live2d_models/`
- `live2d-master.zip`
- `vosk-model-*/`

如需共享模型，建议单独提供下载链接而非直接入库。

## 📄 License

MIT License

## 🙏 致谢

- [edge-tts](https://github.com/rany2/edge-tts)
- [Vosk](https://github.com/alphacep/vosk)
- [sounddevice](https://github.com/spatialaudio/python-sounddevice)
