from src import ChatBot, VoiceModule, FaceEmotionRecognizer
from config import Config

def main():
    bot = ChatBot()
    voice = VoiceModule()
    face_emotion = FaceEmotionRecognizer()
    ai_name = getattr(Config, "AI_NAME", getattr(bot, "ai_name", "AI"))
    try:
        voice.set_speaker_name(ai_name)
    except Exception:
        pass
    
    voice.speak(f"你好！我是{ai_name}，很高兴认识你！")
    print("=" * 50)
    print("提示：输入'语音'可切换到语音模式")
    print("      输入'表情'打开摄像头识别你的情绪")
    print("      输入'退出'结束对话")
    print("=" * 50)
    
    use_voice = False
    
    while True:
        if use_voice:
            user_input = voice.listen()
            if not user_input:
                continue
        else:
            user_input = input("你：")
        
        if user_input.lower() in ["exit", "quit", "退出", "再见"]:
            voice.speak("好的，下次再聊！")
            break
        
        if user_input == "语音":
            use_voice = True
            voice.speak("已切换到语音模式")
            print("\n💬 现在已进入语音模式")
            print("👉 按住空格键说话，松开空格键结束录音")
            print("输入'文字'可切换回纯文字模式\n")
            continue
        
        if user_input == "文字":
            use_voice = False
            print("已切换到文字模式")
            continue
        
        if user_input == "表情":
            print("\n📸 准备打开摄像头识别情绪...")
            print("提示：按空格键拍照，按q键退出")
            result = face_emotion.get_user_info()
            if result["success"]:
                emotion = result["emotion"]
                prompt = f"用户现在情绪是{emotion}，请根据我的情绪给我一个合适的回复"
                print(f"😊 检测到你的情绪：{emotion}")
                voice.speak(f"我看到你现在看起来{emotion}呢")
                try:
                    ai_response = bot.send_message(prompt)
                    if use_voice:
                        voice.speak(ai_response)
                    else:
                        print(f"{ai_name}：{ai_response}")
                except Exception as e:
                    print(f"{ai_name}：抱歉，我现在有点小问题... ({e})")
            else:
                print(f"❌ {result['info']}")
            continue
        
        try:
            ai_response = bot.send_message(user_input)
            if use_voice:
                voice.speak(ai_response)
            else:
                print(f"{ai_name}：{ai_response}")
        except Exception as e:
            error_msg = f"抱歉，我现在有点小问题..."
            if use_voice:
                voice.speak(error_msg)
            else:
                print(f"{ai_name}：{error_msg} ({e})")

if __name__ == "__main__":
    main()