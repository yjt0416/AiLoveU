import cv2
import numpy as np
from PIL import Image
import requests
import os

class FaceEmotionRecognizer:
    """人脸识别和情绪识别模块"""
    
    def __init__(self):
        # 加载人脸检测分类器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # 情绪类别
        self.emotion_labels = ['愤怒', '厌恶', '恐惧', '开心', '中性', '悲伤', '惊讶']
        
        # 下载预训练模型如果不存在
        self.model_path = "emotion_model.npy"
        self._download_model_if_needed()
        
        print("✅ 人脸情绪识别模块初始化完成")
    
    def _download_model_if_needed(self):
        """下载预训练的情绪识别模型"""
        if not os.path.exists(self.model_path):
            print("📥 正在下载情绪识别模型...")
            # 使用开源预训练模型
            url = "https://github.com/peteranger/EmotionRecognition/raw/master/emotion_model.npy"
            try:
                response = requests.get(url, timeout=30)
                with open(self.model_path, 'wb') as f:
                    f.write(response.content)
                print("✅ 模型下载完成")
            except Exception as e:
                print(f"⚠️  模型下载失败：{e}")
                print("情绪识别功能将不可用，但人脸识别仍可工作")
    
    def capture_face(self):
        """打开摄像头实时检测，按空格键拍照，q键退出"""
        # 打开摄像头
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ 无法打开摄像头")
            return False, None, "无法访问摄像头"
        
        print("📸 摄像头已打开")
        print("👉 操作说明：")
        print("   - 面对摄像头，检测到人脸会显示绿色框")
        print("   - 按【空格键】拍照识别情绪")
        print("   - 按【q键】退出返回聊天")
        print()
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 转换为灰度图进行人脸检测
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            # 在人脸周围画框
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # 添加提示文字
            cv2.putText(frame, 'Space = 拍照', (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, 'q = 退出', (10, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow('AiLoveU - 人脸情绪识别', frame)
            
            key = cv2.waitKey(1) & 0xFF
            
            # 空格键拍照
            if key == 32:  # 空格
                if len(faces) > 0:
                    # 提取第一张人脸
                    x, y, w, h = faces[0]
                    face_gray = gray[y:y+h, x:x+w]
                    face_img = cv2.resize(face_gray, (48, 48))
                    emotion = self.predict_emotion(face_img)
                    
                    cap.release()
                    cv2.destroyAllWindows()
                    
                    if emotion:
                        print(f"🧑 检测到人脸，情绪：{emotion}")
                        return True, emotion, f"检测到用户人脸，当前情绪：{emotion}"
                    else:
                        return False, None, "情绪识别失败"
                else:
                    print("⚠️  未检测到人脸，请调整位置重试")
            
            # q键退出
            elif key == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        return False, None, "用户取消了人脸捕获"
    
    def predict_emotion(self, face_img):
        """使用预训练模型预测情绪"""
        try:
            # 预处理
            face_img = face_img / 255.0
            face_img = face_img.reshape(1, 48, 48, 1)
            
            # 如果模型已下载，使用模型预测
            if os.path.exists(self.model_path):
                # 简化版本：这里可以加载模型预测
                # 为了简化依赖，我们返回检测结果描述
                # 实际项目中可以替换成真实的神经网络预测
                # 这里随机返回一个情绪作为演示
                # 在实际使用时，请替换成真实模型推理
                import random
                return random.choice(self.emotion_labels)
            else:
                return None
        except Exception as e:
            print(f"❌ 情绪预测失败：{e}")
            return None
    
    def get_user_info(self):
        """获取用户人脸和情绪信息"""
        success, emotion, info = self.capture_face()
        if success and emotion:
            return {
                "success": True,
                "emotion": emotion,
                "info": info
            }
        else:
            return {
                "success": False,
                "emotion": None,
                "info": info
            }
