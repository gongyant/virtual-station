"""Apply the v0.5.1 minimal web fixes to W/static (exact-match patches)."""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Patcher:
    def __init__(self, rel):
        self.p = os.path.join(W, rel)
        raw = open(self.p, "rb").read()
        self.nl = "\r\n" if b"\r\n" in raw else "\n"
        self.s = raw.decode("utf-8").replace("\r\n", "\n")

    def rep(self, old, new, count=1):
        n = self.s.count(old)
        if n != count:
            sys.exit("patch failed in %s (%d matches): %r"
                     % (self.p, n, old[:90]))
        self.s = self.s.replace(old, new)

    def save(self):
        with open(self.p, "w", encoding="utf-8", newline=self.nl) as f:
            f.write(self.s)
        print("patched", self.p)


# ---------------------------------------------------------------- JS
J = Patcher(os.path.join("static", "syrdarya.js"))
if "AbortController" in J.s:
    sys.exit("already patched")
J.rep('''/* VHS v0.5 — Syr Darya (锡尔河下游) workbench + dataset switch.''',
      '''/* VHS v0.5.1 — Syr Darya (锡尔河下游) workbench + dataset switch.
 * v0.5.1: history/hash sync (popstate/hashchange, listeners attached once),
 * request tokens + AbortController drop stale responses, bounded cache keyed
 * by snapshot id, α scenario vs fixed-source residual shown side by side,
 * units/statistic basis, F5 paging + science checks, gaps not drawn as 0.''')
J.rep('''              tab: "flow", width: 3, alpha: 0.75, cache: {}, flagCode: "" };''',
      '''              tab: "flow", width: 3, alpha: 0.75, cache: new Map(), flagCode: "",
              flagOffset: 0, seq: 0, ctrl: null, snap: "" };
  const CACHE_MAX = 150, FLAG_PAGE = 40;''')
J.rep('''  async function get(path) {
    if (Y.cache[path]) return Y.cache[path];
    const r = await fetch(path);
    let body; try { body = await r.json(); } catch (x) { body = { error: "BAD_JSON" }; }
    const out = { status: r.status, body };
    if (r.status < 500) Y.cache[path] = out;
    return out;
  }''', '''  async function get(path, signal) {
    const key = Y.snap + "|" + path;
    if (Y.cache.has(key)) { const v = Y.cache.get(key); Y.cache.delete(key); Y.cache.set(key, v); return v; }
    const r = await fetch(path, { signal, credentials: "same-origin" });
    let body; try { body = await r.json(); } catch (x) { body = { error: "BAD_JSON" }; }
    const out = { status: r.status, body };
    const sid = body && body.snapshot && body.snapshot.snapshot_id;
    if (sid && sid !== Y.snap) { Y.snap = sid; Y.cache.clear(); }
    if (r.status < 500) {
      Y.cache.set(Y.snap + "|" + path, out);
      while (Y.cache.size > CACHE_MAX) Y.cache.delete(Y.cache.keys().next().value);
    }
    return out;
  }
  const live = tok => !!tok && tok.id === Y.seq && !tok.signal.aborted;
  function put(tok, id, html) { if (!live(tok)) return false; el(id).innerHTML = html; return true; }''')
J.rep('''  function switchTo(ds) {
    location.hash = "ds=" + ds;
    el("lamahApp").hidden = ds !== "LAMAHCE";''', '''  function switchTo(ds) {
    const h = "#ds=" + ds;
    if (location.hash !== h) history.pushState({ ds }, "", h);
    applyDs(ds);
  }
  function applyDs(ds) {
    if (ds !== "SYRDARYA" && Y.ctrl) { Y.ctrl.abort(); Y.seq++; }
    el("lamahApp").hidden = ds !== "LAMAHCE";''')
J.rep('''      if (f) f.innerHTML = "锡尔河数据：老师提供的六份 CSV，只读、仅本机展示；文件以 SHA-256 锁定，变化即拒绝服务。" +
        "GIS_PENDING（未使用 EPSG:3035）· MODEL_EXECUTION = NOT_AUTHORIZED · prediction = null。";
      if (!Y.inited) initSyr();''', '''      if (f) f.innerHTML = "锡尔河数据：老师提供的六份 CSV，只读、仅本机展示；启动时整体校验冻结清单（缺项/错哈希即拒绝加载），以不可变内存快照提供。" +
        "GIS_PENDING（未使用 EPSG:3035）· MODEL_EXECUTION = NOT_AUTHORIZED · prediction = null。";
      if (!Y.inited) initSyr(); else if (Y.lastTok !== Y.seq) refresh();''')
