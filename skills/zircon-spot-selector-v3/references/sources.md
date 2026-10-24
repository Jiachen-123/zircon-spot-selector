# V3资料继承说明

以下是原skill保存、经V2保留的2026-10-18至19访问记录。V3本次核读本地记录，没有重新联网阅读全文。科学原则仅沿用其注明范围；新增规则来自用户明确要求及本次实际读取的本地修正证据，详见upgrade-evidence.md。下文“已读”均指既往记录的访问范围。

# 资料与实际访问范围

核查：2026-10-18至19。只将实际读取范围作为依据；本文件不声称已复现作者同位素分析或其全部软件。

- **S1 Corfu et al. (2003), Atlas of Zircon Textures**, RiMG 53, 469–500。[DOI](https://doi.org/10.2113/0530469)；[实际读取的32页PDF](https://www.micromineral.org/images/stories/pieces_jointes/articles_placers/atlas_%20of_zircon_textures.pdf)。DOI入口失败，但PDF已下载/提取。重点：Zircon imaging pp.470–472/Fig.1；Zoning textures pp.476–478/Fig.4；Xenocrystic cores pp.478–480/Fig.5；Subsolidus…/高压变质 pp.480–486/Figs.6–10；Fracturing/Alteration/Inclusions pp.489–494/Figs.13–15。视觉检查的具体图页见验证记录。图谱有已知地质背景，不能直接给未知样品贴成因标签；普通RL不能冒充HF蚀刻RL。
- **S2 Acevedo Zamora et al. (2026), Forward Image Registration…**, [论文HTML](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025GC012671)及[24页PDF文本](https://agupubs.onlinelibrary.wiley.com/doi/epdf/10.1029/2025GC012671)。实际重点阅读§§2.2.3、2.3.1–2.3.5（尤其2.3.3）、3.1、4.3.1–4.3.3及Fig.3说明。正式发表年2026，不因DOI含2025而写成2025。Fig.3从[作者图件包](https://zenodo.org/records/20267840)提取并视觉查看；下载曾被暂停导致ZIP尾部不全，完整的Fig.3本地条目已提取，不声称整个包完整。S1补充DOCX链接访问失败，未读Text S1选点细则，也未运行MATLAB/QuPath。25 µm、BSE参考及§3.1避核/边仅为该研究配置/策略。
- **S3 UCSB Preston Cloud Lab, Sample Preparation**，[实验室指南](https://petrochronology.geol.ucsb.edu/node/195)。已读整页，重点How to Prepare Samples与How to Prepare Thin Sections：CL、位置图/放大图；20–40 µm只是该页规划范围，不是实径默认值。
- **S4 Dröllner et al. (2021), Every zircon deserves a date…**，[原始研究全文](https://www.cambridge.org/core/journals/geological-magazine/article/every-zircon-deserves-a-date-selection-bias-in-detrital-geochronology/84331A9C52679F6DCB62D72D9969C811)，[DOI](https://doi.org/10.1017/S0016756821000145)。实际阅读§1、§§3–6及Figs.3–5说明，未重算数据。支持区分定量代表性与定向找组分；形状/颜色偏选可改变分布。不推导普适样本数或相同方向的偏差。
- **S5 Zametzer et al. (2025), Grain selection for representative detrital zircon age populations**，[出版社](https://www.sciencedirect.com/science/article/pii/S0012821X25004170)，[DOI](https://doi.org/10.1016/j.epsl.2025.119619)。仅实际读取搜索工具返回的作者摘要/Highlights；全文页打开失败。只补充粒度偏差认识，不采用其模拟样本数为阈值。
- **S6 Gehrels, Valencia & Ruiz (2008), Enhanced precision…**，[全文入口](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007GC001805)，[DOI](https://doi.org/10.1029/2007GC001805)。已实际读取§2 Sample Preparation and Laser Ablation，尤其[6] CL偏选警示、[7]束斑与深度设置。没有把其方法规格直接移植成默认值。
- **S7 Johnston et al., Small-Volume U-Pb Zircon Geochronology…**，[作者机构页](https://digitalcommons.calpoly.edu/phy_fac/314/)。实际阅读机构页摘要，未阅读全文；用于说明空间分辨率和采样深度依赖具体方法，不表示送测实验室可直接使用该小束斑。
- **S8 人工圈点练习数据**，[Zenodo 16750323](https://zenodo.org/records/16750323)，DOI 10.5281/zenodo.16750323。已打开记录页并核对Step 3 manual spot placement、标注贡献者、约3.5 GB ZIP。未下载整个包、未运行QuPath、未把其中点位当通用专家标准答案；实际图像验证优先用用户样品副本。

## 条件差异

S2用BSE参考，旧skill强制RL：现在按局部图像选择并保存变换。S2特定物源例避核/边，S1恰显示核/边可记录不同事件：是否分析由目标决定。S1中均一、暗或振荡纹理都有多种可能，不能亮暗/有无带二分类。S4控制群体偏选不取消局部障碍避让。不同论文/实验室的20–40、25、小体积束斑与旧任务30 µm不合并为默认值；余量、定位预算单列P/E参数。
