import edge_tts
import asyncio
import os
import tempfile
import sounddevice as sd
import soundfile as sf
import numpy as np
import keyboard
from playsound import playsound
import time
import random
import sys
from typing import Callable, List, Optional, Tuple


def safe_print(*args, **kwargs):
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    flush = kwargs.pop("flush", False)
    text = sep.join(str(arg) for arg in args)
    stream = kwargs.pop("file", sys.stdout)
    try:
        print(text, end=end, file=stream, flush=flush, **kwargs)
    except UnicodeEncodeError:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        fallback = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(fallback, end=end, file=stream, flush=flush, **kwargs)

class VoiceModule:
    def __init__(self):
        # 使用微软晓晓（中文女声，非常自然生动）
        self.voice = "zh-CN-XiaoxiaoNeural"  # 活泼的年轻女声
        # 可选的其他语音：
        # "zh-CN-YunxiNeural"  # 温暖的男声
        # "zh-CN-YunyangNeural"  # 深沉的男声
        # "zh-CN-XiaoyiNeural"  # 可爱的小女孩声音
        # "zh-HK-HiuMaanNeural"  # 粤语女声
        # 语速太快会显得“播音腔/机器人”，这里调回更自然的范围
        self.rate = "+10%"  # 建议区间：0% ~ +15%
        self.volume = "+0%"  # 音量
        self.pitch = "+0Hz"  # 轻微变化会更像真人（见 _humanize_prosody）
        self._humanize = True
        self._humanize_rate_jitter = 6   # ±6%
        self._humanize_pitch_jitter = 6  # ±6Hz
        self.speaker_name = os.getenv("AI_NAME", "AiLoveU")
        
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
        
        safe_print("语音模块加载成功，使用微软晓晓语音")
        if self.asr_model:
            safe_print(f"离线语音识别已加载（{self.asr_model_type}）")
        safe_print("录音方式：按住Ctrl键开始录音，松开Ctrl键结束录音")

    def _humanize_prosody(self) -> Tuple[str, str]:
        """
        给每次合成增加轻微“人味”波动（避免机械感）。
        返回 (rate, pitch)
        """
        if not self._humanize:
            return self.rate, self.pitch

        r = random.randint(-self._humanize_rate_jitter, self._humanize_rate_jitter)
        p = random.randint(-self._humanize_pitch_jitter, self._humanize_pitch_jitter)

        rate = f"{r:+d}%"
        pitch = f"{p:+d}Hz"
        return rate, pitch

    def _split_sentences(self, text: str) -> List[str]:
        # 简单按常见中文/英文句末标点分段，提升停顿自然度
        parts: List[str] = []
        buf: List[str] = []
        enders = set("。！？!?；;…")
        for ch in text:
            buf.append(ch)
            if ch in enders:
                s = "".join(buf).strip()
                if s:
                    parts.append(s)
                buf = []
        tail = "".join(buf).strip()
        if tail:
            parts.append(tail)
        return parts or [text]

    def _synthesize_mp3_with_word_marks(self, text: str) -> Tuple[str, List[Tuple[float, float]]]:
        """
        合成语音为 mp3 临时文件，并同时获取 WordBoundary 时间戳。

        返回:
        - mp3_path: 临时 mp3 文件路径（调用方负责删除）
        - marks: [(start_s, end_s), ...] 以播放开始为 0 的秒级区间
        """
        # 分句合成：停顿更自然，同时仍可拿到 word boundary 做口型
        segments = self._split_sentences(text)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_filename = temp_file.name

        marks_100ns: List[Tuple[int, int]] = []
        try:
            async def _run():
                offset_base = 0
                for seg in segments:
                    rate, pitch = self._humanize_prosody()
                    communicate = edge_tts.Communicate(
                        seg,
                        self.voice,
                        rate=rate,
                        volume=self.volume,
                        pitch=pitch,
                        boundary="WordBoundary",
                    )
                    last_end = 0
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            with open(temp_filename, "ab") as f:
                                f.write(chunk["data"])
                        elif chunk["type"] == "WordBoundary":
                            start = int(chunk.get("offset", 0)) + offset_base
                            dur = int(chunk.get("duration", 0))
                            if dur <= 0:
                                continue
                            end = start + dur
                            marks_100ns.append((start, end))
                            last_end = max(last_end, end)

                    # 给段落末尾留一点“自然停顿”，并把下一段 marks 的时间基准往后推
                    # 这里用 250ms 作为经验值（不会太拖，也不会粘连）
                    offset_base = max(offset_base, last_end) + 2_500_000

            asyncio.run(_run())

            # edge-tts 的 offset/duration 单位为 100ns（1s = 10,000,000）
            marks_s: List[Tuple[float, float]] = [
                (s / 10_000_000.0, e / 10_000_000.0) for (s, e) in marks_100ns
            ]

            # 去掉非常短的片段，避免口型抖动
            marks_s = [(s, e) for (s, e) in marks_s if (e - s) >= 0.03]
            return temp_filename, marks_s
        except Exception:
            try:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)
            finally:
                raise
    
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
            safe_print(f"加载vosk模型失败：{e}")
        
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
            safe_print(f"加载whisper模型失败：{e}")
    
    async def _speak_async(self, text: str):
        """异步合成语音并播放"""
        rate, pitch = self._humanize_prosody()
        communicate = edge_tts.Communicate(
            text,
            self.voice,
            rate=rate,
            volume=self.volume,
            pitch=pitch,
        )
        
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
        safe_print(f"{self.speaker_name}：{text}")
        # 运行异步任务
        asyncio.run(self._speak_async(text))

    def speak_with_word_marks(
        self,
        text: str,
        on_start: Optional[Callable[[List[Tuple[float, float]]], None]] = None,
        on_end: Optional[Callable[[], None]] = None,
    ):
        """
        带“口型同步用时间戳”的播放接口。

        - on_start: 在真正开始播放时回调，参数为 word marks 秒级区间列表
        - on_end: 播放结束回调
        """
        safe_print(f"{self.speaker_name}：{text}")
        mp3_path: Optional[str] = None
        try:
            mp3_path, marks = self._synthesize_mp3_with_word_marks(text)
            if on_start:
                on_start(marks)
            playsound(mp3_path)
            if on_end:
                on_end()
        finally:
            if mp3_path and os.path.exists(mp3_path):
                try:
                    os.remove(mp3_path)
                except Exception:
                    pass

    def set_speaker_name(self, name: str):
        name = (name or "").strip()
        if name:
            self.speaker_name = name
    
    def _audio_callback(self, indata, frames, time, status):
        """音频回调函数，不断收集音频数据"""
        if status:
            safe_print(status)
        if self.recording:
            self.audio_frames.append(indata.copy())
    
    def record_audio(self):
        """按住ctrl键开始录音，松开ctrl键结束录音"""
        try:
            self.audio_frames = []
            self.recording = False
            
            safe_print("\n准备就绪，请按住【Ctrl键】开始说话")
            safe_print("   松开Ctrl键结束录音")
            
            # 启动音频流
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._audio_callback
            )
            
            with stream:
                # 等待ctrl键按下
                keyboard.wait('ctrl')
                self.recording = True
                safe_print("\n正在录音...（松开Ctrl键停止）", flush=True)
                
                # 等待ctrl键松开 - 兼容旧版本keyboard
                while True:
                    if keyboard.is_pressed('ctrl'):
                        continue
                    break
                
                self.recording = False
                safe_print("\n录音结束", flush=True)
            
            # 清除输入缓冲区，移除按下ctrl产生的字符
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
            safe_print(f"录音失败：{e}")
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
            safe_print("正在识别语音...")
            
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
                safe_print(f"你：{text}")
                return text
            
            # 如果没有离线模型或者识别失败，让用户手动输入
            safe_print("离线语音识别未启用或识别失败")
            safe_print("请直接输入你说的内容：")
            text = input("你：").strip()
            return text
            
        except Exception as e:
            safe_print(f"识别失败：{e}")
            safe_print("请直接输入你说的内容：")
            return input("你：").strip()
    
    def listen(self) -> str:
        """语音模式下：用户按Ctrl键开始录音，松开结束，不混文字输入"""
        safe_print("\n语音模式已激活")
        safe_print("按住【Ctrl键】开始说话，松开【Ctrl键】结束录音")
        safe_print("提示：全程不需要按回车键，只需要操作Ctrl键")
        
        try:
            audio_data = self.record_audio()
            if audio_data is not None:
                result = self.recognize_audio(audio_data)
                if result:
                    return result
            
            # 如果录音或识别失败，回退到文字输入
            safe_print("\n语音输入失败，请输入文字：")
            return input("你：").strip()
            
        except Exception as e:
            safe_print(f"\n语音输入出错：{e}")
            safe_print("请输入文字：")
            return input("你：").strip()
