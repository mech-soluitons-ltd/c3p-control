# Top level package definition for c3p controller
#
# Copyright (C) 2024 Cloud3dPrint
#

import sys
import importlib
import pathlib
import logging

# 配置日志
log_path = pathlib.Path.home().joinpath("printer_data/logs/")
log_path.mkdir(parents=True, exist_ok=True)  # 确保日志目录存在
logging.basicConfig(
    filename=log_path.joinpath("c3p_mqtt_py.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def setup_package_path():
    pkg_parent = pathlib.Path(__file__).parent
    sys.path.pop(0)
    sys.path.insert(0, str(pkg_parent))

def main():
    setup_package_path()
    try:
        svr = importlib.import_module("server", "c3p—mqtt")
        svr.main()  # type: ignore
    except ImportError as e:
        logging.error(f"导入模块时出错: {e}")
        print(f"导入模块时出错: {e}")  # 可选：在控制台输出错误信息

if __name__ == "__main__":
    main()
