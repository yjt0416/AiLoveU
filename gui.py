import tkinter as tk
from tkinter import scrolledtext, ttk, messagebox
import threading
import queue
from src import ChatBot, VoiceModule, FaceEmotionRecognizer
from config import Config

class AiLoveUGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AiLoveU - AI语音对话助手")
        self.root.geometry("800x700")
        self.root.minsize(600, 500)
        
        self.bot = ChatBot()
        self.voice = VoiceModule()
        self.face_emotion = FaceEmotionRecognizer()
        self.ai_name = getattr(Config, "AI_NAME", getattr(self.bot, "ai_name", "AI"))
        try:
            self.bot.set_ai_name(self.ai_name)
        except Exception:
            pass
        try:
            self.voice.set_speaker_name(self.ai_name)
        except Exception:
            pass
        
        self.use_voice = False
        self.recording = False
        
        self.create_widgets()
        
        self.output_queue = queue.Queue()
        self.update_output()
    
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_label = ttk.Label(top_frame, text="🤖 AiLoveU - AI语音对话助手", font=("Arial", 16, "bold"))
        title_label.pack(side=tk.LEFT)
        
        self.mode_button = ttk.Button(top_frame, text="🎤 语音模式", command=self.toggle_voice_mode)
        self.mode_button.pack(side=tk.RIGHT, padx=5)
        
        self.emotion_button = ttk.Button(top_frame, text="📸 表情识别", command=self.open_emotion_detection)
        self.emotion_button.pack(side=tk.RIGHT, padx=5)
        
        clear_button = ttk.Button(top_frame, text="🗑️ 清空聊天", command=self.clear_chat)
        clear_button.pack(side=tk.RIGHT, padx=5)
        
        chat_frame = ttk.Frame(main_frame)
        chat_frame.pack(fill=tk.BOTH, expand=True)
        
        self.chat_history = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, font=("Microsoft YaHei", 10))
        self.chat_history.pack(fill=tk.BOTH, expand=True)
        self.chat_history.config(state=tk.DISABLED)
        
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.input_box = ttk.Entry(bottom_frame, font=("Microsoft YaHei", 11))
        self.input_box.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 5))
        self.input_box.bind("<Return>", self.send_message)
        
        send_button = ttk.Button(bottom_frame, text="发送", command=self.send_message)
        send_button.pack(side=tk.RIGHT)
        
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(status_frame, text="💬 文字模式", foreground="green")
        self.status_label.pack(side=tk.LEFT)
        
        self.add_system_message(f"👋 你好！我是{self.ai_name}，很高兴认识你！\n- 输入文字点击发送即可聊天\n- 点击'🎤 语音模式'切换语音输入\n- 点击'📸 表情识别'让我看看你的心情\n")
        self.voice.speak(f"你好！我是{self.ai_name}，很高兴认识你！")
    
    def add_message(self, sender, message, is_user=False):
        self.chat_history.config(state=tk.NORMAL)
        if is_user:
            self.chat_history.insert(tk.END, f"\n你: {message}\n", "user")
        else:
            self.chat_history.insert(tk.END, f"\n{self.ai_name}: {message}\n", "ai")
        self.chat_history.config(state=tk.DISABLED)
        self.chat_history.see(tk.END)
    
    def add_system_message(self, message):
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.insert(tk.END, f"\n💡 {message}\n", "system")
        self.chat_history.config(state=tk.DISABLED)
        self.chat_history.see(tk.END)
    
    def clear_chat(self):
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)
    
    def toggle_voice_mode(self):
        self.use_voice = not self.use_voice
        if self.use_voice:
            self.mode_button.config(text="✏️ 文字模式")
            self.status_label.config(text="🎤 语音模式", foreground="blue")
            self.add_system_message("已切换到语音模式\n👉 按住空格键开始说话，松开空格键结束录音")
        else:
            self.mode_button.config(text="🎤 语音模式")
            self.status_label.config(text="💬 文字模式", foreground="green")
            self.add_system_message("已切换回文字模式")
    
    def send_message(self, event=None):
        user_input = self.input_box.get().strip()
        if not user_input:
            return
        
        self.input_box.delete(0, tk.END)
        self.add_message("你", user_input, is_user=True)
        
        threading.Thread(target=self.process_message, args=(user_input,), daemon=True).start()
    
    def process_message(self, user_input):
        try:
            response = self.bot.send_message(user_input)
            self.output_queue.put(("response", user_input, response))
        except Exception as e:
            self.output_queue.put(("error", str(e), None))
    
    def update_output(self):
        try:
            while not self.output_queue.empty():
                item = self.output_queue.get()
                msg_type = item[0]
                content = item[1]
                
                if msg_type == "response":
                    response = content
                    self.add_message(self.ai_name, response, is_user=False)
                    if self.use_voice:
                        self.voice.speak(response)
                elif msg_type == "system_prompt":
                    prompt = content
                    self.add_system_message(f"😊 检测到情绪，AI正在回复...")
                    response = self.bot.send_message(prompt)
                    self.add_message(self.ai_name, response, is_user=False)
                    if self.use_voice:
                        self.voice.speak(response)
                elif msg_type == "system_message":
                    msg = content
                    self.add_system_message(msg)
                elif msg_type == "error":
                    messagebox.showerror("错误", f"发生错误: {content}")
        except Exception as e:
            print(f"更新输出错误: {e}")
        finally:
            self.root.after(100, self.update_output)
    
    def open_emotion_detection(self):
        self.add_system_message("📸 正在打开摄像头...")
        threading.Thread(target=self._emotion_detection_thread, daemon=True).start()
    
    def _emotion_detection_thread(self):
        result = self.face_emotion.get_user_info()
        if result["success"]:
            emotion = result["emotion"]
            prompt = f"我现在看起来看起来{emotion}，请根据我的情绪给一个合适温柔的回应"
            self.output_queue.put(("system_prompt", prompt, None))
        else:
            self.output_queue.put(("system_message", result["info"], None))
    
    def start_voice_recording(self):
        pass

def main():
    root = tk.Tk()
    app = AiLoveUGUI(root)
    
    app.chat_history.tag_configure("user", foreground="#000000", font=("Microsoft YaHei", 10, "bold"))
    app.chat_history.tag_configure("ai", foreground="#1a73e8")
    app.chat_history.tag_configure("system", foreground="#666666", font=("Microsoft YaHei", 9))
    
    root.mainloop()

if __name__ == "__main__":
    main()