J.rep('''  document.querySelectorAll("#dsSwitch button").forEach(b => b.onclick = () => switchTo(b.dataset.ds));''',
      '''  document.querySelectorAll("#dsSwitch button").forEach(b => b.onclick = () => switchTo(b.dataset.ds));
  if (!window.__vhsNavBound) {            /* attached exactly once */
    window.__vhsNavBound = true;
    window.addEventListener("popstate", () => applyDs(currentDs()));
    window.addEventListener("hashchange", () => applyDs(currentDs()));
  }''')
J.rep('''  /* Serialise refreshes so the most recent selection always renders last
   * (prevents a slow earlier request from overwriting a newer panel). */
  Y.chain = Promise.resolve();
  function refresh() {
    Y.chain = Y.chain.then(doRefresh, doRefresh);
    return Y.chain;
  }
  window.VHS_SYR = { state: Y, refresh: () => refresh(), switchTo: ds => switchTo(ds) };

  async function doRefresh() {
    const f = el("footer");
    if (f) f.innerHTML = "锡尔河数据：老师提供的六份 CSV，只读、仅本机展示；文件以 SHA-256 锁定，变化即拒绝服务。" +
      "坐标 GIS_PENDING（不套用 EPSG:3035）· MODEL_EXECUTION = NOT_AUTHORIZED · prediction = null。";
    renderTime(); renderList();
    const codes = Y.mode === "reach" ? [UP, DOWN] : [Y.code];
    renderProfile(codes); renderAvail();
    const fn = { flow: fFlow, metrs: fMetRs, wb: fWb, dq: fDq, pred: fPred, gis: fGis }[Y.tab];
    el("syrPanel").innerHTML = `<div class="empty">加载中…</div>`;
    await fn(codes);
  }''', '''  /* Every refresh gets a token; the previous one is aborted. A response is
   * rendered only if its token is still the newest (stale ones are dropped). */
  function refresh() {
    if (Y.ctrl) Y.ctrl.abort();
    Y.ctrl = new AbortController();
    const tok = { id: ++Y.seq, signal: Y.ctrl.signal };
    Y.lastTok = tok.id;
    return doRefresh(tok).catch(err => {
      if (err && err.name === "AbortError") return;
      if (put(tok, "syrPanel", errBox({ error: "FETCH_FAILED", message: String(err) }) +
          `<button class="btn" id="syrRetry">重试</button>`)) el("syrRetry").onclick = () => refresh();
    });
  }
  window.VHS_SYR = { state: Y, refresh: () => refresh(), switchTo: ds => switchTo(ds) };

  async function doRefresh(tok) {
    const f = el("footer");
    if (f) f.innerHTML = "锡尔河数据：老师提供的六份 CSV，只读、仅本机展示；启动时整体校验冻结清单并生成不可变内存快照（不代表磁盘文件此刻未变，可在 F5 按需复核）。" +
      "坐标 GIS_PENDING（不套用 EPSG:3035）· MODEL_EXECUTION = NOT_AUTHORIZED · prediction = null。";
    renderTime(); renderList();
    const codes = Y.mode === "reach" ? [UP, DOWN] : [Y.code];
    renderProfile(codes, tok).catch(() => {}); renderAvail(tok).catch(() => {});
    const fn = { flow: fFlow, metrs: fMetRs, wb: fWb, dq: fDq, pred: fPred, gis: fGis }[Y.tab];
    put(tok, "syrPanel", `<div class="empty">加载中…</div>`);
    await fn(codes, tok);
  }''')
J.rep('''  async function renderProfile(codes) {
    const dq = await get(B + "/data-quality?limit=1");''', '''  async function renderProfile(codes, tok) {
    const dq = await get(B + "/data-quality?limit=1", tok.signal);
    if (!live(tok)) return;''')
J.rep('''    el("syrProfile").innerHTML = html;
    el("syrProv").innerHTML = provHtml(dq.body.provenance);
  }''', '''    put(tok, "syrProfile", html);
    put(tok, "syrProv", provHtml(dq.body.provenance) + snapHtml(dq.body.snapshot));
  }
  function snapHtml(s) {
    if (!s) return "";
    return `<div class="note">快照 <span class="mono">${e(s.snapshot_id)}</span> · 加载于 ${e(s.loaded_at)} · ${e(s.source_status)}<br>
      “加载时与冻结清单一致”≠“磁盘文件此刻未变”；F5 可按需复核。</div>`;
  }''')
J.rep('''  async function renderAvail() {
    const r = await get(`${B}/availability?year=${Y.year}&month=${Y.month}`);
    if (r.status !== 200) { el("syrAvail").innerHTML = errBox(r.body); return; }
    const a = r.body;
    el("syrAvail").innerHTML = `''', '''  async function renderAvail(tok) {
    const r = await get(`${B}/availability?year=${Y.year}&month=${Y.month}`, tok.signal);
    if (r.status !== 200) { put(tok, "syrAvail", errBox(r.body)); return; }
    const a = r.body;
    put(tok, "syrAvail", `''')
