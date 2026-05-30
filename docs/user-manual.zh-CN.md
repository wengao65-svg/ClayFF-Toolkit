# ClayFF-Toolkit 中文使用手册

## 1. 手册范围

本手册面向实际使用者，覆盖当前仓库中**已经落地并经过验证**的能力：

- 结构输入与格式要求
- 安装与启动
- 命令行工作流
- Qt 图形界面使用
- 常见输出说明
- 常见问题与排错

本手册不描述尚未实现的规划能力，也不把启发式 profile 推断写成绝对真值。

## 2. 工具定位

`ClayFF-Toolkit` 是一个面向层状粘土矿物体系的 ClayFF 工具包，当前可以完成：

1. 从周期结构读取 `cif`、`xyz/extxyz` 等输入
2. 执行同晶置换
3. 分配 ClayFF 原子类型与电荷
4. 输出 LAMMPS `data` 文件
5. 计算并检查净电荷
6. 在 GUI 中按步骤完成同晶替换、力场赋予、力场校验与导出

## 3. 当前支持范围

### 3.1 已支持元素

当前已接入并验证过的元素包括：

- `Si`
- `Al`
- `Mg`
- `Fe`
- `Li`
- `Na`
- `K`
- `Cs`
- `Ca`
- `Ba`
- `Sr`
- `Pb`
- `Cl`
- `O`
- `H`

### 3.2 当前支持的 profile 推断

当前 GUI 和验证服务会对已分配结构给出启发式矿物 profile 推断：

- Montmorillonite（蒙脱石）
- Beidellite（贝得石）
- Mica（云母类）
- Kaolinite（高岭石）

注意：

- 这是**建议性推断**，用于辅助检查，不是严格矿物学判定。
- 如果 profile `confidence` 较低，说明结构特征在多个 profile 之间不够区分，必须人工复核。

### 3.3 当前输入格式

当前推荐输入格式：

- `cif`
- `xyz`
- `extxyz`

其他由 ASE 支持的结构格式也可能可用，但当前回归验证主要覆盖：

- `cif`
- 周期性 `xyz/extxyz`

## 4. 安装

### 4.1 Windows GUI 免安装包

Windows 普通用户推荐使用独立 GUI 可执行文件：

1. 从发布页或 CI artifact 下载 `ClayFF-Toolkit.exe`
2. 双击运行：

```text
ClayFF-Toolkit.exe
```

首次启动可能较慢；如果 Windows Defender 弹出提示，请确认来源可信后再运行。

如需在不打开 GUI 窗口的情况下检查可执行文件是否完整，可在 PowerShell 中执行：

```powershell
.\ClayFF-Toolkit.exe --smoke-test
```

### 4.2 命令行/开发安装

Linux 用户在项目根目录执行：

```bash
bash scripts/install-clayff-toolkit.sh
```

Windows 开发者或命令行用户在 PowerShell 中执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-clayff-toolkit.ps1
```

安装脚本会在仓库内创建或复用 `.venv`，并把稳定的 `clayff-toolkit`
启动器写入用户级命令目录。Linux 写入 `~/.local/bin`，Windows 写入
`%LOCALAPPDATA%\ClayFF-Toolkit\bin`。脚本也会更新用户级 PATH，因此重启或重新打开终端后仍可直接使用：

```bash
clayff-toolkit --help
```

如果命令存在，说明本地可执行入口已经安装成功。

如果只需要命令行功能、不需要 GUI，可执行：

```bash
bash scripts/install-clayff-toolkit.sh --no-gui
```

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-clayff-toolkit.ps1 -NoGui
```

开发者也可以继续使用 editable install：

```bash
python -m pip install -e '.[gui]'
```

但这种方式只保证当前 Python 环境可用；如果虚拟环境没有激活，重启后可能仍然找不到
`clayff-toolkit` 命令。开发和测试时请使用仓库内的 `.venv`：

