# Infer Operator Deploy Tool

## 1. 基本介绍

Infer Operator Deploy Tool 是一个用于在 Kubernetes 集群上部署和管理 InferServiceSet 资源的命令行工具。该工具通过模板渲染和 Kubernetes API 交互，简化了推理服务的部署流程，支持 PD 混部（union）和 PD 分离（pd_separate）两种部署模式。

### 功能特性
- 支持 PD 混部和 PD 分离两种部署模式
- 基于 Jinja2 模板的配置渲染
- 与 Kubernetes API 无缝集成
- 提供部署和删除操作的命令行接口
- 支持试运行模式，预览生成的 YAML 配置

### 依赖
- Python 3.6+
- click>=8.0.0
- kubernetes>=24.2.0
- jinja2>=3.0.0

## 2. 操作流程

### 2.1 环境准备

1. 安装依赖
```bash
pip install -r requirements.txt
```

2. 确保 Kubernetes 集群可访问
   - 确保 `~/.kube/config` 文件存在且配置正确
   - 或通过 `--kubeconfig` 参数指定配置文件路径

3. 确保Infer Operator组件成功安装并运行在Kubernetes集群中

### 2.2 配置文件准备

1. 复制并修改配置文件
```bash
# 根据需求编辑配置文件
cp config/user_config.json config/my_config.json
```

2. 验证配置文件格式
```bash
python main.py deploy --config config/my_config.json --dry-run
```

### 2.3 部署应用

```bash
# 使用默认配置文件部署
python main.py deploy

# 使用指定配置文件部署
python main.py deploy --config config/my_config.json

# 使用指定 kubeconfig 文件部署
python main.py deploy --kubeconfig /path/to/kubeconfig

# 试运行模式，仅预览生成的 YAML 配置
python main.py deploy --dry-run
```

### 2.4 删除应用

```bash
# 删除指定名称的应用，应用名取配置文件中的`deploy_config.job_name`字段。
python main.py delete --app-name my-app

# 在指定命名空间删除应用，应用名取配置文件中的`deploy_config.job_name`字段。
python main.py delete --app-name my-app --namespace my-namespace

# 使用指定 kubeconfig 文件删除，应用名取配置文件中的`deploy_config.job_name`字段。
python main.py delete --app-name my-app --kubeconfig /path/to/kubeconfig
```

## 3. 配置文件字段说明

配置文件采用 JSON 格式，包含以下主要部分：

### 3.1 deploy_config

部署相关配置，包含作业名称、命名空间、推理服务数量等基本信息。

| 字段 | 类型 | 说明 | 是否必填 | 默认值 |
|------|------|------|----------|--------|
| namespace | string | Kubernetes 命名空间 | 否 | default |
| job_name | string | 作业名称，将作为资源名称前缀 | 是 | - |
| infer_service_num | integer | 推理服务副本数量 | 是 | - |
| prefill | object | Prefill 角色配置（混部模式作为混部引擎配置） | 是 | - |
| decode | object | Decode 角色配置（仅 PD 分离模式） | PD分离模式下必填 | - |
| router | object | Router 角色配置（仅 PD 分离模式） | PD分离模式下必填 | - |

### 3.2 deploy_config中的角色配置（prefill/decode/router）

每个角色配置包含资源需求、容器镜像、环境变量等信息。

| 字段 | 类型 | 说明 | 是否必填 | 默认值 |
|------|------|------|----------|--------|
| hardware_type | string | 硬件类型，支持 module-910b-8、module-a3-16、module-a3-16-super-pod，根据实际节点上的accelerator-type填写 | 是 | - |
| instance_count | integer | 实例数量 | 否 | 1 |
| single_instance_pod_num | integer | 单个实例的 Pod 数量 | 否 | 1 |
| single_pod_npu_num | integer | 单个 Pod 的 NPU 数量 | 否 | 0 |
| image | string | 容器镜像地址 | 是 | - |
| env | object | 环境变量键值对 | 否 | {} |
| labels | object | Pod 标签键值对 | 否 | {} |
| annotations | object | Pod 注解键值对 | 否 | {} |
| node_selector | object | 节点选择器键值对 | 否 | {} |

### 3.3 engine_common_config

引擎通用配置，定义部署模式、引擎类型、模型路径等。

