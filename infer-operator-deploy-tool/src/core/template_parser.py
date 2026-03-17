from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, TemplateError
import os


class Jinja2TemplateParser:
    """
    Jinja2模板解析器，用于渲染各种格式的Jinja2模板文件
    """
    
    def __init__(self, template_dir: str =  "src/templates", config: Dict[str, Any] = None):
        """
        初始化模板解析器
        """
        # 存储模板目录
        self.template_dir = template_dir
        
        # 设置默认配置
        default_config = {
            'trim_blocks': True,
            'lstrip_blocks': True,
            'keep_trailing_newline': False,
            'autoescape': False
        }
        
        # 如果提供了配置字典，合并它
        if config:
            default_config.update(config)
        
        # 创建Jinja2环境
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            **default_config
        )
    
    def render_template(self, template_name: str, params: Dict[str, Any]) -> str:
        """
        渲染单个模板文件
        """
        try:
            # 检查模板文件是否存在
            template_path = os.path.join(self.template_dir, template_name)
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"模板文件不存在: {template_path}")
            
            # 获取并渲染模板
            template = self.env.get_template(template_name)
            return template.render(**params)
            
        except FileNotFoundError:
            raise
        except TemplateError as e:
            raise TemplateError(f"模板渲染失败 '{template_name}': {str(e)}") from e
        except Exception as e:
            raise Exception(f"渲染模板时发生未知错误 '{template_name}': {str(e)}") from e