```bash
./.venv/bin/python -m pytest
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 5. 快速开始

### 5.1 只做 ClayFF 分配

适用于已经准备好的周期结构，直接输出 `.data` 文件：

```bash
clayff-toolkit assign input.cif output.data
```

也可以指定 ClayFF 参数文件：

```bash
clayff-toolkit assign input.cif output.data --clayff ./src/clayff_toolkit/resources/clayff.txt
```

### 5.2 分配后顺便检查净电荷

```bash
clayff-toolkit pipeline input.cif output.data
```

命令会输出：

- 写出的 `.data` 文件路径
- `net_charge=...`

### 5.3 一步完成“同晶置换 -> 分配 -> 校验 -> 导出”

这是当前最推荐的单命令工作流：

```bash
clayff-toolkit workflow input.cif substituted.cif output.data --preset octa-only --interlayer Ca
```

命令会依次输出：

1. 置换后结构文件路径
2. 导出的 `.data` 文件路径
3. `net_charge=...`

### 5.4 单独检查已有 `data` 文件的净电荷

```bash
clayff-toolkit charge output.data
```

返回值是净电荷数值。

### 5.5 启动 GUI

```bash
clayff-toolkit visualize
```

也可以直接带上参数文件和已有 `data` 文件：

```bash
clayff-toolkit visualize --clayff ./src/clayff_toolkit/resources/clayff.txt --data output.data
```

## 6. 命令行详细说明

### 6.1 `assign`

用途：

- 对已有结构直接执行 ClayFF 分配

基本格式：

```bash
clayff-toolkit assign <输入结构> <输出data>
```

参数：

- `input`：输入结构路径
- `output`：输出 `.data` 文件路径，或输出目录
- `--clayff`：ClayFF 参数文件路径

### 6.2 `pipeline`

用途：

- 对已有结构执行分配并计算净电荷

基本格式：

```bash
clayff-toolkit pipeline <输入结构> <输出data>
```

### 6.3 `workflow`

用途：

- 单命令完成“置换 -> 分配 -> 校验 -> 导出”

基本格式：

```bash
clayff-toolkit workflow <输入结构> <置换输出结构> <输出data> [选项]
```

常用选项：

- `--preset {tetra-octa,octa-only}`
- `--interlayer {Ca,Na}`
- `--seed <整数>`
- `--strict-ratio`
- `--clayff <路径>`

示例：

```bash
clayff-toolkit workflow \
  tests/fixtures/substitution_input/cammt_c2m_32.cif \
  /tmp/cammt_substituted.cif \
  /tmp/cammt_substituted.data \
  --preset octa-only \
  --interlayer Ca
```

### 6.4 `substitute`

用途：

- 直接调用原始同晶置换引擎

说明：

- 这个入口保留了 legacy substitution engine 的参数风格。
- 如果你只想完成标准单结构工作流，优先使用 `workflow`。

### 6.5 `visualize`

用途：

- 启动分步向导式 GUI

参数：

- `--clayff`：可选 ClayFF 参数文件路径
- `--data`：可选 LAMMPS `data` 文件路径

## 7. GUI 使用说明

### 7.1 向导结构

当前 GUI 不是旧式单页面板，而是三步向导：

1. 同晶替换
2. 力场赋予
3. 力场校验与导出

左侧边栏用于步骤切换。完成上一步后，再点击“下一步”进入下一页。

### 7.2 同晶替换页面

该页面负责：

- 选择输入结构
- 设置替换输出路径
- 导入已有替换结果
- 选择替换规则
- 选择层间离子
- 执行同晶替换
- 预览替换后结构

### 7.3 力场赋予页面

该页面负责：

- 选择 ClayFF 文件
- 选择用于赋予的结构来源
- 执行 ClayFF 分配
- 直接导出当前 `.data`
- 查看局部环境
- 查看 Atom 表
- 选择 `Element / ClayFF Type / Profile` 预览模式

### 7.4 力场校验与导出页面

该页面负责：

- 选择要校验的 `data`
- 载入已有 `data`
- 对 `data` 文件执行校验
- 查看 `data` 级别的 validation warnings
- 导出 LAMMPS `data`

### 7.5 3D 结构视图

当前行为：

- 显示 triclinic 晶胞线框
- 显示所有原子点
- 点击原子可选中
- 选中原子会在右侧显示局部环境信息

颜色逻辑取决于 `Overlay` 模式。

### 7.6 Overlay 模式

当前 GUI 使用 OVITO 默认渲染模式进行结构渲染。当前版本中，结构渲染保留在“同晶替换”页面，用于在执行同晶替换之前预览输入结构。

#### `Element`

按元素着色。

适合：

- 快速看元素分布
- 检查层间离子、水分子和框架原子的大致位置

#### `ClayFF Type`

按分配后的 ClayFF 类型分组着色。

适合：

- 查看 `st / ao / at / mgo / ob / obts / obos / oh / ohs / o* / h*` 的空间分布

#### `Profile`

按 profile 相关特征着色。

当前会高亮：

- 层间离子
- 四面体取代相关位点
- 八面体取代相关位点
- 水分子
- 羟基相关位点

适合：

- 快速判断 profile 推断是否“看起来合理”

#### `Warnings`

按 validation warning 涉及的原子着色。

适合：

- 快速定位 profile 不一致、层间离子不合预期等问题原子

### 7.7 原子选择与局部环境

当前版本以 Atom 表格选择为主，局部环境信息会在“力场赋予”页面更新。

选中后右侧 `Local Environment` 会显示：

- 原子编号、标签、元素
- 分数坐标
- ClayFF 类型
- 电荷
- 邻近原子列表及距离
- 与该原子直接相关的 validation warning

### 7.8 Data 校验面板

当前会显示：

- `data` 文件路径
- atom / bond / angle 数
- atom type / coeff type 数
- 净电荷
- warning 列表

这个面板现在面向最终导出的 `data` 文件，而不是原始结构。

### 7.7 Forcefield Catalog 页

该页展示当前 ClayFF 参数文件中的类型表，包含：

- Type
- Mass
- Element
- Connections
- Charge
- LJ 参数（epsilon, sigma）

适合：

- 检查某个类型是否在参数表内
- 交叉核对电荷和非键参数

### 7.8 Data Preview 页

在导出后或手动载入 `.data` 文件后，界面会显示：

- 原子数
- 键数
- 角数
- 净电荷
- 导出类型统计

适合：

- 快速确认导出结果是否符合预期

## 8. 输出文件说明

### 8.1 `workflow` 的输出

`workflow` 通常会生成两个文件：

1. 置换后的结构文件，例如 `substituted.cif`
2. LAMMPS `data` 文件，例如 `output.data`

### 8.2 `substitute` / `workflow` 的附加输出

置换阶段还会输出：

- `.substitution.json` 日志
- substitution summary 文件

这些文件可用于追踪：

- 选择了哪些 tetra/octa 位点
- 层间离子如何平衡电荷
- 采用了哪一层 placement constraint

### 8.3 `data` 文件内容

当前导出的 `.data` 文件包含：

- Header
- `Masses`
- `Pair Coeffs`
- `Bond Coeffs`（如有）
- `Angle Coeffs`（如有）
- `Atoms # full`
- `Bonds`（如有）
- `Angles`（如有）

