"""Build an offline literature registry from inspected publisher snapshots; no models."""
from __future__ import annotations
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
from html.parser import HTMLParser
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'outputs/vhs_bd1m/paper'
CACHE = ROOT / 'reports/literature/e5g0_sources'
DATE = '2026-10-04'
sys.stdout.reconfigure(encoding='utf-8')

# Editorial interpretations, each restricted to the inspected abstract or section.
# Identity fields are extracted from publisher metadata, never supplied here.
# study type; context; method; finding/claim; use; caution; evidence location
NOTES = {
'A1': ('Review', 'Ungauged catchments; continuous discharge', 'Distance-based and regression-based regionalisation', 'Continuous streamflow can be estimated by transferring information from gauged catchments through several regionalisation approaches.', 'P1 importance and P2 regionalisation taxonomy.', 'Review of available approaches; no universal transferability guarantee or local DSK provenance evidence.', 'Abstract'),
'A2': ('Comparative synthesis', 'Ungauged catchments across climate and landscape settings', 'Meta-analysis and leave-one-out assessment', 'Runoff-hydrograph prediction performance varies with climate, catchment properties and regionalisation approach.', 'P1 PUB problem; P2 fair discussion of context-dependent regionalisation.', 'Basin holdout differs from chronological holdout; does not establish our reconstruction mechanism.', 'Abstract'),
'A3': ('Comparative synthesis', 'Ungauged flood and low-flow prediction', 'Meta-analysis and leave-one-out assessment', 'Flood and low-flow regionalisation skill depends on climate and catchment characteristics.', 'P1 observational limitations and P2 regionalisation scope.', 'Extreme-flow signatures are distinct from daily reconstruction; do not transfer numerical rankings.', 'Abstract'),
'A4': ('Benchmark comparison', 'Pseudo-ungauged catchments in northeast North America', 'LSTM versus conceptual-model regionalisation', 'A shared-data comparison found LSTM regionalisation more accurate than the tested conceptual approaches across most study catchments.', 'P1 information transfer; P2 acknowledge ML strengths.', 'Regional sample and tested models bound the comparison; title must not become a universal superiority claim.', 'Abstract'),
'B1': ('Method and benchmark', 'CAMELS rainfall-runoff catchments', 'Local and regional LSTM; SAC-SMA plus Snow-17 comparison', 'LSTM models can learn long-term input-output dependencies and benefit from regional training in the tested rainfall-runoff setting.', 'P2 sequence-learning family and temporal storage representation.', 'Prediction skill is not causal identification; not a river-network routing test.', 'Abstract'),
'B2': ('Large-sample benchmark', 'CAMELS multi-basin rainfall-runoff', 'Entity-Aware LSTM with meteorology and static attributes', 'A regional LSTM and its entity-aware variant learn catchment similarities and outperform the evaluated hydrological benchmarks.', 'P2 multi-basin sequence models; acknowledge analysis of learned catchment representations.', 'Counterexample to blanket claims that ML ignores hydrological interpretation; not proof of local residual causes.', 'Abstract'),
'B3': ('Method and benchmark', 'Daily and hourly streamflow prediction in US basins', 'Multi-timescale LSTM', 'Joint modelling of multiple temporal resolutions improves computational efficiency without sacrificing accuracy against separate LSTM models in the evaluated benchmark.', 'P2 timescale-aware ML and distinction between daily envelopes and short peaks.', 'Not a Transformer study or an independent causal attribution method.', 'Abstract'),
'B4': ('Physics-guided graph surrogate study', 'US river networks; snow-dominated watershed and larger basin', 'GNN surrogate, observation fine-tuning, graph data fusion and coarsening', 'Graph connectivity and data fusion allow river-model emulation and reduction of observation mismatch.', 'P2 graph learning; P3 acknowledge existing physics-guided and bias-diagnostic work.', 'Simulation-trained surrogate skill differs from observation skill; data fusion requires accessible gauges and proper withholding.', 'Abstract'),
'B5': ('Network learning benchmark', 'Upper Danube; connected subbasins', 'LSTM local runoff generation plus GNN routing', 'Explicit graph routing improves tested LSTM predictions, particularly at strongly connected downstream locations.', 'P2 recent graph routing; P3 acknowledge routing can matter.', 'One network and evaluated architectures; neither establishes routing failure here nor universal GNN superiority.', 'Abstract'),
'B6': ('Hybrid prediction study', 'Great Lakes gauged and pseudo-ungauged basins', 'Subbasin LSTM predictions plus physics-based routing', 'Spatially recursive routing of local LSTM predictions improves prediction in large and pseudo-ungauged basins relative to the tested lumped baseline.', 'P2 hybrid methods; P3 distinguish local runoff generation from transport.', 'Spatial improvement is context dependent; study already distinguishes spatial aggregation and routing.', 'Abstract'),
'C1': ('Routing model description', 'Headwaters to continental river networks', 'Hillslope unit hydrograph plus channel KWT or IRF-UH routing', 'Runoff generation and channel transport can be represented in separate stages to estimate discharge along a river network.', 'P2 process-based methods; P3 transport cannot substitute for absent local runoff inputs.', 'Separation is a structural modelling principle, not a diagnosis of the BYBLK-DSK reach.', 'Abstract'),
'C2': ('Differentiable framework description', 'Catchment to regional high-resolution hydrology', 'Modular vertical/lateral processes; adjoint optimisation; linear-reservoir and kinematic-wave routing options', 'A differentiable process-based framework supports local runoff operators, river routing and distributed or regionalised parameter estimation.', 'P2 physics-data methods; P3 distinguish routing operator from production operator.', 'Distributed differentiation is established prior work; our simple routing chain is not equivalent to this framework.', 'Abstract; routing operator description (linear reservoir module)'),
'C3': ('Global model description', 'Gridded water cycle, river discharge and irrigation', 'Process-based WBM with Muskingum-Cunge or linear-reservoir routing and water-source tracking', 'Routing choice is scale sensitive, and source tracking can distinguish runoff origins and anthropogenic return flows.', 'P2 routing alternatives; P3/D support spatially generated and returned-water contributions.', 'Global gridded implementation does not validate our residence time, topology or reach-specific processes.', 'Abstract; river routing method description'),
'C4': ('Routing representation study', 'Mediterranean rivers across climate and size gradients', 'High-resolution HydroSHEDS-based ORCHIDEE routing', 'Revised routing captures seasonal discharge variability while substantial biases can still arise from the simulated water budget.', 'P3 direct support for separating routing representation errors from runoff/water-budget errors.', 'Routing improvements were useful in this study; cannot cite as evidence that heterogeneity never helps.', 'Abstract'),
'C5': ('Calibration and validation study', 'Mediterranean flash-flood catchment', 'Adjoint-based variational calibration of distributed GRD', 'Distributed calibration can improve predictions; adequacy, identifiability and numerical stability remain relevant constraints.', 'P2 differentiable/adjoint modelling; P3 fair treatment of parameter heterogeneity.', 'Counterexample to general rejection of complexity; not an independent test of our R2 specification.', 'Abstract'),
'D1': ('Global model description and evaluation', 'Groundwater, surface water, human water use and storages', 'WaterGAP hydrology, water-use models and net-abstraction coupling', 'Surface-water and groundwater abstractions, storage and human water use affect water flows represented by large-scale hydrological models.', 'P3 motivate candidate non-routing components without attribution.', 'Global model formulation is not evidence of local reservoir or irrigation activity; sign and magnitude may vary.', 'Abstract; reservoir and net-abstraction model descriptions'),
'D2': ('Field/process assessment', 'Catchment baseflow with groundwater and ungauged tributaries', 'Groundwater-surface mapping, digital filtering and tracer mixing', 'Groundwater discharge contributes to baseflow, but hydrograph-based baseflow estimates need not identify groundwater or tributary sources uniquely.', 'P3 missing contribution and attribution ambiguity; avoid identifying a physical process from residual shape.', 'Site-specific study; baseflow is not synonymous with groundwater and source separation has uncertainty.', 'Abstract'),
'D3': ('Field and modelling process study', 'Tropical glacierised watershed in Ecuador', 'Hydrochemical mixing, time-series analysis and integrated watershed model', 'Meltwater, groundwater and streamflow relationships differ across timescales and pathways.', 'P3 physical plausibility of seasonal and delayed contributions.', 'Different climatic region; neither raw temperature correlation nor Fourier seasonality establishes glacier causation here.', 'Abstract'),
'D4': ('Multi-region observational study', 'Glacier-fed catchments in Canada, Norway and the Alps', 'Warm/dry-event streamflow comparison against long-term regimes', 'Glacier-fed catchments can respond to warm dry periods through meltwater and other storages, with compensation varying among catchments and events.', 'P3 discuss possible seasonal contributions and temperature dependence cautiously.', 'Glacier cover and event conditions matter; no evidence for glacier dominance in this case.', 'Abstract'),
'D5': ('Coupled global model evaluation', 'Large glacierised basins', 'GloGEM coupled with PCR-GLOBWB 2', 'Explicit glacier dynamics and mass loss can change runoff estimates compared with a hydrological model with simplified glacier representation.', 'P3 demonstrate omitted source processes can alter simulated runoff.', 'Model-based and glacier-specific; no inferred glacier contribution fraction at DSK.', 'Abstract'),
'E1': ('Evaluation-method technical note', 'Hydrological models under changed climatic conditions', 'Robustness assessment test inspired by differential split-sample testing', 'Temporal transferability and extrapolation require explicit assessment rather than reliance on calibration performance.', 'P3 generalisation caution and P4 fixed out-of-period evaluation.', 'Climate-robustness assessment differs from our single-year holdout; neither certifies universal generalisation.', 'Abstract'),
'E2': ('Temporal-transferability study', 'Australian unimpaired catchments under climatic contrasts', 'Differential split-sample tests and parameter-stability assessment', 'Calibration and evaluation under different climatic periods reveal context-dependent model transferability.', 'P3/P4 motivate cross-year stability and chronological holdout.', 'Not proof that our short record samples climate extremes or satisfies a full differential split-sample protocol.', 'Abstract'),
'E3': ('Benchmark dataset description', 'US catchments minimally impacted by human activity', 'CAMELS meteorology, streamflow and catchment attributes', 'Public large-sample data and documented attributes support comparative hydrology, with source limitations explicitly described.', 'P2 benchmarks and P4 transparency of data context.', 'Dataset does not prescribe our chronological split or demonstrate leakage prevalence; minimally impacted basins limit direct transfer to regulated rivers.', 'Abstract'),
'E4': ('Network-aware benchmark dataset description', 'Central Europe; nested and intermediate catchments', 'LamaH-CE hourly/daily records, topology, quality and human-impact attributes', 'Connected/intermediate catchments and documented quality and human-impact attributes enable network-aware comparative studies.', 'P2 river benchmarks; P4 source quality and topology-aware evaluation.', 'Connectivity can create shared information; dataset description itself does not prove leakage in other studies.', 'Abstract'),
'E5': ('Statistical runoff modelling and evaluation study', 'CONUS NHDPlus catchments; NLDAS-2 reference runoff', 'Three-part chronological splitting and spatial holdout', 'Separating selection from final accuracy assessment and withholding time and space are used to avoid optimistically biased evaluation from leakage.', 'P4 freeze-before-holdout rationale; state partition roles rather than copying labels.', 'Authors call the selection partition test and final assessment validation; our labels differ. Reference runoff is modelled, not independent measured discharge.', 'Section 1.2 Model validation and selection; Figure 1'),
'E6': ('Differentiable-model parsimony and interpretation study', 'CAMELS-US HBV configurations', 'Static/dynamic and ensemble comparisons; feature replacement experiments', 'Similar predictive skill can coexist with different parameter interpretations; static features may function as proxies or identifiers rather than physical representations.', 'P3 limited support for capacity-versus-interpretation concern and proxy ambiguity.', 'Static geographic/attribute proxies differ from our temporal temperature proxy; does not prove a general literature-wide diagnostic omission.', 'Abstract'),
}