J.rep('''      <dt>KZDAM</dt><dd>${a.kzdam_observed.length ? e(a.kzdam_observed.join(" ")) : tag("NO_OBSERVATION")}</dd></dl>`;
  }''', '''      <dt>KZDAM</dt><dd>${a.kzdam_observed.length ? e(a.kzdam_observed.join(" ")) : tag("NO_OBSERVATION")}</dd></dl>`);
  }''')
# F2
J.rep('''  async function fFlow(codes) {
    const res = await Promise.all(codes.map(c => get(`${B}/discharge?station=SYRDARYA:${c}&year=${Y.year}`)));
    const ann = await Promise.all(codes.map(c => get(`${B}/discharge?station=SYRDARYA:${c}&view=annual`)));''',
      '''  async function fFlow(codes, tok) {
    const res = await Promise.all(codes.map(c => get(`${B}/discharge?station=SYRDARYA:${c}&year=${Y.year}`, tok.signal)));
    const ann = await Promise.all(codes.map(c => get(`${B}/discharge?station=SYRDARYA:${c}&view=annual`, tok.signal)));
    if (!live(tok)) return;
    const pct = v => v === null || v === undefined ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%";''')
J.rep('''        <th>W 由 Q 重算 (10⁶ m³, 假设 Q=m³/s)</th><th>相对差</th><th>状态</th></tr></thead><tbody>${a.body.years.map(y => `
        <tr style="${y.year === Y.year ? "background:#eef4fe" : ""}"><td>${y.year}</td><td>${n(y.W_source)}</td><td>${n(y.W_from_Q)}</td>
        <td>${y.rel_diff === null || y.rel_diff === undefined ? "—" : (y.rel_diff * 100).toFixed(1) + "%"}</td><td>${tag(y.status)}</td></tr>`).join("")}</tbody></table>`).join("");''',
      '''        <th>W 由 Q 重算 (10⁶ m³, 假设 Q=m³/s)</th><th>(W_Q−W_源)/W_源<br><small>分母=源 W</small></th><th>(W_源−W_Q)/W_Q<br><small>分母=Q 积分</small></th><th>状态</th></tr></thead><tbody>${a.body.years.map(y => `
        <tr style="${y.year === Y.year ? "background:#eef4fe" : ""}"><td>${y.year}</td><td>${n(y.W_source)}</td><td>${n(y.W_from_Q)}</td>
        <td>${pct(y.dual_pct && y.dual_pct.pct_denominator_W_source)}</td><td>${pct(y.dual_pct && y.dual_pct.pct_denominator_W_from_Q)}</td><td>${tag(y.status)}</td></tr>`).join("")}</tbody></table>`).join("") +
      `<div class="note">源 W 原值保留、不覆盖；两种分母并列显示。${e((ann[0].body || {}).target_q_notice || "")}</div>`;''')
J.rep('''      ✕ = 疑似占位值（数值等于月份序号），不作为观测绘制；○ = 源表空值。来源：discharge_syr_darya_monthly_all.csv。</div>`;
    el("syrPanel").innerHTML = html;''', '''      ✕ = 疑似占位值（数值等于月份序号），不作为观测绘制；○ = 源表空值；缺测/疑似处折线断开，不画成 0。
      统计口径：月均/月最大/月最小均为源表原值（不重算）。来源：discharge_syr_darya_monthly_all.csv。</div>`;
    if (!put(tok, "syrPanel", html)) return;''')
# F3
J.rep('''  async function fMetRs() {
    const [mm, md, rs, ra] = await Promise.all([
      get(`${B}/meteorology?year=${Y.year}`),
      get(`${B}/meteorology?year=${Y.year}&granularity=daily&month=${Y.month}`),
      get(`${B}/remote-sensing?year=${Y.year}&month=${Y.month}`),
      get(`${B}/remote-sensing?year=${Y.year}`)]);''', '''  async function fMetRs(_, tok) {
    const [mm, md, rs, ra] = await Promise.all([
      get(`${B}/meteorology?year=${Y.year}`, tok.signal),
      get(`${B}/meteorology?year=${Y.year}&granularity=daily&month=${Y.month}`, tok.signal),
      get(`${B}/remote-sensing?year=${Y.year}&month=${Y.month}`, tok.signal),
      get(`${B}/remote-sensing?year=${Y.year}`, tok.signal)]);
    if (!live(tok)) return;''')
