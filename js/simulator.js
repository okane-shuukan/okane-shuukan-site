(function () {
  "use strict";

  var dataEl = document.getElementById("sim-data");
  if (!dataEl) return;

  var data = JSON.parse(dataEl.textContent);

  var incomeSelect = document.getElementById("income-select");
  var attributeSelect = document.getElementById("attribute-select");
  var pensionSelect = document.getElementById("pension-select");
  var resultEl = document.getElementById("sim-result");

  function populateSelect(select, options) {
    options.forEach(function (opt) {
      var el = document.createElement("option");
      el.value = opt.value;
      el.textContent = opt.label;
      select.appendChild(el);
    });
  }

  populateSelect(
    incomeSelect,
    data.income_brackets.map(function (b) {
      return { value: String(b.income_man_yen), label: "年収" + b.income_man_yen + "万円" };
    })
  );

  populateSelect(
    attributeSelect,
    data.attributes.map(function (a) {
      return { value: a.id, label: a.name };
    })
  );

  function findBracket(incomeManYen) {
    return data.income_brackets.filter(function (b) {
      return String(b.income_man_yen) === String(incomeManYen);
    })[0];
  }

  function render() {
    var bracket = findBracket(incomeSelect.value);
    if (!bracket) {
      resultEl.innerHTML = "<p>該当するデータがありません。</p>";
      return;
    }

    var attr = bracket.by_attribute[attributeSelect.value] || {};
    var furusatoLimit =
      attr.furusato_limit_man_yen !== undefined && attr.furusato_limit_man_yen !== null
        ? attr.furusato_limit_man_yen
        : bracket.furusato_limit_single_man_yen;

    var idecoKey = pensionSelect.value === "with_pension" ? "with_pension" : "no_pension";
    var ideco = data.ideco_limits[idecoKey] || {};
    var idecoMonthly = ideco.monthly_limit_yen ? (ideco.monthly_limit_yen / 10000).toFixed(1) : null;
    var idecoAnnual = ideco.annual_limit_yen ? (ideco.annual_limit_yen / 10000).toFixed(1) : null;

    var rows = [];
    rows.push(["ふるさと納税 控除上限額の目安", furusatoLimit != null ? "約" + furusatoLimit + "万円" : "—"]);
    rows.push(["iDeCo 拠出限度額の目安", idecoMonthly ? "月" + idecoMonthly + "万円（年間 約" + idecoAnnual + "万円）" : "—"]);
    if (attr.estimated_income_tax_man_yen != null) {
      rows.push(["所得税額の目安", "約" + attr.estimated_income_tax_man_yen + "万円"]);
    }
    if (attr.estimated_resident_tax_man_yen != null) {
      rows.push(["住民税額の目安", "約" + attr.estimated_resident_tax_man_yen + "万円"]);
    }
    if (attr.net_take_home_estimate_man_yen != null) {
      rows.push(["手取り額の目安", "約" + attr.net_take_home_estimate_man_yen + "万円"]);
    }

    var dl = document.createElement("dl");
    rows.forEach(function (pair) {
      var dt = document.createElement("dt");
      dt.textContent = pair[0];
      var dd = document.createElement("dd");
      dd.textContent = pair[1];
      dl.appendChild(dt);
      dl.appendChild(dd);
    });

    var note = document.createElement("p");
    note.className = "sim-disclaimer";
    note.textContent = data.disclaimer || "";
    // 企業年金ありのときだけ、月2.0万円が「上限」であることの補足を同じ注記に足す。
    if (idecoKey === "with_pension" && data.ideco_with_pension_note) {
      note.textContent += data.ideco_with_pension_note;
    }

    resultEl.innerHTML = "";
    resultEl.appendChild(dl);
    resultEl.appendChild(note);
  }

  incomeSelect.addEventListener("change", render);
  attributeSelect.addEventListener("change", render);
  pensionSelect.addEventListener("change", render);

  render();
})();
