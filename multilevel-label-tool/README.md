# 多层级标签工具 (Multilevel Label Tool)

## 工具概述

这是一套用于Kubernetes节点标签管理的工具集，包含两个主要脚本：

1. **lld_parser.py**：从LLD部署配置Excel文件中提取节点信息，生成符合要求的CSV配置文件
2. **label_tool.py**：根据CSV配置文件批量管理Kubernetes节点标签（添加或删除）

## 功能说明

### 1. lld_parser.py

从包含超节点规划信息的Excel文件中提取数据，生成用于Kubernetes节点标签配置的CSV文件。

主要功能：
- 自动查找包含"超节点规划"的工作表
- 提取"主机名称"和"机框编号"列数据
- 根据机框编号计算groupid（机框编号除以每机架组数的整数商）
- 生成包含节点名称、groupid和topotree名称的CSV文件

### 2. label_tool.py

基于CSV配置文件，批量管理Kubernetes节点标签。

主要功能：
- 支持从CSV文件读取节点信息和标签配置
- 批量添加标签（apply命令）
- 批量删除标签（delete命令）
- 支持命令行参数和交互式输入两种模式
- 提供详细的执行结果反馈

## 安装要求

- Python 3.x
- 依赖库：openpyxl（用于处理Excel文件）

安装依赖：
```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 使用lld_parser.py生成CSV配置文件

#### 命令行参数模式：
```bash
python lld_parser.py --input <Excel文件路径> --output <CSV输出路径> --topotree-name <拓扑树名称> --group-per-rack <每机架组数>
```

#### 交互式输入模式：
```bash
python lld_parser.py
```

#### 参数说明：
- `--input/-i`：输入Excel文件路径（必填）
- `--output/-o`：输出CSV文件路径（可选，默认使用输入文件名+_output.csv）
- `--topotree-name/-t`：拓扑树名称（必填）
- `--group-per-rack/-g`：每机架组数（可选，默认12）

### 2. 使用label_tool.py管理节点标签

#### 命令行参数模式：
```bash
# 添加标签
python label_tool.py apply --config-path <CSV文件路径>

# 删除标签
python label_tool.py delete --config-path <CSV文件路径>
```

#### 交互式输入模式：
```bash
# 添加标签
python label_tool.py apply

# 删除标签
python label_tool.py delete
```

#### 参数说明：
- `apply`：添加标签命令
- `delete`：删除标签命令
- `--config-path`：CSV配置文件路径（可选，不提供则进入交互式输入）

## 文件格式说明

### 1. Excel文件格式要求

- 必须包含名为"超节点规划"的工作表（或名称中包含"超节点规划"的工作表）
- 工作表中必须包含以下列：
  - "主机名称"：Kubernetes节点名称
  - "机框编号"：数值类型，用于计算groupid

### 2. CSV文件格式

#### 输入格式（由lld_parser.py生成或手动创建）：
```csv
nodeName,huawei.com/topotree.groupid,huawei.com/topotree
node1,0,topo1
node2,0,topo1
node3,1,topo1
node4,1,topo1
```

- 第一列必须为`nodeName`，表示Kubernetes节点名称
- 后续列为标签键值对，格式为`标签键,标签值`

## 示例

### 示例1：生成CSV配置文件

```bash
python lld_parser.py --input node_plan.xlsx --output node_labels.csv --topotree-name production --group-per-rack 12
```

执行结果：
```
Target worksheet found: 超节点规划工作表
CSV file successfully generated: node_labels.csv
Processed 100 rows of data
Topotree name: production
Group per rack (divisor): 12
Script execution completed
```

### 示例2：批量添加节点标签

```bash
python label_tool.py apply --config-path node_labels.csv
```

执行结果：
```
Starting adding labels...
Processing node node1 for adding labels...
Processing node node2 for adding labels...
...
Adding labels completed successfully!
```

### 示例3：批量删除节点标签

```bash
python label_tool.py delete --config-path node_labels.csv
```

执行结果：
```
Starting removing labels...
Processing node node1 for removing labels...
Processing node node2 for removing labels...
...
Removing labels completed successfully!
```

## 注意事项

1. 使用`label_tool.py`前，请确保已正确配置Kubernetes集群访问（kubectl命令可用）
2. Excel文件中的"机框编号"列必须包含有效的数值数据
3. CSV文件中的标签值如果为空，将被忽略（不添加或删除）
4. 删除标签时，只会删除CSV文件中列出的标签键
5. 操作前建议先备份当前节点标签配置

## 故障排除

### 常见错误及解决方案：

1. **Excel文件无法找到**
   ```
   Error: Input file 'node_plan.xlsx' does not exist
   ```
   解决方案：检查文件路径是否正确，确保文件存在

2. **缺少必要的列**
   ```
   Error: The following headers are not found: 主机名称
   ```
   解决方案：检查Excel文件中是否包含所需的列名

3. **Kubernetes访问错误**
   ```
   Failed nodes (1) and error messages:
     - node1: The connection to the server localhost:8080 was refused - did you specify the right host or port?
   ```
   解决方案：确保已正确配置Kubernetes集群访问，kubectl命令可以正常使用

4. **CSV文件格式错误**
   ```
   Error: First column of CSV file must be 'nodeName'
   ```
   解决方案：检查CSV文件格式，确保第一列为`nodeName`