J.rep('''    if (ra.status === 200) h += rsGrid(ra.body.months);
    el("syrPanel").innerHTML = h;''', '''    if (ra.status === 200) h += rsGrid(ra.body.months);
    if (!put(tok, "syrPanel", h)) return;''')
J.rep('''    const pts = months.filter(m => m.T_mean !== null).map(m => `${x(m.month)},${yt(m.T_mean)}`).join(" ");
    g += `<polyline points="${pts}" fill="none" stroke="#dc2626" stroke-width="2"/>`;''',
      '''    let seg = [];                       /* break the line at missing months */
    const flush = () => { if (seg.length > 1) g += `<polyline class="tseg" points="${seg.join(" ")}" fill="none" stroke="#dc2626" stroke-width="2"/>`;
      else if (seg.length === 1) g += `<circle class="tseg" cx="${seg[0].split(",")[0]}" cy="${seg[0].split(",")[1]}" r="2.5" fill="#dc2626"/>`; seg = []; };
    months.forEach(m => { if (m.T_mean === null || m.T_mean === undefined) flush(); else seg.push(`${x(m.month)},${yt(m.T_mean)}`); });
    flush();''')
J.rep('''    const pmax = Math.max(1, ...days.map(d => d.P || 0)) * 1.1, bw = (W - L - R) / days.length * 0.7;
    const x = i => L + (i + 0.5) * (W - L - R) / days.length;
    let g = `<svg viewBox="0 0 ${W} ${H}">`;
    days.forEach((d, i) => { g += `<rect x="${x(i) - bw / 2}" y="${H - Bm - (d.P || 0) / pmax * (H - T - Bm)}" width="${bw}" height="${(d.P || 0) / pmax * (H - T - Bm)}" fill="#60a5fa"><title>${d.date} P=${d.P} T=${d.T}</title></rect>`;''',
      '''    const has = v => v !== null && v !== undefined && !Number.isNaN(v);
    const pmax = Math.max(1, ...days.filter(d => has(d.P)).map(d => d.P)) * 1.1, bw = (W - L - R) / days.length * 0.7;
    const x = i => L + (i + 0.5) * (W - L - R) / days.length;
    let g = `<svg viewBox="0 0 ${W} ${H}">`;
    days.forEach((d, i) => { g += has(d.P) ? `<rect x="${x(i) - bw / 2}" y="${H - Bm - d.P / pmax * (H - T - Bm)}" width="${bw}" height="${d.P / pmax * (H - T - Bm)}" fill="#60a5fa"><title>${d.date} P=${d.P} T=${d.T}</title></rect>`
        : `<text class="pmiss" x="${x(i)}" y="${H - Bm - 2}" font-size="8" text-anchor="middle" fill="#9aa4b2">缺<title>${d.date} P 缺测（不画成 0）</title></text>`;''')
# F4
J.rep('''  async function fWb() {
    const r = await get(`${B}/water-balance?year=${Y.year}&width_km=${Y.width}&alpha=${Y.alpha}`);''',
      '''  async function fWb(_, tok) {
    const r = await get(`${B}/water-balance?year=${Y.year}&width_km=${Y.width}&alpha=${Y.alpha}`, tok.signal);
    if (!live(tok)) return;''')
J.rep('''    if (r.status !== 200) { el("syrPanel").innerHTML = h + errBox(r.body); bindWb(); return; }
    const b = r.body, bl = b.balance, s = b.selected_scenario, c = b.checks;''',
      '''    if (r.status !== 200) { if (put(tok, "syrPanel", h + errBox(r.body))) bindWb(); return; }
    const b = r.body, bl = b.balance, s = b.selected_scenario, c = b.checks, R = b.residuals || {};
    const FS = R.fixed_source_record || {}, SS = R.selected_scenario || {};''')
J.rep('''      ["河段降水 P_vol", bl.P_vol], ["河段蒸散发 ET_vol", bl.ET_vol], [`反演引水 α=${b.alpha.toFixed(2)}`, s.value],
      ["残余（源文件公式）", c.residual_recomputed_file_convention], ["残余（标准水量平衡公式，对照）", c.residual_recomputed_standard_balance]];''',
      '''      ["河段降水 P_vol", bl.P_vol], ["河段蒸散发 ET_vol", bl.ET_vol], [`反演引水 α=${b.alpha.toFixed(2)}（所选情景）`, s.value],
      [`固定源残余（源公式·源取水 α=${e(FS.source_alpha_detected)}）`, FS.residual_file_value],
      [`所选 α=${b.alpha.toFixed(2)} 情景残余（源公式）`, SS.residual_file_formula_with_selected_intake],
      ["控制体诊断·固定源取水", FS.residual_control_volume_diagnostic],
      [`控制体诊断·所选 α=${b.alpha.toFixed(2)}`, SS.residual_control_volume_diagnostic]];''')
