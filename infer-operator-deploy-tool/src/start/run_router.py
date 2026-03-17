from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
import subprocess
import time

from user_config_loader import UserConfig
from utils import convert_args_dict_to_list, resolve_with_retry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

MAX_RESOLVE_ATTEMPTS = 5
RESOLVE_DELAY = 10
MAX_WORKERS = 20


def _validate_router_config(user_config: UserConfig) -> int:
    if user_config.router_config is None:
        raise ValueError("router_config must not be None")

    if 'port' not in user_config.router_config:
        raise ValueError("router_config must contain 'port' field")

    port = user_config.router_config['port']
    if not isinstance(port, int) or port <= 0 or port > 65535:
        raise ValueError(f"port must be a valid positive integer between 1 and 65535, got: {port}")

    return port


def get_prefiller_or_decoder_hosts(user_config: UserConfig, role: str) -> list:
    infer_service_name = os.environ.get('INFER_SERVICE_NAME')
    infer_service_index = os.environ.get('INFER_SERVICE_INDEX')
    namespace = user_config.deploy_config.namespace
    if role == 'prefill':
        instance_count = user_config.deploy_config.prefill.instance_count
    elif role == 'decode':
        instance_count = user_config.deploy_config.decode.instance_count
    else:
        raise ValueError(f"Unsupported role: {role}")

    hostnames = []
    for instance_index in range(instance_count):
        hostname = f"{infer_service_name}-{infer_service_index}-{role}-{instance_index}-0.service-{infer_service_name}-{infer_service_index}-{role}-{instance_index}.{namespace}.svc.cluster.local"
        hostnames.append(hostname)

    def resolve_hostname(hostname: str) -> str:
        max_resolve_attempts = MAX_RESOLVE_ATTEMPTS
        resolve_delay = RESOLVE_DELAY

        for attempt in range(max_resolve_attempts):
            ip = resolve_with_retry(hostname)
            if ip is not None:
                return ip
            logging.debug(
                "Attempt %s/%s failed to resolve hostname %s. Retrying in %s seconds...",
                attempt + 1,
                max_resolve_attempts,
                hostname,
                resolve_delay
            )
            if attempt < max_resolve_attempts - 1:
                time.sleep(resolve_delay)

        raise ValueError(f"Failed to resolve hostname {hostname} after {max_resolve_attempts} attempts")

    result = []
    max_workers = min(instance_count, MAX_WORKERS)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_hostname = {
            executor.submit(resolve_hostname, hostname): hostname
            for hostname in hostnames
        }

        for future in as_completed(future_to_hostname):
            try:
                ip = future.result()
                result.append(ip)
            except Exception as e:
                raise e

    return result


def get_prefiller_or_decoder_ports(user_config: UserConfig, role: str) -> list:
    if role == 'prefill':
        port_num = user_config.deploy_config.prefill.instance_count
    elif role == 'decode':
        port_num = user_config.deploy_config.decode.instance_count
    else:
        raise ValueError(f"Unsupported role: {role}")

    port = user_config.engine_common_config.server_port
    port_list = [port] * port_num

    return port_list


def run_router(config_path):
    try:
        user_config = UserConfig.load_from_file(config_path)
        port = _validate_router_config(user_config)
        host = os.environ.get('POD_IP')
        args_dict = {}
        args_dict['port'] = port
        args_dict['host'] = host
        args_dict['prefiller_hosts'] = get_prefiller_or_decoder_hosts(user_config, 'prefill')
        args_dict['prefiller_ports'] = get_prefiller_or_decoder_ports(user_config, 'prefill')
        args_dict['decoder_hosts'] = get_prefiller_or_decoder_hosts(user_config, 'decode')
        args_dict['decoder_ports'] = get_prefiller_or_decoder_ports(user_config, 'decode')

        converted_args_list = convert_args_dict_to_list(args_dict)
        current_dir = os.path.dirname(__file__)
        script_path = os.path.join(current_dir, 'load_balance_proxy_layerwise_server_example.py')
        router_cmd = ['python', script_path] + converted_args_list
        logging.info(f"Starting router with command: {' '.join(router_cmd)}")

        process = subprocess.Popen(router_cmd, shell=False)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            logging.error(f"Router process failed with return code {process.returncode}")
            logging.error(f"stdout: {stdout}")
            logging.error(f"stderr: {stderr}")
            raise subprocess.CalledProcessError(process.returncode, router_cmd, output=stdout, stderr=stderr)

    except Exception as e:
        logging.error(f"Error in run_router: {e}")
        raise
