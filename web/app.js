const state = {
  selectedDate: null,
  activePage: "summary",
};

const formatNumber = (value) => new Intl.NumberFormat("ko-KR").format(value || 0);
const ownedStoreOrder = ["잠실점", "홍대점", "혜화점", "성수점", "연무장", "제주점"];

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`;
}

function ownedStoreLabel(name) {
  const value = String(name || "");
  if (value.includes("잠실")) return "잠실점";
  if (value.includes("홍대")) return "홍대점";
  if (value.includes("혜화") || value.includes("대학로")) return "혜화점";
  if (value.includes("성수연무장") || value.includes("연무장")) return "연무장";
  if (value.includes("성수")) return "성수점";
  if (value.includes("제주")) return "제주점";
  return value;
}

function ownedStoreSortKey(row) {
  const label = ownedStoreLabel(row.name);
  const index = ownedStoreOrder.indexOf(label);
  return index === -1 ? ownedStoreOrder.length : index;
}

function sortOwnedStores(rows) {
  return [...rows].sort((a, b) => ownedStoreSortKey(a) - ownedStoreSortKey(b) || ownedStoreLabel(a.name).localeCompare(ownedStoreLabel(b.name)));
}

function formatPointDelta(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${Number(value).toFixed(1)}%p`;
}

function formatCollectedAt(value) {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function formatDateWithWeekday(value, options = {}) {
  if (!value) {
    return "";
  }
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return value;
  }
  const date = new Date(year, month - 1, day);
  const weekday = date.toLocaleDateString("ko-KR", { weekday: "short" });
  if (options.short) {
    return `${month}/${day} (${weekday})`;
  }
  return `${value} (${weekday})`;
}

function formatShortMonthDay(value) {
  if (!value) {
    return "";
  }
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return value;
  }
  return `${month}/${day}`;
}

function formatReservationMetricLabel(label, payload) {
  const updatedAt = formatCollectedAt(payload.reservations.collectedAt);
  return updatedAt ? `${label} (${updatedAt})` : label;
}

function formatUsedReservationMetricLabel(payload) {
  return formatReservationMetricLabel("직영점 오늘 이용", payload);
}

function formatReviewMetricLabel(label, payload) {
  const dateLabel = formatShortMonthDay(payload.reviewDate || payload.date);
  return dateLabel ? `${label} (${dateLabel} 기준)` : label;
}

function reviewMarketShare(payload) {
  if (payload.reviews.marketShare !== undefined && payload.reviews.marketShare !== null) {
    return payload.reviews.marketShare;
  }
  const ourTotal = payload.reviews.totalsByType["당사"] || 0;
  const competitorTotal = payload.reviews.totalsByType["경쟁사"] || 0;
  const denominator = ourTotal + competitorTotal;
  return denominator > 0 ? (ourTotal / denominator) * 100 : 0;
}

function formatDelta(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (value > 0) {
    return `+${formatNumber(value)}`;
  }
  return formatNumber(value);
}

