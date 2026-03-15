import edge_tts
import asyncio
import os
import tempfile
import sounddevice as sd
import soundfile as sf
import numpy as np
import keyboard
from playsound import playsound

class VoiceModule:
    def __init__(self):
        # 使用微软晓晓（中文女声，非常自然生动）
        self.voice = "zh-CN-XiaoxiaoNeural"  # 活泼的年轻女声
        # 可选的其他语音：
        # "zh-CN-YunxiNeural"  # 温暖的男声
        # "zh-CN-YunyangNeural"  # 深沉的男声
        # "zh-CN-XiaoyiNeural"  # 可爱的小女孩声音
        # "zh-HK-HiuMaanNeural"  # 粤语女声
        self.rate = "+30%"  # 语速，+10%稍微快一点更自然
        self.volume = "+0%"  # 音量
        
        # 录音参数
        self.sample_rate = 16000
        self.channels = 1
        self.dtype = np.int16
        
        # 录音控制
        self.recording = False
        self.audio_frames = []
        
        # 离线语音识别模型
        self.asr_model = None
        self.asr_model_type = None  # 'vosk' or 'whisper'
        
        # 尝试加载离线语音识别模型
        self._load_asr_model()
        
        print("语音模块加载成功，使用微软晓晓语音")
        if self.asr_model:
            print(f"✅ 离线语音识别已加载（{self.asr_model_type}）")
        print("ℹ️  录音方式：按住空格键开始录音，松开空格键结束录音")
    
    def _load_asr_model(self):
        """尝试加载离线语音识别模型"""
        # 先尝试加载vosk（更轻量）
        try:
            from vosk import Model, KaldiRecognizer
            # 模型下载地址：https://alphacephei.com/vosk/models
            # 下载中文模型后解压到vosk-model-small-cn-0.22文件夹
            model_path = "vosk-model-small-cn-0.22"
            if os.path.exists(model_path):
                self.asr_model = Model(model_path)
                self.asr_recognizer = KaldiRecognizer(self.asr_model, self.sample_rate)
                self.asr_model_type = "vosk"
                return
        except ImportError:
            pass
        except Exception as e:
            print(f"加载vosk模型失败：{e}")
        
        # 尝试加载whisper
        try:
            import whisper
            # 使用最小的模型，速度快
            self.asr_model = whisper.load_model("base")
            self.asr_model_type = "whisper"
            return
        except ImportError:
            pass
        except Exception as e:
            print(f"加载whisper模型失败：{e}")
    
    async def _speak_async(self, text: str):
        """异步合成语音并播放"""
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, volume=self.volume)
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_filename = temp_file.name
        
        try:
            # 保存音频到临时文件
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    with open(temp_filename, "ab") as f:
                        f.write(chunk["data"])
            
            # 播放音频
            playsound(temp_filename)
        finally:
            # 删除临时文件
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
    
    def speak(self, text: str):
        print(f"天天：{text}")
        # 运行异步任务
        asyncio.run(self._speak_async(text))
    
    def _audio_callback(self, indata, frames, time, status):
        """音频回调函数，不断收集音频数据"""
        if status:
            print(status)
        if self.recording:
            self.audio_frames.append(indata.copy())
    
    def record_audio(self):
        """按住空格键开始录音，松开空格键结束录音"""
        try:
            self.audio_frames = []
            self.recording = False
            
            print("\n🎤 准备就绪，请按住【空格键】开始说话")
            print("   松开空格键结束录音")
            
            # 启动音频流
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback
            )
            
            with stream:
                # 等待空格键按下
                keyboard.wait('space')
                self.recording = True
                print("\n🔴 正在录音...（松开空格键停止）", flush=True)
                
                # 等待空格键松开
                keyboard.wait('space', release=True)
                self.recording = False
                print("\n✅ 录音结束", flush=True)
            
            # 清除输入缓冲区，移除按下空格产生的空格字符
            import sys
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
            
            # 合并音频数据
            if len(self.audio_frames) > 0:
                recording = np.concatenate(self.audio_frames, axis=0)
                return recording
            else:
                return None
            
        except Exception as e:
            print(f"❌ 录音失败：{e}")
            # 尝试清除输入缓冲区
            import sys
            import msvcrt
            try:
                while msvcrt.kbhit():
                    msvcrt.getch()
            except:
                pass
            return None
    
    def recognize_audio(self, audio_data):
        """离线语音识别，直接处理numpy数组，不使用文件"""
        if audio_data is None:
            return ""
        
        text = ""
        
        try:
            print("🔍 正在识别语音...")
            
            # 如果有离线模型，使用离线识别
            if self.asr_model and self.asr_model_type == "vosk":
                # 使用vosk识别，直接处理字节数据
                import json
                
                # 将numpy数组转换为字节
                audio_bytes = audio_data.tobytes()
                
                self.asr_recognizer.SetWords(True)
                # 分块处理音频
                chunk_size = 4000
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i:i+chunk_size]
                    if self.asr_recognizer.AcceptWaveform(chunk):
                        pass
                
                result = json.loads(self.asr_recognizer.FinalResult())
                text = result.get("text", "").strip()
                    
            elif self.asr_model and self.asr_model_type == "whisper":
                # 使用whisper识别
                result = self.asr_model.transcribe(audio_data, language="zh")
                text = result.get("text", "").strip()
            
            # 如果识别到文本
            if text:
                print(f"你：{text}")
                return text
            
            # 如果没有离线模型或者识别失败，让用户手动输入
            print("ℹ️  离线语音识别未启用或识别失败")
            print("请直接输入你说的内容：")
            text = input("你：").strip()
            return text
            
        except Exception as e:
            print(f"❌ 识别失败：{e}")
            print("请直接输入你说的内容：")
            return input("你：").strip()
    
    def listen(self) -> str:
        """监听用户输入，支持语音和文字"""
        print("\n🎙️ 语音模式：")
        print("1. 直接输入文字，按回车键发送")
        print("2. 按回车键不输入内容，进入语音录音")
        print("   然后按住【空格键】开始说话，松开结束录音")
        print("请选择：输入内容或直接按回车开始录音")
        
        user_input = input("你：")
        
        # 如果用户输入了文字，直接返回
        if user_input.strip():
            return user_input.strip()
        
        # 如果用户没有输入，尝试录音
        try:
            audio_data = self.record_audio()
            if audio_data is not None:
                result = self.recognize_audio(audio_data)
                if result:
                    return result
            
            # 如果录音或识别失败，让用户输入文字
            print("请输入你想说的话：")
            return input("你：").strip()
            
        except Exception as e:
            print(f"❌ 语音输入出错：{e}")
            print("请输入文字：")
            return input("你：").strip()