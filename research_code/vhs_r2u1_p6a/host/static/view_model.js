/* VHS v0.6 -- model layer: architecture, parameter config, run workflow */
(function () {
  'use strict';
  var V = window.VHS;
  var SUB = [
    { key: 'index', label: '模型架构' },
    { key: 'config', label: '参数配置' },
    { key: 'run', label: '运行方式' }
  ];
  function subnav(active) { return V.subnav('model', SUB, active || 'index'); }

  function architecture(ctx) {
    return V.get('/api/v6/model/registry?dataset=' + V.state.dataset).then(function (d) {
      var cards = d.registry.map(function (m) {
        var leak = m.leakage || {};
        var leakRows = Object.keys(leak).map(function (t) {
          var ok = leak[t].ok;
          return [V.esc(t), { html: ok ? V.pill('谱系检查通过', 'ok') : V.pill('存在违规', 'bad') },
            String((leak[t].violations || []).length)];
        });
        return V.card({
          title: m.id + ' · ' + m.name,
          badge: V.spill(m.status),
          body: '<div class="tagline" style="margin-bottom:8px">' +
            V.pill('已实现：' + V.bool(m.implemented), m.implemented ? 'ok' : 'warn') +
            V.pill('已训练：' + V.bool(m.trained), m.trained ? 'ok' : 'warn') +
            V.pill('已评估：' + V.bool(m.evaluated), m.evaluated ? 'ok' : 'warn') +
            V.pill('执行：' + m.execution, 'bad') + '</div>' +
            '<div class="kv"><dt>输入变量</dt><dd class="mono-s">' + V.esc(m.inputs.join(', ')) + '</dd>' +
            '<dt>输出</dt><dd>' + V.esc(m.output) + '</dd>' +
            '<dt>族</dt><dd>' + V.esc(m.family) + '</dd></div>' +
            '<div class="hr"></div><h4>预测任务的谱系检查</h4>' +
            V.table(['任务', '结论', '违规数'], leakRows) +
            '<p class="notice">' + V.esc(m.note) + '</p>'
        });
      }).join('');

      var roadmap = V.card({
        title: '后续模型架构（仅预留，未实现）',
        lead: '明确区分：已实现 / 仅定义 / 未训练 / 已完成训练 / 已验证。下方全部为 NOT_IMPLEMENTED。',
        body: '<div class="grid4">' + d.roadmap.map(function (r) {
          return '<div class="kpi na"><div class="k">' + V.esc(r.family) + '</div><div class="v" style="font-size:14px">' +
            V.esc(r.name) + '</div><div class="s">' + V.spill(r.status) + '</div>' +
            '<div class="tiny muted" style="margin-top:4px">' + V.esc(r.note) + '</div></div>';
        }).join('') + '</div>'
      });

      var legend = '<div class="kpis">' +
        Object.keys(d.status_legend).map(function (k) {
          return V.kpi(k, '', V.esc(d.status_legend[k]), 'na');
        }).join('') + '</div>';

      var html = subnav('index') +
        V.card({ title: '模型层 · 不是模型名称清单，而是可复现的构建与运行', lead: '当前只有接口与谱系检查；没有任何训练或评估。',
          body: V.banner('bad', 'MODEL_EXECUTION = NOT_AUTHORIZED',
            'prediction = null；仅修改前端按钮不能解除（后端 403 拒绝）。' + V.esc(d.badge_meaning)) }) +
        V.card({ title: '状态定义', body: legend }) +
        '<div class="grid3">' + d.registry.map(function (m, i) { return ''; }).join('') + cards + '</div>' +
        roadmap +
        V.card({ title: '任务类型（严格区分）', body: V.table(['任务', '说明'],
          Object.keys(d.tasks).map(function (k) { return [V.esc(k), V.esc(d.tasks[k])]; })) }) +
        V.card({ title: '独立性声明', body: '<p class="small muted">' + V.esc(d.independence_note) + '</p>' });

      var side = V.sideCards({
        dataset: { id: V.state.dataset, title: V.state.dataset === 'SYRDARYA' ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网',
          crs: V.state.dataset === 'SYRDARYA' ? 'GIS_PENDING' : 'EPSG:3035',
          authorization: V.state.dataset === 'SYRDARYA' ? 'TEACHER_CSV_READ_ONLY' : 'OPEN_METADATA_ONLY' },
        permissions: d.permissions,
        model: { registered_models: d.registry.length, implemented_models: 0, trained_models: 0, evaluated_models: 0,
          notice: d.badge_meaning },
        links: [
          { href: V.href('model', 'config'), label: '参数配置' },
          { href: V.href('model', 'run'), label: '运行方式' },
          { href: V.href('results', 'evaluation'), label: '评估结果' }
        ]
      });
      return { html: html, side: side };
    });
  }

  function configView(ctx) {
    var ds = V.state.dataset;
    var model = (ctx.q.model || 'SYR-B1').toUpperCase();
    return Promise.all([
      V.get('/api/v6/model/config?dataset=' + ds + '&model=' + model),
      V.get('/api/v6/model/configs?dataset=' + ds),
      V.get('/api/v6/model/registry?dataset=' + ds)
    ]).then(function (arr) {
      var d = arr[0], saved = arr[1], reg = arr[2];
      var feats = reg.feature_catalog || [];
      var cfg = d.config;
      var inputsHtml = feats.map(function (f) {
        var on = cfg.inputs.indexOf(f.feature) >= 0;
        return '<label class="chk" style="display:flex;gap:6px;align-items:flex-start;font-size:11.8px;margin:3px 0">' +
          '<input type="checkbox" class="inpBox" value="' + V.esc(f.feature) + '"' + (on ? ' checked' : '') + '>' +
          '<span><b>' + V.esc(f.feature) + '</b>' +
          (f.target_q_derived ? ' ' + V.pill('目标站 Q 派生', 'warn') : '') +
          '<span class="tiny muted" style="display:block">' + V.esc((f.transform_chains || [])[0] || '') + '</span></span></label>';
      }).join('');

      var form = '<div class="formgrid">' +
        '<div class="field"><label>模型</label>' + V.select('cfgModel', ['SYR-B0', 'SYR-B1', 'SYR-B2'], model) + '</div>' +
        '<div class="field"><label>数据集</label><input type="text" value="' + V.esc(ds) + '" disabled></div>' +
        '<div class="field"><label>目标（输出）</label><input type="text" value="' + V.esc(cfg.output) + '" disabled></div>' +
        '<div class="field"><label>时间尺度</label>' + V.select('cfgScale', ['MONTH'], cfg.time_scale) + '</div>' +
        '<div class="field"><label>滞后窗口（月）</label><input type="number" id="cfgLag" min="0" max="24" value="' + cfg.lag_months + '"></div>' +
        '<div class="field"><label>正则系数</label><input type="number" id="cfgReg" step="0.01" min="0" value="' + (cfg.regularization === null ? '' : cfg.regularization) + '" placeholder="空 = 未设"></div>' +
        '<div class="field"><label>随机种子</label><input type="number" id="cfgSeed" step="1" min="0" value="' + (cfg.random_seed === null ? '' : cfg.random_seed) + '" placeholder="空 = 未设"></div>' +
        '<div class="field"><label>任务类型</label>' + V.select('cfgTask', Object.keys(reg.tasks), cfg.task) + '</div>' +
        '<div class="field"><label>训练年份（逗号分隔）</label><input type="text" id="cfgTrain" value="' + V.esc(cfg.train_years.join(',')) + '"></div>' +
        '<div class="field"><label>测试年份</label><input type="text" id="cfgTest" value="' + V.esc(cfg.test_years.join(',')) + '"></div>' +
        '<div class="field"><label>数据版本</label><input type="text" value="' + V.esc(cfg.data_version) + '" disabled></div>' +
        '<div class="field"><label>特征版本</label><input type="text" value="' + V.esc(cfg.feature_version) + '" disabled></div>' +
        '</div>';

      var savedRows = (saved.configs || []).map(function (c) {
        return [V.esc(c.file), V.esc(c.config.model), V.esc((c.config.train_years || []).join(',')),
          V.esc((c.config.test_years || []).join(',')),
          { html: '<span class="mono-s">' + V.esc(c.sha256.slice(0, 16)) + '…</span>' }];
      });

      var html = subnav('config') +
        V.card({ title: '参数配置 · ' + model, lead: '配置可保存为 JSON 以便科研复现；保存 ≠ 执行。',
          body: '<div class="grid2"><div>' + form + '</div><div>' +
            '<h4>输入变量（来自特征谱系目录）</h4><div style="max-height:280px;overflow:auto">' + inputsHtml + '</div>' +
            '</div></div><div class="hr"></div><h4>配置 JSON 预览</h4>' +
            '<pre class="pre" id="cfgPreview"></pre>' +
            '<div class="chips" style="margin-top:10px"><button class="btn primary" id="cfgSave">保存配置 JSON</button>' +
            '<button class="btn" id="cfgCopy">复制 JSON</button>' +
            '<a class="btn" href="' + V.href('model', 'run') + '">下一步：运行方式</a></div>' +
            '<div id="cfgMsg" style="margin-top:9px"></div>' }) +
        V.card({ title: '泄漏预检（按任务）', body: V.table(['任务', '结论'],
          Object.keys(d.leakage_preview).map(function (t) {
            var r = d.leakage_preview[t];
            return [V.esc(t), { html: r.ok ? V.pill('通过', 'ok') :
              V.pill('违规 ' + (r.violations || []).length, 'bad') }];
          })) + '<p class="notice">通过谱系检查不等于已执行实验。</p>' }) +
        V.card({ title: '已保存的配置（' + saved.count + '）',
          body: savedRows.length ? V.table(['文件', '模型', '训练年份', '测试年份', 'SHA-256'], savedRows) :
            V.empty('尚未保存任何配置。') });

      function readCfg(root) {
        var boxes = root.querySelectorAll('.inpBox');
        var inputs = [];
        Array.prototype.forEach.call(boxes, function (b) { if (b.checked) inputs.push(b.value); });
        function nums(id) {
          var el = root.querySelector('#' + id);
          var t = (el && el.value || '').trim();
          if (!t) return [];
          return t.split(',').map(function (x) { return parseInt(x.trim(), 10); })
            .filter(function (x) { return !isNaN(x); });
        }
        function maybeNum(id) {
          var el = root.querySelector('#' + id);
          if (!el || el.value === '') return null;
          var v = parseFloat(el.value);
          return isNaN(v) ? null : v;
        }
        var scale = root.querySelector('#cfgScale');
        var task = root.querySelector('#cfgTask');
        var modelEl = root.querySelector('#cfgModel');
        return {
          model: modelEl ? modelEl.value : model,
          dataset: ds, target: cfg.output, inputs: inputs, output: cfg.output,
          time_scale: scale ? scale.value : 'MONTH',
          lag_months: parseInt((root.querySelector('#cfgLag') || {}).value, 10) || 0,
          train_years: nums('cfgTrain'), test_years: nums('cfgTest'),
          regularization: maybeNum('cfgReg'), random_seed: maybeNum('cfgSeed'),
          data_version: cfg.data_version, feature_version: cfg.feature_version,
          task: task ? task.value : cfg.task, notes: ''
        };
      }

      var side = V.sideCards({
        dataset: { id: ds, title: ds === 'SYRDARYA' ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网',
          crs: ds === 'SYRDARYA' ? 'GIS_PENDING' : 'EPSG:3035',
          authorization: ds === 'SYRDARYA' ? 'TEACHER_CSV_READ_ONLY' : 'OPEN_METADATA_ONLY' },
        permissions: d.permissions,
        links: [{ href: V.href('model'), label: '模型架构' }, { href: V.href('model', 'run'), label: '运行方式' }]
      }) + V.card({ title: '保存位置', tight: true,
        body: '<p class="small mono-s">var/model_configs/</p><p class="notice">仅配置 JSON；不写观测值、不训练。</p>' });

      return {
        html: html, side: side,
        mount: function (root) {
          var pre = root.querySelector('#cfgPreview');
          function sync() {
            var c = readCfg(root);
            pre.textContent = JSON.stringify({ config: c }, null, 2);
          }
          root.addEventListener('change', sync);
          root.addEventListener('input', sync);
          sync();
          var btn = root.querySelector('#cfgSave');
          var msg = root.querySelector('#cfgMsg');
          if (btn) btn.addEventListener('click', async function () {
            btn.disabled = true;
            msg.innerHTML = '<span class="pill">保存中…</span>';
            try {
              var body = JSON.stringify({ config: readCfg(root) });
              var r = await V.api('/api/v6/model/configs', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body
              });
              V.clearCache();
              msg.innerHTML = V.banner('ok', '配置已保存（未执行模型）',
                '文件 ' + V.esc(r.file) + '；SHA-256 ' + V.esc(r.sha256.slice(0, 24)) + '…；executed=' + V.esc(r.executed));
            } catch (e) {
              var extra = '';
              if (e.body && e.body.violations) {
                extra = '<br>违规：' + V.esc(JSON.stringify(e.body.violations).slice(0, 400));
              }
              msg.innerHTML = '<div class="err"><b>' + V.esc(e.message) + '</b>' + extra + '</div>';
            }
            btn.disabled = false;
          });
          var cp = root.querySelector('#cfgCopy');
          if (cp) cp.addEventListener('click', function () {
            var txt = pre.textContent;
            if (navigator.clipboard) navigator.clipboard.writeText(txt);
            cp.textContent = '已复制';
          });
        }
      };
    });
  }

  function runView(ctx) {
    return V.get('/api/v6/model/workflow?dataset=' + V.state.dataset).then(function (d) {
      var steps = d.steps.map(function (s) {
        return '<div class="step ' + s.status + '"><div class="n">' + s.n + '</div>' +
          '<div class="st"><b>' + V.esc(s.title) + '</b> <span class="pill">' + V.esc(s.value) + '</span>' +
          '<p>' + V.esc(s.detail) + '</p>' +
          (s.blockers ? V.ul(s.blockers.map(function (b) { return V.esc(b); })) : '') + '</div>' +
          '<div>' + V.spill(s.status) + '</div></div>';
      }).join('');
      var html = subnav('run') +
        V.card({ title: '运行工作流', lead: '选择研究区 → 选择目标 → 选择模型 → 查看数据资格 → 配置参数 → 验证条件 → 运行 → 查看结果',
          body: '<div class="stepper">' + steps + '</div>' }) +
        V.card({ title: '尝试运行（后端门禁）',
          lead: '按钮只是入口；真正的限制在 API：POST /api/v6/model/execute 始终返回 403。',
          body: '<div class="chips"><button class="btn primary" id="runBtn">运行模型（将被拒绝）</button>' +
            '<a class="btn" href="' + V.href('model', 'config') + '">先配置参数</a></div>' +
            '<div id="runMsg" style="margin-top:10px">' + V.banner('bad', 'MODEL_EXECUTION = NOT_AUTHORIZED',
              '这是当前的真实科研状态：未授权、未训练、无预测。') + '</div>' });
      var side = V.sideCards({
        dataset: { id: V.state.dataset, title: V.state.dataset === 'SYRDARYA' ? 'Syr Darya 锡尔河下游' : 'LamaH-CE 欧洲河网',
          crs: V.state.dataset === 'SYRDARYA' ? 'GIS_PENDING' : 'EPSG:3035', authorization: 'READ_ONLY' },
        permissions: d.permissions,
        links: [{ href: V.href('results', 'station'), label: '结果层' }, { href: V.href('model'), label: '模型架构' }]
      });
      return {
        html: html, side: side,
        mount: function (root) {
          var btn = root.querySelector('#runBtn');
          var msg = root.querySelector('#runMsg');
          if (!btn) return;
          btn.addEventListener('click', async function () {
            btn.disabled = true;
            try {
              await V.api('/api/v6/model/execute', { method: 'POST', body: '{}' });
              msg.innerHTML = '<div class="err">意外：服务端没有拒绝，请检查。</div>';
            } catch (e) {
              msg.innerHTML = V.banner('bad', '请求被后端拒绝（预期行为）',
                'HTTP ' + e.status + ' · ' + V.esc(e.message) +
                '　prediction = ' + V.esc(String(e.body && e.body.prediction)) +
                '<pre class="pre" style="margin-top:8px">' + V.esc(JSON.stringify(e.body, null, 1)) + '</pre>');
            }
            btn.disabled = false;
          });
        }
      };
    });
  }

  V.views.model = async function (ctx) {
    if (!ctx.sub) return architecture(ctx);
    if (ctx.sub === 'config') return configView(ctx);
    if (ctx.sub === 'run') return runView(ctx);
    return architecture(ctx);
  };
})();