function deltaClass(value) {
  if (value === null || value === undefined || value === 0) {
    return "delta neutral";
  }
  return value > 0 ? "delta positive" : "delta negative";
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function renderDateSelect(payload) {
  const select = document.getElementById("dateSelect");
  const dates = payload.availableDates.length ? payload.availableDates : [payload.date];
  select.innerHTML = dates
    .map((date) => `<option value="${date}" ${date === payload.date ? "selected" : ""}>${formatDateWithWeekday(date)}</option>`)
    .join("");
  state.selectedDate = payload.date;
}

function renderMetrics(payload) {
  setText("reservationMetricLabel", formatReservationMetricLabel("직영점 예약 확정", payload));
  setText("usedReservationMetricLabel", formatUsedReservationMetricLabel(payload));
  setText("ourReviewsMetricLabel", formatReviewMetricLabel("당사 전일 리뷰", payload));
  setText("competitorReviewsMetricLabel", "경쟁사 전일 리뷰");
  setText("franchiseReviewsMetricLabel", "가맹점 전일 리뷰");
  setText("reservationTotal", formatNumber(payload.reservations.totalConfirmed));
  setText("usedReservationTotal", formatNumber(payload.reservations.totalUsed));
  setText("ourReviews", formatNumber(payload.reviews.totalsByType["당사"]));
  setText("competitorReviews", formatNumber(payload.reviews.totalsByType["경쟁사"]));
  setText("franchiseReviews", formatNumber(payload.reviews.totalsByType["가맹점"]));
  setText("reviewMarketShare", formatPercent(reviewMarketShare(payload)));
  renderMetricDelta("ourReviewsDelta", payload.reviews.totalDeltasByType["당사"], formatDelta);
  renderMetricDelta("competitorReviewsDelta", payload.reviews.totalDeltasByType["경쟁사"], formatDelta);
  renderMetricDelta("franchiseReviewsDelta", payload.reviews.totalDeltasByType["가맹점"], formatDelta);
  renderMetricDelta("reviewMarketShareDelta", payload.reviews.marketShareDelta, formatPointDelta);
  renderMetricDelta("reservationDelta", payload.reservations.totalDelta, formatDelta);
  renderMetricDelta("usedReservationDelta", payload.reservations.totalUsedDelta, formatDelta);
}

function renderSummary(payload) {
  renderSummaryReservations(payload.reservations);
  renderSummaryOurStores(payload.reviews.ourPlaces || []);
  renderSummaryCompetitors((payload.reviews.competitorPlaces || []).slice(0, 6));
  renderSummaryFranchiseStores(payload.reviews.franchisePlaces || []);
  renderSummaryKeywords(payload.reviews.keywords || []);
}

function renderSummaryReservations(reservations) {
  const rows = reservations.stores || [];
  renderSummaryReservationMetric({
    targetId: "summaryConfirmedReservations",
    rows,
    valueKey: "confirmedReservations",
    deltaKey: "dailyDelta",
    totalValue: reservations.totalConfirmed,
    totalDelta: reservations.totalDelta,
    emptyMessage: "예약 확정 데이터가 아직 없습니다.",
  });
  renderSummaryReservationMetric({
    targetId: "summaryUsedReservations",
    rows,
    valueKey: "usedReservations",
    deltaKey: "usedDelta",
    prefixKey: "usedMonthToDate",
    totalValue: reservations.totalUsed,
    totalPrefixValue: reservations.totalUsedMonthToDate,
    totalDelta: reservations.totalUsedDelta,
    emptyMessage: "오늘 이용 데이터가 아직 없습니다.",
  });
}

function formatMetricWithPrefix(value, prefixValue) {
  const prefix = prefixValue === null || prefixValue === undefined
    ? ""
    : `<small>(누계 ${formatNumber(prefixValue)})</small>`;
  return `<strong class="${prefix ? "metric-with-prefix" : ""}">${prefix}${formatNumber(value)}</strong>`;
}

function formatOptionalNumber(value) {
  return value === null || value === undefined ? "-" : formatNumber(value);
}

function formatSummaryCumulative(value, options = {}) {
  if (value === null || value === undefined) {
    return "-";
  }
  const label = options.label ? `${options.label} ` : "";
  return `(${label}${formatNumber(value)})`;
}

function renderSummaryReservationMetric({
  targetId,
  rows,
  valueKey,
  deltaKey,
  prefixKey,
  totalValue,
  totalPrefixValue,
  totalDelta,
  emptyMessage,
}) {
  const target = document.getElementById(targetId);
  const sortedRows = sortOwnedStores(rows);
  const hasPrefix = Boolean(prefixKey);
  target.innerHTML = sortedRows.length
    ? `
        <div class="summary-table-head ${hasPrefix ? "used-reservation-grid" : "reservation-metric-grid"}">
          <span>지점</span>
          ${hasPrefix ? "<span>당월 누계</span>" : '<span class="summary-spacer"></span>'}
          <span>${hasPrefix ? "오늘 이용" : "건수"}</span>
          <span>전일비</span>
        </div>
        <div class="summary-table-row summary-total-row ${hasPrefix ? "used-reservation-grid" : "reservation-metric-grid"}">
          <span>합계</span>
          ${hasPrefix ? `<span class="summary-cumulative">${formatSummaryCumulative(totalPrefixValue, { label: "누계" })}</span>` : '<span class="summary-spacer"></span>'}
          <strong>${formatNumber(totalValue)}</strong>
          <em class="${deltaClass(totalDelta)}">${formatDelta(totalDelta)}</em>
        </div>
        ${sortedRows
          .map(
            (row) => `
              <div class="summary-table-row ${hasPrefix ? "used-reservation-grid" : "reservation-metric-grid"}">
                <span>${ownedStoreLabel(row.name) || "-"}</span>
                ${hasPrefix ? `<span class="summary-cumulative">${formatSummaryCumulative(row[prefixKey])}</span>` : '<span class="summary-spacer"></span>'}
                <strong>${formatNumber(row[valueKey])}</strong>
                <em class="${deltaClass(row[deltaKey])}">${formatDelta(row[deltaKey])}</em>
              </div>
            `
          )
          .join("")}
      `
    : `<p class="muted">${emptyMessage}</p>`;
}

function renderSummaryOurStores(rows) {
  const target = document.getElementById("summaryOurStores");
  const sortedRows = sortOwnedStores(rows);
  target.innerHTML = sortedRows.length
    ? `
        <div class="summary-table-head our-summary-grid">
          <span>지점</span>
          <span>리뷰</span>
          <span>전일비</span>
        </div>
        ${sortedRows
          .map(
            (row) => `
              <div class="summary-table-row our-summary-grid">
                <span>${ownedStoreLabel(row.name)}</span>
                <strong>${formatNumber(row.dailyReviews)}</strong>
                <em class="${deltaClass(row.dailyDelta)}">${formatDelta(row.dailyDelta)}</em>
              </div>
            `
          )
          .join("")}
      `
    : `<p class="muted">표시할 데이터가 없습니다.</p>`;
}

function renderSummaryCompetitors(rows) {
  const target = document.getElementById("summaryCompetitors");
  target.innerHTML = rows.length
    ? `
        <div class="summary-table-head competitor-summary-grid">
          <span>플레이스</span>
          <span>리뷰</span>
          <span>영수증</span>
          <span>전일비</span>
        </div>
        ${rows
        .map(
          (row) => `
            <div class="summary-table-row competitor-summary-grid">
              <span>${row.name}</span>
              <strong>${formatNumber(row.dailyReviews)}</strong>
              <span class="summary-cumulative">${formatSummaryCumulative(row.receiptReviews)}</span>
              <em class="${deltaClass(row.dailyDelta)}">${formatDelta(row.dailyDelta)}</em>
            </div>
          `
        )
        .join("")}
      `
    : `<p class="muted">표시할 데이터가 없습니다.</p>`;
}

function renderSummaryFranchiseStores(rows) {
  const target = document.getElementById("summaryFranchiseStores");
  const topRows = [...rows].sort((a, b) => b.dailyReviews - a.dailyReviews || a.name.localeCompare(b.name)).slice(0, 6);
  target.innerHTML = topRows.length
    ? `
        <div class="summary-table-head our-summary-grid">
          <span>지점</span>
          <span>리뷰</span>
          <span>전일비</span>
        </div>
        ${topRows
          .map(
            (row) => `
              <div class="summary-table-row our-summary-grid">
                <span>${row.name}</span>
                <strong>${formatNumber(row.dailyReviews)}</strong>
                <em class="${deltaClass(row.dailyDelta)}">${formatDelta(row.dailyDelta)}</em>
              </div>
            `
          )
          .join("")}
      `
    : `<p class="muted">표시할 데이터가 없습니다.</p>`;
}

function renderSummaryKeywords(keywords) {
  const target = document.getElementById("summaryKeywords");
  target.innerHTML = keywords.length
    ? keywords
        .slice(0, 8)
        .map((item) => `<span class="keyword">${item.keyword} <strong>${formatNumber(item.count)}</strong></span>`)
        .join("")
    : `<span class="muted">수집된 리뷰 본문이 없습니다.</span>`;
}

function renderReservations(payload) {
  const tbody = document.getElementById("reservationRows");
  const empty = document.getElementById("reservationEmpty");
  const stores = sortOwnedStores(payload.reservations.stores);
  setText("reservationDetailConfirmedTotal", formatNumber(payload.reservations.totalConfirmed));
  document.getElementById("reservationDetailUsedTotal").innerHTML = formatMetricWithPrefix(
    payload.reservations.totalUsed,
    payload.reservations.totalUsedMonthToDate
  );
  empty.textContent = payload.dataStatus.hasReservations
    ? ""
    : "예약 스냅샷 파일이 아직 없습니다.";

  tbody.innerHTML = stores.length
    ? `
        <tr class="total-row">
          <td>합계</td>
          <td class="number-cell">${formatNumber(payload.reservations.totalConfirmed)}</td>
          <td><em class="${deltaClass(payload.reservations.totalDelta)}">${formatDelta(payload.reservations.totalDelta)}</em></td>
          <td class="number-cell">${formatOptionalNumber(payload.reservations.totalUsedMonthToDate)}</td>
          <td class="number-cell">${formatNumber(payload.reservations.totalUsed)}</td>
          <td><em class="${deltaClass(payload.reservations.totalUsedDelta)}">${formatDelta(payload.reservations.totalUsedDelta)}</em></td>
          <td>-</td>
        </tr>
        ${stores
        .map(
          (row) => `
            <tr>
              <td>${ownedStoreLabel(row.name) || "-"}</td>
              <td class="number-cell">${formatNumber(row.confirmedReservations)}</td>
              <td><em class="${deltaClass(row.dailyDelta)}">${formatDelta(row.dailyDelta)}</em></td>
              <td class="number-cell">${formatOptionalNumber(row.usedMonthToDate)}</td>
              <td class="number-cell">${formatNumber(row.usedReservations)}</td>
              <td><em class="${deltaClass(row.usedDelta)}">${formatDelta(row.usedDelta)}</em></td>
              <td class="${row.error ? "status-error" : ""}">${row.error ? "오류" : "정상"}</td>
            </tr>
          `
        )
        .join("")}
      `
    : `<tr><td colspan="7" class="muted">snapshots/reservations-${payload.date}.json 파일을 추가하면 표시됩니다.</td></tr>`;
}

function renderComparisonNote(payload) {
  document.getElementById("comparisonNote").textContent = payload.previousReviewDate
    ? `리뷰 기준: ${payload.reviewDate} / 전일비 기준: ${payload.previousReviewDate}`
    : `리뷰 기준: ${payload.reviewDate || "-"} / 전일비 기준 데이터가 아직 없습니다.`;
}

function renderTotalDelta(id, value) {
  const target = document.getElementById(id);
  target.textContent = formatDelta(value);
  target.className = deltaClass(value);
}

function renderLabeledDelta(id, value) {
  const target = document.getElementById(id);
  target.textContent = `전일비 ${formatDelta(value)}`;
  target.className = deltaClass(value);
}

function renderMarketShareDelta(id, value) {
  const target = document.getElementById(id);
  target.textContent = `전일비 ${formatPointDelta(value)}`;
  target.className = deltaClass(value);
}

function renderMetricDelta(id, value, formatter) {
  const target = document.getElementById(id);
  target.textContent = `전일비 ${formatter(value)}`;
  target.className = deltaClass(value).replace("delta", "metric-delta");
}

function renderReviewBoards(payload) {
  const ourTotal = payload.reviews.totalsByType["당사"] || 0;
  const competitorTotal = payload.reviews.totalsByType["경쟁사"] || 0;
  const franchiseTotal = payload.reviews.totalsByType["가맹점"] || 0;
  const ourDelta = payload.reviews.totalDeltasByType["당사"];
  const competitorDelta = payload.reviews.totalDeltasByType["경쟁사"];
  const franchiseDelta = payload.reviews.totalDeltasByType["가맹점"];

  setText("ourBoardTotal", formatNumber(ourTotal));
  setText("franchiseBoardTotal", formatNumber(franchiseTotal));
  setText("competitorBoardTotal", formatNumber(competitorTotal));
  renderTotalDelta("ourBoardDelta", ourDelta);
  renderTotalDelta("franchiseBoardDelta", franchiseDelta);
  renderTotalDelta("competitorBoardDelta", competitorDelta);

  renderOurReviewRows(payload.reviews.ourPlaces || []);
  renderFranchiseReviewRows(payload.reviews.franchisePlaces || []);
  renderCompetitorReviewRows(payload.reviews.competitorPlaces || []);
}

function renderOurReviewRows(rows) {
  const tbody = document.getElementById("ourReviewRows");
  const sortedRows = sortOwnedStores(rows);
  tbody.innerHTML = sortedRows.length
    ? sortedRows
        .map(
          (row) => `
            <tr>
              <td class="place-name">${ownedStoreLabel(row.name)}</td>
              <td class="number-cell">${formatNumber(row.dailyReviews)}</td>
              <td><span class="${deltaClass(row.dailyDelta)}">${formatDelta(row.dailyDelta)}</span></td>
              <td class="number-cell">${formatNumber(row.receiptReviews)}</td>
              <td class="number-cell">${row.totalReviews === null ? "-" : formatNumber(row.totalReviews)}</td>
            </tr>
          `
        )
        .join("")
    : `<tr><td colspan="5" class="muted">당사 리뷰 스냅샷이 아직 없습니다.</td></tr>`;
}

function renderCompetitorReviewRows(rows) {
  const tbody = document.getElementById("competitorReviewRows");
  tbody.innerHTML = rows.length
    ? rows
        .map(
          (row, index) => `
            <tr>
              <td class="rank-cell">${index + 1}</td>
              <td class="place-name">${row.name}</td>
              <td class="number-cell">${formatNumber(row.dailyReviews)}</td>
              <td><span class="${deltaClass(row.dailyDelta)}">${formatDelta(row.dailyDelta)}</span></td>
              <td class="number-cell">${formatNumber(row.receiptReviews)}</td>
              <td class="number-cell">${row.totalReviews === null ? "-" : formatNumber(row.totalReviews)}</td>
            </tr>
          `
        )
        .join("")
    : `<tr><td colspan="6" class="muted">경쟁사 리뷰 스냅샷이 아직 없습니다.</td></tr>`;
}

function renderFranchiseReviewRows(rows) {
  const tbody = document.getElementById("franchiseReviewRows");
  tbody.innerHTML = rows.length
    ? rows
        .map(
          (row) => `
            <tr>
              <td class="place-name">${row.name}</td>
              <td class="number-cell">${formatNumber(row.dailyReviews)}</td>
              <td><span class="${deltaClass(row.dailyDelta)}">${formatDelta(row.dailyDelta)}</span></td>
              <td class="number-cell">${formatNumber(row.receiptReviews)}</td>
              <td class="number-cell">${row.totalReviews === null ? "-" : formatNumber(row.totalReviews)}</td>
            </tr>
          `
        )
        .join("")
    : `<tr><td colspan="5" class="muted">가맹점 리뷰 스냅샷이 아직 없습니다.</td></tr>`;
}

function renderKeywords(payload) {
  const target = document.getElementById("keywords");
  const keywords = payload.reviews.keywords;
  target.innerHTML = keywords.length
    ? keywords
        .map((item) => `<span class="keyword">${item.keyword} <strong>${formatNumber(item.count)}</strong></span>`)
        .join("")
    : `<span class="muted">당일 리뷰 본문이 수집되면 주요 키워드가 표시됩니다.</span>`;
}

async function loadDashboard(date) {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  const response = await fetch(`/api/dashboard${query}`);
  const payload = await response.json();
  await hydrateReservationMetadata(payload);
  renderDateSelect(payload);
  renderMetrics(payload);
  renderSummary(payload);
  renderReservations(payload);
  renderComparisonNote(payload);
  renderReviewBoards(payload);
  renderKeywords(payload);
}

async function hydrateReservationMetadata(payload) {
  try {
    const response = await fetch(`/reservation-latest.json?v=${Date.now()}`, { cache: "no-store" });
    if (response.ok) {
      const latest = await response.json();
      if (latest.reservationDate !== payload.reservationDate && latest.reservationDate !== payload.date) {
        return;
      }
      payload.reservations.collectedAt = latest.collectedAt;
      payload.reservations.totalUsed = payload.reservations.totalUsed ?? latest.totalUsed;
      payload.reservations.totalUsedMonthToDate =
        latest.totalUsedMonthToDate ?? payload.reservations.totalUsedMonthToDate;
      if (Array.isArray(latest.stores)) {
        const latestByPlace = Object.fromEntries(latest.stores.map((row) => [row.place_id || row.placeId, row]));
        payload.reservations.stores = (payload.reservations.stores || []).map((row) => {
          const latestRow = latestByPlace[row.placeId];
          if (!latestRow) {
            return row;
          }
          return {
            ...row,
            usedReservations: row.usedReservations ?? latestRow.used_reservations ?? latestRow.usedReservations,
            usedMonthToDate: latestRow.used_month_to_date ?? latestRow.usedMonthToDate ?? row.usedMonthToDate,
          };
        });
      }
    }
    await hydrateReservationPreviousMetadata(payload);
  } catch {
    // Latest collection time is optional display metadata.
  }
}

async function hydrateReservationPreviousMetadata(payload) {
  if (payload.reservations.totalUsedDelta !== undefined && payload.reservations.totalUsedDelta !== null) {
    return;
  }
  const response = await fetch(`/reservation-previous.json?v=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) {
    return;
  }
  const previous = await response.json();
  if (previous.reservationDate !== payload.previousReservationDate) {
    return;
  }
  const previousTotalUsed = Number(previous.totalUsed || 0);
  const currentTotalUsed = Number(payload.reservations.totalUsed || 0);
  payload.reservations.totalUsedDelta = currentTotalUsed - previousTotalUsed;
  if (!Array.isArray(previous.stores)) {
    return;
  }
  const previousByPlace = Object.fromEntries(previous.stores.map((row) => [row.place_id || row.placeId, row]));
  payload.reservations.stores = (payload.reservations.stores || []).map((row) => {
    const previousRow = previousByPlace[row.placeId];
    if (!previousRow || row.usedReservations === undefined || row.usedReservations === null) {
      return row;
    }
    return {
      ...row,
      usedDelta: Number(row.usedReservations || 0) - Number(previousRow.used_reservations || previousRow.usedReservations || 0),
    };
  });
}

function showPage(pageName) {
  state.activePage = pageName;
  document.querySelectorAll("[data-page-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.pagePanel === pageName);
  });
  document.querySelectorAll(".tab-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.page === pageName);
  });
}

document.getElementById("dateSelect").addEventListener("change", (event) => {
  loadDashboard(event.target.value);
});

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => showPage(button.dataset.page));
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/service-worker.js").catch(() => {});
}

loadDashboard();
