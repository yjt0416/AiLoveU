from src import ChatBot, VoiceModule

def main():
    bot = ChatBot()
    voice = VoiceModule()
    
    voice.speak("你好！我是天天，很高兴认识你！")
    print("=" * 50)
    print("提示：输入'语音'可切换到语音模式，输入'退出'结束对话")
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
            print("\n提示：语音模式下你可以：")
            print("1. 直接输入文字，按回车键发送")
            print("2. 按回车键不输入内容，将会录制5秒语音")
            print("输入'文字'可切换回纯文字模式\n")
            continue
        
        if user_input == "文字":
            use_voice = False
            print("已切换到文字模式")
            continue
        
        try:
            ai_response = bot.send_message(user_input)
            if use_voice:
                voice.speak(ai_response)
            else:
                print(f"天天：{ai_response}")
        except Exception as e:
            error_msg = f"抱歉，我现在有点小问题..."
            if use_voice:
                voice.speak(error_msg)
            else:
                print(f"天天：{error_msg} ({e})")

if __name__ == "__main__":
    main()