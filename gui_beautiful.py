import html
import sys
import os
import threading
import queue
import time
import math
import OpenGL.GL as gl
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QSplitter, QFrame, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QMouseEvent, QCursor
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QEvent
import live2d.v2 as live2d
from src import ChatBot, VoiceModule, FaceEmotionRecognizer

class Live2dOpenGLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.is_model_loaded = False  # 🆕 新增标志位，记录核心模型是否加载成功
        self.click_x = -1
        self.click_y = -1
        self.is_clicked = False
        self._model_path = None
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(33)  # ~30fps
        self._frame_timer.timeout.connect(self.update)
        self._idle_t0 = time.monotonic()
        self._mouth_value = 0.0
        self._mouth_target = 0.0
        self._bg_color = QColor("#f7f9fc")
        self._scale = 1.25  # 默认放大一点，避免人物偏小
        # 模型平移（用于修正不同模型的中心点/对齐）
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._is_panning = False
        self._pan_last_x = 0.0
        self._pan_last_y = 0.0
    
    def set_scale(self, scale: float):
        self._scale = float(scale)
        if not self.is_model_loaded or not self.model:
            return
        for scale_method in ("SetScale", "setScale", "SetModelScale", "setModelScale"):
            fn = getattr(self.model, scale_method, None)
            if callable(fn):
                try:
                    fn(float(self._scale))
                    break
                except Exception:
                    pass
        self.update()

    def _try_set_transform(self, x: float, y: float, scale: float) -> bool:
        """
        尝试设置模型的平移/缩放（不同 live2d 绑定方法名差异很大，尽量兼容）。
        x,y: 通常是 -1..1 的归一化坐标（不保证所有绑定一致）
        """
        if not self.is_model_loaded or not self.model:
            return False

        # 先尝试 set offset / translate
        for method_name in (
            "SetOffset", "setOffset",
            "SetTranslate", "setTranslate",
            "SetPosition", "setPosition",
            "SetModelOffset", "setModelOffset",
            "SetModelPosition", "setModelPosition",
        ):
            fn = getattr(self.model, method_name, None)
            if callable(fn):
                try:
                    fn(float(x), float(y))
                    # 缩放单独设置
                    self.set_scale(scale)
                    return True
                except Exception:
                    pass

        # 有的绑定把 transform 放在 view/renderer 上
        for attr in ("view", "View", "render", "renderer", "Renderer"):
            obj = getattr(self.model, attr, None)
            if not obj:
                continue
            for method_name in ("SetOffset", "setOffset", "SetTranslate", "setTranslate", "SetPosition", "setPosition"):
                fn = getattr(obj, method_name, None)
                if callable(fn):
                    try:
                        fn(float(x), float(y))
                        self.set_scale(scale)
                        return True
                    except Exception:
                        pass

        return False

    def initializeGL(self) -> None:
        live2d.glInit()
        # 让背景不是“纯黑”
        gl.glClearColor(
            self._bg_color.redF(),
            self._bg_color.greenF(),
            self._bg_color.blueF(),
            1.0,
        )
        # 先创建模型实例（此时只是一个空壳，内部 live2DModel 仍为 None）
        self.model = live2d.LAppModel()
        # 如果 load_model 在 initializeGL 之前被调用，这里补做实际加载
        if self._model_path:
            try:
                prev_cwd = os.getcwd()
                try:
                    os.chdir(os.path.dirname(self._model_path))
                    self.model.LoadModelJson(self._model_path)
                finally:
                    os.chdir(prev_cwd)
                self.is_model_loaded = True
            except Exception as e:
                print(f"加载Live2D模型失败: {e}")
        if self.is_model_loaded:
            # 尝试在加载后设置缩放（不同 live2d 绑定方法名不同，尽量兼容）
            for scale_method in ("SetScale", "setScale", "SetModelScale", "setModelScale"):
                fn = getattr(self.model, scale_method, None)
                if callable(fn):
                    try:
                        fn(float(self._scale))
                        break
                    except Exception:
                        pass
            self._frame_timer.start()
    
    def load_model(self, model_path):
        try:
            self._model_path = os.path.abspath(model_path)
            if self.model is not None:
                # 切换模型时重建实例，避免切回后不显示（部分绑定/模型在重复 Load 时会残留状态）
                try:
                    self.is_model_loaded = False
                    self.model = live2d.LAppModel()
                except Exception:
                    pass
                prev_cwd = os.getcwd()
                try:
                    os.chdir(os.path.dirname(self._model_path))
                    self.model.LoadModelJson(self._model_path)
                finally:
                    os.chdir(prev_cwd)
                self.is_model_loaded = True  # 🆕 模型实际加载成功后，设为 True
                # 尝试设置缩放
                for scale_method in ("SetScale", "setScale", "SetModelScale", "setModelScale"):
                    fn = getattr(self.model, scale_method, None)
                    if callable(fn):
                        try:
                            fn(float(self._scale))
                            break
                        except Exception:
                            pass
                # 立即按当前控件尺寸 resize，避免首次不渲染/显示异常
                try:
                    self.model.Resize(self.width(), self.height())
                except Exception:
                    pass
                self._idle_t0 = time.monotonic()
                self._frame_timer.start()
                return True
            # QOpenGLWidget 只有在真正创建 OpenGL 上下文后才会 initializeGL；
            # 这里先记录路径并让 UI 继续挂载 widget，等 initializeGL 再加载
            return True
        except Exception as e:
            print(f"加载Live2D模型失败: {e}")
            return False
    
    def set_mouth_open(self, value: float):
        # value: 0..1
        if not self.is_model_loaded:
            return
        self._mouth_target = max(0.0, min(1.0, float(value)))

    def _try_set_param(self, param_id: str, value: float) -> bool:
        """
        兼容不同 live2d python 绑定的参数写法。
        """
        if not self.model or not self.is_model_loaded:
            return False

        # 尽可能多地尝试不同绑定暴露出来的“核心模型对象”
        candidates = [self.model]
        for attr in ("live2DModel", "Live2DModel", "model", "Model", "coreModel", "core_model"):
            candidates.append(getattr(self.model, attr, None))
        for getter in ("GetModel", "getModel", "GetLive2DModel", "getLive2DModel"):
            fn = getattr(self.model, getter, None)
            if callable(fn):
                try:
                    candidates.append(fn())
                except Exception:
                    pass

        for obj in candidates:
            if not obj:
                continue
            for method_name in ("SetParamFloat", "setParamFloat", "set_parameter", "setParameter"):
                fn = getattr(obj, method_name, None)
                if callable(fn):
                    try:
                        fn(param_id, float(value))
                        return True
                    except Exception:
                        continue
        return False

    def paintGL(self) -> None:
        # 🆕 添加 self.is_model_loaded 判断
        if self.model is not None and self.is_model_loaded:
            # 某些环境/流程下 clear color 会被覆盖，这里每帧强制一次
            gl.glClearColor(
                self._bg_color.redF(),
                self._bg_color.greenF(),
                self._bg_color.blueF(),
                1.0,
            )
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
            # 叠加一个轻微 idle（呼吸/摆动），确保“会动”
            t = time.monotonic() - self._idle_t0
            breath = 0.5 + 0.5 * math.sin(t * 1.2)  # 0..1
            sway = math.sin(t * 0.6)  # -1..1

            # 平滑口型：目标 -> 当前
            self._mouth_value += (self._mouth_target - self._mouth_value) * 0.35

            self.model.Update()
            # 应用“用户拖拽”的平移（尽量不和模型内部交互 Drag 冲突）
            self._try_set_transform(self._pan_x, self._pan_y, self._scale)
            # 注意：很多模型/框架会在 Update() 里覆盖参数，所以把口型/idle 放在 Update() 之后更稳
            # 常见嘴巴参数兼容：v2 / v3
            for pid in (
                "PARAM_MOUTH_OPEN_Y",
                "ParamMouthOpenY",
                "MouthOpenY",
                "PARAM_MOUTH_OPEN",
            ):
                self._try_set_param(pid, self._mouth_value)

            # 轻微呼吸（有的模型支持 BodyAngleX/AngleX/ParamBodyAngleX 等）
            for pid in ("PARAM_BODY_ANGLE_X", "ParamBodyAngleX", "PARAM_ANGLE_X", "ParamAngleX"):
                self._try_set_param(pid, sway * (10.0 if "BODY" in pid.upper() else 8.0))

            # 让嘴形在非说话时也有一点点“活气”
            if self._mouth_target <= 0.001:
                for pid in ("PARAM_MOUTH_FORM", "ParamMouthForm", "MouthForm"):
                    self._try_set_param(pid, (breath - 0.5) * 0.3)

            self.model.Draw()
    
    def resizeGL(self, width, height) -> None:
        # 🆕 添加 self.is_model_loaded 判断
        if self.model is not None and self.is_model_loaded:
            self.model.Resize(width, height)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.is_model_loaded: # 🆕 同样加上保护
            return
        
        x, y = event.position().x(), event.position().y()
        # Shift + 左键：平移模型显示位置
        if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = True
            self._pan_last_x = x
            self._pan_last_y = y
            return
        if self._is_in_live2d_area(x, y):
            self.is_clicked = True
            self.click_x = x
            self.click_y = y
    
    def mouseReleaseEvent(self, event) -> None:
        if not self.is_model_loaded:  # 🆕
            return
        if self._is_panning:
            self._is_panning = False
            return
        if not self.is_clicked:
            return
        
        x, y = event.position().x(), event.position().y()
        try:
            if self._is_in_live2d_area(x, y) and self.model:
                if hasattr(self.model, "Touch"):
                    self.model.Touch(x, y)
        except Exception as e:
            print(f"Live2D点击交互失败: {e}")
        self.is_clicked = False
    
    def mouseMoveEvent(self, event) -> None:
        if not self.is_model_loaded: # 🆕
            return
        if self._is_panning:
            x, y = event.position().x(), event.position().y()
            dx = x - self._pan_last_x
            dy = y - self._pan_last_y
            self._pan_last_x = x
            self._pan_last_y = y
            # 将像素移动转为近似归一化偏移（经验映射，确保拖起来直观）
            if self.width() > 0 and self.height() > 0:
                self._pan_x += dx / float(self.width()) * 2.0
                self._pan_y -= dy / float(self.height()) * 2.0
                # 限制范围，避免拖飞
                self._pan_x = max(-2.0, min(2.0, self._pan_x))
                self._pan_y = max(-2.0, min(2.0, self._pan_y))
            self.update()
            return
        if not self.is_clicked:
            return
        
        x, y = event.position().x(), event.position().y()
        if self.model:
            dx, dy = x - self.click_x, y - self.click_y
            try:
                if hasattr(self.model, "Drag"):
                    self.model.Drag(dx, dy)
            except Exception as e:
                print(f"Live2D拖拽交互失败: {e}")
    
    def _is_in_live2d_area(self, click_x, click_y):
        if not self.is_model_loaded: # 🆕
            return False
        # H10: glReadPixels 在部分环境会导致原生崩溃（窗口直接关闭，无 Python 异常）。
        # 这里改为“在 widget 内部即视为有效区域”，避免读回 framebuffer。
        return 0 <= click_x <= self.width() and 0 <= click_y <= self.height()

