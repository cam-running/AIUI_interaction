# ict 机器人系统代码说明

本目录为机器人项目：

| 项目 | 定位 | 端口 |
| --- | --- | --- |
| `face_voice` | 机器人主服务（管理后台 + 人脸识别签到 + 状态推送） | 34555（主服务）、8765/8766（状态服务） |
| `robot_ai` | 语音交互服务（AIUI 版，话筒 MIC） | 8840（状态查询） |
| `robot_nc` | 语音交互服务（NC 版，头顶 6MIC） | 8841（状态查询） |

三者关系：`face_voice/main_server.py` 是整机管理入口，通过 `start_robotai.sh` / `start_robotnc.sh` 等脚本启停语音服务；状态查询接口根据当前录音模式（1=话筒 MIC、4=胸前 4MIC、6=头顶 6MIC）自动路由到 robot_ai（8840）或 robot_nc（8841）。

---

## 一、face_voice —— 机器人主服务

### 功能概述

1. **管理后台 API（main_server.py）**：基于 FastAPI 的主控服务，提供：
   - 服务启停控制：人脸识别（`start_client.sh`/`stop_client.sh`）、语音交互（AIUI/NC）、TTS 服务
   - 签到管理：签到名单 Excel 上传/导出、签到人数统计（`/headcount_num`）、分组切换与备份
   - 音频相关：音量设置、音色/语言模式切换（中/粤/英，联动 robot_ai、robot_nc 的 AIUI 配置）、任意文本 TTS 播放
   - 大模型配置：模型连通性测试、Dify 配置管理
   - 录音测试接口：录音设备查询、录制与下载
   - AIUI 唤醒状态 / TTS 播放状态查询（转发到 8840/8841）
2. **人脸识别签到客户端（main_client.py）**：通过 WebSocket 接收摄像头视频帧，OpenCV 检测人脸后调用百度 AI 完成人脸识别，识别成功后语音播报并写入签到记录（Excel + 签到文件）
3. **状态管理服务（state_management.py）**：采集语音状态、机器人硬件状态，通过 WebSocket（8765）定时推送到前端，并提供硬件查询 HTTP API（8766）
4. **用户注册服务（face_v.py）**：Flask 服务，用于人脸库用户添加与语音初始化

### 目录结构

```
face_voice/
├── main_server.py          # 主服务入口（FastAPI，端口 34555）
├── main_client.py          # 人脸识别签到客户端
├── state_management.py     # 状态采集与推送服务（WS 8765 / HTTP 8766）
├── face_v.py               # 用户注册/语音初始化服务（Flask）
├── init_voice.py           # 语音合成/提示音生成
├── conf/                   # 配置（basic.py 全局配置、日志配置）
├── middlewares/            # 日志初始化、动作监听
├── models/                 # Pydantic 请求模型
├── utils/                  # 工具集（音频播放、音量控制、百度AI、
│                           #   科大讯飞TTS/识别、AIoT控制、Excel同步等）
├── voice/                  # 提示音音频资源
├── name_file/              # 签到名单 Excel
├── logs/                   # 运行日志
└── *.sh                    # 启停脚本（main_server.sh、start_client.sh 等）
```

---

## 二、robot_ai —— 语音交互服务（AIUI 版）

### 功能概述

机器人 AI 语音交互主程序，完整链路为：

**录音采集（VAD） → ASR 语音识别 → 意图分类（Dify / AIUI 语义） → 技能处理（IntentHandler）或大模型问答（NLP/Dify） → TTS 播放（支持 VAD 实时打断）**

- 入口 `main_robot.py` 中的 `RobotAI` 类根据 `config.yaml` 的 `speech_recognition.service` 配置选择识别后端：
  - `xunfei_linux`：讯飞 Linux SDK（AIUI，本地唤醒）
  - `xunfei_aiui`：讯飞 AIUI（Socket 通道）
  - `qwen_asr`：阿里千问 ASR（阿里云 NLS WebSocket）
  - `baidu_realtime` / `aliyun_asr`：百度实时识别 / 阿里云 ASR
- 意图分类采用后置路由架构：ASR 出文本后先调用 Dify 意图分类（`recognize_intention.chat_with_dify()`），命中技能（rc=0）则走 `IntentHandler` 技能处理，否则进入 NLP/大模型问答路径
- 内置 HTTP 状态服务（端口 8840），对外提供 AIUI 唤醒状态与 TTS 播放状态查询
- TTS 播放过程中持续监听人声（VAD），检测到用户说话立即打断，支持新对话

### 目录结构

