from __future__ import annotations
import base64
import json
import time
import asyncio
import urllib.request
import logging
from tornado.websocket import websocket_connect
from typing import Optional, Dict, Any, Callable
import random
import string
import os

class MQTTConfig:
    """MQTT 配置类"""
    # 默认配置
    DEFAULT_API_HOST = "http://127.0.0.1"
    
    # MQTT 主题定义
    TOPICS = {
        'printer_status': "c3p/printer/status",    
        'print_status': "c3p/print/status",        
        'command': "{instance_name}/c3p/api/request",  
        'response': "{instance_name}/c3p/api/response"  
    }

    # 消息方法定义
    METHODS = {
        'webcam_snapshot': "webcam.snapshot",      
        'print_new': "print.new",          
        'print_progress': "print.progress", 
        'print_status': "print.status", 
        'printer_status': "printer.status",        
    }

class MQTTListener:
    def __init__(self, config):
        self.server = config.get_server()
        self.mqtt = self.server.load_component(config, 'mqtt')
        self.instance_name = self.mqtt.get_instance_name()
        
        # 配置日志
        self.setup_logging()
        
        # 配置
        self.config = {
            'moonraker_api': MQTTConfig.DEFAULT_API_HOST,
            'instance_name': self.instance_name
        }
        
        self.mqtt.moonraker_status_topic = f'server/will/{self.instance_name}'
        
        
        # Websocket 配置
        self.ws_url = f"ws://{self.config['moonraker_api'].replace('http://', '')}/websocket"
        self.ws_client = None
        
        # 状态管理
        self.last_status_update = time.time()
        self.status_timeout = 5
        self.stop_status_check = None
        
        # 注册监听器
        self.register_listeners()
        
        # 启动 WebSocket 连接
        try:
            asyncio.create_task(self.connect_websocket())
        except Exception as e:
            self.logger.error(f"Task creation failed: {e}")
        
        # 状态缓存
        self.previous_status_data = None
        self.same_status_count = 0
        self.max_same_status_count = 100

    def setup_logging(self):
        """配置日志系统"""
        # 创建日志记录器
        self.logger = logging.getLogger('mqtt_listener')
        self.logger.setLevel(logging.INFO)
        
        # 设置日志文件路径
        log_dir = os.path.expanduser('~/printer_data/logs')
        os.makedirs(log_dir, exist_ok=True)

        # 设置日志文件路径
        log_file = os.path.join(log_dir, 'c3p_mqtt_py.log')
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, mode='w')
        file_handler.setLevel(logging.INFO)
        
        # 设置日志格式
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # 添加处理器到记录器
        self.logger.addHandler(file_handler)
        
        # 记录初始化消息
        self.logger.info("MQTT监听器已启动")

    async def _init_test_message(self):
        """延迟发送测试消息"""
        try:
            # 等待 MQTT 连接建立
            await asyncio.sleep(2)
            self.logger.info("开始发送初始化测试消息")
            # self.send_error_message("测试消息")
        except Exception as e:
            self.logger.error(f"发送初始化测试消息失败: {str(e)}")

    def register_listeners(self):
        """注册MQTT主题监听"""
        topic = MQTTConfig.TOPICS['command'].format(instance_name=self.instance_name)
        self.mqtt.subscribe_topic(topic, self._handle_message, qos=1)
        self.logger.info(f"已订阅MQTT主题: {topic}")

    def get_message_handler(self, method_name: str) -> Optional[Callable]:
        """获取消息处理器"""
        handlers = {
            MQTTConfig.METHODS['webcam_snapshot']: self.handle_webcam_snapshot,
            MQTTConfig.METHODS['print_new']: self.handle_print_new,
            MQTTConfig.METHODS['printer_status']: None  # 忽略状态消息
        }
        return handlers.get(method_name)

    async def _handle_message(self, payload):
        """处理MQTT消息"""
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            data = json.loads(payload)
            self.logger.info(f"收到消息: {data}")
            
            method = data.get('method', '')
            handler = self.get_message_handler(method)
            
            if handler:
                await handler(data)
                self.logger.info(f"处理完成: {method}")
            else:
                self.logger.warning(f"未知的方法: {method}")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解码错误: {str(e)}")
            # self.send_error_message(f"无效的JSON格式: {str(e)}")
        except Exception as e:
            self.logger.error(f"处理消息时出错: {str(e)}")
            # self.send_error_message(str(e))

    def handle_webcam_snapshot(self, payload: Dict[str, Any] = None):
        """处理摄像头快照请求"""
        try:
            self.logger.info("开始获取摄像头快照")
            
            snapshot_url = f"{self.config['moonraker_api']}/webcam/snapshot"
            self.logger.info(f"请求URL: {snapshot_url}")
            
            snapshot_url_with_params = f"{snapshot_url}?timestamp={int(time.time())}"
            response = urllib.request.urlopen(snapshot_url_with_params)
            image_base64 = base64.b64encode(response.read()).decode('utf-8')
            self.logger.info("成功获取并编码图片")
            
            self.send_snapshot_response("success", image_base64)
            
        except urllib.request.HTTPError as e:
            error_msg = f"请求摄像头快照失败: {str(e)}"
            self.logger.error(error_msg)
            self.send_snapshot_response(error_msg)
        except Exception as e:
            error_msg = f"处理摄像头快照失败: {str(e)}"
            self.logger.error(error_msg)
            self.send_snapshot_response(error_msg)

    def send_snapshot_response(self, status: str, value: Optional[str] = None):
        """发送摄像头快照响应"""
        response_payload = {
            "method": MQTTConfig.METHODS['webcam_snapshot'],
            "params": {
                "status": status,
            }
        }
        if value:
            response_payload["params"]["value"] = value

        self.publish_message(
            MQTTConfig.TOPICS['response'].format(**self.config),
            response_payload,
            qos=0
        )
        self.logger.info("已发送摄像头快照响应")

    async def handle_print_new(self, payload: Dict[str, Any]):
        """处理新打印任务"""
        try:
            # 获取参数
            params = payload.get('params', {})
            file_key = params.get('fileKey')
            file_url = params.get('fileUrl')
            file_name = params.get('fileName')
            job_uuid = params.get('printjobuuid')

            if not all([file_key, file_url, file_name, job_uuid]):
                raise ValueError("缺少必要参数")

            self.logger.info(f"处理打印任务: {file_name}, fileKey: {file_key}")
            
            # 使用 urllib 替代 requests
            url = f"{self.config['moonraker_api']}/server/files/directory?path=gcodes"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, urllib.request.urlopen, url)
            data = await loop.run_in_executor(None, response.read)
            files = json.loads(data).get('result', {}).get('files', [])
            self.logger.info(f"文件列表: {files}")

            # 查找匹配的文件
            for file in files:
                parts = file['filename'].split('-@-')
                if len(parts) > 1 and parts[1] == file_key:
                    new_name = f"{parts[0]}-@-{job_uuid}-@-{file_key}.gcode"
                    self.logger.info(f"找到匹配文件: {file['filename']} -> {new_name}")
                    return await self.handle_existing_file(file['filename'], new_name, job_uuid)

            # 未找到匹配文件，处理新文件
            self.logger.info("未找到匹配文件，开始下载新文件")
            return await self.handle_new_file(params)

        except Exception as e:
            error_msg = f"处理打印任务失败: {str(e)}"
            self.logger.error(error_msg)
            status_payload = {
                "method": MQTTConfig.METHODS['print_status'],
                "params": {
                    "job_uuid": job_uuid,
                    "state": 'error',
                    "message": error_msg
                },
                "printerUUID": self.instance_name
            }
            self.publish_message(
                MQTTConfig.TOPICS['print_status'],
                status_payload
            )
            self.publish_message(
                MQTTConfig.TOPICS['response'].format(**self.config),
                status_payload
            )
            return False

    async def handle_existing_file(self, old_name: str, new_name: str, job_uuid: str) -> bool:
        """处理已存在的文件"""
        try:
            # 重命名文件
            rename_url = f"{self.config['moonraker_api']}/server/files/move"
            rename_data = json.dumps({
                'source': f"/gcodes/{old_name}",
                'dest': f"/gcodes/{new_name}"
            }).encode('utf-8')
            
            loop = asyncio.get_event_loop()
            req = urllib.request.Request(
                rename_url,
                data=rename_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            await loop.run_in_executor(None, urllib.request.urlopen, req)
            
            # 开始打印
            print_url = f"{self.config['moonraker_api']}/printer/print/start"
            print_data = json.dumps({
                'filename': f"/gcodes/{new_name}"
            }).encode('utf-8')
            
            req = urllib.request.Request(
                print_url,
                data=print_data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            await loop.run_in_executor(None, urllib.request.urlopen, req)
            
            state_msg = f"文件重命名并开始打印: {new_name}"
            self.logger.info(state_msg)

            status_payload = {
                "method": MQTTConfig.METHODS['print_status'],
                "params": {
                    "job_uuid": job_uuid,
                    "state": 'printing',
                    "message": state_msg
                },
                "printerUUID": self.instance_name
            }
            self.publish_message(
                MQTTConfig.TOPICS['print_status'],
                status_payload
            )
            self.publish_message(
                MQTTConfig.TOPICS['response'].format(**self.config),
                status_payload
            )
            return True
            
        except Exception as e:
            error_msg = f"处理已存在文件失败: {str(e)}"
            self.logger.error(error_msg)
            status_payload = {
                "method": MQTTConfig.METHODS['print_status'],
                "params": {
                    "job_uuid": job_uuid,
                    "state": 'error',
                    "message": error_msg
                },
                "printerUUID": self.instance_name
            }
            self.publish_message(
                MQTTConfig.TOPICS['print_status'],
                status_payload
            )
            self.publish_message(
                MQTTConfig.TOPICS['response'].format(**self.config),
                status_payload
            )
            return False

    async def handle_new_file(self, params: Dict[str, Any]) -> bool:
        """处理新文件"""
        try:
            file_name = params['fileName']
            file_key = params['fileKey']
            job_uuid = params['printjobuuid']
            file_url = params['fileUrl']
            
            # 构造新文件名
            new_name = f"{file_name}-@-{job_uuid}-@-{file_key}.gcode"
            
            # 下载文件并监控进度
            loop = asyncio.get_event_loop()
            req = urllib.request.Request(file_url)
            response = await loop.run_in_executor(None, urllib.request.urlopen, req)
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            file_content = bytearray()
            last_report_time = time.time()
            last_report_progress = 0
            
            while True:
                chunk = await loop.run_in_executor(None, response.read, 8192)
                if not chunk:
                    break
                    
                file_content.extend(chunk)
                downloaded_size += len(chunk)
                
                current_time = time.time()
                current_progress = int(downloaded_size / total_size * 100)
                
                # 检查是否满足发送消息的条件
                if (current_time - last_report_time >= 3) or (current_progress - last_report_progress >= 5):
                    self._send_progress_status(
                        job_uuid=job_uuid,
                        file_name=file_name,
                        progress=current_progress,
                        uploaded=downloaded_size,
                        total=total_size
                    )
                    last_report_time = current_time
                    last_report_progress = current_progress
            
            # 上传文件到打印机
            boundary = '----WebKitFormBoundary' + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
            
            content_type = f'multipart/form-data; boundary={boundary}'
            
            # 构建 multipart form-data
            body = []
            # 添加表单字段
            body.append(f'--{boundary}'.encode())
            body.append(b'Content-Disposition: form-data; name="path"')
            body.append(b'')
            body.append(b'')
            
            body.append(f'--{boundary}'.encode())
            body.append(b'Content-Disposition: form-data; name="filename"')
            body.append(b'')
            body.append(new_name.encode())
            
            body.append(f'--{boundary}'.encode())
            body.append(b'Content-Disposition: form-data; name="print"')
            body.append(b'')
            body.append(b'true')
            
            # 添加文件内容
            body.append(f'--{boundary}'.encode())
            body.append(f'Content-Disposition: form-data; name="file"; filename="{new_name}"'.encode())
            body.append(b'Content-Type: application/octet-stream')
            body.append(b'')
            body.append(bytes(file_content))
            
            body.append(f'--{boundary}--'.encode())
            body.append(b'')
            
            body = b'\r\n'.join(body)
            
            req = urllib.request.Request(
                f"{self.config['moonraker_api']}/server/files/upload",
                data=body,
                headers={'Content-Type': content_type},
                method='POST'
            )
            
            await loop.run_in_executor(None, urllib.request.urlopen, req)
            
            # 检查打印机状态
            status_url = f"{self.config['moonraker_api']}/printer/objects/query?print_stats"
            response = await loop.run_in_executor(None, urllib.request.urlopen, status_url)
            printer_status = json.loads(await loop.run_in_executor(None, response.read))
            print_state = printer_status.get('result', {}).get('status', {}).get('print_stats', {}).get('state', 'error')
            
            if print_state == 'printing':
                self.logger.info(f"文件 {new_name} 上传成功并已开始打印")
                
                # 发送任务状态消息
                status_payload = {
                    "method": MQTTConfig.METHODS['print_status'],
                    "params": {
                        "job_uuid": job_uuid,
                        "state": 'printing',
                        "message": f"文件 {new_name} 正在打印"
                    },
                    "printerUUID": self.instance_name
                }
                self.publish_message(
                    MQTTConfig.TOPICS['print_status'],
                    status_payload
                )
                self.publish_message(
                    MQTTConfig.TOPICS['response'].format(**self.config),
                    status_payload
                )
                
                return True
            else:
                error_msg = f"文件已上传但未开始打印，当前状态: {print_state}"
                self.logger.error(error_msg)
                status_payload = {
                    "method": MQTTConfig.METHODS['print_status'],
                    "params": {
                        "job_uuid": job_uuid,
                        "state": print_state,
                        "message": error_msg
                    },
                    "printerUUID": self.instance_name
                }
                self.publish_message(
                    MQTTConfig.TOPICS['print_status'],
                    status_payload
                )
                self.publish_message(
                    MQTTConfig.TOPICS['response'].format(**self.config),
                    status_payload
                )
                return False
                
        except Exception as e:
            error_msg = f"处理新文件失败: {str(e)}"
            self.logger.error(error_msg)
            status_payload = {
                "method": MQTTConfig.METHODS['print_status'],
                "params": {
                    "job_uuid": job_uuid,
                    "state": 'error',
                    "message": error_msg
                },
                "printerUUID": self.instance_name
            }
            self.publish_message(
                MQTTConfig.TOPICS['print_status'],
                status_payload
            )
            self.publish_message(
                MQTTConfig.TOPICS['response'].format(**self.config),
                status_payload
            )
            # self.send_error_message(error_msg)
            return False

    def _send_progress_status(self, file_name: str, job_uuid: str, progress: int, uploaded: int = 0, total: int = 0):
        """发送进度状态"""
        status = {
            "progress": progress,
            "file_name": file_name,
            "job_uuid": job_uuid,
            "uploaded": uploaded,
            "total": total,
            # "timestamp": int(time.time())
        }
        
        status_payload = {
            "method": MQTTConfig.METHODS['print_progress'],
            "params": status,
            "printerUUID": self.instance_name
        }
        
        self.publish_message(
            MQTTConfig.TOPICS['response'],
            status_payload
        )


    def publish_message(self, topic: str, payload: Dict[str, Any], retain: bool = False, qos: int = 1):
        """发布消息到 MQTT"""
        try:
            # 如果 topic 中包含 {instance_name}，进行替换
            if "{instance_name}" in topic:
                topic = topic.format(instance_name=self.instance_name)
                
            message = json.dumps(payload, ensure_ascii=False)
            self.mqtt.publish_topic(topic, message, retain=retain, qos=qos)
            self.logger.info(f"消息已发布到 MQTT - Topic: {topic}")
            # self.logger.info(f"消息内容: {message}")
        except Exception as e:
            self.logger.error(f"发布 MQTT 消息失败: {str(e)}")


    def cleanup(self):
        """清理资源"""
        try:
            if self.stop_status_check:
                self.stop_status_check.set()
            if self.ws_client:
                self.ws_client.close()
        except Exception as e:
            self.logger.error(f"清理资源时出错: {str(e)}")

    async def connect_websocket(self):
        """连接到 Moonraker Websocket"""
        try:
            self.logger.info("正在连接到 WebSocket...")
            self.ws_client = await websocket_connect(self.ws_url)
            self.logger.info("WebSocket 连接成功")
            
            # 订阅状态更新
            await self.get_printer_status()
            
            # 启动状态检查
            self.stop_status_check = asyncio.Event()
            asyncio.create_task(self.check_status_updates())
            
            # 开始接收消息
            while True:
                msg = await self.ws_client.read_message()
                if msg is None:
                    self.logger.warning("WebSocket 连接已关闭")
                    break
                    
                await self.handle_websocket_message(msg)
                
        except Exception as e:
            self.logger.error(f"WebSocket 连接失败: {str(e)}")
            if self.stop_status_check:
                self.stop_status_check.set()
            await asyncio.sleep(5)
            asyncio.create_task(self.connect_websocket())

    async def handle_websocket_message(self, msg: str):
        """处理 websocket 消息"""
        try:
            data = json.loads(msg)
            # self.logger.info(f"收到消息: {data}")
            
            if "result" in data:
                status = data['result'].get('status', {})
                self.process_status_message(status)
            else:
                # self.logger.warning("收到不相关的消息，忽略")
                pass
                
        except json.JSONDecodeError:
            self.logger.error("JSON解析错误")
        except Exception as e:
            self.logger.error(f"处理 WebSocket 消息失败: {str(e)}")

    def process_status_message(self, status: Dict[str, Any]):
        """处理状态消息"""
        if 'webhooks' in status or 'print_stats' in status:
            # self.logger.info("处理包含 'webhooks' 或 'print_stats' 的消息")
            
            status_data = {
                "method": "printer.status",
                "printerUUID": self.instance_name,
                "params": {
                    "state": status.get('webhooks', {}).get('state', 'unknown'),
                    "message": status.get('webhooks', {}).get('state_message', ''),
                    "print_stats": status.get('print_stats', {}),
                    # "timestamp": int(time.time())
                }
            }
            
            # 检查状态是否变化
            if status_data != self.previous_status_data:
                self.logger.info("状态已变化，发送消息")
                self.publish_status_message(status_data)
                self.previous_status_data = status_data
                self.same_status_count = 0
            else:
                self.same_status_count += 1
                # self.logger.info(f"状态未变化，计数: {self.same_status_count}")
                if self.same_status_count >= self.max_same_status_count:
                    # self.logger.info("状态未变化达到10次，发送消息")
                    self.publish_status_message(status_data)
                    self.same_status_count = 0
        else:
            self.logger.warning("消息中缺少 'webhooks' 和 'print_stats'，忽略")

    def publish_status_message(self, status_data):
        """发布状态消息到 MQTT"""
        self.publish_message(
            MQTTConfig.TOPICS['printer_status'],
            status_data,
            retain=True,
            qos=1
        )
        self.logger.info(f"已发送状态消息: {status_data}")

    async def check_status_updates(self):
        """检查状态更新"""
        self.logger.info("状态更新检查任务已启动")
        check_count = 0
        
        while not self.stop_status_check.is_set():
            try:
                current_time = time.time()
                check_count += 1
                self.logger.info(f"第 {check_count} 次检查状态更新")
                # self.logger.info(f"距离上次更新: {current_time - self.last_status_update}秒")
                
                if current_time - self.last_status_update > self.status_timeout:
                    # self.logger.info("开始获取打印机状态")
                    await self.get_printer_status()
                else:
                    self.logger.info("未到更新时间")
                    
            except Exception as e:
                self.logger.error(f"状态更新检查失败: {str(e)}")
                import traceback
                self.logger.error(f"错误详情: {traceback.format_exc()}")
            
            # self.logger.info("等待300秒后进行下一次检查...")
            await asyncio.sleep(2)

    async def get_printer_status(self) -> Dict[str, Any]:
        """获取打印机状态"""
        try:
            # self.logger.info("正在获取打印机状态...")
            
            # 构造查询请求
            request = {
                "jsonrpc": "2.0",
                "method": "printer.objects.query",
                "params": {
                    "objects": {
                        "webhooks": None,
                        "print_stats": ["state", "filename"]
                    }
                },
                "id": time.time()
            }
            
            # 发送请求并等待响应
            if self.ws_client:
                # self.logger.info("发送状态查询请求...")
                await self.ws_client.write_message(json.dumps(request))
            else:
                self.logger.error("WebSocket 客户端未连接")
                
        except Exception as e:
            self.logger.error(f"获取打印机状态失败: {str(e)}")
            return {
                "state": "error",
                "message": f"获取状态失败: {str(e)}",
                # "timestamp": int(time.time())
            }


def load_component(config):
    return MQTTListener(config)
