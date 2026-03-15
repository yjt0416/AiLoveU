# 🤖 AI情感伴侣 - 离线语音对话系统

一个完全离线的AI情感伴侣对话系统，支持语音输入输出，基于大语言模型和离线语音识别。

## ✨ 功能特性

- 💬 **AI对话** - 基于DeepSeek大语言模型，支持多轮对话，带有情感陪伴人设
- 🎤 **离线语音识别** - 使用Vosk离线语音识别，不需要网络，保护隐私
- 🔊 **自然语音合成** - 使用微软Edge-TTS，晓晓女声非常自然生动
- 🎹 **智能录音** - 按住空格键开始录音，松开空格键结束，自由控制时长
- 📱 **两种输入模式** - 支持语音模式和文字模式自由切换
- 🔒 **完全离线** - 所有语音识别都在本地完成，不需要上传任何数据
- 🚫 **无依赖问题** - 使用sounddevice替代PyAudio，完美支持Python 3.14+

## 🛠️ 技术栈

- **大语言模型API**：DeepSeek API
- **语音合成**：edge-tts (微软晓晓)
- **语音识别**：Vosk (离线)
- **音频录制**：sounddevice (不需要PyAudio)
- **键盘事件**：keyboard

## 📋 环境要求

- Python 3.8+ (已测试Python 3.14可用)
- Windows/Linux/MacOS

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/你的用户名/AI-Partner.git
cd AI-Partner
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 下载Vosk中文离线语音识别模型
```bash
# 下载地址：https://alphacephei.com/vosk/models
# 下载 vosk-model-small-cn-0.22.zip
# 解压后放到项目根目录，命名为 vosk-model-small-cn-0.22
```

### 4. 配置API密钥
创建 `.env` 文件：
```env
API_KEY=你的DeepSeek API密钥
API_URL=https://api.deepseek.com/v1/chat/completions
DEEPSEEK_MODEL=deepseek-chat
TEMPERATURE=0.8
```

### 5. 运行程序
```bash
python main.py
```

## 🎮 使用说明

### 基本操作
- **文字模式**：默认模式，直接输入文字聊天
- **切换语音模式**：输入 `语音`，按回车
- **语音输入**：按住空格键开始说话，松开空格键结束录音
- **切换文字模式**：输入 `文字`，按回车
- **退出程序**：输入 `退出`，按回车

### 交互流程
```
你：语音
天天：已切换到语音模式
👉 按住空格键开始说话...
(你按住空格说话 → 松开空格)
✅ 录音结束
🔍 正在识别...
你：[识别结果]
天天：(语音回复)
(自动等待下一次录音)
```

## 📁 项目结构

```
AI-Partner/
├── main.py                 # 主程序入口
├── config/
│   └── settings.py         # 配置管理
├── src/
│   ├── __init__.py
│   ├── chat_bot.py         # 聊天机器人核心
│   ├── voice.py            # 语音模块（TTS + ASR）
│   └── api_client.py       # API客户端
├── requirements.txt        # 依赖列表
├── .gitignore             # Git忽略文件
├── .env.example           # 环境变量示例
└── README.md             # 项目说明
```

## 🎯 项目亮点

1. **完整的语音交互闭环**：从语音输入到语音输出，完整的对话体验
2. **离线隐私保护**：语音识别完全在本地完成，不依赖网络
3. **良好的工程实践**：模块化设计，代码结构清晰，易于扩展
4. **解决实际问题**：处理了Python版本兼容性、文件占用冲突、终端输入冲突等问题
5. **用户体验优化**：按住录音松开停止，符合用户习惯，交互自然

## 🔧 可选配置

### 更换语音
在 `src/voice.py` 中修改 `self.voice`：
```python
self.voice = "zh-CN-XiaoxiaoNeural"  # 默认：晓晓女声
# self.voice = "zh-CN-YunxiNeural"    # 云希男声
# self.voice = "zh-CN-XiaoyiNeural"    # 晓伊女声
```

### 使用Whisper替代Vosk
如果想要更高的识别准确率，可以使用OpenAI Whisper：
```bash
pip install openai-whisper
```
程序会自动检测并加载Whisper模型。

## 📄 许可证

MIT License

## 🙏 致谢

- [edge-tts](https://github.com/rany2/edge-tts) - 提供免费的微软语音合成
- [Vosk](https://github.com/alphacep/vosk) - 开源离线语音识别
- [sounddevice](https://github.com/spatialaudio/python-sounddevice) - 跨平台音频录制

---

*💖 如果你觉得这个项目对你有帮助，欢迎点个 Star！*
