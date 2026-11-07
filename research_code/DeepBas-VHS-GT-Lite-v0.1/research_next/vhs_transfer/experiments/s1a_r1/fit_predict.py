"""Once-only fit/predict worker. Reads feature and fold-train views, never eval labels."""
import numpy as np
from common import *
from data_roles import split_fit_views,load_fit_view
from methods_v2 import Fold, fit_model, design_diagnostics, common_support, months
from same_day import fit_same_day,diagnostics as same_diagnostics

def main():
    frozen=verify_freeze()
    if (HERE/'prediction_freeze.json').exists() or (HERE/'views').exists():
        raise RuntimeError('One execution already started; no automatic refit')
    split_fit_views()
    all_rows=[]; parameter_rows=[]; diag_rows=[]
    for year in (1981,1982,1983):
        fold=Fold(year); up,labels=load_fit_view(year)
        fold_rows=[]
        specs=[('past_only','PAST_ONLY',0),('same_day','SAME_DAY',0),('f2','F2',0)]
        specs += [(f'placebo_k_{k:+d}','PLACEBO',k) for k in load(HERE/'execution_config.json')['placebo_k']]
        for comparison,family,k in specs:
            fit_dates=common_support(fold,up)[0] if family=='PLACEBO' else fold.train
            dev=common_support(fold,up)[1] if family=='PLACEBO' else fold.dev
            event('FIT_STARTED',fold=year,comparison=comparison,family=family,k=k,
                  target_role='fold train only',target_parameter_fit_start=str(fold.train[0]),target_parameter_fit_end=str(fold.train[-1]),
                  beta_fit_start=str(fit_dates[0]),beta_fit_end=str(fit_dates[-1]),beta_fit_n=len(fit_dates),
                  upstream_role='feature only; no DSK history',code_hashes=frozen['frozen_hashes'],
                  environment_sha256=sha(HERE/'environment.json'))
            if family=='SAME_DAY':
                m=fit_same_day(up,labels,fold); p=m.predict(up,dev)
                diag=same_diagnostics(m,up,fit_dates)
                climate=m.target_climate[months(dev)]
                params={'target_climate':m.target_climate.tolist(),'upstream_monthly_climate':m.source_climate.tolist(),
                        'upstream_scale':m.scale.tolist(),'beta':m.beta.tolist(),'calendar':'monthly'}
            else:
                m=fit_model(up,labels,fold,k=k,placebo=family=='PLACEBO',calendar='fourier2' if family=='F2' else 'monthly')
                p=m.predict(up,dev); diag=design_diagnostics(m,up); climate=m.baseline_raw(dev)
                params={'target_climate':m.target_climate.tolist(),'upstream_monthly_climate':m.transform.climate.tolist(),
                        'upstream_scale':m.transform.scale.tolist(),'beta':m.beta.tolist(),'calendar':m.calendar}
            if not np.isfinite(p['prediction']).all() or not np.isfinite(p['baseline']).all():
                raise ValueError('Nonfinite predictions')
            threshold=float(np.quantile(labels.q,0.2))
            parameter_rows.append({'fold':year,'comparison':comparison,'family':family,'k':k,
                'role':p['role'],'train_low_threshold':threshold,'fit_start':str(fit_dates[0]),
                'fit_end':str(fit_dates[-1]),'fit_n':len(fit_dates),'source_parameter_fit_n':len(fold.train),
                'dev_start':str(dev[0]),'dev_end':str(dev[-1]),'dev_n':len(dev),**params})
            diag_rows.append({'fold':year,'comparison':comparison,'family':family,'k':k,
                'beta_1':diag['beta'][0],'beta_7':diag['beta'][1],'beta_30':diag['beta'][2],
                'sign_1':diag['beta_signs'][0],'sign_7':diag['beta_signs'][1],'sign_30':diag['beta_signs'][2],
                'condition_number':diag['condition_number'],'singular_values':json.dumps(diag['singular_values']),
                'VIF':json.dumps(diag['VIF']),'correlation_matrix':json.dumps(diag['correlation'])})
            for i,d in enumerate(dev):
                fold_rows.append({'fold':year,'comparison':comparison,'family':family,'k':k,'date':str(d),
                    'information_role':p['role'],'q_baseline':float(p['baseline'][i]),
                    'q_prediction':float(p['prediction'][i]),'q_baseline_raw':float(climate[i]),
                    'q_prediction_raw':float(p['unclipped'][i]),'train_low_threshold':threshold})
            event('FIT_AND_PREDICT_COMPLETE',fold=year,comparison=comparison,dev_start=str(dev[0]),dev_end=str(dev[-1]),
                  dev_n=len(dev),evaluation_label_access=False,fit_role='train DSK supervision; upstream features only')
        write_csv(HERE/f'predictions_F{year}.csv',fold_rows)
        all_rows.extend(fold_rows)
    write_csv(HERE/'s1a_r1_predictions.csv',all_rows)
    write_csv(HERE/'s1a_r1_feature_diagnostics.csv',diag_rows)
    dump(HERE/'fitted_parameters.json',parameter_rows,exclusive=True)
    files=[HERE/f'predictions_F{y}.csv' for y in (1981,1982,1983)]
    files += [HERE/'s1a_r1_predictions.csv',HERE/'fitted_parameters.json',HERE/'s1a_r1_feature_diagnostics.csv',
              HERE/'execution_config.json',HERE/'environment.json',HERE/'views_manifest.json']
    seal={'frozen_at':now(),'files':{p.relative_to(ROOT).as_posix():sha(p) for p in files},
          'all_folds_predictions_saved_before_evaluation':True,'prediction_rows':len(all_rows),
          'fits':len(parameter_rows),'code_hashes':frozen['frozen_hashes'],
          'environment_sha256':sha(HERE/'environment.json'),'evaluation_not_started':True}
    dump(HERE/'prediction_freeze.json',seal,exclusive=True)
    event('ALL_PREDICTIONS_FROZEN',prediction_freeze_sha256=sha(HERE/'prediction_freeze.json'),
          fits=len(parameter_rows),rows=len(all_rows),evaluation_label_access=False)
    print({'fits':len(parameter_rows),'prediction_rows':len(all_rows),'predictions_frozen':True,'evaluation_started':False})

if __name__=='__main__': main()