## 9. 常见工作流建议

### 9.1 已有结构，只想导出 `data`

用：

```bash
clayff-toolkit assign input.cif output.data
```

### 9.2 想做一套标准置换后结构

用：

```bash
clayff-toolkit workflow input.cif substituted.cif output.data --preset tetra-octa --interlayer Ca
```

### 9.3 想人工检查 profile 与局部环境

先运行：

```bash
clayff-toolkit visualize
```

然后：

1. 载入结构
2. 运行分配
3. 切换 `Profile` 或 `Warnings` overlay
4. 点击原子查看局部环境

## 10. 常见问题

### 10.1 `clayff-toolkit: command not found`

说明当前 shell 的 `PATH` 中没有 `clayff-toolkit` 启动器。

Linux 推荐重新执行用户级安装脚本：

```bash
bash scripts/install-clayff-toolkit.sh
```

然后重新打开终端，或在当前终端执行：

```bash
source ~/.bashrc
```

检查命令位置：

```bash
command -v clayff-toolkit
clayff-toolkit --help
```

Windows 推荐重新执行 PowerShell 安装脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-clayff-toolkit.ps1
```

然后重新打开 PowerShell，检查命令位置：

```powershell
where.exe clayff-toolkit
clayff-toolkit --help
```

如果 PowerShell 拒绝运行脚本，请确认命令中包含
`-ExecutionPolicy Bypass -File scripts\install-clayff-toolkit.ps1`。

### 10.2 GUI 启动失败，提示缺少 Qt

如果使用的是 Windows GUI 可执行文件，先确认文件来自发布页或可信 CI artifact。
然后在 PowerShell 中执行：

```powershell
.\ClayFF-Toolkit.exe --smoke-test
```

如果 smoke test 提示缺少 GUI 依赖，说明可执行文件构建不完整，应重新下载或重新构建 artifact。

如果使用的是 Python/PowerShell 安装脚本，说明 GUI 依赖没有装好。

先检查 GUI 环境：

```bash
clayff-toolkit doctor --gui
```

Linux 执行：

```bash
bash scripts/install-clayff-toolkit.sh
```

Windows 执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-clayff-toolkit.ps1
```

### 10.3 结构能读入，但分配时报不支持元素

说明输入中出现了当前工具尚未接入的元素种类。

应当：

1. 检查结构中是否有意外元素
2. 确认 ClayFF 参数表中是否定义了相应类型
3. 如需扩展元素，继续在 assignment 规则和 ClayFF 参数映射中补齐

### 10.4 `net_charge` 不接近 0

说明结构、置换、电荷平衡或输入体系本身需要复核。

优先检查：

1. 同晶置换数量和层间离子是否匹配
2. 水分子和羟基识别是否合理
3. 输入结构是否存在不完整分子或异常原子

### 10.5 GUI 中 profile confidence 很低

这通常表示：

- 结构同时带有多类 profile 的特征
- 同晶置换/层间离子/含水情况不够典型
- 当前规则对这类体系的区分度还不够高

此时应把它当作“需要人工复核”的信号，而不是 bug。

## 11. 已验证能力

当前仓库已经通过的关键验证包括：

- `assign`
- `pipeline`
- `workflow`
- `visualize`
- GUI `offscreen` smoke test
- CIF 无 warning triclinic 加载
- profile 推断与 validation warning

## 12. 后续增强方向

如果继续扩展，下一步最值得做的是：

1. 更严格的矿物 profile 规则与可人工 override 的 profile 选择
2. 更细的 topology/bond ambiguity 告警
3. substitution provenance 的可视化覆盖层
4. GUI 中可交互的手动确认/忽略 warning 流程
