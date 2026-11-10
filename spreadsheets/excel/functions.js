/* Counterfact custom functions for Excel: =CF.EFFECT() and =CF.WITHOUT(). Uses the public Counterfact API. */
const CF_API = "https://mastyf-support--counterfact-api-api.us-east.modal.run";
const cache = new Map();

function numbers(range, name) {
  const out = [];
  (range || []).forEach((row) => (Array.isArray(row) ? row : [row]).forEach((v) => { if (v !== "" && v !== null && v !== undefined) out.push(Number(v)); }));
  if (!out.length || out.some((v) => !Number.isFinite(v))) throw new CustomFunctions.Error(CustomFunctions.ErrorCode.invalidValue, name + " must contain only numbers.");
  return out;
}
function columns(range, n) {
  if (!range || !range.length || (range.length === 1 && range[0].length === 1 && (range[0][0] === "" || range[0][0] === null))) return null;
  if (range.length !== n) throw new CustomFunctions.Error(CustomFunctions.ErrorCode.invalidValue, "comparisons must have the same number of rows as metric.");
  const covs = {};
  for (let j = 0; j < range[0].length; j++) covs["comparison_" + (j + 1)] = range.map((r) => Number(r[j]));
  return covs;
}
async function call(metric, changeRow, comparisons) {
  const y = numbers(metric, "metric");
  const t0 = Math.round(Number(changeRow)) - 1;
  if (!(t0 >= 8 && t0 < y.length)) throw new CustomFunctions.Error(CustomFunctions.ErrorCode.invalidValue, "change_row must be the first period after the change, with at least 8 periods before it.");
  const body = { target: y, t0 };
  const c = columns(comparisons, y.length); if (c) body.covariates = c;
  const key = JSON.stringify(body);
  if (cache.has(key)) return cache.get(key);
  const r = await fetch(CF_API + "/v1/effect", { method: "POST", headers: { "content-type": "application/json" }, body: key });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new CustomFunctions.Error(CustomFunctions.ErrorCode.notAvailable, d.detail || "Counterfact API error " + r.status);
  cache.set(key, d);
  return d;
}
async function effect(metric, changeRow, comparisons) {
  const d = await call(metric, changeRow, comparisons);
  const verdict = d.verdict === "real" ? (d.effect_mean > 0 ? "worked" : "hurt") : "can't tell yet";
  const pct = d.relative_effect === null || d.relative_effect === undefined ? "" : Math.round(1000 * d.relative_effect) / 10;
  return [[verdict, d.effect_mean, d.effect_lo90, d.effect_hi90, pct]];
}
async function without(metric, changeRow, comparisons) {
  const d = await call(metric, changeRow, comparisons);
  return d.cf_median.map((m, i) => [m, d.cf_lo90[i], d.cf_hi90[i]]);
}
CustomFunctions.associate("EFFECT", effect);
CustomFunctions.associate("WITHOUT", without);
