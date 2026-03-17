#!/usr/bin/env python3
import click
import logging
import sys
import os

from src.core.config_parser import ConfigParser
from src.core.job_manager import InferServiceSetManager

# 添加src目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('infer_operator_deploy_tool.log', mode='a', encoding='utf-8')],
    encoding='utf-8',
)

@click.group()
def cli():
    """InferServiceSet部署工具"""
    pass

@cli.command()
@click.option('--config', '-c', default='config/user_config.json', help='配置文件路径')
@click.option('--dry-run', is_flag=True, help='试运行模式，不实际部署')
@click.option('--kubeconfig', '-k', default='~/.kube/config', help='Kubeconfig文件路径')
def deploy(config, kubeconfig, dry_run):
    """部署InferServiceSet到Kubernetes"""
    try:
        logging.info(f"加载配置文件: {config}")
        config_parser = ConfigParser(config)
        user_config = config_parser.parse_config()
        
        if not user_config:
            raise ValueError("配置文件解析失败")
        
        logging.info("渲染模板...")
        # 转换配置为模板所需的格式
        config_parser.validate_config(user_config)
        template_params = config_parser.transform_config(user_config)
        
        job_manager = InferServiceSetManager(kubeconfig)
        rendered_templates = job_manager.render_template(template_params)

        if dry_run:
            click.echo("=== 生成的YAML配置 ===")
            for resource_type, yaml_content in rendered_templates.items():
                if isinstance(yaml_content, str):
                    click.echo(f"\n--- {resource_type} ---")
                    click.echo(yaml_content)
        else:
            logging.info("部署应用...")
            namespace = user_config.get('namespace', 'default')
            results = job_manager.deploy_app(user_config, rendered_templates, namespace)
            if results:
                click.echo("✅ 应用下发成功!")
                click.echo(f"应用名称: {template_params.get('job_name', 'unknown')}")
                click.echo(f"命名空间: {namespace}")
            else:
                click.echo("❌ 应用下发失败: 未创建任何资源", err=True)
            
    except Exception as e:
        click.echo(f"❌ 应用下发失败: {str(e)}", err=True)

@cli.command()
@click.option('--app-name', '-n', required=True, help='要删除的应用名称')
@click.option('--namespace', '-ns', default='default', help='Kubernetes命名空间')
@click.option('--kubeconfig', '-k', default='~/.kube/config', help='Kubeconfig文件路径')
def delete(app_name, namespace, kubeconfig):
    """从Kubernetes删除InferServiceSet"""
    try:
        logging.info(f"创建作业管理器...")
        job_manager = InferServiceSetManager(kubeconfig)

        logging.info(f"删除应用: {app_name} (命名空间: {namespace})...")
        job_manager.delete_app(app_name, namespace)
        click.echo("✅ 应用删除成功!")
            
    except Exception as e:
        click.echo(f"❌ 删除失败: {str(e)}", err=True)

if __name__ == '__main__':
    cli()