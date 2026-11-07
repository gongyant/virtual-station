"""Finalize only R2 artifacts after numerical and visual QA."""
from analyze import *

def main():
    h=protected();v=load(HERE/'delivery_validation.json');assert v['status']=='PASS'
    names=['s1a_r2_1_strata','s1a_r2_2_concentration','s1a_r2_3_orthogonal','s1a_r2_4_year_swap','s1a_r2_5_four_cell']
    notes=[
        'All three panels retain signed LOW/MID/HIGH bars, explicit n, same y scale; 1981 adverse MID/HIGH and tiny LOW contributions visible.',
        'All three year curves use same 0–365 x and 0–103 y ranges; top5/10/20 orange points remain, no independence claim.',
        'All three panels show both Monthly/F2 and between/within signed values on identical y scales; 1983 F2 adverse within retained.',
        'All six donors/self in each year and both frozen baselines shown on identical y ranges; real filled, controls hollow; 1980 adverse donor retained.',
        'All four cells for both LOW masks retained per year with n and common y limits; 1981 F2 degradation visible; A/B and C/D references explicit.'
    ]
    dump('visual_qa.json',dict(method='Manual inspection of final Python-rendered PNGs at whole-figure and individual a/b/c panels; automated audits on exact final PDFs',figures=[dict(name=n,panels=['a PASS','b PASS','c PASS'],whole_figure='PASS',sha256_png=sha(HERE/f'{n}.png'),review=note) for n,note in zip(names,notes)],readability='No clipped marks/labels, legends separated, all years/controls visible; 183mm design, minimum font verified by PDF audit',cross_year_scales='Matched for comparable panels in every figure'))
    p=REPORTS/(PREFIX+'results.md');text=p.read_text(encoding='utf-8')
    figure_titles=['R2-1｜固定流量分层绝对贡献（365日）','R2-2｜贡献集中度（365日）','R2-3｜正交误差分解（365日）','R2-4｜完整年份交换对照（335日）','R2-5｜四格低状态绝对误差（365日）']
    text+='\n## 图件与完整交付\n\n各图均为回顾性事后诊断点估计；图中年度面板不是独立重复。完整原始格、日期和所有donor在CSV，图件不替代数值清单。\n'
    for n,title in zip(names,figure_titles):
        text+=f'\n### {title}\n\n![{title}](../experiments/s1a_r2/{n}.png)\n\n[PDF](../experiments/s1a_r2/{n}.pdf) · [SVG](../experiments/s1a_r2/{n}.svg)\n'
    text+='\n附加可复核文件：monthly_strata（全部year×month×stratum含空格）、monthly_metrics（主和交换逐月总贡献）、low_flow_month_phase（固定两半月）、low_flow_group_overlap、year_swap_ranks（全部分层/分量名次）、thresholds、pre_swap_validation、delivery_validation、visual_qa及delivery_manifest。\n\n1982主模型净DeltaSSE仅为总绝对日贡献的约1.014%，正负抵消强。初始固定1%占比守卫处于边界，正文仅用绝对贡献，不把CSV中数学有符号比值解释为稳定百分比证据。\n'
    p.write_text(text,encoding='utf-8')
    assert protected()==h
    files=list(HERE.glob('*'));files=[x for x in files if x.is_file() and x.name!='delivery_manifest.json']
    files += [REPORTS/(PREFIX+n) for n in ('results.md','interpretation_limits.md','validation_report.md','status.txt')]
    dump('delivery_manifest.json',{x.relative_to(ROOT).as_posix():dict(sha256=sha(x),bytes=x.stat().st_size) for x in sorted(files)})
    print(dict(status='COMPLETE_STOPPED',delivery_files=len(files),historical_changes=0,fit_calls=0))

if __name__=='__main__':main()
