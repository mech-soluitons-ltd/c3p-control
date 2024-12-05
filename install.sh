#!/bin/bash

# 定义路径变量
MOONRAKER_PATH="${HOME}/moonraker"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"
USER_NAME=$(echo "$SCRIPT_DIR" | awk -F'/' '{print $3}')

# 检查用户权限
verify_ready()
{
    if [ "$EUID" -eq 0 ]; then
        echo "此脚本不能以root身份运行"
        exit -1
    fi
}

# 检查并更新 Moonraker
check_moonraker()
{
    if [ ! -d "$MOONRAKER_PATH" ]; then
        echo "Moonraker 目录不存在，准备克隆..."
        install_moonraker
        return
    fi

    cd "$MOONRAKER_PATH" || exit 1
    VERSION=$(git describe --tags --dirty)
    
    if [[ $(echo -e "v0.9\n$VERSION" | sort -V | head -n 1) == "$VERSION" ]]; then
        echo "Moonraker 版本需要更新: $VERSION"
        rm -rf "$MOONRAKER_PATH"
        install_moonraker
    else
        echo "Moonraker 版本正常: $VERSION"
    fi
}

# 安装 Moonraker
install_moonraker()
{
    echo "正在克隆 Moonraker..."
    if git clone https://gitee.com/MrCakeFuck/moonraker.git "$MOONRAKER_PATH"; then
        echo "Moonraker 克隆成功"
    else
        echo "克隆 Moonraker 失败"
        exit 1
    fi
}

# 创建并配置服务
setup_service()
{
    echo "正在配置 C3P 服务..."
    SERVICE_FILE="/etc/systemd/system/c3p.service"
    
    # 创建服务文件
    cat << EOF | sudo tee $SERVICE_FILE > /dev/null
[Unit]
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
ExecStart=python3 $SCRIPT_DIR/c3p_mqtt.py
Restart=always
RestartSec=10
EOF

    echo "服务文件已创建: $SERVICE_FILE"
}

# 创建配置文件链接
create_links()
{
    echo "正在创建配置文件链接..."
    ln -sf ~/printer_data/config/c3p-mqtt.cfg ~/KlipperScreen/config/c3p-mqtt.cfg
}

# 重启服务
restart_service()
{
    echo "正在重启服务..."
    sudo systemctl daemon-reload
    sudo systemctl restart c3p.service
    sudo systemctl enable c3p.service
    echo "服务已启动并设置为开机自启"
    
    # 显示服务状态
    sudo systemctl status c3p.service
}

# 主程序
main()
{
    # 强制脚本在错误时退出
    set -e
    
    # 执行安装步骤
    verify_ready
    check_moonraker
    setup_service
    create_links
    restart_service
    
    echo "安装完成！"
}

# 运行主程序
main