SEARCHES = [
('site.hess.copernicus.org prediction ungauged basins review regionalisation streamflow','A1 A2 A3 A4','Broad PUB/regionalisation discovery.'),
('site.hess.copernicus.org graph neural networks streamflow routing','B4 B5','Graph/network discovery; unrelated urban-drainage and general pages excluded.'),
('site.hess.copernicus.org "comparative assessment" "Part 1" 2013','A2','Accepted final publisher article; review comments and preprints excluded as duplicate identities.'),
('site.hess.copernicus.org "decade" "PUB" review Hrachowitz 2013','Hrachowitz et al. (2013)','Deferred: valid review candidate, but retained four focused A sources; not entered or marked verified in matrix.'),
('site.hess.copernicus.org "Rainfall–runoff modelling using" "2018"','B1','Accepted publisher version rather than secondary index.'),
('site.hess.copernicus.org "Towards learning universal"','B2','Accepted large-sample LSTM benchmark.'),
('site.gmd.copernicus.org "mizuRoute" "2016"','C1','Accepted routing model description.'),
('site.hess.copernicus.org "differentiable" "routing"','C5 E6','Accepted publisher papers with scope restrictions; computing/vehicle routing excluded.'),
('site.gmd.copernicus.org "RAPID" "2011"','RAPID-related pages','Deferred: insufficient targeted original identity from this query; not inserted.'),
('site.hess.copernicus.org "mHM" "2010" multiscale','mHM-related papers','Deferred: no focused original added; C5/C2 used for distributed parameterisation.'),
('hydrology "data leakage" temporal validation benchmark','E5','Accepted hydrology-specific explicit split/leakage discussion; social posts and unrelated forecasting papers excluded.'),
('site.hess.copernicus.org "nonstationary" "split-sample" testing','E1 E2','Accepted explicit transferability evaluations.'),
('site.hess.copernicus.org "CAMELS" "2017" attributes dataset','E3','Accepted original dataset description.'),
('site.hess.copernicus.org glacier melt streamflow contributions Huss Hock 2018','D3 D4 D5; Huss and Hock (2018)','Accepted focused open publisher sources; Huss/Hock candidate deferred, not needed for additional coverage.'),
('site.hess.copernicus.org "reservoir" "irrigation" "WaterGAP" 2021','D1','Accepted original model description; review comments not used as scientific evidence.'),
('site.hess.copernicus.org "groundwater" "baseflow" review','D2','Accepted original field/process paper after publisher-page lookup.'),
('"10.1029/2023WR035337"','Bindas et al. (2024)','Deferred in this query; later precise search verifies publisher identity but not added to matrix.'),
('"RAPID" "David" "2011" river discharge','RAPID software/citation pages','Deferred: developer pages establish context, but C1-C5 provide adequate original routing coverage.'),
('"differentiable" "hydrological" "Feng" "2022WR032404"','Feng et al. (2022)','Deferred: secondary index alone not accepted; B6/C2 provide verified hybrid coverage.'),
('site.hess.copernicus.org "Gauch" "training" "2021"','B3','Accepted only verified multi-timescale article; no inference of a different Gauch title.'),
('site.hess.copernicus.org "WaterGAP" "2.2d"','D1','Accepted original GMD article; preprints excluded as duplicates.'),
('site.hess.copernicus.org "hybrid" "Yu" "2107"','B6','Accepted exact publisher article by direct lookup.'),
('Bindas 2024 differentiable Muskingum Cunge river routing physics informed machine learning','Bindas et al. (2024)','Relevant original publisher and NOAA manuscript located; deferred from selected matrix, not a negative scientific assessment.'),
('site.gmd.copernicus.org "routing" "linear reservoir"','C2 C3 C4','Accepted explicit routing formulations; off-topic routing pages excluded.'),
('site.hess.copernicus.org "Li" "transferability" "1239"','E2','Accepted original publisher identity.'),
('"Catchment scale runoff time-series generation and validation" authors DOI','E5','Accepted publisher text and author manuscript; verified DOI and complete author list.'),
('site.hess.copernicus.org "Gauch" "data" "much" "2021"','Gauch-related papers','No additional reference accepted; B3 retained only for its actual timescale contribution.'),
('site.hess.copernicus.org "LamaH-CE" "2021"','E4','Accepted original ESSD dataset paper, not secondary index.'),
]

