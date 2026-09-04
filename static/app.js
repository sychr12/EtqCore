/*
 * CONTROLE DA INTERFACE
 * Liga os campos à prévia, à API e aos botões. A impressão é montada
 * no servidor; este arquivo mostra a prova e envia as ações do usuário.
 *
 * Partes principais:
 * - loadState/findPrinters: carregam contador, opções e impressoras;
 * - updatePreview/showPrintPreview: atualizam e ampliam a prova;
 * - fitText/fitLabelTexts: evitam que textos ultrapassem as células;
 * - generate: confirma e solicita o PRN ou a impressão direta;
 * - loadHistory: mostra e permite reutilizar etiquetas anteriores;
 * - showToast/setBusy: exibem mensagens e o estado de processamento.
 */
let cfg = {}, timer, qrUrl, historyCache = {}, lastPrintProfile = null;
const form = document.querySelector('#labelForm');
const values = () => Object.fromEntries(new FormData(form));
const MESES = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
const fmtDate = v => v ? v.replace(/(\d{4})-(\d{2})-(\d{2})/, '$3/$2/$1') : '';
const fmtMesAno = v => { if (!v) return ''; const m = v.match(/(\d{4})-(\d{2})-(\d{2})/); if (!m) return v; return MESES[Number(m[2]) - 1] + '/' + m[1] };
const setText = (selector, value) => { const el = document.querySelector(selector); if (el) el.textContent = value ?? ''; return el };
async function loadState(restoreLast = false) { const r = await fetch('/api/estado'), s = await r.json(); cfg = s.config; document.querySelector('#nextTop').textContent = 'Próximo: ' + s.proximo_numero; document.querySelector('#branchChip').textContent = 'Filial ' + cfg.filial; for (const [k, v] of Object.entries(cfg)) { const el = document.querySelector(`#settingsForm [name="${k}"]`); if (el) el.value = v } if (restoreLast && s.ultima_etiqueta) { fillForm(s.ultima_etiqueta.dados, false); status(`Última etiqueta ${s.ultima_etiqueta.identificador} restaurada automaticamente.`, 'info') } resizePreview(); return s }
async function findPrinters(showResult = true) { const out = document.querySelector('#settingsStatus'), input = document.querySelector('#settingsForm [name="impressora"]'), options = document.querySelector('#printerOptions'); try { const response = await fetch('/api/impressoras'); if (!response.ok) throw new Error('Falha ao consultar as impressoras do Windows.'); const data = await response.json(); options.replaceChildren(...data.impressoras.map(name => Object.assign(document.createElement('option'), { value: name }))); if (data.recomendada && (!input.value || !data.impressoras.some(name => name.toLowerCase() === input.value.toLowerCase()))) input.value = data.recomendada; if (showResult) { const message = data.recomendada ? `Zebra encontrada: ${data.recomendada}. Clique em Salvar configurações.` : data.impressoras.length ? 'Impressoras encontradas, mas nenhuma Zebra ZD220 foi identificada.' : 'Nenhuma impressora instalada foi encontrada. Instale o driver ZDesigner da ZD220.'; out.textContent = message; out.className = 'status ' + (data.recomendada ? 'ok' : 'error'); showToast(message, data.recomendada ? 'ok' : 'error') } } catch (error) { out.textContent = error.message; out.className = 'status error'; if (showResult) showToast(error.message, 'error') } }
function fitText(el, maxWidthPx, minFontPx = 7) { if (!el || !maxWidthPx) return; el.style.fontSize = ''; const style = getComputedStyle(el), canvas = fitText.canvas || (fitText.canvas = document.createElement('canvas')), context = canvas.getContext('2d'); let fs = parseFloat(style.fontSize); const text = (el.textContent || '').trim(); if (!text || !context) return; const measure = size => { context.font = `${style.fontStyle} ${style.fontWeight} ${size}px ${style.fontFamily}`; return context.measureText(text).width + Math.max(0, text.length - 1) * (parseFloat(style.letterSpacing) || 0) }; const width = measure(fs); if (width > maxWidthPx) { fs = Math.max(minFontPx, Math.floor(fs * maxWidthPx / width)); el.style.fontSize = fs + 'px' } }
function fitLabelTexts(root) { if (!root) return; root.querySelectorAll('.dataTable .cellValue:not([data-out="operador"])').forEach(v => fitText(v, v.parentElement.clientWidth * 0.92)); const content = root.querySelector('.content'); fitText(root.querySelector('.titleText'), content.clientWidth * 0.94, 22); const codMain = root.querySelector('.codMain'), codValueMain = root.querySelector('.codValueMain'), codStack = root.querySelector('.codStack'), codValue = root.querySelector('.codValue'); if (codMain && codValueMain) fitText(codValueMain, Math.max(40, codMain.clientWidth - 22), 18); if (codStack && codValue) fitText(codValue, Math.max(40, codStack.clientWidth - 22), 18); const medValue = root.querySelector('.medValue'), medContent = root.querySelector('.medContent'); if (medValue && medContent) fitText(medValue, medContent.clientWidth * 0.98, 16) }
function resizePreview() {
  const el = document.querySelector('#previewLabel'), wmm = Number(cfg.largura_mm || 100), hmm = Number(cfg.comprimento_mm || 60); el.style.aspectRatio = `${wmm}/${hmm}`; requestAnimationFrame(() => {
    fitLabelTexts(el);
  })
}
async function updatePreview() { const d = values(); document.querySelectorAll('[data-out]').forEach(el => { const k = el.dataset.out; el.textContent = d[k] || '' }); const brandBand = document.querySelector('.brandBand'); if (brandBand) brandBand.classList.toggle('isEmpty', !String(d.cliente || '').trim()); const observationBox = document.querySelector('.observationBox'); if (observationBox) observationBox.classList.toggle('isEmpty', !String(d.observacao || '').trim()); const lotParts = String(d.lote_base || '').split('/', 2); setText('[data-out-lot] .lotTop', lotParts.length > 1 ? lotParts[1] : lotParts[0]); setText('[data-out-lot] .lotBottom', lotParts.length > 1 ? lotParts[0] : ''); setText('[data-out-qty] .qtyNumber', d.quantidade); setText('[data-out-qty] .qtyUnit', d.unidade); setText('[data-out-date="fabricacao"]', fmtDate(d.fabricacao)); setText('[data-out-valmes="validade"]', fmtMesAno(d.validade)); resizePreview(); if (!d.quantidade) return; try { const r = await fetch('/api/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) }), x = await r.json(); if (!r.ok) return; lastPrintProfile = x.impressao; setText('#qrText', x.qr); if (qrUrl) URL.revokeObjectURL(qrUrl); const qr = await fetch('/api/qr.svg', { method: 'POST', body: x.qr }); if (!qr.ok) return; const blob = await qr.blob(); qrUrl = URL.createObjectURL(blob); const qrBox = document.querySelector('#qrBox'); if (qrBox) { qrBox.classList.remove('empty'); qrBox.replaceChildren(Object.assign(document.createElement('img'), { alt: 'QR Code', src: qrUrl })) } resizePreview(); return x } catch (e) { console.error('Falha ao atualizar a prévia:', e) } }
async function showPrintPreview() { if (!form.reportValidity()) return; setBusy(true, 'Preparando visualização', 'Gerando QR e conferindo dimensões'); try { const result = await updatePreview(); if (!result || !lastPrintProfile) throw new Error('Não foi possível gerar a prova da etiqueta. Confira os campos.'); const modal = document.querySelector('#printPreviewModal'), canvas = document.querySelector('#printPreviewCanvas'), clone = document.querySelector('#previewLabel').cloneNode(true), p = lastPrintProfile; clone.removeAttribute('id'); clone.querySelectorAll('[id]').forEach(el => el.removeAttribute('id')); clone.querySelectorAll('*').forEach(el => el.style.removeProperty('font-size')); clone.style.aspectRatio = `${p.largura_mm}/${p.comprimento_mm}`; canvas.replaceChildren(clone); document.querySelector('#printPreviewMeta').textContent = `${p.largura_mm} × ${p.comprimento_mm} mm • ${p.dpi} dpi • ${p.largura_dots} × ${p.comprimento_dots} dots`; modal.classList.add('show'); modal.setAttribute('aria-hidden', 'false'); fitLabelTexts(clone); document.querySelector('#closePrintPreview').focus() } catch (error) { status(error.message, 'error') } finally { setBusy(false) } }
function closePrintPreview() { const modal = document.querySelector('#printPreviewModal'); modal.classList.remove('show'); modal.setAttribute('aria-hidden', 'true') }
form.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(updatePreview, 250) });
function showToast(message, type = 'info') { const host = document.querySelector('#toasts'), toast = document.createElement('div'), text = document.createElement('div'), title = document.createElement('strong'), detail = document.createElement('span'); toast.className = 'toast ' + type; text.className = 'toastText'; title.textContent = type === 'error' ? 'Atenção' : type === 'ok' ? 'Concluído' : 'Informação'; detail.textContent = message; text.append(title, detail); toast.append(text); host.append(toast); setTimeout(() => { toast.classList.add('out'); setTimeout(() => toast.remove(), 320) }, 4500) }
function status(msg, type = '') { const e = document.querySelector('#status'); e.textContent = msg; e.className = 'status ' + type; if (type) showToast(msg, type) }
function setBusy(active, title = 'Processando etiqueta', message = 'Aguarde') { const overlay = document.querySelector('#busyOverlay'); document.querySelector('#busyTitle').textContent = title; document.querySelector('#busyMessage').childNodes[0].nodeValue = message; overlay.classList.toggle('show', active); overlay.setAttribute('aria-hidden', String(!active)); for (const id of ['print', 'download', 'saveProject', 'saveSettings']) { const button = document.querySelector('#' + id); if (button) button.disabled = active } }
function confirmAction(title, message, confirmText = 'Confirmar') { return new Promise(resolve => { const modal = document.querySelector('#confirmModal'), ok = document.querySelector('#confirmOk'), cancel = document.querySelector('#confirmCancel'); document.querySelector('#confirmTitle').textContent = title; document.querySelector('#confirmMessage').textContent = message; ok.textContent = confirmText; modal.classList.add('show'); modal.setAttribute('aria-hidden', 'false'); const finish = value => { modal.classList.remove('show'); modal.setAttribute('aria-hidden', 'true'); ok.onclick = null; cancel.onclick = null; window.removeEventListener('keydown', onKey); resolve(value) }, onKey = e => { if (e.key === 'Escape') finish(false) }; ok.onclick = () => finish(true); cancel.onclick = () => finish(false); window.addEventListener('keydown', onKey); setTimeout(() => ok.focus(), 120) }) }
function fillForm(data, refresh = true) { for (const [name, value] of Object.entries(data || {})) { const el = form.elements.namedItem(name); if (el) el.value = value ?? '' } if (refresh) updatePreview() }
function downloadBlob(content, type, filename) { const blob = new Blob([content], { type }), a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000) }
document.querySelector('#saveProject').onclick = () => { const d = values(), project = { tipo_arquivo: 'etiqueta-zebra-editavel', versao: 1, salvo_em: new Date().toISOString(), dados: d, dimensoes: { largura_mm: cfg.largura_mm, comprimento_mm: cfg.comprimento_mm, dpi: cfg.dpi } }; const name = (d.produto_codigo || 'etiqueta').replace(/[^a-zA-Z0-9_-]+/g, '_'); downloadBlob(JSON.stringify(project, null, 2), 'application/json;charset=utf-8', name + '.etq'); status('Etiqueta editável salva. Para reabrir, use “Abrir etiqueta salva”.', 'ok') };
document.querySelector('#openProject').onchange = async e => { const file = e.target.files[0]; if (!file) return; setBusy(true, 'Abrindo etiqueta', 'Carregando dados salvos'); try { if (file.size > 1024 * 1024) throw new Error('O arquivo é grande demais.'); const project = JSON.parse(await file.text()); if (project.tipo_arquivo !== 'etiqueta-zebra-editavel' || !project.dados) throw new Error('Este arquivo não é uma etiqueta .etq válida.'); fillForm(project.dados); if (project.dimensoes) { const merged = { ...cfg, ...project.dimensoes }; const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(merged) }); if (!r.ok) throw new Error((await r.json()).erro); await loadState() } status('Etiqueta aberta para edição. O contador não foi consumido.', 'ok') } catch (err) { status(err.message, 'error') } finally { setBusy(false); e.target.value = '' } };
async function generate(dest) { if (!form.reportValidity()) return; const count = dest === 'imprimir' ? Number(document.querySelector('#labelCount').value) : 1; if (!Number.isInteger(count) || count < 1 || count > 1000) { status('A quantidade de etiquetas deve ficar entre 1 e 1000.', 'error'); return } const warning = dest === 'imprimir' ? `Serão impressas ${count} etiqueta${count > 1 ? 's' : ''}, cada uma com contador e QR próprios. Mesmo em caso de falha, os números ficarão reservados.` : 'O próximo contador será reservado permanentemente para este arquivo de impressão.'; const confirmed = await confirmAction(dest === 'imprimir' ? 'Confirmar envio para a Zebra' : 'Gerar arquivo da impressora', warning, dest === 'imprimir' ? 'Enviar agora' : 'Gerar PRN'); if (!confirmed) return; setBusy(true, dest === 'imprimir' ? 'Enviando para a Zebra' : 'Gerando arquivo PRN', dest === 'imprimir' ? `Preparando ${count} etiqueta${count > 1 ? 's' : ''} com QR exclusivo` : 'Montando etiqueta e reservando contador'); status(dest === 'imprimir' ? 'Preparando o lote para envio…' : 'Gerando arquivo de impressão…'); try { const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...values(), destino: dest, quantidade_etiquetas: count }) }), x = await r.json(); if (!r.ok) { const range = x.quantidade > 1 ? ` Os números de ${x.identificador} até ${x.ultimo_identificador} foram consumidos por segurança.` : ` O número ${x.identificador} foi consumido por segurança.`; throw new Error(x.erro + (x.consumido ? range : '')) } if (dest === 'download') downloadBlob(x.zpl, 'application/octet-stream', x.identificador + '.prn'); const range = x.quantidade > 1 ? `${x.identificador} até ${x.ultimo_identificador}` : x.identificador; status(`${x.quantidade} etiqueta${x.quantidade > 1 ? 's' : ''} (${range}) ${dest === 'imprimir' ? 'enviada' + (x.quantidade > 1 ? 's' : '') : 'gerada'} com sucesso.`, 'ok'); await loadState(); await updatePreview() } catch (e) { status(e.message, 'error') } finally { setBusy(false) } }
document.querySelector('#download').onclick = () => generate('download'); document.querySelector('#print').onclick = () => generate('imprimir');
document.querySelector('#viewPrintPreview').onclick = showPrintPreview; document.querySelector('#closePrintPreview').onclick = closePrintPreview; document.querySelector('#printPreviewModal').addEventListener('click', e => { if (e.target.id === 'printPreviewModal') closePrintPreview() }); window.addEventListener('keydown', e => { if (e.key === 'Escape' && document.querySelector('#printPreviewModal').classList.contains('show')) closePrintPreview() });
document.querySelector('#viewPrintPreviewTop').onclick = showPrintPreview;
document.querySelector('#findPrinters').onclick = () => findPrinters(true);
document.querySelectorAll('nav button').forEach(b => b.onclick = () => { document.querySelectorAll('nav button,.tab').forEach(x => x.classList.remove('active')); b.classList.add('active'); document.querySelector('#' + b.dataset.tab).classList.add('active'); if (b.dataset.tab === 'history') Promise.all([loadHistory(), loadReportPeriods()]) });
document.querySelector('#reportsMount').append(document.querySelector('.monthlyReportPanel'));
document.querySelector('nav button[data-tab="reports"]').addEventListener('click', loadReportPeriods);
document.querySelector('#saveSettings').onclick = async () => { const settingsForm = document.querySelector('#settingsForm'), out = document.querySelector('#settingsStatus'); if (!settingsForm.reportValidity()) return; setBusy(true, 'Salvando configurações', 'Aplicando filial, dimensões e impressora'); try { const d = Object.fromEntries(new FormData(settingsForm)), r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) }), x = await r.json(); if (!r.ok) throw new Error(x.erro); out.textContent = 'Configurações salvas.'; out.className = 'status ok'; await loadState(); await updatePreview(); showToast(`Filial ${cfg.filial} e configurações aplicadas.`, 'ok') } catch (e) { out.textContent = e.message; out.className = 'status error'; showToast(e.message, 'error') } finally { setBusy(false) } };
async function loadHistory() { const body = document.querySelector('#historyRows'); body.innerHTML = '<tr><td colspan="10">Carregando histórico...</td></tr>'; try { const response = await fetch('/api/historico'); if (!response.ok) throw new Error('Não foi possível carregar o histórico.'); const rows = await response.json(); historyCache = Object.fromEntries(rows.map(x => [x.id, x])); body.innerHTML = rows.map((x, index) => `<tr><td><strong>${escapeHtml(x.identificador)}</strong></td><td>${escapeHtml(x.criada_em.replace('T', ' '))}</td><td>${escapeHtml(x.dados.produto_codigo || '')}</td><td>${escapeHtml(x.dados.lote_controle || '')}</td><td>${escapeHtml(x.destino)}</td><td>${escapeHtml(x.dados.observacao || '')}</td><td><span class="badge ${x.sucesso ? '' : 'fail'}">${x.sucesso ? 'OK' : 'Falha'}</span>${x.erro ? `<br><small title="${escapeHtml(x.erro)}">${escapeHtml(x.erro.slice(0, 45))}</small>` : ''}</td><td><button class="smallButton" onclick="reuseHistory(${Number(x.id)})">Usar novamente</button></td><td><a class="button smallButton" href="/api/etiqueta/${Number(x.id)}.prn">PRN</a></td><td>${index === 0 ? `<button class="smallButton undoButton" onclick="undoLastHistory(${Number(x.id)}, '${escapeHtml(x.identificador)}')">Apagar erro e recuperar número</button>` : '<span class="correctionUnavailable">Somente a última</span>'}</td></tr>`).join('') || '<tr><td colspan="10">Nenhuma etiqueta gerada.</td></tr>' } catch (e) { body.innerHTML = '<tr><td colspan="10">Não foi possível carregar o histórico.</td></tr>'; showToast(e.message, 'error') } }
const loadHistoryRows = loadHistory;
loadHistory = async function () {
  await loadHistoryRows();
  const rows = Object.values(historyCache);
  setText('#historyTotal', rows.length);
  setText('#historySuccess', rows.filter(item => item.sucesso).length);
  setText('#historyFailures', rows.filter(item => !item.sucesso).length);
  const latest = rows.reduce((current, item) => !current || Number(item.id) > Number(current.id) ? item : current, null);
  setText('#historyLatest', latest?.identificador || '—');
};

