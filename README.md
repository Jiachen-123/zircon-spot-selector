# Zircon Spot Selector

一个用于锆石微区分析靶点辅助筛选的 Codex skill。它联合分析同一视野的反射光、透射光和阴极发光（CL）图像，完成图像配准、缺陷识别和 30 µm 圆形靶区筛选，并将最终靶点输出为以 CL 原图为背景、圆圈可独立编辑的 PDF。

> 本工具是保守的辅助筛选工具，不代表已经排除所有亚像素裂缝或不可见包裹体。正式上机分析前必须由专业人员复核原图、掩膜和推荐位置。

## 主要功能

- 必须联合使用反射光、透射光和 CL 三类图像；不接受缺失模态或重复图片代替。
- 自动尝试 ORB + RANSAC 单应性配准，失败时回退到梯度 ECC 仿射配准。
- 自动配准不可靠时停止推荐，并生成网页工具供用户选取人工控制点校正。
- 分别识别三类图像中的裂缝、包裹体、孔洞、破损、颗粒边缘、内部不均一和 CL 环带边界。
- 使用“任一图发现即排除”的联合掩膜，不对三图结果取平均或多数表决。
- 对整个 30 µm 圆形区域进行硬性相交检查，并加入缺陷、颗粒边缘及配准误差安全缓冲。
- 允许某颗锆石输出 0 个可靠靶点，不强行推荐低质量位置。
- 输出诊断掩膜、淘汰原因、坐标表、预览图和可编辑 PDF。
- PDF 中靶点圆为独立 `/Subtype /Circle` 批注，编号为独立 `/FreeText` 批注，不会压平到 CL 背景图中。

## 安装为 Codex Skill

将本仓库克隆或下载到 Codex skills 目录：

```powershell
git clone https://github.com/Jiachen-123/zircon-spot-selector.git "$env:CODEX_HOME/skills/zircon-spot-selector"
```

如果未设置 `CODEX_HOME`，Windows 上通常可放在：

```text
C:\Users\<用户名>\.codex\skills\zircon-spot-selector
```

安装 Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

需要 Python 3.10 或更高版本。如果系统 Python 不在 `PATH` 中，可使用 Codex 自带的 Python 运行环境。

## 必需输入

每组数据必须包含同一视野、同一批锆石且位置对应的三张不同图像：

1. 反射光图像；
2. 透射光图像；
3. CL 图像。

应尽量使用未经缩放的最高分辨率原图。默认分析圆直径为 30 µm，比例尺可以自动识别，也可以手动提供比例尺像素长度或端点。

## 基本用法

```powershell
python scripts/zircon_spots.py analyze `
  --reflected reflected.png `
  --transmitted transmitted.png `
  --cl cl.png `
  --output-dir results `
  --spot-um 30 `
  --safety-um 4 `
  --scale-bar-um 100 `
  --auto-scale
```

手动指定比例尺像素长度：

```powershell
python scripts/zircon_spots.py analyze ... `
  --scale-bar-um 100 `
  --scale-bar-px 98
```

如果自动配准失败，打开输出目录中的 `manual_registration.html`，分别为透射光→反射光、CL→反射光选取至少四个分布较广的对应点，导出 JSON 后重新运行：

```powershell
python scripts/zircon_spots.py analyze ... `
  --registration-points registration_points.json
```

## 主要输出

- `zircon_targets_editable.pdf`：正式成果；CL 原图背景和独立可编辑圆形批注。
- `cl_target_coordinates.csv`：靶点编号、CL 图像名、圆心像素坐标、像素直径、物理直径、比例和置信度。
- `registered_reflected.png`、`registered_transmitted.png`、`registered_cl.png`：配准结果。
- `mask_reflected*.png`、`mask_transmitted*.png`、`mask_cl*.png`：三类图像的独立缺陷掩膜。
- `mask_combined_exclusion.png`：三类缺陷掩膜的联合排除区域。
- `rejected_candidates.csv`、`rejected_candidates.png`：被淘汰候选点及原因。
- `cl_targets_original_preview.png`：PNG 预览，仅供快速检查。
- `registration.json`、`summary.json`、`pdf_validation.json`：配准、筛选及 PDF 验证报告。

## 验证可编辑 PDF

```powershell
python scripts/zircon_spots.py verify-pdf `
  --pdf results/zircon_targets_editable.pdf `
  --report results/pdf_validation.json `
  --mutation-output results/annotation_edit_test.pdf
```

验证会枚举 `/Circle` 批注，并随机修改一个测试圆圈的位置和大小，保存后重新读取，以确认批注未被压平且可编辑。

## 筛选原则

候选圆只有在完整圆形区域满足下列条件时才会保留：

- 不与任意模态识别出的裂缝、包裹体、孔洞或破损相交；
- 不跨越 CL 环带边界或继承核边界；
- 完整位于锆石颗粒内部，并与边缘保持安全距离；
- 圆内亮度、纹理和 CL 响应相对均一；
- 配准误差不超过阈值，并计入安全缓冲区。

详细规则见 [`references/selection-criteria.md`](references/selection-criteria.md)，完整参数说明见 [`references/usage.md`](references/usage.md)。

## 已知限制

- 低分辨率、失焦、过曝、低对比度或噪声可能造成漏检或误排除。
- 亚像素隐裂缝和在现有成像条件下不可见的包裹体无法被可靠排除。
- 抛光痕迹、颗粒重叠、复杂环带和强烈发光异常可能影响分割。
- 自动配准和缺陷掩膜必须人工检查；程序输出不能替代岩相学判断和仪器操作人员确认。

## License

当前仓库尚未添加开源许可证。在添加许可证之前，默认保留全部权利。
