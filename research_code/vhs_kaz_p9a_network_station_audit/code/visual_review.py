from common import *
names=['P9A_MAP_ORD_CLAS','P9A_MAP_ORD_STRA','P9A_ORDER_LENGTHS','P9A_FIRST_BASIN_MAP']
q=read(ROOT/'evidence/FIGURE_AUTOMATED_QA.json');q['visual_review']='ALL4_PNGS_INSPECTED';q['visual_review_notes']='Reviewed final4 PNGs: complete national sovereign boundary, visible1-7/>7legend, untruncated largest190.65thousandkm bar,20pilot markers/numbers and distinction from49provisionalgauges. Visual review is not PDF geometry collision certification.';q['visual_review_png_sha256']={n:sha(ROOT/'figures'/f'{n}.png') for n in names};js(ROOT/'evidence/FIGURE_AUTOMATED_QA.json',q)
(ROOT/'P9A_FIGURE_QA_NOTES.md').write_text('''# 图形核验

四张最终PNG已逐张视觉查看：全国主权国界（含拜科努尔）、两个序级和>7图例、所有数值条形完整显示、20点工程试点及49临时站标识可辨。初次条形图固定上限180千km使190.65千km条形被截，已改为实际最大值×1.15并重新导出全部PDF/SVG/PNG，再做字形与视觉核验；未更改任何真实数据。

4图均为单数据面板，对齐检查NOT_APPLICABLE。静态源检查通过（18PASS、0FAIL，3WARN：组会版宽度、300dpiPNG、无TIFF）；4个PDF字形检查通过且最小9pt。标准碰撞工具4次均因PyMuPDF缺失返回NOT_AUDITABLE，未安装依赖、未计为PASS；不能声称自动排版碰撞审计已完成。

河网按每条真实几何绘制，图面线条为栅格化图层、文字保留可编辑PDF/SVG，未随机减少河段、未制造空间预测。GIS坐标为P8相同LAEA，长度始终WGS84测地线。地图只用于研究与组会，不构成官方测绘/业务认证或期刊生产终稿。
''',encoding='utf-8')
event('visual_review_complete',figure_count=4,auto_collision_not_auditable=4)
