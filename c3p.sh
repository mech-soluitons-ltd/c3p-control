#!/bin/bash

# 定义 Moonraker 目录路径
MOONRAKER_PATH="~/moonraker"
eval MOONRAKER_PATH="$MOONRAKER_PATH"

# 检查 Moonraker 目录是否存在
if [ ! -d "$MOONRAKER_PATH" ]; then
  echo "Moonraker directory not found at $MOONRAKER_PATH"
  exit 1
fi

# 切换到 Moonraker 目录并获取版本号
cd "$MOONRAKER_PATH" || { echo "无法切换到 Moonraker 目录"; exit 1; }
VERSION=$(git describe --tags --dirty)

# 返回上一级目录
cd .. || { echo "无法返回上一级目录"; exit 1; }

# 判断版本号是否小于0.9并处理
if [[ $(echo -e "v0.9\n$VERSION" | sort -V | head -n 1) == "$VERSION" ]]; then
  echo "Moonraker version 小于 0.9: $VERSION"
  rm -rf ~/moonraker  
  echo "正在克隆新的Moonraker版本到 ~/moonraker..."
  
  # 执行克隆操作并检查是否成功
  if git clone https://gitee.com/MrCakeFuck/moonraker.git ~/moonraker; then
    echo "Moonraker 克隆成功"
  else
    echo "克隆 Moonraker 失败"
    exit 1
  fi
  echo "克隆完成，准备继续执行后续代码..."
elif [ -z "$VERSION" ]; then
  echo "无法获取 Moonraker version"
  if git clone https://gitee.com/MrCakeFuck/moonraker.git ~/moonraker; then
    echo "Moonraker 克隆成功"
  else
    echo "克隆 Moonraker 失败"
    exit 1
  fi
  echo "克隆完成，准备继续执行后续代码..."
else
  echo "Moonraker version: $VERSION"  # Moonraker version: v0.9.3-1-g4e00a07
fi

# 获取脚本所在目录
SCRIPT_DIR=$(dirname "$(realpath "$0")") 
echo "脚本所在目录: $SCRIPT_DIR"

# 提取第二个文件夹名称
USER_NAME=$(echo "$SCRIPT_DIR" | awk -F'/' '{print $3}')
echo "用户名称: $USER_NAME"

# 定义服务文件内容
SERVICE_FILE_CONTENT="[Unit]
Description=C3P Printer Controller for Klipper SV1
Requires=network-online.target
After=network-online.target
Before=moonraker.service

[Install]
WantedBy=multi-user.target
[Service]
Type=simple
User=$USER_NAME
SupplementaryGroups=moonraker-admin
RemainAfterExit=yes
WorkingDirectory=$SCRIPT_DIR
ExecStart=python3 $SCRIPT_DIR/c3p-control/c3p_mqtt.py
Restart=always
RestartSec=10
"

# 创建服务文件
echo "$SERVICE_FILE_CONTENT" | sudo tee /etc/systemd/system/c3p.service > /dev/null
echo "服务文件已创建: /etc/systemd/system/c3p.service"

echo "正在创建c3p-mqtt.cfg的符号链接..."  
ln -s ~/printer_data/config/c3p-mqtt.cfg ~/KlipperScreen/config/c3p-mqtt.cfg

# 重新加载系统服务并启动
sudo systemctl daemon-reload
echo "系统服务已重新加载"
sudo systemctl restart c3p.service
echo "服务已启动: c3p.service"
sudo systemctl enable c3p.service
echo "服务已设置为开机自启"

# 输出服务状态
sudo systemctl status c3p.service