```
robot_ai/
├── main_robot.py           # 主程序入口（RobotAI 类）
├── aiui.py                 # AIUI 测试/调试工具
├── build_nuitka.py         # Nuitka 打包脚本
├── config/                 # 配置（config.yaml、action/dify/aiot/回声消除等配置）
├── core/                   # 核心逻辑
│   ├── aiui/recorder.py    # 音频录制器（VAD 静音检测）
│   ├── message_processor.py# 消息处理
│   └── socket_client.py    # Socket 客户端
├── handlers/               # 语音识别与语义处理器
│   ├── aiui/               #   讯飞 AIUI（EventListener、AIUINode、pyaiui）
│   ├── qwen/               #   阿里千问 ASR 处理器（默认主用）
│   ├── baidu/ aliyun/      #   百度/阿里云 ASR 处理器
│   ├── xunfei/             #   讯飞意图/知识/NLP 处理器
│   └── dify/               #   Dify 意图分类与大模型对接
├── strategies/             # 策略层（AIUI流程、确认流程、动作执行、视觉问答）
├── utils/                  # 工具集（TTS客户端、回声消除、AIoT控制、
│                           #   MQTT订阅、状态服务、日志、时间同步等）
├── tts_cache/              # TTS 缓存
├── docker/                 # 代理等辅助服务
├── docs/                   # 文档
└── logs/                   # 运行日志
```

---

## 三、robot_nc —— 语音交互服务（NC / 头顶 6MIC 版）

### 功能概述

`robot_nc` 与 `robot_ai` 同源，是针对**头顶 6 麦克风阵列（NC 板）**的语音交互版本：

- 代码结构与 `robot_ai` 基本一致，主入口同为 `main_robot.py`，状态服务端口改为 **8841**
- 差异点：
  - `core/aiui/` 下新增 `ws_recorder.py`、`ws_pcm_recorder.py`、`audio_segment.py`，适配 NC 板的 WebSocket 音频流采集
  - 新增 `mcp_action_server.py`：基于 MCP（Model Context Protocol）的动作工具服务，暴露机器人动作指令接口（挥手、握手、拥抱、比心、鼓掌等，动作名到动作 ID 映射后调用机器人 HTTP 动作接口），供聆思平台 MCP Tools 节点调用
  - 新增 `play_audio.py`（音频播放）、`test_nc3.py`（NC 板测试）、`tts_cache/pkl_to_pcm.py`（缓存格式转换）

### 目录结构

```
robot_nc/robot_nc/
├── main_robot.py           # 主程序入口（与 robot_ai 同构，状态服务端口 8841）
├── mcp_action_server.py    # MCP 动作工具服务（机器人动作指令）
├── play_audio.py           # 音频播放工具
├── test_nc3.py             # NC 板测试脚本
├── config/                 # 配置（同 robot_ai）
├── core/                   # 核心逻辑（含 NC 专用 ws_recorder / ws_pcm_recorder）
├── handlers/               # 语音识别与语义处理器（同 robot_ai）
├── strategies/             # 策略层（动作执行、AIUI流程等）
├── utils/                  # 工具集（同 robot_ai）
├── tts_cache/              # TTS 缓存（含 pkl_to_pcm 转换）
├── vad_pcm_out/            # VAD 音频调试输出
├── requirements.txt        # 依赖
│                           #   requirements_mcp.txt 为 MCP 服务依赖
└── logs/                   # 运行日志
```

---

## 四、整体协作流程

1. **开机启动**：`face_voice/main_server.sh` 拉起主服务（34555）
2. **开启功能**：
   - 开启人脸识别 → `start_client.sh` 启动签到客户端
   - 开启语音交互 → 按录音模式选择 `start_robotai.sh`（robot_ai，8840）或 `start_robotnc.sh`（robot_nc，8841）
3. **语音交互链路**（robot_ai / robot_nc）：麦克风采集 → VAD 判定说话结束 → ASR 识别 → Dify 意图分类 → 技能处理 / 大模型回答 → TTS 合成播放（说话可打断）
4. **人脸识别链路**（face_voice）：摄像头帧（WebSocket）→ 人脸检测 → 百度 AI 识别 → 签到记录 + 语音播报
5. **状态联动**：`state_management.py` 聚合语音状态与硬件状态推送给前端；主服务的状态查询接口按录音模式自动转发到 8840 / 8841
6. **人脸识别链路**（face_voice）：摄像头帧（WebSocket）→ 人脸检测 → 百度 AI 识别 → 签到记录 + 语音播报

7. **状态联动**：`state_management.py` 聚合语音状态与硬件状态推送给前端；主服务的状态查询接口按录音模式自动转发到 8840 / 8841