class AiLoveUGUI(QMainWindow):
    message_received = pyqtSignal(str, str)
    speech_start = pyqtSignal(object)  # marks: List[Tuple[float,float]]
    speech_end = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AiLoveU - 多角色 AI 伴侣")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        self.bot = ChatBot()
        self.voice = VoiceModule()
        self.face_emotion = FaceEmotionRecognizer()

        # AI 昵称（可在界面里修改）
        self.ai_name = getattr(self.bot, "ai_name", "AiLoveU")
        self.current_character_id = self.bot.get_current_character().character_id
        try:
            self.voice.set_speaker_name(self.ai_name)
        except Exception:
            pass
        
        self.use_voice = False
        self._voice_thread = None
        self.output_queue = queue.Queue()
        self._speech_marks = []
        self._speech_t0 = None
        self._mouth_timer = QTimer(self)
        self._mouth_timer.setInterval(33)
        self._mouth_timer.timeout.connect(self._tick_mouth)
        self._model_scales = {}  # 每个模型单独记忆缩放
        self._current_model_key = None
        
        self.init_ui()
        self.init_live2d()
        self._refresh_character_selector(select_id=self.current_character_id)
        self._reload_active_character_view()
        self._refresh_memory_panel()

        self.speech_start.connect(self._on_speech_start)
        self.speech_end.connect(self._on_speech_end)
        
        # 欢迎语也走同一条“口型同步”链路（后台播放，不阻塞 UI）
        self._speak_with_lipsync(f"你好！我是{self.ai_name}，很高兴认识你！")
        self.add_system_message(
            "👋 欢迎使用AiLoveU！\n"
            "- 语音模式：点击麦克风按钮开启\n"
            "- 表情识别：点击摄像头按钮拍照识别你的情绪\n"
            f"- {self.ai_name} 会根据你的情绪给出更合适的回复~"
        )
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 更统一、现代的整体风格（不改变功能逻辑）
        self.setStyleSheet("""
            QMainWindow { background: #eef2f7; }
            QLabel { color: #1f2d3d; }
            QTextEdit {
                font-family: "Microsoft YaHei";
                font-size: 11pt;
            }
            QPushButton {
                font-family: "Microsoft YaHei";
                font-size: 10pt;
            }
        """)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)
        
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #f7f9fc;
                border: 1px solid rgba(31,45,61,0.08);
                border-radius: 12px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("🤖 AiLoveU")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50;")
        left_layout.addWidget(title_label)

        # Live2D 模型选择（从 live2d_models/ 扫描）
        from PyQt6.QtWidgets import QComboBox, QSlider, QLineEdit
        character_row = QHBoxLayout()
        character_row.setSpacing(8)
        self.character_selector = QComboBox()
        self.character_selector.setMinimumHeight(36)
        self.character_selector.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                border-radius: 10px;
                padding: 6px 10px;
            }
            QComboBox::drop-down { border: none; width: 26px; }
            QComboBox::down-arrow { width: 0px; height: 0px; }
        """)
        self.character_selector.currentIndexChanged.connect(self._on_character_selected)
        character_row.addWidget(self.character_selector, 1)

        self.import_card_button = QPushButton("导入角色卡")
        self.import_card_button.setMinimumHeight(36)
        self.import_card_button.setStyleSheet("""
            QPushButton {
                background: #1f8f6b;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #187255; }
        """)
        self.import_card_button.clicked.connect(self.import_character_card)
        character_row.addWidget(self.import_card_button)
        left_layout.addLayout(character_row)

        self.character_meta_label = QLabel("当前伴侣：AiLoveU")
        self.character_meta_label.setWordWrap(True)
        self.character_meta_label.setStyleSheet("color: rgba(31,45,61,0.70); font-size: 12px; padding: 2px 2px 6px 2px;")
        left_layout.addWidget(self.character_meta_label)

        self.model_selector = QComboBox()
        self.model_selector.setMinimumHeight(36)
        self.model_selector.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                border-radius: 10px;
                padding: 6px 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 26px;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                selection-background-color: #cfe8ff;
                selection-color: #1f2d3d;
            }
        """)
        self.model_selector.currentIndexChanged.connect(self._on_model_selected)
        left_layout.addWidget(self.model_selector)

        # AI 昵称设置
        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_label = QLabel("AI昵称")
        name_label.setStyleSheet("color: rgba(31,45,61,0.75); font-size: 12px;")
        name_row.addWidget(name_label)

        self.name_input = QLineEdit()
        self.name_input.setText(self.ai_name)
        self.name_input.setPlaceholderText("输入后回车应用")
        self.name_input.setMinimumHeight(32)
        self.name_input.setStyleSheet("""
            QLineEdit {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                border-radius: 10px;
                padding: 6px 10px;
            }
        """)
        self.name_input.returnPressed.connect(self._apply_ai_name)
        name_row.addWidget(self.name_input, 1)

        self.name_apply_btn = QPushButton("应用")
        self.name_apply_btn.setMinimumHeight(32)
        self.name_apply_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                border-radius: 10px;
                padding: 6px 10px;
            }
            QPushButton:hover { background: #f2f6fb; }
        """)
        self.name_apply_btn.clicked.connect(self._apply_ai_name)
        name_row.addWidget(self.name_apply_btn)

        left_layout.addLayout(name_row)

        # 模型缩放控制（不同模型大小差异很大）
        scale_row = QHBoxLayout()
        scale_row.setSpacing(8)
        self.scale_label = QLabel("大小 125%")
        self.scale_label.setStyleSheet("color: rgba(31,45,61,0.75); font-size: 12px;")
        scale_row.addWidget(self.scale_label)

        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setMinimum(50)
        self.scale_slider.setMaximum(200)
        self.scale_slider.setValue(125)
        self.scale_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(31,45,61,0.10);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: #3498db;
            }
            QSlider::sub-page:horizontal {
                background: rgba(52,152,219,0.45);
                border-radius: 3px;
            }
        """)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)
        scale_row.addWidget(self.scale_slider, 1)

        self.scale_reset_btn = QPushButton("重置")
        self.scale_reset_btn.setMinimumHeight(30)
        self.scale_reset_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                border-radius: 10px;
                padding: 4px 10px;
            }
            QPushButton:hover { background: #f2f6fb; }
        """)
        self.scale_reset_btn.clicked.connect(self._reset_scale)
        scale_row.addWidget(self.scale_reset_btn)

        left_layout.addLayout(scale_row)
        
        # Live2D 显示“画布卡片”：用 QFrame 避免 QLabel 边框/对齐造成的可见裁剪边界
        self.live2d_container = QFrame()
        self.live2d_container.setMinimumSize(360, 520)  # 扩大显示框
        self.live2d_container.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid rgba(31,45,61,0.10);
                border-radius: 12px;
            }
        """)
        live2d_layout = QVBoxLayout(self.live2d_container)
        live2d_layout.setContentsMargins(0, 0, 0, 0)
        live2d_layout.setSpacing(0)
        self.live2d_placeholder = QLabel("Live2D加载中...")
        self.live2d_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.live2d_placeholder.setStyleSheet("color: rgba(31,45,61,0.60);")
        live2d_layout.addWidget(self.live2d_placeholder, 1)
        left_layout.addWidget(self.live2d_container, 1)
        
        control_panel = QFrame()
        control_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        control_panel.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid rgba(31,45,61,0.08);
                border-radius: 12px;
                padding: 12px;
            }
        """)
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(5, 5, 5, 5)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.voice_button = QPushButton("🎤 语音模式")
        self.voice_button.setCheckable(True)
        self.voice_button.clicked.connect(self.toggle_voice_mode)
        self.voice_button.setMinimumHeight(40)
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                padding: 8px;
            }
            QPushButton:checked {
                background-color: #e74c3c;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2c3e50;
            }
        """)
        button_layout.addWidget(self.voice_button)
        
        self.emotion_button = QPushButton("📸 表情识别")
        self.emotion_button.clicked.connect(self.open_emotion_detection)
        self.emotion_button.setMinimumHeight(40)
        self.emotion_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
            QPushButton:pressed {
                background-color: #16a085;
            }
        """)
        button_layout.addWidget(self.emotion_button)
        
        clear_button = QPushButton("🗑️ 清空")
        clear_button.clicked.connect(self.clear_chat)
        clear_button.setMinimumHeight(40)
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        button_layout.addWidget(clear_button)
        
        control_layout.addLayout(button_layout)
        
        status_label = QLabel("💬 文字模式")
        status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
        self.status_label = status_label
        control_layout.addWidget(status_label)

        # 语音角色/声音切换（edge-tts voice id）
        from PyQt6.QtWidgets import QComboBox
        self.voice_selector = QComboBox()
        self.voice_selector.setMinimumHeight(34)
        self.voice_selector.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                border-radius: 10px;
                padding: 6px 10px;
            }
            QComboBox::drop-down { border: none; width: 26px; }
            QComboBox::down-arrow { width: 0px; height: 0px; }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #1f2d3d;
                border: 1px solid rgba(31,45,61,0.12);
                selection-background-color: #cfe8ff;
                selection-color: #1f2d3d;
            }
        """)
        self._voice_presets = [
            ("晓晓（自然女声）", "zh-CN-XiaoxiaoNeural"),
            ("晓伊（可爱女声）", "zh-CN-XiaoyiNeural"),
            ("云希（温暖男声）", "zh-CN-YunxiNeural"),
            ("云扬（低沉男声）", "zh-CN-YunyangNeural"),
            ("粤语-晓曼", "zh-HK-HiuMaanNeural"),
        ]
        for label, vid in self._voice_presets:
            self.voice_selector.addItem(label, userData=vid)
        # 默认选中当前 VoiceModule.voice
        try:
            cur = getattr(self.voice, "voice", None)
            if cur:
                for i in range(self.voice_selector.count()):
                    if self.voice_selector.itemData(i) == cur:
                        self.voice_selector.setCurrentIndex(i)
                        break
        except Exception:
            pass
        self.voice_selector.currentIndexChanged.connect(self._on_voice_selected)
        control_layout.addWidget(self.voice_selector)
        
        left_layout.addWidget(control_panel)
        main_layout.addWidget(left_panel, 1)
        
        right_panel = QFrame()
        right_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid rgba(31,45,61,0.08);
                border-radius: 12px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        chat_label = QLabel("💬 聊天记录")
        chat_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        chat_label.setStyleSheet("color: #2c3e50; margin-bottom: 5px;")
        header_row = QHBoxLayout()
        header_row.addWidget(chat_label)
        self.memory_mode_chip = QLabel("记忆模式 --")
        self.memory_mode_chip.setStyleSheet("""
            QLabel {
                background: #edf6ff;
                color: #1d5f8c;
                border: 1px solid #c8ddf0;
                border-radius: 999px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        header_row.addStretch(1)
        header_row.addWidget(self.memory_mode_chip)
        right_layout.addLayout(header_row)

        self.chat_hint_label = QLabel("已启用长期记忆、用户画像抽取和多角色会话隔离。")
        self.chat_hint_label.setWordWrap(True)
        self.chat_hint_label.setStyleSheet("color: rgba(31,45,61,0.70); font-size: 12px; margin-bottom: 4px;")
        right_layout.addWidget(self.chat_hint_label)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        profile_card, self.profile_stat_value = self._create_stat_card("Profile", "0")
        memory_card, self.memory_stat_value = self._create_stat_card("Memories", "0")
        session_card, self.session_stat_value = self._create_stat_card("Session turns", "0")
        stats_row.addWidget(profile_card)
        stats_row.addWidget(memory_card)
        stats_row.addWidget(session_card)
        right_layout.addLayout(stats_row)

        self.memory_preview_label = QLabel("当前还没有结构化记忆。")
        self.memory_preview_label.setWordWrap(True)
        self.memory_preview_label.setStyleSheet("""
            QLabel {
                background: #f8fafc;
                color: #5b6776;
                border: 1px solid rgba(31,45,61,0.08);
                border-radius: 12px;
                padding: 10px 12px;
                font-size: 12px;
                margin-bottom: 6px;
            }
        """)
        right_layout.addWidget(self.memory_preview_label)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFont(QFont("Microsoft YaHei", 11))
        self.chat_history.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(31,45,61,0.10);
                border-radius: 12px;
                background-color: #fbfcfe;
                color: #1f2d3d;
                selection-background-color: #cfe8ff;
                selection-color: #1f2d3d;
            }
        """)
        right_layout.addWidget(self.chat_history, 1)
        
        input_layout = QHBoxLayout()
        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("在这里输入文字，按Ctrl+Enter发送...")
        self.input_box.setFont(QFont("Microsoft YaHei", 11))
        self.input_box.setMaximumHeight(80)
        self.input_box.setStyleSheet("""
            QTextEdit {
                border: 1px solid rgba(31,45,61,0.12);
                border-radius: 12px;
                background-color: #fff;
                color: #1f2d3d;
            }
        """)
        input_layout.addWidget(self.input_box, 1)
        # Ctrl+Enter 发送
        self.input_box.installEventFilter(self)
        
        send_button = QPushButton("发送")
        send_button.clicked.connect(self.send_message)
        send_button.setMinimumSize(80, 50)
        send_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #2c3e50;
            }
        """)
        input_layout.addWidget(send_button)
        
        right_layout.addLayout(input_layout)
        self.input_hint = QLabel("提示：Ctrl+Enter 发送。稳定的偏好、目标和设定会自动写入记忆。")
        self.input_hint.setWordWrap(True)
        self.input_hint.setStyleSheet("color: rgba(31,45,61,0.60); font-size: 11px; padding: 2px 4px 0 4px;")
        right_layout.addWidget(self.input_hint)
        main_layout.addWidget(right_panel, 2)
        
        self.message_received.connect(self.on_message_received)
        QTimer.singleShot(100, self.update_output)

    def eventFilter(self, obj, event):
        if obj is getattr(self, "input_box", None) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if (mods & Qt.KeyboardModifier.ControlModifier) and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.send_message()
                return True
        return super().eventFilter(obj, event)
    
    def init_live2d(self):
        try:
            # 先扫描本地模型列表并填充下拉框
            self._models = self._scan_live2d_models()
            self.model_selector.blockSignals(True)
            self.model_selector.clear()
            for name in sorted(self._models.keys(), key=lambda x: x.lower()):
                self.model_selector.addItem(name)
            self.model_selector.blockSignals(False)

            model_path = None
            # 优先选择：若存在 Pio / Epsilon2.1 则默认选它，否则选第一个
            for preferred in ("Pio", "Epsilon2.1"):
                if preferred in self._models:
                    # 用 index 设置，避免 setCurrentText 在有重复 text 时出现异常行为
                    idx = self.model_selector.findText(preferred)
                    if idx >= 0:
                        self.model_selector.setCurrentIndex(idx)
                    model_path = self._models[preferred]
                    break
            if model_path is None and self.model_selector.count() > 0:
                model_path = self._models.get(self.model_selector.currentText())

            if not model_path:
                model_path = self._download_live2d_model()
            if model_path:
                model_path = os.path.abspath(model_path)
            if model_path and os.path.exists(model_path):
                self.live2d_widget = Live2dOpenGLWidget(self.live2d_container)
                if self.live2d_widget.load_model(model_path):
                    # 清理占位内容并挂载 OpenGL 画布
                    if hasattr(self, "live2d_placeholder") and self.live2d_placeholder:
                        self.live2d_placeholder.hide()
                    self.live2d_container.layout().addWidget(self.live2d_widget)
                    # 应用当前模型缩放（若有记忆则用记忆值）
                    self._current_model_key = self.model_selector.currentText()
                    scale = self._model_scales.get(self._current_model_key, 1.25)
                    self._apply_scale_to_live2d(scale, update_slider=True, persist=False)
                else:
                    self._set_live2d_placeholder(f"💬 {self.ai_name}\n\n加载失败，请检查模型文件\n需要下载Live2D模型后启用")
            else:
                self._set_live2d_placeholder(f"💬 {self.ai_name}\n\n这里将显示虚拟人物\n需要下载Live2D模型后启用")
        except Exception as e:
            print(f"Live2D初始化失败: {e}")
            self._set_live2d_placeholder(f"💬 {self.ai_name}\n\n这里将显示虚拟人物\n需要下载Live2D模型后启用")

    def _set_live2d_placeholder(self, text: str):
        if hasattr(self, "live2d_placeholder") and self.live2d_placeholder:
            self.live2d_placeholder.setText(text)
            self.live2d_placeholder.show()

    def _scan_live2d_models(self):
        """
        扫描 live2d_models/ 下的模型入口文件。
        返回: {显示名: model_json_path}
        """
        models = {}
        # 以当前文件目录为基准，避免运行时 cwd 不在项目根目录导致扫描不全
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "live2d_models"))
        if not os.path.exists(base):
            return models

        # 递归扫描：支持 live2d_models/ 下多层目录组织
        # 规则：每个目录优先 index.json；其次 *.model.json / *.model3.json；最后 model.json
        # 同时排除 physics/exp 等非入口 json
        for root, dirs, files in os.walk(base):
            files_set = set(files)
            candidates = []

            if "index.json" in files_set:
                candidates.append(os.path.join(root, "index.json"))
            else:
                # 先收集更“像入口”的 json
                for fn in files:
                    lower = fn.lower()
                    if not lower.endswith(".json"):
                        continue
                    if lower.endswith(".physics.json") or lower.endswith(".exp.json") or lower == "physics.json":
                        continue
                    if lower.endswith(".model.json") or lower.endswith(".model3.json"):
                        candidates.append(os.path.join(root, fn))
                # 再兜底：很多 v2 模型入口叫 model.json
                if not candidates and "model.json" in files_set:
                    candidates.append(os.path.join(root, "model.json"))

            if not candidates:
                continue

            rel = os.path.relpath(root, base)
            display = rel.replace("\\\\", "/")
            # 避免重名：若已存在则追加序号
            if display in models:
                k = 2
                while f"{display} ({k})" in models:
                    k += 1
                display = f"{display} ({k})"

            models[display] = candidates[0]

        return models

    def _on_model_selected(self, _index: int = -1):
        if not hasattr(self, "_models"):
            return
        name = self.model_selector.currentText()
        path = self._models.get(name)
        if not path:
            return
        if not hasattr(self, "live2d_widget"):
            return
        try:
            ok = self.live2d_widget.load_model(path)
            if not ok:
                self.add_system_message(f"⚠️ 切换模型失败：{name}")
                return
            self._current_model_key = name
            scale = self._model_scales.get(name, 1.25)
            self._apply_scale_to_live2d(scale, update_slider=True, persist=False)
        except Exception as e:
            self.add_system_message(f"⚠️ 切换模型异常：{e}")

    def _apply_scale_to_live2d(self, scale: float, update_slider: bool, persist: bool):
        if hasattr(self, "live2d_widget"):
            try:
                self.live2d_widget.set_scale(scale)
            except Exception:
                pass

        pct = int(round(scale * 100))
        self.scale_label.setText(f"大小 {pct}%")
        if update_slider:
            self.scale_slider.blockSignals(True)
            self.scale_slider.setValue(max(50, min(200, pct)))
            self.scale_slider.blockSignals(False)
        if persist and self._current_model_key:
            self._model_scales[self._current_model_key] = scale

    def _on_scale_changed(self, value: int):
        # slider value is percent
        scale = float(value) / 100.0
        self._apply_scale_to_live2d(scale, update_slider=False, persist=True)

    def _reset_scale(self):
        self._apply_scale_to_live2d(1.25, update_slider=True, persist=True)

    def _on_voice_selected(self, _index: int = -1):
        try:
            voice_id = self.voice_selector.currentData()
            if voice_id:
                self.voice.voice = voice_id
                self.add_system_message(f"🔊 已切换声音：{self.voice_selector.currentText()}")
        except Exception as e:
            self.add_system_message(f"⚠️ 切换声音失败：{e}")
    
    def _download_live2d_model(self):
        models_dir = "live2d_models"
        os.makedirs(models_dir, exist_ok=True)
        
        # 默认尝试加载Pio模型，如果下载了其他模型请修改这个路径
        # 比如你下载了Epsilon2.1，路径就是:
        # model_path = os.path.join(models_dir, "Epsilon2.1")
        # model_json = os.path.join(model_path, "Epsilon2.1.model.json")
        model_path = os.path.join(models_dir, "Pio")
        if os.path.exists(model_path):
            model_json = os.path.join(model_path, "index.json")
            if os.path.exists(model_json):
                return model_json
        
        # 检查是否有Epsilon2.1模型
        epsilon_path = os.path.join(models_dir, "Epsilon2.1")
        if os.path.exists(epsilon_path):
            model_json = os.path.join(epsilon_path, "Epsilon2.1.model.json")
            if os.path.exists(model_json):
                return model_json
        
        print("⚠️  Live2D模型未下载，请手动下载:")
        print("推荐下载免费模型: https://github.com/guansss/Pio-Live2D/releases/download/v1.0.0/Pio.zip")
        print(f"解压后放到 {model_path} 目录")
        return None
    
    def toggle_voice_mode(self):
        self.use_voice = self.voice_button.isChecked()
        if self.use_voice:
            self.status_label.setText("🎤 语音模式（按住Ctrl说话，松开结束）")
            self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
            self.add_system_message("已切换到语音模式\n👉 按住Ctrl键开始说话，松开Ctrl键结束录音")
            if self._voice_thread is None or not self._voice_thread.is_alive():
                self._voice_thread = threading.Thread(target=self._voice_loop_thread, daemon=True)
                self._voice_thread.start()
        else:
            self.status_label.setText("💬 文字模式")
            self.status_label.setStyleSheet("color: #27ae60; font-size: 12px;")
            self.add_system_message("已切换回文字模式")

    def _voice_loop_thread(self):
        while True:
            if not self.use_voice:
                return
            try:
                text = self.voice.listen()
                if not self.use_voice:
                    return
                if text:
                    self.output_queue.put(("voice_input", text))
            except Exception as e:
                self.output_queue.put(("system_message", f"❌ 语音输入出错: {e}"))
    
    def open_emotion_detection(self):
        self.add_system_message("📸 正在打开摄像头...")
        threading.Thread(target=self._emotion_detection_thread, daemon=True).start()
    
    def _emotion_detection_thread(self):
        result = self.face_emotion.get_user_info()
        if result["success"]:
            emotion = result["emotion"]
            prompt = f"我现在看起来{emotion}，请根据我的情绪给一个合适温柔的回应"
            self.output_queue.put(("system_prompt", prompt))
        else:
            self.output_queue.put(("system_message", result["info"]))
    
    def send_message(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        
        self.input_box.clear()
        self.add_message("你", text, True)
        
        threading.Thread(target=self._process_message, args=(text,), daemon=True).start()
    
    def _process_message(self, user_input):
        try:
            response = self.bot.send_message(user_input)
            self.output_queue.put(("response", response))
        except Exception as e:
            self.output_queue.put(("error", str(e)))

    def _create_stat_card(self, title: str, value: str):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #f8fbff;
                border: 1px solid rgba(31,45,61,0.08);
                border-radius: 14px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: rgba(31,45,61,0.60); font-size: 11px;")
        value_label = QLabel(value)
        value_label.setStyleSheet("color: #1f2d3d; font-size: 18px; font-weight: 700;")

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return card, value_label

    def _refresh_memory_panel(self):
        summary = {}
        try:
            summary = self.bot.get_memory_summary()
        except Exception:
            summary = {}

        if not summary:
            return

        storage_mode = str(summary.get("storage_mode", "memory")).upper()
        self.memory_mode_chip.setText(f"记忆模式 {storage_mode}")
        self.profile_stat_value.setText(str(summary.get("profile_count", 0)))
        self.memory_stat_value.setText(str(summary.get("memory_count", 0)))
        self.session_stat_value.setText(str(summary.get("session_turn_count", 0)))

        profile_preview = summary.get("profile_preview") or []
        recent_preview = summary.get("recent_memory_preview") or []
        lines = profile_preview + recent_preview
        if not lines:
            self.memory_preview_label.setText("当前还没有结构化记忆。可以告诉伴侣你的偏好、目标或交流风格。")
        else:
            self.memory_preview_label.setText(" | ".join(lines[:4]))

    def _refresh_character_selector(self, select_id: str | None = None):
        if not hasattr(self, "character_selector"):
            return
        characters = self.bot.list_characters()
        self.character_selector.blockSignals(True)
        self.character_selector.clear()
        selected_index = 0
        for index, character in enumerate(characters):
            label = character.name
            if character.built_in:
                label += " (默认)"
            self.character_selector.addItem(label, userData=character.character_id)
            if character.character_id == (select_id or self.current_character_id):
                selected_index = index
        self.character_selector.setCurrentIndex(selected_index)
        self.character_selector.blockSignals(False)

    def _reload_active_character_view(self):
        profile = self.bot.get_current_character()
        self.current_character_id = profile.character_id
        self.ai_name = profile.name
        self.setWindowTitle(f"AiLoveU - {profile.name}")
        try:
            self.voice.set_speaker_name(self.ai_name)
        except Exception:
            pass
        if hasattr(self, "name_input"):
            self.name_input.setText(self.ai_name)
        if hasattr(self, "character_meta_label"):
            tag_text = " / ".join(profile.tags[:3]) if profile.tags else "本地角色"
            source_text = "默认角色" if profile.built_in else "角色卡导入"
            self.character_meta_label.setText(
                f"当前伴侣：{profile.name}\n来源：{source_text}\n标签：{tag_text}"
            )
        if hasattr(self, "chat_hint_label"):
            self.chat_hint_label.setText(
                f"当前角色：{profile.name}。每个角色的聊天记录、会话上下文和长期记忆都相互隔离。"
            )

        self.chat_history.clear()
        transcript = self.bot.get_transcript(limit=200)
        for item in transcript:
            role = item.get("role")
            if role == "user":
                self.add_message("你", item.get("content", ""), True, speak_voice=False)
            elif role == "assistant":
                self.add_message(profile.name, item.get("content", ""), False, speak_voice=False)

    def _on_character_selected(self, _index: int = -1):
        character_id = self.character_selector.currentData()
        if not character_id or character_id == self.current_character_id:
            return
        try:
            self.bot.switch_character(character_id)
            self._reload_active_character_view()
            self._refresh_memory_panel()
        except Exception as e:
            QMessageBox.warning(self, "切换失败", f"切换角色失败：{e}")

    def import_character_card(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择角色卡 PNG",
            "",
            "PNG Files (*.png)",
        )
        if not file_path:
            return
        try:
            profile = self.bot.import_character_card(file_path)
            self.current_character_id = profile.character_id
            self._refresh_character_selector(select_id=profile.character_id)
            self._reload_active_character_view()
            self._refresh_memory_panel()
            QMessageBox.information(
                self,
                "导入成功",
                f"已导入角色：{profile.name}\n之后该角色会与其他角色使用隔离的聊天记录和记忆。",
            )
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"角色卡解析失败：{e}")

    def _append_chat_html(self, block: str):
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(block)
        self.chat_history.setTextCursor(cursor)
        self.chat_history.ensureCursorVisible()
    
    def add_message(self, sender, message, is_user=False, speak_voice=True):
        speaker = "你" if is_user else html.escape(sender or self.ai_name)
        safe_message = html.escape(message).replace("\n", "<br>")
        align = "right" if is_user else "left"
        bubble_color = "#dbeafe" if is_user else "#f8fafc"
        border_color = "#93c5fd" if is_user else "#d7e0ea"
        meta_color = "#456b8c" if is_user else "#5f6f82"

        block = f"""
        <div style="margin: 12px 0; text-align: {align};">
            <div style="display: inline-block; max-width: 78%; text-align: left;">
                <div style="font-size: 11px; color: {meta_color}; margin-bottom: 4px;">{speaker}</div>
                <div style="background: {bubble_color}; border: 1px solid {border_color}; border-radius: 18px; padding: 12px 14px; color: #1f2d3d; line-height: 1.6;">
                    {safe_message}
                </div>
            </div>
        </div>
        """
        self._append_chat_html(block)
        if speak_voice and (not is_user) and self.use_voice:
            self._speak_with_lipsync(message)
        return

    def _apply_ai_name(self):
        name = ""
        try:
            name = self.name_input.text().strip()
        except Exception:
            name = ""
        if not name:
            return
        self.ai_name = name
        try:
            self.bot.set_ai_name(name)
        except Exception:
            pass
        try:
            self.current_character_id = self.bot.get_current_character().character_id
            self._refresh_character_selector(select_id=self.current_character_id)
            self._reload_active_character_view()
        except Exception:
            pass
        try:
            self.voice.set_speaker_name(name)
        except Exception:
            pass
        self.add_system_message(f"✅ AI昵称已更新为：{name}")

    def _speak_with_lipsync(self, text: str):
        # 在后台合成+播放，避免阻塞 UI，同时驱动 live2d 口型
        def _worker():
            try:
                self.voice.speak_with_word_marks(
                    text,
                    on_start=lambda marks: self.speech_start.emit(marks),
                    on_end=lambda: self.speech_end.emit(),
                )
            except Exception as e:
                self.output_queue.put(("system_message", f"❌ 语音播放出错: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_speech_start(self, marks):
        self._speech_marks = list(marks or [])
        self._speech_t0 = time.monotonic()
        self._mouth_timer.start()

    def _on_speech_end(self):
        self._mouth_timer.stop()
        self._speech_marks = []
        self._speech_t0 = None
        if hasattr(self, "live2d_widget"):
            try:
                self.live2d_widget.set_mouth_open(0.0)
            except Exception:
                pass

    def _tick_mouth(self):
        if not hasattr(self, "live2d_widget"):
            return
        if not self._speech_t0:
            self.live2d_widget.set_mouth_open(0.0)
            return

        t = time.monotonic() - self._speech_t0

        # 根据 word boundary 时间戳做“开合包络”
        mouth = 0.0
        for (s, e) in self._speech_marks:
            if t < s - 0.06:
                break
            if (s - 0.06) <= t <= (s + 0.04):
                # attack
                x = (t - (s - 0.06)) / 0.10
                mouth = max(mouth, x * 0.85)
            elif (s + 0.04) < t < e:
                mouth = max(mouth, 0.85)
            elif e <= t <= (e + 0.08):
                # release
                x = 1.0 - (t - e) / 0.08
                mouth = max(mouth, x * 0.65)

        self.live2d_widget.set_mouth_open(mouth)
    
    def add_system_message(self, message):
        safe_message = html.escape(message).replace("\n", "<br>")
        block = f"""
        <div style="margin: 8px 0; text-align: center;">
            <span style="display: inline-block; background: #eef3f8; color: #5f6f82; border: 1px solid #d8e2ec; border-radius: 999px; padding: 7px 12px; font-size: 12px; line-height: 1.5;">
                {safe_message}
            </span>
        </div>
        """
        self._append_chat_html(block)
        return
    
    def clear_chat(self):
        self.chat_history.clear()
        try:
            self.bot.reset_session()
            profile = self.bot.get_current_character()
            if profile.first_message:
                self.add_message(profile.name, profile.first_message, False, speak_voice=False)
        except Exception:
            pass
        self._refresh_memory_panel()
        self.add_system_message("已为当前角色开启新的会话，本角色的历史记录仍会保留并与其他角色隔离。")
    
    def on_message_received(self, msg_type, content):
        if msg_type == "response":
            self.add_message(self.ai_name, content, False)
            self._refresh_memory_panel()
        elif msg_type == "system_prompt":
            self.add_system_message(f"😊 检测到情绪，AI正在回复...")
        elif msg_type == "system_message":
            self.add_system_message(content)
        elif msg_type == "voice_input":
            # 语音输入当作用户消息发送
            self.add_message("你", content, True)
            threading.Thread(target=self._process_message, args=(content,), daemon=True).start()
        elif msg_type == "error":
            self.add_system_message(f"❌ 发生错误: {content}")
    
    def update_output(self):
        try:
            while not self.output_queue.empty():
                item = self.output_queue.get()
                msg_type, content = item
                self.message_received.emit(msg_type, content)
        except Exception as e:
            print(f"更新输出错误: {e}")
        finally:
            QTimer.singleShot(100, self.update_output)

def main():
    try:
        if hasattr(live2d, "init"):
            live2d.init()
    except Exception:
        raise
    # 🆕 高分屏适配设置必须在实例化 QApplication 之前执行，并直接使用类名调用
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    if hasattr(Qt.ApplicationAttribute, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
        
    # 🆕 在设置完策略之后再实例化 App
    app = QApplication(sys.argv)
    
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f0f0f0"))
    app.setPalette(palette)
    
    window = AiLoveUGUI()
    window.show()
    try:
        sys.exit(app.exec())
    finally:
        try:
            if hasattr(live2d, "dispose"):
                live2d.dispose()
        except Exception as e:
            print(f"Live2D释放失败: {e}")

if __name__ == "__main__":
    main()