async function undoLastHistory(id, identifier) { const confirmed = await confirmAction('Desfazer última etiqueta', `A etiqueta ${identifier} será apagada do histórico e seu número voltará a ficar disponível. Isso não cancela uma etiqueta que já saiu fisicamente da impressora. Um backup será criado antes da alteração.`, 'Desfazer etiqueta'); if (!confirmed) return; setBusy(true, 'Corrigindo histórico', 'Criando backup e restaurando o contador'); try { const response = await fetch(`/api/historico/${id}/desfazer`, { method: 'POST' }), result = await response.json(); if (!response.ok) throw new Error(result.erro || 'Não foi possível desfazer a etiqueta.'); status(`Etiqueta ${result.identificador} removida. A numeração voltou para esse número.`, 'ok'); reportPeriods = []; document.querySelector('#reportYear').replaceChildren(); await Promise.all([loadState(), loadHistory(), loadReportPeriods()]); } catch (error) { showToast(error.message, 'error') } finally { setBusy(false) } }
function reuseHistory(id) { const item = historyCache[id]; if (!item) return; fillForm(item.dados); document.querySelectorAll('nav button,.tab').forEach(x => x.classList.remove('active')); document.querySelector('nav button[data-tab="editor"]').classList.add('active'); document.querySelector('#editor').classList.add('active'); status(`Dados da etiqueta ${item.identificador} carregados. Uma nova impressão receberá outro contador.`, 'ok') }
const escapeHtml = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); document.querySelector('#refreshHistory').onclick = loadHistory;
document.querySelector('#refreshHistoryBottom').onclick = loadHistory;