J.rep('''    let g = `<svg viewBox="0 0 780 ${terms.length * 30 + 20}">`;''',
      '''    let g = `<svg viewBox="0 0 780 ${terms.length * 30 + 20}" id="wbSvg">`;''')
J.rep('''        <text x="${266 + w}" y="${i * 30 + 26}" font-size="11" fill="#111827">${n(t[1], 3)}</text>`; });''',
      '''        <text x="${266 + w}" y="${i * 30 + 26}" font-size="11" fill="#111827" data-term="${i}">${n(t[1], 3)}</text>`; });''')
J.rep('''    h += `<table><thead><tr><th>α</th><th>反演引水</th><th>说明</th></tr></thead><tbody>${b.intake_scenarios.map(x => `<tr style="${Math.abs(x.alpha - b.alpha) < 1e-9 ? "background:#fdf7ec" : ""}"><td>${x.alpha.toFixed(2)}</td><td>${n(x.value, 3)}</td><td>${x.is_measurement ? "实测" : "反演情景（Q 派生）"}</td></tr>`).join("")}</tbody></table>`;''',
      '''    h += `<div class="banner info">固定源残余 = 源文件“残余”列（对应源文件取水 ${n(FS.W_intake_source, 3)}，不随 α 改变）；所选 α 情景残余 = 用所选 α 的引水代入同一公式的情景代数。二者不是同一组收支。
      年度平衡 W 实际数值聚合公式：<b class="mono">${e(b.balance_w_formula)}</b>。单位：${e(R.units || "UNKNOWN")}。${e(b.target_q_notice || "")}</div>`;
    h += `<div class="tblwrap"><table id="wbAlphaTable"><thead><tr><th>α</th><th>反演引水</th><th>情景残余（源公式）</th><th>控制体诊断</th><th>说明</th></tr></thead><tbody>${(R.all_alphas || []).map(x => `<tr style="${Math.abs(x.alpha - b.alpha) < 1e-9 ? "background:#fdf7ec" : ""}"><td>${x.alpha.toFixed(2)}</td><td>${n(x.W_intake, 3)}</td><td>${n(x.residual_file_formula, 3)}</td><td>${n(x.residual_control_volume_diagnostic, 3)}</td><td>反演情景（Q 派生）${Math.abs(x.alpha - FS.source_alpha_detected) < 1e-9 ? " · 源文件取水对应此 α" : ""}</td></tr>`).join("")}</tbody></table></div>
      <div class="note">${e(R.control_volume_definition || "")}</div>`;''')
J.rep('''      <dt>残余符号约定</dt><dd>${c.residual_matches_file_convention ? tag("SUSPECT", "源文件为 dW − P + ET − 引水") : "—"}</dd></dl>`;
    el("syrPanel").innerHTML = h; bindWb();''', '''      <dt>残余公式（源）</dt><dd>${c.residual_matches_file_convention ? tag("UNKNOWN", "源文件为 dW − P + ET − 引水；控制体未定义，待确认") : "—"}</dd></dl>`;
    if (put(tok, "syrPanel", h)) bindWb();''')
# F5
J.rep('''  async function fDq() {
    const r = await get(`${B}/data-quality?limit=40${Y.flagCode ? "&code=" + Y.flagCode : ""}`);
    if (r.status !== 200) { el("syrPanel").innerHTML = errBox(r.body); return; }''',
      '''  async function fDq(_, tok) {
    const [r, sci] = await Promise.all([
      get(`${B}/data-quality?limit=${FLAG_PAGE}&offset=${Y.flagOffset}${Y.flagCode ? "&code=" + Y.flagCode : ""}`, tok.signal),
      get(`${B}/science`, tok.signal)]);
    if (!live(tok)) return;
    if (r.status !== 200) { put(tok, "syrPanel", errBox(r.body)); return; }''')
J.rep('''    let h = `<div class="banner">所有计数均由程序在启动时从六份 CSV 重新计算；数据质量问题只标记、不改写源值。规则版本 ${e(d.rules_version)}。</div>`;''',
      '''    let h = `<div class="banner">所有计数均由程序在启动时从六份 CSV 重新计算；数据质量问题只标记、不改写源值。规则版本 ${e(d.rules_version)}。</div>`;
    h += snapBlock(d.snapshot);
    if (sci.status === 200) h += sciHtml(sci.body);''')
