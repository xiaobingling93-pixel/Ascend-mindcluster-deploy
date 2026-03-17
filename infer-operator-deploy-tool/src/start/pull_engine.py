import json
import logging
import os
import subprocess

from user_config_loader import UserConfig
from utils import convert_args_dict_to_list, resolve_with_retry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

COMMON_KEYS = ['model_path', 'serve_name', 'enable_ep', 'dp_rpc_port', 'server_port']
PREFILL_ROLES = ['prefill', 'union']
DECODE_ROLE = 'decode'
PREFILL_KEYS = ['prefill_dp_size', 'prefill_tp_size']
DECODE_KEYS = ['decode_dp_size', 'decode_tp_size']
HARDWARE_TYPE_A2 = 'module-910b-8'
HARDWARE_TYPES_A3 = ['module-a3-16', 'module-a3-16-super-pod']
DATA_PARALLEL_ADDRESS_KEY = 'data_parallel_address'
HOST_KEY = 'host'
HEADLESS_KEY = 'headless'
DATA_PARALLEL_START_RANK_KEY = 'data_parallel_start_rank'
DATA_PARALLEL_SIZE_LOCAL_KEY = 'data_parallel_size_local'
KV_TRANSFER_CONFIG_KEY = 'kv_transfer_config'
DEPLOY_TYPE_PD_SEPARATE = 'pd_separate'
POD_INDEX_PRIMARY = 0

engine_type_args_map = {
    'vllm': {
        'model_path': 'model',
        'serve_name': 'served_model_name',
        'prefill_dp_size': 'data_parallel_size',
        'decode_dp_size': 'data_parallel_size',
        'prefill_tp_size': 'tensor_parallel_size',
        'decode_tp_size': 'tensor_parallel_size',
        'enable_ep': 'enable_expert_parallel',
        'dp_rpc_port': 'data_parallel_rpc_port',
        'server_port': 'port'
    }
}


def get_args_from_user_config(role, user_config: UserConfig) -> dict:
    engine_type = user_config.engine_common_config.engine_type
    if engine_type not in engine_type_args_map:
        raise ValueError(f"Unsupported engine type: {engine_type}")
    args_map = engine_type_args_map[engine_type]

    result = {}
    engine_common_config_dict = user_config.engine_common_config.__dict__

    for key, value in engine_common_config_dict.items():
        if key in COMMON_KEYS:
            if key not in args_map:
                raise ValueError(f"Key '{key}' not found in args_map for engine type '{engine_type}'")
            result[args_map[key]] = value

        elif role in PREFILL_ROLES and key in PREFILL_KEYS:
            if key not in args_map:
                raise ValueError(f"Key '{key}' not found in args_map for engine type '{engine_type}'")
            result[args_map[key]] = value

        elif role == DECODE_ROLE and key in DECODE_KEYS:
            if key not in args_map:
                raise ValueError(f"Key '{key}' not found in args_map for engine type '{engine_type}'")
            result[args_map[key]] = value

    # Define a helper function to process role-specific configuration
    def _process_role_config(deploy_config, dp_size_key, role_desc, engine_config):
        if deploy_config:
            single_instance_pod_num = deploy_config.single_instance_pod_num
            if single_instance_pod_num == 0:
                raise ValueError(f"single_instance_pod_num must be int greater than 0")
            data_parallel_size = engine_common_config_dict.get(dp_size_key, 1)

            if data_parallel_size % single_instance_pod_num != 0:
                raise ValueError(
                    f"For {role} role, {dp_size_key} ({data_parallel_size}) must be divisible by {role_desc}.single_instance_pod_num ({single_instance_pod_num})")

            data_parallel_size_local = data_parallel_size // single_instance_pod_num
            result['data_parallel_size_local'] = data_parallel_size_local

        if engine_config:
            result.update(engine_config)

    # Process configuration based on role
    if role in PREFILL_ROLES:
        _process_role_config(
            user_config.deploy_config.prefill,
            'prefill_dp_size',
            'prefill',
            user_config.prefill_engine_config
        )
    elif role == DECODE_ROLE:
        _process_role_config(
            user_config.deploy_config.decode,
            'decode_dp_size',
            'decode',
            user_config.decode_engine_config
        )

    return result


