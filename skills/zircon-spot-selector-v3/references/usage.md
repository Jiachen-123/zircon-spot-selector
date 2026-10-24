# 配置、命令与边界

Python 3.10+；依赖requirements.txt。所有相对路径以计划JSON目录为基准。每样品独立计划、registry、稳定粒ID与新输出目录；不导入旧项目模块。`pdf_engine.py`为内部低级模块；正式V3从workflow.py执行，不能绕过review和共享缺陷检查。

```text
python scripts/workflow.py review --plan batch.json --key p1 --reviewer operator --basis "实际查看三图及完整圆的具体结论" --output reviewed.json
python scripts/workflow.py check --plan reviewed.json
python scripts/workflow.py checkpoint --plan reviewed.json --output checkpoint.json --next-step "继续原PDF下一页"
python scripts/workflow.py resume --checkpoint checkpoint.json
python scripts/workflow.py export --plan reviewed.json --output-dir new-version
python scripts/render_pdf.py --pdf new-version/spots.pdf --output-dir render-v1 --poppler /path/to/pdftoppm
python -m unittest discover -s tests -v
```

review只记录实际已做的检查，不看图、不替用户确认。批量复核可从Python逐点调用record_review，但必须在真实查看后填写具体依据。改坐标、状态、尺度、源图/裁图、缺陷registry或定位依据后指纹失效，要重新实际检查。

## 计划字段

- sample_id明确；source_pdf为无圈原始PDF。现有输入含圈时先保存前版并识别对象来源，不能自动清空全部批注。
- objective显式字符串；未知时null且objective_status=pending；不默认碎屑。碎屑需要sampling_strategy。target_domain/target_count/minimum_count/beam_diameter_um按本批填；没有目标数量用null。count_basis=candidates或accepted，include_image_uncertain仅用户授权候选口径true。
- numbering_start为本批起点；one_per_grain显式；多点需multi_domain_strategy与可区分位置/目标域。
- fields：id、page(原PDF一基)、cl_image、image_size_px、pdf_rect(left,bottom,right,top)、scale及可选scale_y。scale含endpoints_px/value_um/verified/isotropic_verified；非等向不能只取均值。uncertainty_um为径向项字典，未知null。
- 默认native CL顶左→PDF底左轴对齐矩形映射。可选pdf_transform为3×3仿射矩阵，直接native→未旋转PDF用户坐标；支持裁剪、缩放、镜像、90度旋转及仍为轴对齐的椭圆。任意剪切/旋转椭圆不能冒充Circle，会拒绝。源PDF有Rotate/UserUnit先在副本规范化并重新核实映射；不会静默猜测变换。
- 跨重叠视野用physical_frame及native_to_frame_um标明公共物理坐标；只计canonical spots。跨模式展示放panels，不另建相同spot。未知跨页映射时稳定grain_key人工核实，不能声称自动物理去重已充分。
- defect_registry为独立JSON的path和sha256；文件结构sample_id、features数组。每个特征field、kind(circle/polyline/polygon)、certainty、description、source_evidence及center_px/radius_um或points_px/half_width_um。空表也须明确记录未标记不代表没有缺陷；不从灰度自动生成已确认缺陷。光学特征未可靠转移不可直接填CL坐标。
- spots：key、sample_id、grain_key、field、xy_px、include_in_main、coverage、image_judgment、positioning；observation/pending_issues/domain_review/identity_basis/whole_footprint_reviewed及panels[mode].path。panel.native_box_px为对应CL原生裁图框，图册据此正确换算尺寸；不支持默默缩放的裁图，须先提供经验证映射或重裁原生图。缺图在可得模态记录和待办中说明，不复制别的模式。
- uncertain候选需resolution_attempts（具体移位/换域/换粒尝试与仍未解决事项）；suitable不得有unresolved_image_issues。positioning sufficient需positioning_evidence；不自动签核。manual_acceptance true另需acceptance_basis、充分定位、完整预算、人工粒界和无已录冲突。
- interior_polygon_px为人工审查粒界。已知缺陷来自共享registry，不因点位改状态消失。程序仅检查所录特征，没标缺陷不是干净证据。partial/unknown不放常规主图，另表和边缘图。
- aliases保留旧新编号；history保留原/新粒、原/新坐标、动作原因及证据；不要只覆盖旧坐标。previous_panel和previous_spot用于图册旧位对照（换粒不伪叠加）。defect_panels可给实际标记图；缺失会明确显示未提供。
- style.font_size_pt/line_width_pt可调；固定红色实线空心，普通红色数字。可设label_rect_px人工避结构；自动排版只防圈和标签相撞，不识别重要地质结构。

## 同步与恢复

export生成同一计划对应的spots.pdf、review-atlas.pdf、coordinates.csv、state.json、mapping-and-revisions.csv、summary.json、检查点与对象编辑测试。文件哈希写入summary；不允许覆盖旧版本。失败目录有FAILED.json，不算交付。主PDF页序和图像流不变，无封面；图册展示不增主图计数。

归档的reviewed-plan.json保留_plan_base指向原计划数据目录，避免保存到成果目录后相对路径失效；移动原始资料时应重新核实路径与证据并生成新版本。prepared-plan.json仅为内部低级PDF重现计划，不代替V3复核入口。source_clone_warnings记录源PDF结构克隆警告；页面流一致和渲染正常不意味着原始文档全部非视觉结构已修好。

checkpoint为同文件原子快照，包含计划、来源内容哈希、事件链和下一步；断电前最后一次完整快照可恢复。证据源改变会拒绝继续沿用旧复核，须重核与另存。哈希链检测意外不一致，不是数字签名或防恶意改写机制。

导出后用Poppler逐页渲染检查，圈字独立修改副本也要渲染重开；不要以代码验收代替人工全圆检查。没有专家参考标注不能报告地质准确率。