J.rep('''    h += `<h3>质量标记（${codes.map(([k, v]) => `<button class="mbtn ${Y.flagCode === k ? "on" : ""}" data-fc="${k}">${k} ${v}</button>`).join(" ")} <button class="mbtn ${Y.flagCode ? "" : "on"}" data-fc="">全部</button>）</h3>
      <div class="scroll"><table><thead><tr><th>代码</th><th>级别</th><th>范围</th><th>说明</th></tr></thead><tbody>${d.flags.map(f => `<tr><td class="mono">${e(f.code)}</td><td>${e(f.severity)}</td><td class="mono" style="font-size:11px">${e(f.scope)}</td><td>${e(f.message)}</td></tr>`).join("")}</tbody></table></div>
      <div class="note">显示 ${d.flags.length} / ${d.flags_total} 条（分页上限 200，避免一次请求批量暴露）。</div>`;
    el("syrPanel").innerHTML = h;
    el("syrPanel").querySelectorAll("[data-fc]").forEach(b => b.onclick = () => { Y.flagCode = b.dataset.fc; refresh(); });
  }''', '''    const off = d.flags_offset || 0, lo = d.flags_total ? off + 1 : 0, hi = off + d.flags.length;
    h += `<h3>质量标记（${codes.map(([k, v]) => `<button class="mbtn ${Y.flagCode === k ? "on" : ""}" data-fc="${k}">${k} ${v}</button>`).join(" ")} <button class="mbtn ${Y.flagCode ? "" : "on"}" data-fc="">全部</button>）</h3>
      <div class="timebar" id="flagPager"><button class="mbtn" id="flagPrev" ${off <= 0 ? "disabled" : ""}>上一页</button>
        <span class="pill" id="flagRange">第 ${lo}–${hi} 条 / 共 ${d.flags_total} 条</span>
        <button class="mbtn" id="flagNext" ${hi >= d.flags_total ? "disabled" : ""}>下一页</button></div>
      <div class="scroll"><table><thead><tr><th>代码</th><th>级别</th><th>范围</th><th>说明</th></tr></thead><tbody>${d.flags.map(f => `<tr><td class="mono">${e(f.code)}</td><td>${e(f.severity)}</td><td class="mono" style="font-size:11px">${e(f.scope)}</td><td>${e(f.message)}</td></tr>`).join("")}</tbody></table></div>
      <div class="note">每页 ${FLAG_PAGE} 条（API 单页上限 200，避免一次请求批量暴露）。</div>`;
    if (!put(tok, "syrPanel", h)) return;
    el("syrPanel").querySelectorAll("[data-fc]").forEach(b => b.onclick = () => { Y.flagCode = b.dataset.fc; Y.flagOffset = 0; refresh(); });
    el("flagPrev").onclick = () => { Y.flagOffset = Math.max(0, off - FLAG_PAGE); refresh(); };
    el("flagNext").onclick = () => { if (hi < d.flags_total) { Y.flagOffset = off + FLAG_PAGE; refresh(); } };
    const rb = el("recheckBtn");
    if (rb) rb.onclick = async () => {
      rb.disabled = true;
      const x = await fetch(`${B}/provenance-recheck`, { credentials: "same-origin" });
      const j = await x.json(); const rc = j.recheck || {};
      el("recheckOut").innerHTML = `复核于 ${e(rc.rechecked_at)}：${rc.disk_matches_snapshot ? tag("CONSISTENT", "磁盘与快照哈希一致") : tag("SUSPECT", "磁盘与快照不一致")} · ${e(rc.effect || "")}`;
      rb.disabled = false;
    };
  }
  function snapBlock(s) {
    if (!s) return "";
    return `<h3>不可变加载快照</h3><dl class="kv"><dt>snapshot_id</dt><dd class="mono">${e(s.snapshot_id)}</dd>
      <dt>加载时间</dt><dd>${e(s.loaded_at)}</dd><dt>来源状态</dt><dd>${tag(s.source_status)}</dd><dt>策略</dt><dd>${e(s.policy)}</dd></dl>
      <div class="note">语义：内存快照与<b>加载时</b>磁盘内容一致 ≠ 磁盘原文件<b>当前</b>仍未改变。</div>
      <button class="btn" id="recheckBtn">按需复核磁盘哈希</button> <span id="recheckOut" class="note"></span>`;
  }
  function sciHtml(s) {
    const qc = s.qc_classification, sq = s.sequence_index, c8 = s.case_16037_2008, wf = s.water_balance_w_formula, u = s.units;
    const pct = v => v === null || v === undefined ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
    let h = `<h3>科研口径核对（v0.5.1，均由快照复算）</h3>
      <div class="grid2"><div><b>① 366 站年五类 QC</b>（闭合：${qc.closed ? tag("CONSISTENT", "闭合") : tag("SUSPECT", "未闭合")}）
      <div class="tblwrap"><table id="qcTable"><thead><tr><th>类别</th><th>站年数</th></tr></thead><tbody>${Object.entries(qc.counts).map(([k, v]) => `<tr><td>${tag(k)}</td><td>${v}</td></tr>`).join("")}
      <tr><td><b>合计</b></td><td><b>${Object.values(qc.counts).reduce((a, b) => a + b, 0)}</b> / ${qc.n_discharge_records} 条记录</td></tr></tbody></table></div>
      <div class="note">${e(qc.rule)}</div></div>
      <div><b>②③ 序号疑值：run 与单元格分开计</b>
      <div class="tblwrap"><table id="seqTable"><thead><tr><th>统计量</th><th>run 数</th><th>标记单元格</th><th>受影响站年</th><th>等于月号(全部)</th></tr></thead><tbody>${["mean", "max", "min"].map(k => { const v = sq.by_stat[k]; return `<tr><td>${{ mean: "月均", max: "月最大", min: "月最小" }[k]}</td><td>${v.runs}</td><td>${v.flagged_cells}</td><td>${v.station_years}</td><td>${v.equal_month_cells}</td></tr>`; }).join("")}
      <tr><td><b>合计</b></td><td><b>${sq.runs_total}</b></td><td><b>${sq.flagged_cells_total}</b></td><td>—</td><td>${sq.equal_month_cells_total}（其中 ${sq.equal_month_not_in_run} 个未达连续 3 月规则，不判无效）</td></tr></tbody></table></div>
      <div class="note">${e(sq.semantics)}。月均受影响站年：${e(sq.by_stat.mean.station_year_list.join("、"))}</div></div></div>`;
    if (c8) h += `<b>④⑤ ${e(c8.station)} / ${c8.year} 年度 W（源值保留、不覆盖）</b><dl class="kv" id="case2008">
      <dt>源 W (10⁶ m³)</dt><dd>${n(c8.W_source, 4)}</dd><dt>Q 积分 W_Q</dt><dd>${n(c8.W_from_Q, 4)}（假设 Q=m³/s，实际月长）</dd>
      <dt>以源 W 为分母</dt><dd>${pct(c8.pct_denominator_W_source)} · ${e(c8.pct_denominator_W_source_label)}</dd>
      <dt>以 W_Q 为分母</dt><dd>${pct(c8.pct_denominator_W_from_Q)} · ${e(c8.pct_denominator_W_from_Q_label)}</dd></dl>`;
    h += `<b>⑥ 年度平衡 W 实际数值聚合公式</b>：<span class="mono" id="wbFormula">${e(wf.formula_in_use)}</span>（${wf.comparisons} 次站年比对，相对误差容差 ${wf.tolerance_rel}）<div class="note">${e(wf.note)}</div>`;
    h += `<b>⑧ 单位</b>：Q ${e(u.discharge_Q.join("/"))} · 气象 ${e(u.meteorology_P_T.join("/"))} · KZDAM ${e(u.kzdam.join("/"))} · 引水 ${e(u.intake_scenarios.join("/"))} · 未确认单位保持 UNKNOWN：${u.unconfirmed_kept_unknown ? tag("CONSISTENT", "是") : tag("SUSPECT", "否")}`;
    h += `<div class="banner bad">⑨ ${e(s.target_q_derived.notice)}：${e(s.target_q_derived.features.map(f => f.diagnostic).join("、"))}；${e(s.target_q_derived.also_labelled_in_api.join("、"))}</div>`;
    return h;
  }''')