def get_ip_of_pod0(user_config: UserConfig) -> str:
    required_env_vars = [
        'INFER_SERVICE_NAME',
        'INFER_SERVICE_INDEX',
        'INSTANCE_INDEX',
        'INSTANCE_ROLE',
    ]
    for env_var in required_env_vars:
        if env_var not in os.environ:
            raise ValueError(f"Required environment variable {env_var} is not set")

    infer_service_name = os.environ.get('INFER_SERVICE_NAME')
    infer_service_index = os.environ.get('INFER_SERVICE_INDEX')
    instance_index = os.environ.get('INSTANCE_INDEX')
    instance_role = os.environ.get('INSTANCE_ROLE')
    namespace = user_config.deploy_config.namespace
    hostname = f"{infer_service_name}-{infer_service_index}-{instance_role}-{instance_index}-0.service-{infer_service_name}-{infer_service_index}-{instance_role}-{instance_index}.{namespace}.svc.cluster.local"
    ip = resolve_with_retry(hostname)
    if ip is None:
        raise ValueError(f"Failed to resolve hostname {hostname}")
    return ip


def get_args_from_env(user_config: UserConfig, dp_parallel_size_local: int) -> dict:
    result = {}

    pod_ip = os.environ.get('POD_IP')
    if pod_ip:
        result[DATA_PARALLEL_ADDRESS_KEY] = pod_ip

    pod_name = os.environ.get('POD_NAME')
    if pod_name:
        parts = pod_name.split('-')
        try:
            pod_index = int(parts[-1])
            if pod_index == POD_INDEX_PRIMARY:
                result[HOST_KEY] = pod_ip
            if pod_index != POD_INDEX_PRIMARY:
                result[HEADLESS_KEY] = True
                data_parallel_start_rank = pod_index * dp_parallel_size_local
                result[DATA_PARALLEL_START_RANK_KEY] = data_parallel_start_rank
                result[DATA_PARALLEL_ADDRESS_KEY] = get_ip_of_pod0(user_config)

        except (ValueError, IndexError) as e:
            logging.error(f"Could not extract pod_index from POD_NAME: {pod_name}")
            logging.error(f"Error details: {e}")

    return result


def get_kv_port_base(hardware_type: str) -> int:
    if hardware_type == HARDWARE_TYPE_A2:
        return 28000
    elif hardware_type in HARDWARE_TYPES_A3:
        return 36000
    else:
        raise ValueError(f"Unsupported hardware_type: {hardware_type}")


def generate_kv_transfer_config(role, user_config: UserConfig) -> str:
    if 'INSTANCE_INDEX' not in os.environ:
        raise ValueError("Required environment variable INSTANCE_INDEX is not set")
    instance_id = int(os.environ.get('INSTANCE_INDEX'))
    if role == 'prefill':
        kv_role = 'kv_producer'
        engine_id_base = 0
        kv_port_base = get_kv_port_base(user_config.deploy_config.prefill.hardware_type)
    elif role == 'decode':
        kv_role = 'kv_consumer'
        engine_id_base = user_config.deploy_config.prefill.instance_count
        kv_port_base = get_kv_port_base(user_config.deploy_config.decode.hardware_type)
    else:
        raise ValueError(f"Unsupported role for KV transfer config: {role}")

    engine_id = engine_id_base + instance_id
    kv_port = kv_port_base + engine_id * 100

    kv_transfer_config = {
        "kv_connector": "MooncakeLayerwiseConnector",
        "kv_role": kv_role,
        "kv_port": str(kv_port),
        "engine_id": str(engine_id),
        "kv_connector_extra_config": {
            "use_ascend_direct": True,
            "prefill": {
                "dp_size": user_config.engine_common_config.prefill_dp_size,
                "tp_size": user_config.engine_common_config.prefill_tp_size
            },
            "decode": {
                "dp_size": user_config.engine_common_config.decode_dp_size,
                "tp_size": user_config.engine_common_config.decode_tp_size
            }
        }
    }

    return json.dumps(kv_transfer_config, indent=2)


def pull_engine(role, config_path):
    try:
        user_config = UserConfig.load_from_file(config_path)
        args_dict = get_args_from_user_config(role, user_config)
        env_args = get_args_from_env(user_config, args_dict[DATA_PARALLEL_SIZE_LOCAL_KEY])
        args_dict.update(env_args)

        if user_config.engine_common_config.deploy_type == DEPLOY_TYPE_PD_SEPARATE:
            args_dict[KV_TRANSFER_CONFIG_KEY] = generate_kv_transfer_config(role, user_config)

        converted_args_list = convert_args_dict_to_list(args_dict)

        vllm_command = ['vllm', 'serve'] + converted_args_list

        logging.info(f"Starting vllm with command: {' '.join(vllm_command)}")

        process = subprocess.Popen(vllm_command, shell=False)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            logging.error(f"vllm serve process failed with return code {process.returncode}")
            logging.error(f"stdout: {stdout}")
            logging.error(f"stderr: {stderr}")
            raise subprocess.CalledProcessError(process.returncode, vllm_command, output=stdout, stderr=stderr)

        logging.info(f"vllm serve process started with PID: {process.pid}")

    except Exception as e:
        logging.error(f"Error in pull_engine: {e}")
        raise
