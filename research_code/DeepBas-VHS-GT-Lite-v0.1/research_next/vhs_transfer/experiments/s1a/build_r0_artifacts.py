"""Build new R0 protocol artifacts from existing design and synthetic evidence only."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import numpy as np
from methods_v2 import DISPLACEMENTS, Fold, common_support, Upstream, days

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
REPORTS=ROOT/'research_next/vhs_transfer/reports'

def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n','utf-8')

def main():
    old_path=REPORTS/'vhs_next_s01_s1a_design_contract.json'
    old=json.loads(old_path.read_text('utf-8'))
    tests=json.loads((HERE/'synthetic_test_results.json').read_text('utf-8'))
    config={
        'phase':'VHS-NEXT-S1A-R0', 'version':2,
        'evaluation_identity':'PRE_SPECIFIED_POST_EXPOSURE_DEVELOPMENT_ANALYSIS',
        'real_execution_authorized':False,'synthetic_execution_only':True,
        'original_contract':{'path':old_path.relative_to(ROOT).as_posix(),
                             'sha256':hashlib.sha256(old_path.read_bytes()).hexdigest()},
        'input':deepcopy(old['input']), 'folds':deepcopy(old['folds']),
        'primary':{'regime':'Nominally past-only daily-index regime',
                   'models':{k:deepcopy(old['models'][k]) for k in ('S1A-0','S1A-1')},
                   'windows':deepcopy(old['regimes']['REGIME_2_PAST_ONLY']['features']),
                   'common_support':deepcopy(old['common_support']),
                   'decision_rules':deepcopy(old['decision_rules']),
                   'uncertainty':deepcopy(old['uncertainty'])},
        'placebo':{
            'definition':'U_k(t)=U(t-k); shifted features W_j(t-k)',
            'k_days':list(DISPLACEMENTS),'negative_k_role':'NONCAUSAL_FUTURE_UPSTREAM_PLACEBO',
            'source_centering':'fit W(s) monthly moments on original full legal train anchors; center at month(s), scale; then move anchor s=t-k',
            'source_windows':'U(s-1), mean U(s-7..s-1), mean U(s-30..s-1)',
            'source_parameter_fit_anchors':'original full fold.train; no dev source moments',
            'target_climate':'same original full train target monthly climate for every k including 0',
            'beta_fit_targets':'intersection over all k: train[90:-90]',
            'beta_fit_sources':'all s=t-k in original full training anchor calendar',
            'score_dates':'dev[:-90], all k including 0; source anchors <= dev_end; no wrapping',
            'k0_refit_on_common_train':True,'primary_full_support_kept':True,
            'missing_values':'stop; do not let Q-dependent exclusion change support',
            'near_group_days':[-7,-3,0,3,7], 'far_group_days':[-90,-60,60,90],
            'summaries':['all 13 displacement gains and metrics per year','equal-year macro gain curve',
                         'g(+a)-g(-a) for each a','mean near gain minus mean far gain',
                         'g(0) minus each far gain','mean far gain and far/g(0) if g(0)>0'],
            'p_values':False, 'best_k_selection':False,
            'interpretation':'descriptive synchronization sensitivity; no transport/causal identification',
            'mask_scope_warning':'275 calendar days Jan1-Oct2 per dev year, not full-year placebo evidence'},
        'sensitivity':{
            'S1A-SENS1':{'enabled_for_future_review':True,'calendar':'intercept + sin/cos harmonics 1 and 2',
                         'period_days':365,'Feb29_phase_day':58.5,
                         'fit_support':'same full primary train','upstream_transform':'same frozen monthly upstream anomaly transform as primary',
                         'contrast':'F2+three upstream coefficients versus F2 only; same dates/clipping',
                         'historical_Fourier6_reuse':False,'model_selection_role':False},
            'S1A-SENS2':{'status':'MODEL_AND_INFORMATION_CONTRACT_ONLY',
                         'identity':'NON_OPERATIONAL_DIAGNOSTIC_ONLY','model':'persistence Q_DSK(t-1), no fitted parameters',
                         'required_input':'separate observer-assisted view of DSK history through t-1; dev own-past explicitly allowed ONLY in this view',
                         'comparison':'descriptive full-dev scores against fixed monthly and upstream models, not missing-station ranking',
                         'fit_main_access_to_ownpast':False,'model_selection_role':False},
            'nonoverlap_windows':{'status':'DEFER_REQUIRES_SEPARATE_APPROVAL','days':[[1],[2,7],[8,30]]},
            'noncircular_bootstrap':{'status':'FIXED_OPTIONAL_SENSITIVITY','block_days':[30,60],
                                      'replicates':10000,'seed':20261011,'selection_role':False},
            'difference_cross_correlation':{'status':'DEFER','lags':'not implemented or searched; cannot infer day boundary'},
            'HAC_DM_CW':{'status':'DEFER','reason':'requires separately specified loss process, nesting and dependence assumptions'}},
        'diagnostics':{'correlation':True,'singular_values':True,'condition_number':True,
                       'VIF':True,'per_fold_beta_and_sign_changes':True,'automatic_feature_removal':False,
                       'ridge_search':False},
        'reference_R1':deepcopy(old['models']['S1A-2']),
        'same_day_secondary':'original S0.1 definition retained; not implemented/run/ranked in R0',
        'evidence_levels':{'L1':'conditional retrospective predictive skill',
                           'L2':'descriptive synchronization-sensitive prediction; conditional on placebo pattern',
                           'L3':'not confirmable by S1A alone','L4':'not confirmable by S1A'},
        'TIMESTAMP_CONVENTION_UNVERIFIED':True,
        'unresolved':['MQ generation/calibration independence','daily unit/statistic/day boundary/provider',
                      'no certified new blind test','common meteorological forcing and interannual states uncontrolled'],
        'future_execution_stops':deepcopy(old['stops'])+[
            'R0 phase prohibits all real fitting/prediction/scoring',
            'any k-specific train/score support or source transform drift',
            'future placebo mixed into lawful main model ranking',
            'manual lag/harmonic/CI selection or elevation to independent confirmation'],
        'readiness':{'execution_review':'pending_validation','execution_authorized':False,
                     'restricted_S1A':'CONDITIONAL','S1B':'BLOCKED','S1C':'BLOCKED'}}
    write_json(HERE/'protocol_v2.json',config)
    reviews=[
        ('月季节基线过于简单','ACCEPT_AS_SENSITIVITY','适用但不是实现错误；S0.1已声明仅控制固定月季节性。','保留主基线，新增固定F2及F2+相同上游异常的配对敏感性。','S0.1协议§5、§9'),
        ('训练残差与开发残差存在估计偏差','ACCEPT','训练残差使用同样本估计气候态，确有有限样本乐观性；开发季节漂移也可能存在。不是开发标签参与train均值。','开发残差只用冻结train气候态；不拼接train/dev残差估计分布；承认未覆盖参数估计误差，不改原主拟合。','S0.1协议§5、§7、§8'),
        ('1/7/30日窗口共线性','ACCEPT','适用。固定边界、train标准化和满秩检查已经解决定义/数值门槛；满秩不能保证系数稳定。','记录相关、SVD、条件数、VIF及各折系数符号；不删窗、不选ridge；非重叠窗延期。','S0.1协议§4、§5、§9'),
        ('上游Q可能反映共同气象驱动','ACCEPT','适用；S0.1本就未宣称因果，当前无气象控制。','placebo检验同步性而非识别传播；共同天气、年际状态、自相关仍可解释结果。','S0.1协议§5、§9'),
        ('缺少DSK自身历史诊断','ACCEPT_AS_SENSITIVITY','作为诊断适用；作为完全缺测站合法主对照不适用。','定义Q_DSK(t-1) persistence，单独观察辅助输入契约，只定义不运行，不影响主选择。','S0泄漏审计E1/E2；S0.1信息矩阵'),
        ('三个expanding folds不是真正独立跨年证据','ACCEPT','适用且S0.1§8已明确相邻年、重叠训练与自相关。','保留三个折，身份细化为post-exposure development；不宣称新独立确认。','S0.1协议§3、§8'),
        ('moving-block CI覆盖有限','ACCEPT','适用且S0.1已限定条件于拟合及年份。','保留30/60与10000/seed；补充年内环绕及有效块数讨论；固定非环绕敏感性，不挑CI。','S0.1协议§8'),
        ('日界影响传播时滞解释','ACCEPT','适用且S0.1元数据报告已保留未知。','用Nominally past-only daily-index regime；禁止最优相关lag认证日界；亚日传播仍未证实。','S0.1观测元数据报告'),
        ('加入displaced-upstream placebo','ACCEPT','确属新增检验；S0.1没有该模块。','冻结±3/7/14/30/60/90以及k=0，源月份去季节后移位，共同训练/评分，负k非因果。','本轮用户要求§四'),
        ('区分预测增益和河道物理机制','ACCEPT','适用，已有非因果边界；本轮用L1-L4细化。','L1、条件性L2可讨论；单独S1A不能确认L3/L4。','S0.1协议§5、§9；本轮用户要求§十'),
        ('原协议未明确窗边界或使用开发期标准化','REJECT_WITH_REASON','该假设不适用；原协议已明确t-1/t-7..t-1/t-30..t-1和train-only尺度。','不将已解决项包装成漏洞；本轮增加实际扰动测试验证实现。','S0.1协议§4、§5'),
        ('原bootstrap会直接连接1981与1983','REJECT_WITH_REASON','不适用；原协议规定各年份内部独立抽取。','保持原设计，代码拒绝多年连续或不连续拼接；仅讨论年内首尾环绕。','S0.1协议§8'),
        ('立即加非重叠窗、ridge或HAC/DM/CW','DEFER','不是当前最小实验必要条件；会新增方法选择或假设。','只登记未来需求；不改变主窗口、不加入本轮真实分析。','本轮用户要求§七、§八')]
    review_rows=[{'issue':a,'decision':b,'applicability':c,'action':d,'evidence':e} for a,b,c,d,e in reviews]
    write_json(HERE/'claude_review_matrix.json',review_rows)
    intro='阶段：VHS-NEXT-S1A-R0，2026-10-11。所有新内容为独立v2；原S0/S0.1、E4/E5与论文冻结。本轮只执行CPU人工合成信号测试，未读取真实开发目标值用于拟合、预测或评分。\n\n'
    links='关联：[原S0.1协议](./vhs_next_s01_mq_free_s1a_protocol.md)、[原设计契约](./vhs_next_s01_s1a_design_contract.json)、[v2配置](../experiments/s1a/protocol_v2.json)、[合成测试](../experiments/s1a/synthetic_test_results.json)。\n\n'
    review=intro+links+'# Claude方法学审查逐项裁决\n\n'
    review+='审查范围以用户粘贴的10条核心意见为准；没有独立的Claude全文，不补造未提供的原话。统计审查采用nature-statistics的单位、配对、条件不确定性与主张边界检查。以下条目及JSON共同构成裁决矩阵。\n\n'
    for i,r in enumerate(review_rows,1):
        review+=f"## {i}. {r['issue']} — {r['decision']}\n\n适用性：{r['applicability']}\n\n处置：{r['action']}\n\n证据：{r['evidence']}。\n\n"
    review+='## 不能由审查自动解决的事项\n\n没有新官方来源、单位或日界证明，没有新的盲测。R1/R2/Fourier6的目标监督身份不改变。新增设计既非预暴露的独立预注册，也非真实河流结果。\n'
    (REPORTS/'vhs_next_s1a_r0_claude_review.md').write_text(review,'utf-8')
    protocol=intro+links+'''# MQ-free S1A Protocol v2

## 身份、继承与执行边界

身份固定为 **PRE_SPECIFIED_POST_EXPOSURE_DEVELOPMENT_ANALYSIS**：时间折未参与新模型fit，不等于该年从未被历史研究接触。原S0.1文件不覆盖；v2是独立方法学补充。MQ生成/校准独立性、日Q单位/日均/日界/供数方仍未证实，没有认证新盲测；R1/R2/Fourier6使用过目标训练监督。当前不是strict zero-shot或新的独立确认试验。

本轮禁止真实数据fit、predict、score、真实placebo评价、GPU、历史搜索或E5I1。只允许新代码及CPU合成测试。Python/NumPy版本见实测日志。测试信号明确为ARTIFICIAL，不能当作观测或向原数据目录写入。

## 保持不变的正式主实验

S1A-0为共同train日期上12个DSK月均；S1A-1为同一月均加3系数OLS，无截距。主制度称 **Nominally past-only daily-index regime**。W1(t)=U(t-1)，W7(t)=mean U(t-7..t-1)，W30(t)=mean U(t-30..t-1)。先按训练锚点月份中心化每个W，再用训练异常标准差(ddof=0)标准化。训练DSK减训练月均为OLS目标，SVD pinv rcond=1e-12，三列满秩且每列尺度>1e-12，否则停止；不删列、不自动ridge。

三折为1978–1980→1981、1978–1981→1982、1978–1982→1983；三折fit均从1978-01-31开始，原始上游历史从1978-01-01提供30日预热。共同主训练日期数按日历为1066/1431/1796，开发每年365日；不等于本轮读取的真实有效Q样本数。完整开发日评价保留，缺失/错日/非法Q则停止，不插补、不按结果挑日期。S1A-0/1共享max(raw_prediction,0)，裁剪率及数值改变量必须报告。

实践规则原样保留：三个年份RMSE均改善；三年等权宏平均相对RMSE改善≥2%；30和60日block的描述性95%CI下界均>0；任一年绝对PBIAS恶化>2个百分点或低流RMSE恶化>5%时标NOT_ROBUST_USEFULNESS。2%是预定实践阈值，非通行显著性标准。低流阈值为该折train DSK的20%分位；阈值和选择不看dev。零基线RMSE或必要指标未定义则证据不足；低流基线RMSE=0而新模型>0按恶化处理。不根据placebo结果追溯改阈值。

指标保留逐年RMSE/MAE/NSE/Bias/PBIAS、DeltaNSE、相对RMSE增益、数值日和误差、低流、峰日/峰值误差、逐月偏差、裁剪及最差年；宏平均等权为主，pooled为辅。峰日平峰取最早日期，日期差不代表实测传播时长。同一训练气候态去除后的残差预测误差与原Q误差相同，残差RMSE不是第二份独立证据。真实单位及日均未证明前不把数值日和换算为m³。

## 新安慰剂独立于主判定

详见placebo_design。k=0与12个位移在共同训练和开发掩码上单独拟合评分；主实验原完整支持的结果另列，不能拿完整年RMSE同安慰剂275日RMSE排名。所有位移同一模型容量、冻结季节统计与指标规则，不能选择目标相关最大的k作为新主lag。非因果未来上游只进入诊断。

## S1A-SENS1：固定平滑季节敏感性

在看任何真实S1A结果之前固定两谐波F2：C_F2(t)=a0+a1 sin(phi)+b1 cos(phi)+a2 sin(2phi)+b2 cos(2phi)，phi=2π d365/365。d365从Jan1=0计；非闰年标准日历；闰年Feb29=58.5，Mar1以后减去闰日，确保不同年同一日历日期相位一致。五系数在原full train上OLS拟合，要求秩5。禁止历史Fourier6系数、harmonic搜索或dev拟合。

分别报告F2-only与F2+固定三上游异常OLS。上游仍用主实验同一monthly-centered/scaled特征，只有目标季节基线及对应残差改变，从而检验月阶梯不足；不同时搜索别的上游平滑法。双方共享训练/开发日期和非负规则，不替代S1A-0或选择主模型。F2同样可能欠拟合年际状态，不能消除所有季节/气象混杂。

## S1A-SENS2：DSK Own-Past仅定义诊断

固定persistence：Qhat(t)=max(Q_DSK(t-1),0)，零可调参数。独立观察辅助数据视图，仅含截至t-1的DSK历史；开发年内过去目标观测允许进入此诊断，因此它是 **NON_OPERATIONAL_DIAGNOSTIC_ONLY**，相对完全缺测站任务不可用，亦未认证实际发布时刻。按主完整开发日描述性评分，首日用上一年Dec31。无目标回填进入任何主模型或placebo。不得拿它做缺测任务统一排名、strict zero-shot证明或主模型选择。本轮仅模型/信息契约，不实现读取此视图或运行真实评价。

## 共线性、估计误差与参数解释

对各折固定设计输出相关矩阵、原标准化设计奇异值、2范数条件数、带截距辅助回归VIF、OLS beta与符号；跨折列表比较符号，不输出未经设计的系数显著性。满秩仅是计算门槛，不是可辨识性证明；高共线时单系数、符号与窗口不能各自解释为水文过程。VIF分母近零返回NA并注明等效无穷。1日/2–7日/8–30日非重叠窗口仅延期登记，未经另批不得使用。

训练残差围绕同样本月均会有限样本乐观；开发残差来自独立于该折fit的目标值但该年早已被历史揭示。开发中的季节/年际漂移不等于数据泄漏。当前不改原主估计法或做cross-fit选择；不将train/dev残差作为同分布独立样本，不声称覆盖训练估计误差。

## Bootstrap：保留原规则并限定含义

每开发年份内部独立抽取circular blocks，配对模型用相同索引；三个年份分别重算RMSE/DeltaNSE，再按年等权汇总。10000次、seed20261011、block30与60，95%分位CI。原方法从未把1981和1983接成一段；实现拒绝包含多个日历年的输入，包括相邻年与不相邻年。

年内Dec31→Jan1的人工连接可能扭曲季节/事件边界；365/30≈12.2、365/60≈6.1仅是长度比，不是独立样本数。代码每次分别抽ceil(n/L)块后截断。非环绕敏感性固定同seed/次数/两种block，start均匀来自0..n-L，每块无年内环绕，串接并截断；该方法有边缘权重差异，不能视为无偏修复。全部CI并列，不按有利程度选择。

CI只条件于既定模型与已揭示三个年份；不覆盖训练气候态/scaler/beta的估计、历史方法筛选、年际依赖及新年份/站点/流域泛化。开发275日placebo掩码也有季节覆盖限制；如对其bootstrap，使用其同年连续日期单独抽取，不混用完整年CI。12个位移是固定对照，不是12个独立随机重复，不计算其虚假p值。HAC/Diebold-Mariano/Clark-West延期，未来须先说明损失过程、嵌套、平稳性与依赖假设。

## 时间戳与机制边界

TIMESTAMP_CONVENTION_UNVERIFIED=true。现有文件日期键不能证明日均或瞬时、两站相同水文日、当天实际发布时间及亚日传播时长。固定t-1只是日期索引上的过去，非认证operational forecasting。相关峰或差分互相关不能反向认证日界；差分互相关本轮延期，不用于调主lag。不能将历史R1单河段tau当独立传播观测。

## 冻结参考与代码信息边界

R1仅保留原冻结参考身份：1981与旧目标校准期重叠排除，1982/83历史参考的训练范围仍不同；past-only下NOT_COMPARABLE_INPUT_REGIME。不重路由、移动预测或重新fit。same-day原定义作为原协议次要制度保留，本轮不执行、不实现统一排名。

代码中FitLabels必须恰为该折train，EvalLabels不得传fit；特征函数只接上游视图。真实适配器在R0配置下于打开文件前拒绝，开发标签加载需未来另授权配置及已保存预测SHA。共享CSV的可信拆分过程仍可接触行字符串，API边界不是OS权限隔离：未来应由独立拆分/评分进程处理，禁止将共享原表传入拟合函数。手工改配置、导入原表或滥用own-past仍是人为可绕过路径，不声称全项目零泄漏。当前不提供真实实验CLI，批准后还需独立冻结执行器、记录预测哈希及运行环境后再开放评分。

## 执行准入与停止

通过合成与完整性校验意味着可进入真实执行方案审查，不是执行许可、真实数据质量验证或物理机制PASS。实际运行仍需用户单独批准，确认受限数值/日期身份，冻结具体执行脚本与环境；源hash、日期、尺度、秩、角色、共同mask任一不合格立即停止。不得自动启动S1A、真实placebo、S1B/S1C、GNN、Muskingum、历史D5或E5I1。
'''
    (REPORTS/'vhs_next_s1a_r0_protocol_v2.md').write_text(protocol,'utf-8')
    placebo=intro+links+'''# Displaced-Upstream Placebo预定设计

问题：If upstream discharge contains day-level predictive information, how sensitive is the observed skill to disruption of its temporal alignment with downstream discharge?

## 符号和变换顺序

固定k=±3、±7、±14、±30、±60、±90及真实对齐k=0。U_k(t)=U(t-k)，因此正k取更早上游、负k取未来上游。对原past-only窗口移位：W1,k(t)=U(t-k-1)，W7,k(t)=mean U(t-k-7..t-k-1)，W30,k(t)=mean U(t-k-30..t-k-1)。负k的W30可能混合过去与未来，整个模型仍统一标NONCAUSAL_FUTURE_UPSTREAM_PLACEBO，绝不参与合法预测主排名。

先在每折原完整合法train锚点s上构造未移位W_j(s)，拟合12个源月均C_Wj(m)与去月均后std s_j(ddof=0)。源窗口可以读取train开始前的合法上游预热，但不得用train结束后的上游估计统计量。定义Z_j(s)=[W_j(s)-C_Wj(month(s))]/s_j，最后以s=t-k取Z_j(t-k)。使用窗口锚点源月份month(t-k)，不能用目标月份month(t)，也不逐原始日先去季节后再平均；这保留原S0.1“窗口后去月均”定义。所有k共享同一个原train源统计估计器。

目标气候态仍是原完整train DSK月均C_y(month(t))，同一折所有k包括0完全相同；目标月份不会随上游位移。三系数OLS只在共同训练目标日期拟合Q_DSK(t)-C_y(month(t))，每个k重新拟合自身beta但不调参。训练负k虽相对训练目标t使用未来上游，也只允许用该折train截止日前源日期，不能偷用开发上游来拟合诊断系数。气候态/源尺度用完整合法train是预定共享nuisance fit，不是开发信息。

## 共同支持、边界与k=0

共同训练T*=交集{t在原train，所有k的s=t-k都在原train锚点范围，且窗口原始源日合法}。已知完整日历下等价原train[90:-90]：起日1978-05-01，各折尾日1980/1981/1982-10-02，计划n=886/1251/1616。删除来自固定±90边界约束，不来自目标值、缺测或性能。所有k的源参数仍按原完整合法train拟合，beta按相同T*拟合。

共同开发D*=原开发日交集{所有k的源锚点≤该开发年Dec31且窗口源日合法}。不借下一年上游，也不虚构1984数据；完整日历下为Jan1..Oct2，每年275日。早期开发日的正位移可用合法上一年上游历史。采用保守锚点截止，即便某窗口原始源日可再多一天也不另扩支持。

必须保存原主完整train/365日开发结果；安慰剂k=0另在T*重新fit并在D*评分，其余k同T*/D*。完整主模型亦可额外在D*计算一个明确标注的support-only诊断，但不能用它代替共同T*的安慰剂k=0，或把不同训练/开发支持混排。所有k的缺值/异常导致整个预定比较停止，不按k各自dropna或按目标流量筛mask。无np.roll、周期重复、年末拼接或边界填充。

275日评分不能代表完整年季节覆盖，特别不覆盖Oct3..Dec31。所有计数由日历计算，并非真实Q完整性检查；真实运行尚未获准。共同训练削减也改变拟合精度，所有k统一受此约束，不能把变化解释成位移的纯物理效应。

## 预定输出与解释规则

每年报告13个k的固定指标、g_y(k)=(RMSE0-RMSE_k)/RMSE0；RMSE0来自同一共享季节基线及D*。另报三年等权宏平均gain-versus-displacement曲线，不按不同n加权、不选择best k。

逐绝对位移a报告g(+a)-g(-a)，正负差仅描述较早/未来信息的不对称。near组固定{-7,-3,0,3,7}，far组固定{-90,-60,60,90}；报告near均值−far均值、g(0)−各far gain、far绝对增益及far均值/g(0)。g(0)≤0时保留绝对值与差值，ratio标NA；远位移gain为负不截成0。三年全部并列，峰形只在此固定网格分辨率上描述，±14/±30也完整展示。

没有新增用于追溯修改2%主规则的安慰剂显著性阈值；不把12个k当随机样本做p值，不用最大峰选择新lag。若主比较成立只先支持L1；若真实对齐/近零相对固定far呈稳定优势，可讨论描述性L2，但须报告各年方向、全部曲线及掩码条件。若placebo-compatible、远错位仍相似或不同年份模式不一致，L2证据不足，可能仅保留实际支持的L1。反向未来优势、平坦曲线、残留季节与自相关均必须披露，不反调窗口。

即便出现尖锐近零峰也不能排除共同天气事件或证明河道传播；没有实测日界与独立强迫控制，不能给出L3/L4、亚日时滞、传播速度或因果贡献。新增检验决定解释边界，不替代主实验判定。
'''
    (REPORTS/'vhs_next_s1a_r0_placebo_design.md').write_text(placebo,'utf-8')
    limits=intro+links+'''# 可辨识性、证据等级与未解决风险

## L1：Conditional Predictive Skill

仅当真实主比较满足预定实践规则及代价检查，才可说在三个已揭示开发年、固定月气候态和线性窗口下有条件增量预测价值。不是新的独立确认、因果贡献、所有模型普遍优势、真实零样本站或未来流域泛化。本轮未运行真实实验，因此当前尚未获得真实L1。

## L2：Synchronization-Sensitive Predictive Information

固定错位对照揭示对日级同步的敏感性，是预测层证据；需同时报告共同掩码、共同beta训练日期、源月份统计、各年曲线、远位移保留能力与正负不对称。近零优势可能来自共同天气事件、残留季节或共同状态，绝不等于传播。placebo-compatible时，即使主RMSE改善也不能声称L2已建立，更不能L3/L4。

## L3：Transport-Consistent Evidence

还需独立传播时滞/过程观测、历史对应的河网几何、共同气象强迫控制等一致证据。现有几何及目标Q校准R1不能替代独立传播证据，日界/亚日变化尚不明。S1A与两站Q不能单独确认L3。

## L4：Causal Hydrological Attribution

还需额外过程观测、外生变化或自然实验以及可辩护的因果识别。当前设计不能确认L4，也不能把OLS系数、误差改善、同步峰或上游方向直接命名为因果传播贡献。

## 竞争解释与未解决P0

月阶梯基线不足可被上游变量作为更平滑的日历代理补偿，F2敏感性只检查其中一部分；共同气象事件、年际状态、目标自身持久性、时间自相关仍可产生预测信息。Own-past只是状态代理诊断，不是控制所有混杂；未来信息负对照不能当实时方法。三个重叠expanding折只有三个相邻开发年，不是三次独立水文复制；bootstrap次数不增加年份/流域独立样本量。训练气候态/标准化/beta估计不确定性与历史探索偏差未进入条件CI。

MQ生成/校准独立性UNVERIFIED；原始日Q单位、日均/瞬时、两站真实日界、发布时间、供数方及正式站址仍缺证明；没有认证的新盲测。TIMESTAMP_CONVENTION_UNVERIFIED=true，最大相关lag不能反向证明时间戳。R1/R2/Fourier6既有目标监督身份与旧研究结果保持冻结。

## 泄漏路径与防护范围

已测试：开发目标扰动不改变主预测；未来上游不改变任何k的训练尺度/beta；FitLabels恰为train、EvalLabels拒绝进入fit；past-only不用t及未来输入；所有k同支持；越界停止；bootstrap拒绝跨年；R0真实读取入口先拒绝。主数值模块不导入真实数据读取、GPU或历史模型模块。

仍可能绕过：用户/未来脚本自行读取已揭示原表、错误构造Upstream为目标历史、手工开启配置、看开发结果再改网格/阈值、把Own-Past数据视图传回主模型。Python类型与标志不是对抗性权限隔离；真实适配器的可信CSV拆分层可接触原行字符串，未来须分离拟合与评分进程/视图并记录访问与预测SHA，代码审查拒绝越界。这里只声称已检查路径未发现实现性开发标签泄漏，不认证整个项目或历史人为决策零泄漏。

## 最小可接受结论措辞

未来如主结果支持：“在预先固定但已暴露的历史开发设计下，上游过去日期索引流量相对月季节基线提供条件性增量预测信息。”

如placebo也支持：“该增益对预定义日级错位呈描述性敏感，支持同步预测信息；共同天气与水文状态解释仍未排除。”

不得写“已识别河道因果传播”“已确认物理机制”“严格zero-shot”“新的独立确认试验”或“认证实时预报”。本轮合成测试不是上述真实数据证据。
'''
    (REPORTS/'vhs_next_s1a_r0_identifiability_limits.md').write_text(limits,'utf-8')
    print(json.dumps({'new_reports_written':4,'config_version':2,'synthetic_tests_pass':tests['pass']}))

if __name__=='__main__':
    main()