| 字段 | 类型 | 说明 | 是否必填 | 默认值 |
|------|------|------|----------|--------|
| deploy_type | string | 部署模式，支持 pd_separate（PD分离）或 union（PD混部） | 是 | - |
| engine_type | string | 引擎类型，如 vllm | 是 | - |
| serve_name | string | 服务名称，将作为推理请求的模型名称 | 是 | - |
| model_path | string | 模型文件路径 | 是 | - |
| prefill_dp_size | integer | Prefill 阶段的 Data Parallelism 大小 | 否 | - |
| prefill_tp_size | integer | Prefill 阶段的 Tensor Parallelism 大小 | 否 | - |
| decode_dp_size | integer | Decode 阶段的 Data Parallelism 大小 | 否 | - |
| decode_tp_size | integer | Decode 阶段的 Tensor Parallelism 大小 | 否 | - |
| enable_ep | boolean | 是否启用专家并行 | 否 | false |
| server_port | integer | 服务器端口 | 否 | 8000 |
| dp_rpc_port | integer | Data Parallelism RPC 端口 | 否 | 10000 |

### 3.4 引擎特定配置

- `prefill_engine_config`: Prefill 引擎的特定配置（混部模式下作为混部引擎配置），该参数将被添加到prefill实例的启动参数中。
- `decode_engine_config`: Decode 引擎的特定配置（仅 PD 分离模式），该参数将被添加到decode实例的启动参数中。
- `router_engine_config`: Router 引擎的特定配置（仅 PD 分离模式），该参数将被添加到router实例的启动参数中。

这些部分用于配置引擎业务特有的参数，根据不同的引擎类型可能有所不同。该部分参数将作为对应角色引擎的命令行配置运行推理业务。

## 4. 部署模式用例

### 4.1 PD 分离模式（pd_separate）

PD 分离模式将推理服务分为三个独立的角色：Prefill、Decode 和 Router，每个角色负责不同的功能，部署在不同的 Pod 中。配置示例见`example/vllm_pd_separate_config.json`。

**部署命令：**
```bash
python main.py deploy --config example/vllm_pd_separate_config.json
```

### 4.2 PD 混部模式（union）

PD 混部模式将 Prefill 和 Decode 功能合并到一个角色中，简化了部署结构，适用于资源有限或架构简单的场景。配置示例见`example/vllm_union_config.json`。

**部署命令：**
```bash
python main.py deploy --config example/vllm_union_config.json
```

## 5. 命令行参数说明

### 5.1 deploy 命令

| 参数 | 简写 | 类型 | 说明 | 默认值 |
|------|------|------|------|--------|
| --config | -c | string | 配置文件路径 | config/user_config.json |
| --dry-run | - | boolean | 试运行模式，不实际部署 | false |
| --kubeconfig | -k | string | Kubeconfig 文件路径 | ~/.kube/config |

### 5.2 delete 命令

| 参数 | 简写 | 类型 | 说明 | 默认值 |
|------|------|------|------|--------|
| --app-name | -n | string | 要删除的应用名称 | - |
| --namespace | -ns | string | Kubernetes 命名空间 | default |
| --kubeconfig | -k | string | Kubeconfig 文件路径 | ~/.kube/config |

## 6. 日志

工具运行日志会同时输出到控制台和 `infer_operator_deploy_tool.log` 文件中，包含部署过程的详细信息。

## 7. 注意事项

1. 确保 Kubernetes 集群已安装并配置好 Infer Operator
2. 确保模型路径在所有节点上都可访问
3. 硬件类型必须在白名单中：module-910b-8, module-a3-16, module-a3-16-super-pod
4. PD 分离模式需要同时配置 prefill、decode 和 router 三个角色
5. PD 混部模式只需要配置 prefill 角色
6. 首次部署时，工具会创建资源；如果资源已存在，会自动更新

## 8. 故障排除

1. **连接 Kubernetes 集群失败**
   - 检查 kubeconfig 文件是否存在且配置正确
   - 确保集群节点可访问

2. **配置文件解析失败**
   - 检查 JSON 格式是否正确
   - 确保所有必填字段都已配置

3. **资源创建失败**
   - 查看日志文件获取详细错误信息
   - 检查集群资源是否足够
   - 确保 Infer Operator 已正确安装

4. **部署后服务不可用**
   - 检查 Pod 状态：`kubectl get pods -n <namespace>`
   - 查看 Pod 日志：`kubectl logs <pod-name> -n <namespace>`
   - 检查服务配置：`kubectl describe service <service-name> -n <namespace>`