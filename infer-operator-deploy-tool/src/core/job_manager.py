from re import split
import yaml
import logging
import time
import os
import json
from typing import Dict, Any

from kubernetes import client, config, dynamic
from kubernetes.client.rest import ApiException
from ..core.template_parser import Jinja2TemplateParser


class InferServiceSetManager():
    """InferServiceSet资源管理类"""
    group = "mindcluster.huawei.com"
    version = "v1"
    plural = "InferServiceSet"
    app_label_key = "infer.huawei.com/inferservice-name"

    def __init__(self, kubeconfig_path: str = "~/.kube/config"):
        self.kubeconfig_path = kubeconfig_path
        self.custom_api = None
        self.dynamic_client = None
        self.core_v1 = None
        self.template_parser = None
        self.deploy_funcs = {
            'inferserviceset': self._create_or_update_iss,
        }
        # 初始化模板解析器
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'templates')
        self.template_parser = Jinja2TemplateParser(template_dir)

    def init_k8s_client(self):
        """初始化Kubernetes客户端"""
        logging.info("初始化Kubernetes客户端...")
        try:
            # 加载kubeconfig
            config.load_kube_config(config_file=self.kubeconfig_path)
            
            # 创建动态客户端
            self.dynamic_client = dynamic.DynamicClient(
                client.api_client.ApiClient()
            )
            
            # 获取自定义资源API
            self.custom_api = self.dynamic_client.resources.get(
                api_version=f"{self.group}/{self.version}",
                kind=self.plural,
            )
            
            # 初始化core_v1客户端
            self.core_v1 = client.CoreV1Api()
            
            logging.info("Kubernetes客户端初始化成功")
            
        except Exception as e:
            logging.error(f"初始化Kubernetes客户端失败: {e}")
            raise

    def render_template(self, template_params: Dict[str, Any]) -> Dict[str, str]:
        """渲染InferServiceSet模板"""
        logging.info("渲染InferServiceSet模板...")
        
        try:
            rendered_content = self.template_parser.render_template("inferserviceset.yaml.j2", template_params)
            logging.info("InferServiceSet模板渲染完成")
            # 返回字典格式，键为资源类型，值为渲染后的内容
            return {"inferserviceset": rendered_content}
        except Exception as e:
            logging.error(f"渲染模板失败: {e}")
            raise

    def deploy_app(self, config_params: Dict[str, Any], rendered_templates: Dict[str, str], namespace: str) -> Dict[str, Any]:
        """部署InferServiceSet到Kubernetes集群"""
        self.init_k8s_client()
        logging.info("部署到Kubernetes集群...")

        results = {}
        for _, yaml_content in rendered_templates.items():
            yaml_documents = list(yaml.safe_load_all(yaml_content))
            for doc in yaml_documents:
                if not doc:
                    continue

                self.create_or_update_configmap(config_params, namespace)

                kind = doc.get('kind', '').lower()
                name = doc['metadata']['name']
                logging.info(f"创建资源: kind={kind}, name={name}, namespace={namespace}")
                deploy_func = self.deploy_funcs.get(kind)
                if not deploy_func:
                    logging.warning(f"不支持的资源类型: {kind}")
                    continue

                results[f"{kind}/{name}"] = deploy_func(doc, namespace)

        return results

    def create_or_update_configmap(self, config_params: Dict[str, Any], namespace: str) -> Dict[str, Any]:
        """创建或更新ConfigMap资源"""
        cm_name = config_params['deploy_config']['job_name'] + '-cm'
        logging.info(f"创建ConfigMap资源: namespace={namespace}, name={cm_name}")

        # 构建ConfigMap的正确结构
        cm_body = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": cm_name,
                "namespace": namespace
            },
            "data": {
                "user_config.json": json.dumps(config_params)
            }
        }
        
        try:
            result = self.core_v1.create_namespaced_config_map(
                namespace=namespace,
                body=cm_body
            )
        except ApiException as e:
            if e.status != 409:
                raise Exception(f"创建ConfigMap失败: {e}") from e
            try:
                # 非交互式环境下默认更新
                logging.info("资源已存在，自动更新")
                result = self.core_v1.patch_namespaced_config_map(
                    name=cm_name,
                    namespace=namespace,    
                    body=cm_body,   
                    content_type="application/merge-patch+json")
            except ApiException as update_e:
                raise Exception(f"更新ConfigMap失败: {update_e}") from update_e
        return result
    

    def delete_app(self, app_name: str, namespace: str = "default"):
        """删除InferServiceSet应用"""
        self.init_k8s_client()
        logging.info(f"删除应用: namespace={namespace}, name={app_name}")
        self._delete_iss(app_name, namespace)
        self._delete_configmap(app_name + '-cm', namespace)

    def _create_or_update_iss(self, iss_manifest: Dict[str, Any], namespace: str) -> Dict[str, Any]:
        """创建或更新InferServiceSet资源"""
        logging.info(f"创建InferServiceSet资源: namespace={namespace}, name={iss_manifest['metadata']['name']}")
        try:
            result = self.custom_api.create(body=iss_manifest, namespace=namespace)
        except ApiException as e:
            if e.status != 409:
                raise Exception(f"创建InferServiceSet失败: {e}") from e
            try:
                # 非交互式环境下默认更新
                logging.info("资源已存在，自动更新")
                result = self.custom_api.patch(
                    name=iss_manifest['metadata']['name'],
                    namespace=namespace,
                    body=iss_manifest,
                    content_type="application/merge-patch+json")
            except ApiException as update_e:
                raise Exception(f"更新InferServiceSet失败: {update_e}") from update_e
        return result

    def _delete_iss(self, iss_name: str, namespace: str):
        """删除InferServiceSet资源"""
        logging.info(f"删除InferServiceSet资源: namespace={namespace}, name={iss_name}")
        try:
            self.custom_api.delete(name=iss_name, namespace=namespace)
        except ApiException as e:
            if e.status != 404:
                raise Exception(f"删除InferServiceSet失败: {e.reason}") from e
            else:
                logging.info("InferServiceSet不存在，跳过删除")

    def _delete_configmap(self, cm_name: str, namespace: str):
        """删除ConfigMap资源"""
        logging.info(f"删除ConfigMap资源: namespace={namespace}, name={cm_name}")
        try:
            self.core_v1.delete_namespaced_config_map(
                name=cm_name,
                namespace=namespace
            )
        except ApiException as e:
            if e.status != 404:
                raise Exception(f"删除ConfigMap失败: {e.reason}") from e
            else:
                logging.info("ConfigMap不存在，跳过删除")