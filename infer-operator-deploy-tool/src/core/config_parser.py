import json
from typing import Dict, Any, Optional
import os
import logging


ROLE_PREFILL = "prefill"
ROLE_DECODE = "decode"
ROLE_ROUTER = "router"

hardware_type_whitelist = ["module-910b-8", "module-a3-16", "module-a3-16-super-pod"]

class ConfigParser:
    """配置文件解析器，用于解析JSON格式的用户配置文件"""

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path

    @staticmethod
    def _validate_role_config(role_name: str, role_config: Dict[str, Any]) -> None:
        """
        验证角色配置是否包含必要的字段
        """
        if "image" not in role_config:
            raise ValueError(f"{role_name}角色配置缺少image字段")

        if "hardware_type" not in role_config:
            raise ValueError(f"{role_name}角色配置缺少hardware_type字段")
        if role_config["hardware_type"] not in hardware_type_whitelist:
            raise ValueError(f"{role_name}角色配置中的hardware_type {role_config['hardware_type']} 不在白名单中: {hardware_type_whitelist}")

        if "labels" in role_config and 'app' in role_config['labels']:
            raise ValueError(f"{role_name}角色配置中的labels字段不能包含app字段")

        if "services" in role_config:
            for service in role_config["services"]:
                if "name" not in service:
                    raise ValueError(f"{role_name}角色服务配置缺少name字段")
                if "type" not in service:
                    raise ValueError(f"{role_name}角色服务配置缺少type字段")
                if "ports" not in service:
                    raise ValueError(f"{role_name}角色服务配置缺少ports字段")
                for port in service["ports"]:
                    if "name" not in port:
                        raise ValueError(f"{role_name}角色服务端口配置缺少name字段")
                    if "protocol" not in port:
                        raise ValueError(f"{role_name}角色服务端口配置缺少protocol字段")
                    if "port" not in port:
                        raise ValueError(f"{role_name}角色服务端口配置缺少port字段")
                    if "targetPort" not in port:
                        raise ValueError(f"{role_name}角色服务端口配置缺少targetPort字段")
    
    def parse_config(self) -> Optional[Dict[str, Any]]:
        """
        解析指定路径的JSON配置文件
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"错误: 配置文件 {self.config_path} 不存在")
        except json.JSONDecodeError:
            logging.error(f"错误: 配置文件 {self.config_path} 格式不正确，无法解析JSON")        
        except Exception as e:
            logging.error(f"解析配置文件时发生错误: {str(e)}")
        return None

    def validate_config(self, config: Dict[str, Any]) -> None:
        """
        验证配置文件是否包含必要的字段
        """
        if "engine_common_config" not in config:
            raise ValueError("缺少engine_common_config配置")
        if "deploy_config" not in config:
            raise ValueError("缺少deploy_config配置")
        
        # 验证engine_common_config中的必须字段
        common_config = config["engine_common_config"]
        if "deploy_type" not in common_config:
            raise ValueError("缺少deploy_type配置")
        
        deploy_type = common_config["deploy_type"]
        if deploy_type not in ["pd_separate", "union"]:
            raise ValueError(f"不支持的deploy_type: {deploy_type}，仅支持pd_separate和union")
        
        # 验证deploy_config中的必须字段
        deploy_config = config["deploy_config"]
        if "job_name" not in deploy_config:
            raise ValueError("缺少job_name配置")
        if "infer_service_num" not in deploy_config:
            raise ValueError("缺少infer_service_num配置")
        
        # 根据deploy_type验证不同的角色配置
        if deploy_type == "pd_separate":
            for role in [ROLE_PREFILL, ROLE_DECODE, ROLE_ROUTER]:
                if role not in deploy_config:
                    raise ValueError(f"deploy_type为pd_separate时，缺少{role}角色配置")
                self._validate_role_config(role, deploy_config[role])
        elif deploy_type == "union":
            if ROLE_PREFILL not in deploy_config:
                raise ValueError("deploy_type为union时，缺少prefill角色配置")
            self._validate_role_config(ROLE_PREFILL, deploy_config[ROLE_PREFILL])

    def transform_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        将用户配置转换为模板所需的格式
        """
        common_config = config.get("engine_common_config", {})
        deploy_config = config.get("deploy_config", {})
        common_config.update(deploy_config)

        if "namespace" not in common_config:
            common_config["namespace"] = "default"
        
        common_config["config_path"] = os.path.abspath(self.config_path)
        # 检索默认start目录
        current_file_path = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(current_file_path))
        common_config["scripts_path"] = os.path.join(project_root, "start")
        
        return common_config