def clean(text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(html.unescape(text)))).strip()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            self.values.setdefault(attrs.get('name', attrs.get('property', '')), []).append(attrs.get('content', ''))

def main():
    protected = {p: sha(p) for p in (ROOT/'outputs/vhs_bd1m').rglob('*') if p.is_file() and (p.name.startswith('e4') or p.name.startswith('e5a'))}
    manifest = json.loads((PAPER/'e5a_reproducibility_manifest.json').read_text(encoding='utf-8'))
    for source in manifest['source_files'].values():
        assert sha(ROOT/source['path']) == source['sha256'], source['path']
    assert 'E5F1_WORDING_POLISH_COMPLETE=true' in (PAPER/'e5f1_status.txt').read_text(encoding='utf-8-sig')
    metadata = json.loads((CACHE/'metadata.json').read_text(encoding='utf-8'))
    urls = json.loads((CACHE/'urls.json').read_text(encoding='utf-8-sig'))
    evidence_dir = PAPER/'e5g0_verification_sources'
    evidence_dir.mkdir(exist_ok=True)
    rows = []
    for rid, note in NOTES.items():
        m = metadata[rid]
        title = clean(m['citation_title'][0])
        authors = '; '.join(m['citation_author'])
        year = re.search(r'\d{4}', m['citation_publication_date'][0]).group()
        doi = m['citation_doi'][0].removeprefix('https://doi.org/').lower()
        venue = clean(m['citation_journal_title'][0])
        assert title and authors and venue and re.fullmatch(r'10\.\d{4,9}/\S+', doi)
        assert int(year) <= 2026
        if rid != 'E5':
            assert doi.endswith(urls[rid].rstrip('/').replace('https://','').split('/')[2]+'-'+urls[rid].rstrip('/').split('/')[-2]+'-'+year) or doi == '10.5194/'+('-'.join([urls[rid].split('.')[0].split('//')[-1],*urls[rid].rstrip('/').split('/')[-3:]]))
        raw = (CACHE/f'{rid}.html').read_text(encoding='utf-8')
        parser = MetadataParser()
        parser.feed(raw)
        for field in ('citation_title','citation_author','citation_publication_date','citation_doi','citation_journal_title'):
            assert parser.values[field] == m[field], (rid, field)
        abstract = clean(m.get('citation_abstract', m.get('description',['']))[0])
        # Local verification payload stores identity and evidence pointer, not a copied article.
        verification = {'reference_id':rid,'accessed_on':DATE,'url':urls[rid], 'doi':doi,'title':title,'authors':authors,'year':year,'journal':venue,'raw_html_cache':str((CACHE/f'{rid}.html').relative_to(ROOT)),'raw_html_sha256':sha(CACHE/f'{rid}.html'),'evidence_location':note[6],'metadata_sha256':sha(CACHE/'metadata.json'),'verification_scope':'Bibliographic identity plus inspected abstract/identified sections; not every claim in full article.'}
        (evidence_dir/f'{rid}.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        rows.append(dict(category=rid[0],reference_id=rid,authors=authors,year=year,title=title,journal_or_venue=venue,doi=doi,url_or_source=urls[rid],study_type=note[0],hydrological_context=note[1],method=note[2],main_finding_relevant_to_this_paper=note[3],claim_supported=note[3],how_we_should_use_it=note[4],limitations_or_caution=note[5],verified='true',verification_source=urls[rid],verification_date=DATE,evidence_location=note[6],verification_snapshot=str((evidence_dir/f'{rid}.json').relative_to(ROOT))))
    assert len({r['doi'] for r in rows}) == len(rows)
    # The JSON is the shared input for the requested plain CSV and Markdown registry.
    (CACHE/'matrix_rows.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    counts = Counter(r['category'] for r in rows)
    matrix = ['# Literature evidence matrix', '', f'Verification date: {DATE}. Selected evidence map, not a systematic or exhaustive review.', '', 'Verified means bibliographic identity and the specified abstract/sections were inspected. Literature does not establish local DSK mechanism or observation provenance.', '', 'Coverage: '+', '.join(f'{c}={counts[c]}' for c in 'ABCDE')+'.', '', '## Claim-map limits', '', '- Central research gap: PARTIALLY_SUPPORTED. C4 and D2 support distinguishing water-budget/source errors from transport; E6 supports cautious interpretation of predictive features. B2, B4, B6 and C5 show that existing work already addresses interpretation, physics and spatial structure.', '- Not established: the prevalence claim that predictive workflows generally increase capacity while neglecting mechanism. No priority or first-ever claim is warranted.', '- A supports PUB and regionalisation. A literal operational virtual-station or missing-record infilling literature is not comprehensively covered; use discharge reconstruction as the study framing, not a survey claim.', '- Transformer-specific comparison is not covered and should not be asserted; verified LSTM, graph and hybrid examples suffice for P2.', '- Raw temperature seasonal-proxy interpretation is a study hypothesis/diagnostic; E6 concerns different feature proxies and cannot validate T7 causally.', '', '## References and scoped claims', '']
    for r in rows:
        matrix += [f"### {r['reference_id']} — {r['title']}",'']
        for key in r:
            value = r[key]
            if key in ('url_or_source','verification_source'):
                value = f'[{key}]({value})'
            matrix.append(f'- **{key}**: {value}')
        matrix.append('')
    (PAPER/'e5g0_literature_evidence_matrix.md').write_text('\n'.join(matrix)+'\n',encoding='utf-8')
    skeleton = '''# Introduction skeleton — five paragraph claim map

Planning bullets only; final Introduction prose has not been written. Reference IDs resolve in the literature matrix. Study protocol comes from the current frozen manifest and claim ledger, not from external literature.

## Paragraph 1 — Problem importance

- Topic: reliable streamflow information is required for water-resource decisions; ungauged and poorly gauged locations motivate information transfer and reconstruction.
- Supported citations: A1 regionalisation review; A2 hydrograph synthesis; A3 flood/low-flow synthesis; A4 pseudo-ungauged evaluation.
- Avoid a numerical global gauge-coverage trend or a claim about missing-record frequency: not established by this selected matrix. The term virtual hydrological station describes this reconstruction setting; no claimed exhaustive review of that term.
- Do not introduce study results.

## Paragraph 2 — Existing approaches

- Process/conceptual models and regionalisation: A1-A4, C1-C5. Strengths: process structure, transport and spatial transfer. Limits: forcing, parameterisation, model adequacy and context-dependent transferability.
- Sequence ML: B1-B3. Strengths: temporal dependencies, multi-basin learning and multiple timescales. Limits: prediction skill alone does not identify a local physical source.
- Graph/network ML: B4-B5. Strengths: topology-aware information exchange and routing. Limits: training targets and observation access affect interpretation and applicability.
- Hybrid physics-data approaches: B6, C2, C5. Existing work already combines local runoff production with transport and interprets spatial effects.
- No claim that existing approaches are ineffective. Do not imply Transformer literature was reviewed; add a verified Transformer source if that family is retained in the eventual prose.

## Paragraph 3 — Specific research gap

- SUPPORTED_COMPONENT: reconstruction errors can involve transport/routing representation, missing or biased local water inputs, and unresolved source/pathway contributions (C1, C3-C4, D1-D5).
- SUPPORTED_COMPONENT: predictive success and feature/parameter interpretation need not be equivalent (D2, E6); transferability deserves explicit evaluation (E1-E2, E5).
- PARTIALLY_SUPPORTED_GAP: "Existing predictive workflows often emphasize improving model capacity, while the source of reconstruction error may remain mechanistically ambiguous."
- Evidence supports the possibility of ambiguity and the value of diagnosis, but not the word "often" as a field-wide prevalence statement. B2/B4/B6/C5 provide counterexamples to neglect of physics or interpretation. A systematic comparison of diagnostic practices is still needed for that broad sentence.
- Safe study-specific objective: distinguish, in the tested upstream-to-downstream configuration, insufficient routing representation from unresolved incremental downstream contribution, then test whether meteorological predictability adds information beyond a seasonal null.
- Seasonal versus temperature-proxy distinction is an explicit study diagnostic; E6 is an analogy about other proxies, not evidence that raw temperature is a seasonal proxy at DSK.
- Novelty boundary: contribution is the assembled diagnostic sequence and evidence discipline for this case, not invention of routing, Fourier analysis, LOYO or bootstrap.

## Paragraph 4 — What this study does

- Describe the BYBLK-to-DSK reconstruction configuration and the tested homogeneous/heterogeneous routing formulations, without reporting performance.
- Diagnostic sequence: routing-complexity diagnosis → downstream residual diagnosis → meteorological ablation → seasonality versus temperature-proxy decomposition → cross-year stability → freeze-before-holdout evaluation.
- Fourier6 is a low-capacity seasonal residual representation; it is not a new hydrological mechanism or a physical source-identification model.
- Literature anchors: C1-C5 separate process/transport issues; D2 cautions against source attribution from aggregate flow; E1-E2/E5 motivate out-of-period evaluation; E6 motivates cautious proxy interpretation.
- Protocol: fit on 1978–1981; development validation in 1982; fixed-method holdout in 1983. No refitting on 1982 before holdout; no test-based model selection.
- Additional monthly comparison has unresolved primary provenance and explicit unit metadata; report external monthly-series consistency only.

## Paragraph 5 — Contributions

- Contribution 1: a mechanism-oriented diagnostic framework distinguishing routing complexity from unresolved incremental downstream contribution under the tested parameterisation. This distinguishes error classes without assigning a definitive local physical source.
- Contribution 2: proxy-disambiguation using a seasonal null, temperature anomalies, training-year LOYO stability and moving-block-bootstrap uncertainty. These are predictive diagnostics, not causal identification.
- Contribution 3: strict freeze-before-holdout evaluation with 1978–1981 fitting, 1982 development validation and 1983 fixed-method holdout, plus a numerically distinct external monthly consistency check. No claim of universal generalisation or official independent hydrological validation.

## Remaining editorial decisions before final writing

- Prefer the bounded study-specific objective in P3. Keep the broad prevalence sentence labelled PARTIALLY_SUPPORTED_GAP unless a targeted review supplies additional evidence.
- If discussing literal virtual stations, missing gauge record infilling or Transformers, add focused primary references first. Their absence does not prevent writing the narrower approved framing.
- Event-scale and physical-source limitations belong in the study framing and Discussion; no detailed final performance numbers enter this skeleton.
- Stop here; final prose requires review and approval of this evidence map.
'''
    assert not any(x in skeleton for x in ('48.332194','55.077037','45.034412'))
    (PAPER/'e5g0_intro_skeleton.md').write_text(skeleton,encoding='utf-8')
    log = ['# Literature search and verification log','',f'Date: {DATE} (Asia/Singapore). Mechanism: web search for discovery; direct publisher/author-manuscript page inspection for identity and scoped claims.','', 'This is a targeted selected evidence map. Accepted means included in the matrix; deferred means not selected, not scientifically refuted. Search-result hits and cited references alone were not treated as verified papers.','', '## Discovery searches','']
    for n, (query,candidates,reason) in enumerate(SEARCHES,1):
        log += [f'### Search {n}','',f'- query: `{query}`','- source/database/search mechanism: web search; domain filters where written in query',f'- date: {DATE}',f'- candidate paper(s): {candidates}',f'- accepted/rejected/deferred and reason: {reason}','']
    log += ['## Direct source verification','', 'Publisher pages were downloaded after discovery and inspected through their metadata, abstracts and identified sections. Cached raw pages remain in reports/literature/e5g0_sources; the delivered per-reference snapshots preserve identity, access date, source location and SHA-256.','']
    for r in rows:
        log += [f"- {r['reference_id']}: direct lookup [{r['title']}]({r['verification_source']}); date={DATE}; ACCEPTED; scope={r['evidence_location']}; snapshot={r['verification_snapshot']}."]
    log += ['', '## Exclusions and unresolved scope', '', '- Wikipedia, social posts, general software indexes, review comments and off-topic computing/vehicle routing results were not used to support scientific claims.', '- Preprints and final publisher versions were not counted as distinct references.', '- Wiley/NOAA Bindas routing candidate is relevant but not included; C1-C5 already cover multiple routing formulations. Future inclusion requires the same per-row verification and claim mapping.', '- Broad capacity-first prevalence/novelty claim remains partly supported; a targeted systematic review is required before that wording is promoted.', '- Local physical source attribution and external monthly observation provenance are not resolved by literature.', '', '## Suggested follow-up queries (not executed)', '', '- upstream downstream streamflow reconstruction routing residual diagnostic lateral inflow seasonal baseline ablation', '- virtual hydrological station missing daily gauge records neighbouring stations reconstruction benchmark', '- hydrological machine learning temperature seasonality anomaly ablation spurious correlation', '- streamflow Transformer chronological holdout leakage benchmark publisher', '', '## Acquisition notes', '', '- Initial sandboxed publisher download failed authentication; approved direct download succeeded. No missing source identity was filled from memory.', '- Verification is scoped to source identity and inspected claims, not an exhaustive full-text systematic review.']
    (PAPER/'e5g0_search_log.md').write_text('\n'.join(log)+'\n',encoding='utf-8')
    for p in (PAPER/'e5g0_literature_evidence_matrix.md',PAPER/'e5g0_intro_skeleton.md',PAPER/'e5g0_search_log.md'):
        assert not re.search(r'ChatGPT|Codex|TODO|粘贴的文本',p.read_text(encoding='utf-8'),re.I),p
    for p, old in protected.items():
        assert sha(p) == old, p
    # CSV is authored via the bundled spreadsheet tool using the shared JSON rows.
    node = Path('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    subprocess.run([str(node),str(ROOT/'scripts/export_bd1m_e5g0_csv.mjs')],check=True,cwd=ROOT)
    with (PAPER/'e5g0_literature_evidence_matrix.csv').open(encoding='utf-8-sig',newline='') as stream:
        assert list(csv.DictReader(stream)) == rows
    status = '''E5G0_LITERATURE_MATRIX_BUILT=true
E5G0_INTRO_SKELETON_BUILT=true
REFERENCES_FABRICATED=false
INTRODUCTION_FINAL_DRAFT_WRITTEN=false
NEW_EXPERIMENTS_RUN=false
FROZEN_RESULTS_CHANGED=false
E5G0_EXTERNAL_LITERATURE_COMPLETE=true
READY_FOR_E5G1_INTRODUCTION=true
CENTRAL_RESEARCH_GAP=PARTIALLY_SUPPORTED
FINAL_INTRODUCTION_REQUIRES_USER_APPROVAL=true
'''
    (PAPER/'e5g0_status.txt').write_text(status,encoding='utf-8')
    print('E5G0 complete')
    print('verified_references='+str(len(rows)))
    print('category_counts='+json.dumps(dict(sorted(counts.items()))))
    print('frozen_files_unchanged='+str(len(protected)))
    print(status)

if __name__ == '__main__':
    main()
