/**
 * Counterfact for Google Sheets: measure the effect of a change without leaving your spreadsheet.
 * Install: Extensions -> Apps Script -> paste this file -> Save. Then use the functions in any cell.
 * Free, no sign-up. Your numbers are sent to the Counterfact API for the calculation and are not stored.
 * Docs: https://counterfact-site.vercel.app/sheets.html
 */
var CF_API = "https://mastyf-support--counterfact-api-api.us-east.modal.run";

function cfNumbers_(range, name) {
  var out = [];
  (range || []).forEach(function (row) {
    (Array.isArray(row) ? row : [row]).forEach(function (v) { if (v !== "" && v !== null) out.push(Number(v)); });
  });
  if (!out.length || out.some(isNaN)) throw new Error(name + " must contain only numbers.");
  return out;
}

function cfColumns_(range, n) {
  if (!range) return null;
  var rows = Array.isArray(range[0]) ? range : range.map(function (v) { return [v]; });
  if (rows.length !== n) throw new Error("Comparison range must have the same number of rows as the metric.");
  var k = rows[0].length, covs = {};
  for (var j = 0; j < k; j++) {
    covs["comparison_" + (j + 1)] = rows.map(function (r) {
      var v = Number(r[j]); if (isNaN(v) || r[j] === "") throw new Error("Comparison range must contain only numbers."); return v;
    });
  }
  return covs;
}

function cfCall_(target, changeRow, comparisons) {
  var t0 = Math.round(Number(changeRow)) - 1;
  if (!(t0 >= 8 && t0 < target.length)) throw new Error("change_row must be the row (1 = first value) of the first period AFTER the change, with at least 8 periods before it.");
  var body = { target: target, t0: t0 };
  if (comparisons) body.covariates = comparisons;
  var key = "cf:" + Utilities.base64Encode(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, JSON.stringify(body)));
  var cache = CacheService.getScriptCache(), hit = cache.get(key);
  if (hit) return JSON.parse(hit);
  var res = UrlFetchApp.fetch(CF_API + "/v1/effect", {
    method: "post", contentType: "application/json", payload: JSON.stringify(body), muteHttpExceptions: true
  });
  var code = res.getResponseCode(), data = JSON.parse(res.getContentText() || "{}");
  if (code !== 200) throw new Error(data.detail || ("Counterfact API error " + code));
  try { cache.put(key, JSON.stringify(data), 21600); } catch (e) {}
  return data;
}

/**
 * Effect of a change: one row with [verdict, effect per period, low, high, effect %].
 * @param {A2:A60} metric_range The number you care about, oldest first (one column).
 * @param {46} change_row Row of the first period after the change, counted from the top of metric_range (1 = first).
 * @param {B2:D60} comparison_range Optional. Series the change could NOT have affected (same rows, one column each).
 * @return Verdict, effect per period, 90% range low, 90% range high, effect in %.
 * @customfunction
 */
function CF_EFFECT(metric_range, change_row, comparison_range) {
  var y = cfNumbers_(metric_range, "metric_range");
  var d = cfCall_(y, change_row, cfColumns_(comparison_range, y.length));
  var verdict = d.verdict === "real" ? (d.effect_mean > 0 ? "worked" : "hurt") : "can't tell yet";
  var pct = d.relative_effect === null || d.relative_effect === undefined ? "" : Math.round(1000 * d.relative_effect) / 10;
  return [[verdict, d.effect_mean, d.effect_lo90, d.effect_hi90, pct]];
}

/**
 * What the metric would have been without the change, one value per period after it.
 * @param {A2:A60} metric_range The number you care about, oldest first.
 * @param {46} change_row Row of the first period after the change (1 = first value).
 * @param {B2:D60} comparison_range Optional comparison series.
 * @return Column of expected values without the change, with 90% low and high.
 * @customfunction
 */
function CF_WITHOUT(metric_range, change_row, comparison_range) {
  var y = cfNumbers_(metric_range, "metric_range");
  var d = cfCall_(y, change_row, cfColumns_(comparison_range, y.length));
  return d.cf_median.map(function (m, i) { return [m, d.cf_lo90[i], d.cf_hi90[i]]; });
}

/** Adds a Counterfact menu with a short help box. */
function onOpen() {
  SpreadsheetApp.getUi().createMenu("Counterfact").addItem("How to use", "cfHelp_").addToUi();
}

function cfHelp_() {
  SpreadsheetApp.getUi().alert("Counterfact",
    "=CF_EFFECT(A2:A60, 46)  measures the change that started at row 46 of A2:A60.\n" +
    "=CF_EFFECT(A2:A60, 46, B2:D60)  also uses comparison series the change couldn't affect (more accurate).\n" +
    "=CF_WITHOUT(A2:A60, 46, B2:D60)  shows what the metric would have been without the change.\n\n" +
    "Full reports with every check and a verifiable receipt: counterfact-site.vercel.app",
    SpreadsheetApp.getUi().ButtonSet.OK);
}