document.querySelector('#clearHistory').onclick = async () => {
  const confirmButton = document.querySelector('#confirmOk');
  confirmButton.classList.add('confirmDanger');
  const confirmed = await confirmAction(
    'Apagar todo o histórico?',
    'Todos os registros de etiquetas serão apagados e o contador voltará para 00001. Essa ação não pode ser desfeita pela tela. Um backup será criado automaticamente antes da exclusão.',
    'Apagar tudo'
  );
  confirmButton.classList.remove('confirmDanger');
  if (!confirmed) return;
  setBusy(true, 'Apagando histórico', 'Criando backup e reiniciando o contador');
  try {
    const response = await fetch('/api/historico/apagar-tudo', { method: 'POST' });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || 'Não foi possível apagar o histórico.');
    reportPeriods = [];
    document.querySelector('#reportYear').replaceChildren();
    await Promise.all([loadState(), loadHistory(), loadReportPeriods()]);
    showToast(`${result.registros_apagados} registro(s) apagado(s). O contador voltou para 00001.`, 'ok');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    setBusy(false);
  }
};

document.querySelector('#deleteHistoryRange').onclick = async () => {
  const inicio = Number(document.querySelector('#deleteRangeStart').value);
  const fim = Number(document.querySelector('#deleteRangeEnd').value);
  const proximo = Number(document.querySelector('#deleteRangeNext').value);
  if (![inicio, fim, proximo].every(Number.isInteger) || inicio < 1 || fim < inicio || proximo < 1) {
    showToast('Preencha o número inicial, o final e o próximo número corretamente.', 'error');
    return;
  }
  const confirmButton = document.querySelector('#confirmOk');
  confirmButton.classList.add('confirmDanger');
  const confirmed = await confirmAction(
    'Confirmar exclusão do intervalo?',
    `Serão apagadas as etiquetas de ${String(inicio).padStart(5, '0')} até ${String(fim).padStart(5, '0')}. Depois, o próximo contador será exatamente ${String(proximo).padStart(5, '0')}. Um backup será criado antes da exclusão.`,
    'Excluir intervalo'
  );
  confirmButton.classList.remove('confirmDanger');
  if (!confirmed) return;
  setBusy(true, 'Excluindo intervalo', 'Criando backup e ajustando a numeração');
  try {
    const response = await fetch('/api/historico/apagar-intervalo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inicio, fim, proximo })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || 'Não foi possível excluir o intervalo.');
    reportPeriods = [];
    document.querySelector('#reportYear').replaceChildren();
    await Promise.all([loadState(), loadHistory(), loadReportPeriods()]);
    showToast(`${result.registros_apagados} registro(s) apagado(s). Próximo número: ${String(result.proximo_contador).padStart(5, '0')}.`, 'ok');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    setBusy(false);
  }
};

const MONTH_NAMES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
let reportPeriods = [];
function updateReportSummary() {
  const type = document.querySelector('#reportType').value, ano = Number(document.querySelector('#reportYear').value), mes = Number(document.querySelector('#reportMonth').value);
  const annual = type === 'anual';
  document.querySelector('#reportMonthField').hidden = annual;
  document.querySelector('#reportPeriodLabel').textContent = annual ? String(ano) : `${MONTH_NAMES[mes - 1]} de ${ano}`;
  const rows = reportPeriods.filter(item => Number(item.ano) === ano && (annual || Number(item.mes) === mes));
  document.querySelector('#reportPeriodTotal').textContent = rows.reduce((sum, item) => sum + Number(item.total), 0).toLocaleString('pt-BR');
  const base = cfg.pasta_relatorios || 'Pasta externa';
  document.querySelector('#reportFolderPreview').textContent = annual ? `${base} / ${ano} / etiquetas-${ano}-anual.xlsx` : `${base} / ${ano} / ${String(mes).padStart(2, '0')}`;
  document.querySelector('#generateMonthlyReport').textContent = annual ? 'Criar relatório anual' : 'Criar relatório mensal';
  const download = document.querySelector('#downloadMonthlyReport'); download.hidden = true;
  document.querySelector('#monthlyReportStatus').textContent = 'Confira o período e clique em criar relatório.';
  document.querySelector('#monthlyReportStatus').className = 'reportPath';
}
async function loadReportPeriods() {
  const year = document.querySelector('#reportYear'), month = document.querySelector('#reportMonth');
  if (year.options.length && month.options.length) return;
  const now = new Date();
  try {
    const response = await fetch('/api/relatorios/periodos');
    if (!response.ok) throw new Error('Não foi possível consultar os períodos.');
    const periods = await response.json(); reportPeriods = periods;
    const years = [...new Set([now.getFullYear(), ...periods.map(item => Number(item.ano))])].sort((a, b) => b - a);
    year.replaceChildren(...years.map(value => Object.assign(document.createElement('option'), { value, textContent: value })));
    month.replaceChildren(...MONTH_NAMES.map((name, index) => Object.assign(document.createElement('option'), { value: index + 1, textContent: `${String(index + 1).padStart(2, '0')} — ${name}` })));
    year.value = String(periods[0]?.ano || now.getFullYear());
    month.value = String(Number(periods[0]?.mes || now.getMonth() + 1));
    updateReportSummary();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function generateMonthlyReport() {
  const tipo = document.querySelector('#reportType').value, ano = Number(document.querySelector('#reportYear').value), mes = Number(document.querySelector('#reportMonth').value), anual = tipo === 'anual';
  const output = document.querySelector('#monthlyReportStatus'), download = document.querySelector('#downloadMonthlyReport');
  setBusy(true, anual ? 'Criando relatório anual' : 'Criando planilha mensal', anual ? `Consolidando todas as etiquetas de ${ano}` : `Organizando as etiquetas de ${MONTH_NAMES[mes - 1]} de ${ano}`);
  download.hidden = true;
  try {
    const response = await fetch(anual ? '/api/relatorios/anual' : '/api/relatorios/mensal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ano, mes }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || 'Não foi possível criar a planilha.');
    output.textContent = `${result.total} etiqueta(s) salva(s) em ${result.arquivo}`;
    output.className = 'reportPath ok';
    download.href = result.download;
    download.hidden = false;
    showToast(anual ? 'Relatório anual criado com sucesso.' : 'Planilha mensal criada com sucesso.', 'ok');
  } catch (error) {
    output.textContent = error.message;
    output.className = 'reportPath error';
    showToast(error.message, 'error');
  } finally {
    setBusy(false);
  }
}
document.querySelector('#generateMonthlyReport').onclick = generateMonthlyReport;
document.querySelector('#reportType').onchange = updateReportSummary;
document.querySelector('#reportYear').onchange = updateReportSummary;
document.querySelector('#reportMonth').onchange = updateReportSummary;
document.querySelector('#testReportsFolder').onclick = async () => {
  const input = document.querySelector('#settingsForm [name="pasta_relatorios"]'), out = document.querySelector('#settingsStatus');
  if (!input.value.trim()) { showToast('Informe uma pasta para testar.', 'error'); return }
  setBusy(true, 'Testando pasta externa', 'Verificando permissão para criar arquivos');
  try {
    const response = await fetch('/api/relatorios/pasta/testar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pasta: input.value }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || 'A pasta não está disponível.');
    input.value = result.pasta;
    out.textContent = `Pasta disponível: ${result.pasta}`;
    out.className = 'status ok';
    showToast('A pasta aceita gravação e pode ser usada.', 'ok');
  } catch (error) {
    out.textContent = error.message;
    out.className = 'status error';
    showToast(error.message, 'error');
  } finally { setBusy(false) }
};
document.querySelector('#chooseReportsFolder').onclick = async () => {
  const input = document.querySelector('#settingsForm [name="pasta_relatorios"]'), out = document.querySelector('#settingsStatus');
  setBusy(true, 'Escolha a pasta', 'A janela do Windows foi aberta; selecione o destino');
  try {
    const response = await fetch('/api/relatorios/pasta/escolher', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pasta_atual: input.value }) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.erro || 'Não foi possível abrir o seletor de pastas.');
    if (result.cancelado) { showToast('Escolha de pasta cancelada.', 'info'); return }
    input.value = result.pasta;
    out.textContent = `Pasta escolhida: ${result.pasta}. Clique em Salvar configurações.`;
    out.className = 'status ok';
    showToast('Pasta selecionada. Agora salve as configurações.', 'ok');
  } catch (error) {
    out.textContent = error.message;
    out.className = 'status error';
    showToast(error.message, 'error');
  } finally { setBusy(false) }
};
document.querySelector('#changeReportFolder').onclick = async () => {
  const output = document.querySelector('#monthlyReportStatus');
  setBusy(true, 'Escolha onde salvar', 'A janela do Windows foi aberta');
  try {
    const chooser = await fetch('/api/relatorios/pasta/escolher', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pasta_atual: cfg.pasta_relatorios }) });
    const selected = await chooser.json();
    if (!chooser.ok) throw new Error(selected.erro || 'Não foi possível abrir o seletor.');
    if (selected.cancelado) { showToast('A pasta atual foi mantida.', 'info'); return }
    const save = await fetch('/api/relatorios/pasta/configurar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pasta: selected.pasta }) });
    const result = await save.json();
    if (!save.ok) throw new Error(result.erro || 'Não foi possível usar essa pasta.');
    cfg.pasta_relatorios = result.pasta;
    const settingsInput = document.querySelector('#settingsForm [name="pasta_relatorios"]');
    if (settingsInput) settingsInput.value = result.pasta;
    updateReportSummary();
    output.textContent = `Novo local salvo: ${result.pasta}`;
    output.className = 'reportPath ok';
    showToast('Novo local de salvamento definido.', 'ok');
  } catch (error) {
    output.textContent = error.message;
    output.className = 'reportPath error';
    showToast(error.message, 'error');
  } finally { setBusy(false) }
};
window.addEventListener('resize', resizePreview); loadState(true).then(() => Promise.all([updatePreview(), findPrinters(false)])).catch(e => status('Não foi possível iniciar: ' + e.message, 'error'));