# F6 / GIS
J.rep('''  async function fPred() {
    const r = await get(`${B}/research`);
    const d = r.body;''', '''  async function fPred(_, tok) {
    const r = await get(`${B}/research`, tok.signal);
    if (!live(tok)) return;
    const d = r.body;''')
J.rep('''    h += `<h3>锡尔河基线（目标 ${e(d.baselines[0].target)}）</h3><table><thead>''',
      '''    h += `<h3>锡尔河基线（目标 ${e(d.baselines[0].target)}）</h3><div class="tblwrap"><table id="predTable"><thead>''')
J.rep('''        Object.keys(d.tasks).map(t => { const L = b.leakage[t]; return `<td>${L.ok ? tag("CONSISTENT", "无泄漏") : tag("SUSPECT", L.violations.map(v => v.rule).join(","))}''',
      '''        Object.keys(d.tasks).map(t => { const L = b.leakage[t]; return `<td>${L.ok ? tag("CONSISTENT", "谱系检查通过·未执行实验") : tag("SUSPECT", L.violations.map(v => v.rule).join(","))}''')
J.rep('''        <td>${tag(b.execution)}</td></tr>`).join("")}</tbody></table>''',
      '''        <td>${tag(b.execution)}</td></tr>`).join("")}</tbody></table></div>''')
