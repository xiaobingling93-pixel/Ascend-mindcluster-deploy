import argparse
import logging
import os

from pull_engine import pull_engine
from run_router import run_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

ALL_POSSIBLE_ROLES = ['union', 'prefill', 'decode', 'router']
INSTANCE_ROLE_LIST = ['union', 'prefill', 'decode']
ROUTER_ROLE = 'router'


class ArgsConfig:
    def __init__(self):
        self.role = None
        self.config_path = None

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Infer Operator Deploy Tool')

        parser.add_argument('--role', required=True, choices=ALL_POSSIBLE_ROLES,
                            help='Role of the component: prefill, decode, or router')

        parser.add_argument('--config', required=True, type=str,
                            help='Path to user_config.json file')

        args = parser.parse_args()

        self.role = args.role
        self.config_path = args.config
        self._validate_config_path()

        return self

    def _validate_config_path(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file '{self.config_path}' does not exist")

        if not self.config_path.endswith('.json'):
            raise ValueError(f"Config file '{self.config_path}' must be a JSON file")


def main():
    args_config = ArgsConfig()
    args_config.parse_args()

    logging.info(f"Role: {args_config.role}")
    logging.info(f"Config Path: {args_config.config_path}")

    if args_config.role in INSTANCE_ROLE_LIST:
        pull_engine(args_config.role, args_config.config_path)
    elif args_config.role == ROUTER_ROLE:
        run_router(args_config.config_path)


if __name__ == "__main__":
    main()
