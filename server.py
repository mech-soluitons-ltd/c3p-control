#!/usr/bin/env python3
import urllib.request
import pathlib
import logging
import json
import configparser
import uuid
import socket
import os
import subprocess
import asyncio

# 配置日志
log_path = pathlib.Path.home().joinpath("printer_data/logs")
log_path.mkdir(parents=True, exist_ok=True)  # 确保日志目录存在
logging.basicConfig(
    filename=log_path.joinpath("c3p_mqtt_py.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Server:
    def __init__(self, data_path: str) -> None:
        self.c3p_registration_url = "http://35.183.199.58:1000/c3p/device/registration"
        self.controller_software_version = 'v0.0.01'
        self.data_path = pathlib.Path(data_path).expanduser().resolve()
        self.get_controller_info()

    def get_local_ip4(self) -> str:
        return self._get_ip("8.8.8.8")

    def _get_ip(self, host: str) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((host, 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception as e:
            logging.debug(f"Error - Get local IP address: {e}")
            return "0.0.0.0"

    def get_controller_info(self) -> None:
        self.hostname = socket.gethostname()
        self.private_ip4 = self.get_local_ip4()
        self.public_ip4 = self.fetch_public_ip()
        self.model = self.get_system_model()
        self.total_storage, self.remaining_storage = self.get_storage_info()
        self.mac_address = self.get_mac_address()
        self.device_internal_uuid = self.generate_device_uuid()

    def fetch_public_ip(self) -> str:
        return self._fetch_data('https://api.ipify.org?format=json', 'ip')

    def _fetch_data(self, url: str, key: str) -> str:
        try:
            with urllib.request.urlopen(url) as response:
                return json.loads(response.read().decode('utf-8'))[key]
        except Exception:
            return '0.0.0.0'

    def get_system_model(self) -> str:
        return self._execute_command('uname -r')

    def get_storage_info(self) -> tuple:
        disk_info = self._execute_command('df -k /').splitlines()[1].split()
        total_storage = int(disk_info[1]) // 1024
        remaining_storage = int(disk_info[3]) // 1024
        return total_storage, remaining_storage

    def _execute_command(self, command: str) -> str:
        return subprocess.check_output(command.split()).decode('utf-8').strip()

    def get_mac_address(self) -> str:
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return ":".join([mac[e:e + 2] for e in range(0, 11, 2)])

    def generate_device_uuid(self) -> str:
        return uuid.uuid3(uuid.NAMESPACE_DNS, self.mac_address).hex

    def build_registration_request(self):
        return {
            "public_ip4": self.public_ip4,
            "private_ip4": self.private_ip4,
            "mac_address": self.mac_address,
            "device_internal_uuid": self.device_internal_uuid,
            "hostname": self.hostname,
            "model": self.model,
            "total_storage": self.total_storage,
            "remaining_storage": self.remaining_storage,
            "controller_software_version": self.controller_software_version
        }

    def register_controller(self):
        headers = self.get_request_headers()
        message = json.dumps(self.build_registration_request())
        self.send_registration_request(headers, message)
        self.create_mqtt_config()

    def get_request_headers(self):
        return {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json"
        }

    def send_registration_request(self, headers, message):
        req = urllib.request.Request(
            self.c3p_registration_url,
            data=message.encode('utf-8'),
            headers=headers,
            method='POST'
        )
        with urllib.request.urlopen(req) as response:
            auth_params = json.loads(response.read().decode('utf-8'))
            self.auth_token = auth_params.get("jwtToken", "")
            self.access_code = auth_params.get("accessCode", "")

    def create_mqtt_config(self):
        config = configparser.ConfigParser()
        self.setup_mqtt_config(config)
        mqtt_config_path = self.data_path.joinpath("config/c3p-mqtt.cfg")
        mqtt_config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 写入配置文件
            self.write_config_to_file(config, mqtt_config_path)
            logging.info("c3p_mqtt.cfg 文件已成功生成。")
            
            # 追加到 moonraker 配置
            self.append_to_moonraker_config()
            
            # 这里重启服务
            subprocess.run(["systemctl", "restart", "moonraker"], check=True)
            logging.info("Moonraker 服务已成功重启。")
            
        except Exception as e:
            logging.error(f"生成配置文件或重启服务时出错: {e}")
            # 这里可以选择抛出异常或进行其他处理

    def setup_mqtt_config(self, config):
        config.add_section('mqtt')
        config.set('mqtt', 'address', '35.183.199.58')
        config.set('mqtt', 'port', '1883')
        config.set('mqtt', 'mqtt_protocol', 'v5')
        config.set('mqtt', 'enable_moonraker_api', 'True')
        config.set('mqtt', 'status_interval', '1')
        config.set('mqtt', 'status_objects',
                    'webhooks=state,state_message\n'
                    'virtual_sdcard=progress,is_active\n'
                    'idle_timeout=state\n'
                    'toolhead=position,print_time,homed_axes\n'
                    'print_stats\n'
                    'display_status=progress\n'
                    'extruder=temperature,target,power\n'
                    'heater_bed=temperature,target,power\n'
                    'fan=speed,rpm'
                    )
        config.set('mqtt', 'publish_split_status', 'False')
        config.set('mqtt', 'default_qos', '0')
        config.set('mqtt', 'api_qos', '0')
        config.set('mqtt', 'username', self.device_internal_uuid)
        config.set('mqtt', 'password', self.auth_token)
        config.set('mqtt', 'client_id', self.device_internal_uuid)
        config.set('mqtt', 'instance_name', self.device_internal_uuid)
        config.add_section('mqtt_listener')

    def write_config_to_file(self, config, path):
        with path.open('w') as configfile:
            config.write(configfile)

    def append_to_moonraker_config(self):
        self.moonraker_path = self.data_path.joinpath("config/moonraker.conf")
        with self.moonraker_path.open('a+') as moonraker_file:
            moonraker_file.seek(0)
            content = moonraker_file.read()
            if "[include c3p-mqtt.cfg]" not in content:
                moonraker_file.write("\n[include c3p-mqtt.cfg]\n")
                logging.info("已添加 [include c3p-mqtt.cfg] 到 moonraker.conf。")
            else:
                logging.info("[include c3p-mqtt.cfg] 已存在，未执行任何操作。")

    def write_mqtt_listener_config(self):
        mqtt_listener_path = pathlib.Path(__file__).parent.joinpath("mqtt_listener.py")
        components_path = pathlib.Path.home().joinpath("moonraker/moonraker/components")
        components_path.mkdir(parents=True, exist_ok=True)
        config_file_path = components_path.joinpath("mqtt_listener.py")

        with mqtt_listener_path.open('r') as source_file:
            config_content = source_file.read()

        with config_file_path.open('w') as configfile:
            configfile.write(config_content)
        logging.info("mqtt_listener.py 配置文件已成功写入到 ~/moonraker/moonraker/components/ 文件夹中。")

def main():
    data_path = "~/printer_data"
    server = Server(data_path)
    server.write_mqtt_listener_config()
    server.register_controller()

if __name__ == "__main__":
    main()