J.rep('''      <div class="note">dW、反演引水、水量平衡残余的谱系均含目标站 16039 的 Q，在“无目标站 Q 校准”任务中被自动判为禁用特征。KZDAM 因单位未知未纳入 SYR-B2。</div>''',
      '''      <div class="note">谱系为递归 DAG：dW、反演引水、水量平衡残余（及其换名/聚合/滞后/平滑派生）均追溯到目标站 16039 的 Q，在“无目标站 Q 校准”任务中被判为禁用特征。KZDAM 因单位未知未纳入 SYR-B2。${e(d.independence_note || "")}</div>''')
J.rep('''    el("syrPanel").innerHTML = h;
    el("syrPredBtn").onclick = async () => {
      const x = await fetch(`${B}/predict`, { method: "POST" });''', '''    if (!put(tok, "syrPanel", h)) return;
    el("syrPredBtn").onclick = async () => {
      const x = await fetch(`${B}/predict`, { method: "POST", credentials: "same-origin" });''')
J.rep('''  async function fGis() {
    const r = await get(`${B}/gis`);
    const d = r.body;
    el("syrPanel").innerHTML = `<div''', '''  async function fGis(_, tok) {
    const r = await get(`${B}/gis`, tok.signal);
    const d = r.body;
    put(tok, "syrPanel", `<div''')
J.rep('''      <div class="note">${e(d.note)}</div>`;
  }''', '''      <div class="note">${e(d.note)}</div>`);
  }''')
J.rep('''  overview();
  if (currentDs() === "SYRDARYA") switchTo("SYRDARYA");''', '''  overview();
  if (currentDs() === "SYRDARYA") applyDs("SYRDARYA");''')
J.save()

# ---------------------------------------------------------------- HTML
H = Patcher(os.path.join("static", "index.html"))
H.rep('''<title>VHS v0.5 · 双流域虚拟水文站（LamaH-CE + 锡尔河）</title>''',
      '''<title>VHS v0.5.1 · 双流域虚拟水文站（LamaH-CE + 锡尔河）</title>''')
H.rep('''<span class="ver" id="verBadge">v0.5</span>''',
      '''<span class="ver" id="verBadge">v0.5.1</span>''')
H.rep('''  @media(max-width:1300px){.syr-grid{grid-template-columns:250px 1fr}}''',
      '''  @media(max-width:1300px){.syr-grid{grid-template-columns:250px 1fr}}
  /* v0.5.1: grid items may shrink; single column at narrow widths; wide
     tables scroll inside their own box instead of widening the page */
  .syr-grid>.col,.workbench>*{min-width:0}
  #syrApp .card{min-width:0;overflow-wrap:anywhere}
  .tblwrap{max-width:100%;overflow-x:auto}
  #syrPanel svg{max-width:100%;height:auto}
  @media(max-width:900px){.syr-grid{grid-template-columns:1fr}
    #syrPanel table,#syrApp .kv{max-width:100%}
    #syrPanel table{display:block;overflow-x:auto}
    .grid2,.grid3,.overview{grid-template-columns:1fr}}''')
H.rep('''/* -------- middle: spatial map -------- */
function renderSpatial(){''', '''/* -------- middle: spatial map -------- */
/* v0.5.1: one drag state and ONE global mouseup listener for the page
   lifetime (v0.5 added a new window listener on every re-render). */
const MAPDRAG = {on:false, lx:0, ly:0};
window.addEventListener("mouseup", ()=>{ MAPDRAG.on=false; });
function renderSpatial(){''')
H.rep('''  let dragging=false, lx=0, ly=0;
  svg.addEventListener("mousedown", e=>{dragging=true;lx=e.clientX;ly=e.clientY;});
  window.addEventListener("mouseup", ()=>dragging=false);
  svg.addEventListener("mousemove", e=>{
    if(!dragging) return;
    const rect = svg.getBoundingClientRect();
    const k = W/rect.width;
    S.mapView.x0 += (e.clientX-lx)*k; S.mapView.y0 += (e.clientY-ly)*k;
    lx=e.clientX; ly=e.clientY;''', '''  const D = MAPDRAG;
  svg.addEventListener("mousedown", e=>{D.on=true;D.lx=e.clientX;D.ly=e.clientY;});
  svg.addEventListener("mousemove", e=>{
    if(!D.on) return;
    const rect = svg.getBoundingClientRect();
    const k = W/rect.width;
    S.mapView.x0 += (e.clientX-D.lx)*k; S.mapView.y0 += (e.clientY-D.ly)*k;
    D.lx=e.clientX; D.ly=e.clientY;''')
H.save()
