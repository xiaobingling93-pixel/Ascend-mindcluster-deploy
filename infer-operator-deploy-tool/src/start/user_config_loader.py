from dataclasses import dataclass
import json
from typing import Any, Dict, Optional


def _validate_required_field(data: Dict[str, Any], field_name: str, expected_type: type) -> Any:
    """Validate that a required field exists and has the correct type."""
    if field_name not in data:
        raise ValueError(f"Required field '{field_name}' is missing")

    value = data[field_name]
    if not isinstance(value, expected_type):
        raise TypeError(f"Field '{field_name}' must be of type {expected_type.__name__}, got {type(value).__name__}")

    return value


def _validate_optional_field(data: Dict[str, Any], field_name: str, expected_type: type) -> Optional[Any]:
    """Validate that an optional field has the correct type if present."""
    if field_name not in data:
        return None

    value = data[field_name]
    if not isinstance(value, expected_type):
        raise TypeError(f"Field '{field_name}' must be of type {expected_type.__name__}, got {type(value).__name__}")

    return value


@dataclass
class InstanceDeployConfig:
    hardware_type: str
    instance_count: int
    single_instance_pod_num: int
    single_pod_npu_num: int
    env: Optional[Dict[str, Any]]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InstanceDeployConfig':
        fields = [
            ('hardware_type', str, True),
            ('instance_count', int, True),
            ('single_instance_pod_num', int, True),
            ('single_pod_npu_num', int, True),
            ('env', dict, False)
        ]
        
        validated_fields = {}
        for field_name, field_type, is_required in fields:
            if is_required:
                validated_fields[field_name] = _validate_required_field(data, field_name, field_type)
            else:
                validated_fields[field_name] = _validate_optional_field(data, field_name, field_type)

        return cls(**validated_fields)


@dataclass
class DeployConfig:
    prefill: InstanceDeployConfig
    decode: Optional[InstanceDeployConfig]
    namespace: Optional[str]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeployConfig':
        prefill = InstanceDeployConfig.from_dict(_validate_required_field(data, 'prefill', dict))

        decode = None
        if 'decode' in data:
            decode = InstanceDeployConfig.from_dict(data['decode'])

        namespace = None
        if 'namespace' in data:
            namespace = _validate_optional_field(data, 'namespace', str)

        return cls(prefill=prefill, decode=decode, namespace=namespace)


@dataclass
class EngineCommonConfig:
    deploy_type: str
    engine_type: str
    model_path: str
    serve_name: str
    prefill_dp_size: int
    prefill_tp_size: int
    decode_dp_size: Optional[int]
    decode_tp_size: Optional[int]
    enable_ep: bool
    server_port: int
    dp_rpc_port: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EngineCommonConfig':
        fields = [
            ('deploy_type', str, True),
            ('engine_type', str, True),
            ('model_path', str, True),
            ('serve_name', str, True),
            ('prefill_dp_size', int, True),
            ('prefill_tp_size', int, True),
            ('decode_dp_size', int, False),
            ('decode_tp_size', int, False),
            ('enable_ep', bool, True),
            ('server_port', int, True),
            ('dp_rpc_port', int, True)
        ]
        
        validated_fields = {}
        for field_name, field_type, is_required in fields:
            if is_required:
                validated_fields[field_name] = _validate_required_field(data, field_name, field_type)
            else:
                validated_fields[field_name] = _validate_optional_field(data, field_name, field_type)

        return cls(**validated_fields)


@dataclass
class UserConfig:
    deploy_config: DeployConfig
    engine_common_config: EngineCommonConfig
    prefill_engine_config: Optional[Dict[str, Any]]
    decode_engine_config: Optional[Dict[str, Any]]
    router_config: Optional[Dict[str, Any]]

    @classmethod
    def load_from_file(cls, config_path: str) -> 'UserConfig':
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            if not isinstance(raw_data, dict):
                raise ValueError("Config file must contain a valid JSON object")

            deploy_config = DeployConfig.from_dict(_validate_required_field(raw_data, 'deploy_config', dict))
            engine_common_config = EngineCommonConfig.from_dict(
                _validate_required_field(raw_data, 'engine_common_config', dict))
            prefill_engine_config = _validate_optional_field(raw_data, 'prefill_engine_config', dict)
            decode_engine_config = _validate_optional_field(raw_data, 'decode_engine_config', dict)
            router_config = _validate_optional_field(raw_data, 'router_config', dict)

            return cls(
                deploy_config=deploy_config,
                engine_common_config=engine_common_config,
                prefill_engine_config=prefill_engine_config,
                decode_engine_config=decode_engine_config,
                router_config=router_config
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON config: {e}") from e
        except FileNotFoundError as e:
            raise ValueError(f"Config file not found: {config_path}") from e
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}") from e
