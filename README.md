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


### 绑定打印设备access code ###
未完成


### WebRTC 监控服务 ###
  - **查看摄像头配置文件**: 
    - ~/c3pcontroller/bin // 进入 bin 目录
    - cat c3p.conf // 查看 c3p.conf 配置

  - **本地拉流观看**:
    - http://pi局域网ip:8080/stream // 访问以下链接进行观看

  - **获取摄像头占用端口**:
    - grep "" /sys/class/video4linux/*/name

  - **使用 MQTT 消息控制摄像头**:
    - 发送 topic：`printerUUID + '/c3p/api/request'` 控制摄像头云端推拉流。事件类型：
    - eventType 10（开启）
    - eventType 11（关闭）
    - {"eventId": 45648,"eventType": 10,"eventDt": 0, "jobId": 0}  // 示例消息
    - 注意监控mrtc.service。如果c3p启动失败，mrtc就不会启动
    - 建议启动c3p.service后，等待1分钟再启动mrtc.service


### 运行服务 ###
  - c3p.service  // cloud3dprint MQTT 服务
  - mrtc.service // cloud3dprint WebRTC 监控服务
  - crowsnest.service   // Klipper 原厂自带的监控服务，如果启动我们的 WebRTC 服务器，则需停止该服务
  - moonraker.service   // Klipper 原厂自带的 API 服务


### Linux 常用命令 ###
  - sudo systemctl daemon-reload  // 重新加载启动系统时引导服务的配置文件
  - sudo systemctl enable *** 	// 服务重启时开机启动
  - sudo systemctl disable ***	// 服务重启时关闭开机启动
  - sudo systemctl status ***	// 查看服务状态
  - sudo systemctl start ***	// 启动服务
  - sudo systemctl restart ***	// 重启服务
  - sudo systemctl stop ***		// 停止服务
  - ls -a  // 查看当前目录下全部文件
  - tail -n 100 ~/printer_data/logs/c3p.log  // 查看最近 100 条日志
  - ipconfig/all  // 回车，能够查看本机的 IP、网关、MAC 地址信息
  - arp -a  // 查询本地局域网中所有与本机通信的监控设备 IP 地址、MAC 地址等
  - chmod 777 ***  // 给服务添加可执行权限（*** 指的是服务名称，比如：mrtc.service）
  - cat /etc/resolv.conf  // 查询 Linux 系统设备的 DNS


