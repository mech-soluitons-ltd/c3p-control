## C3P control for Klipper SV1
C3P control 是一个基于于 Klipper 3D打印机的控制器软件。它通过 MQTT 协议与打印机进行通信,实现远程监控和控制功能。

### 主要功能

- 通过 MQTT 协议实现与打印机的双向通信
- 支持打印机状态监控(温度、位置、打印进度等)
- 支持远程打印控制(开始/暂停/取消打印)
- 支持网络摄像头图像获取
- 自动配置 Moonraker 服务
- 系统服务自动安装和管理

### 主要组件

- **c3p.sh**: 安装脚本,负责:
  - 检查并更新 Moonraker 版本
  - 创建系统服务
  - 配置开机自启动
  - 执行以下命令安装: `chmod +x c3p.sh && ./c3p.sh`
  
- **c3p_mqtt.py**: 主程序入口,负责:
  - 配置日志系统
  - 初始化包路径
  - 加载服务模块

- **server.py**: 核心服务模块,负责:
  - MQTT 配置管理
  - Moonraker 配置文件管理
  - 设备注册和认证

- **mqtt_listener.py**: MQTT 监听器,负责:
  - 监听指定topic (deviceUUID/c3p/api/request)
  - WebSocket 连接管理
  - 打印机状态监控
  - 消息处理和转发

### 安装要求

- Python 3.7+
- Moonraker v0.9+
- 网络连接

### 日志

所有组件的日志文件统一存储在 `~/printer_data/logs/` 目录下:
- MQTT 相关日志: `c3p_mqtt_py.log`
