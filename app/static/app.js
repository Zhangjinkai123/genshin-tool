const state = {
  account: JSON.parse(localStorage.getItem("genshinTool.account") || "{}"),
  featuredItems: JSON.parse(localStorage.getItem("genshinTool.featuredItems") || "{}"),
  wishes: [],
  wishSummary: null,
  wishFullSummary: null,
  artifacts: [],
  artifactSummary: null,
  selectedArtifactId: "",
  characters: [],
  characterSummary: null,
  selectedCharacterKey: "",
  characterGradeFilter: "",
  updatedAt: "",
  intervalShowDate: JSON.parse(localStorage.getItem("genshinTool.intervalShowDate") || "false")
};

const $ = (id) => document.getElementById(id);

const charts = {
  dashWishChart: $("dashWishChart"),
  dashArtifactChart: $("dashArtifactChart"),
  poolChart: $("poolChart"),
  monthChart: $("monthChart"),
  fiveChart: $("fiveChart"),
  intervalChart: $("intervalChart"),
  fiftyChart: $("fiftyChart")
};

const chartInstances = {};
const chartPalette = ["#5e6ad2", "#26a69a", "#f2b84b", "#e76f51", "#7c3aed", "#64748b"];
const wishResultColors = {
  win: "#16a34a",
  lose: "#dc2626",
  unknown: "#64748b"
};
const TALENT_NAMES = { auto: "普攻", skill: "战技", burst: "爆发" };

document.addEventListener("DOMContentLoaded", async () => {
  bindNavigation();
  bindAccount();
  bindFeaturedItems();
  bindWishes();
  bindArtifacts();
  bindCharacters();
  bindIntervalOptions();
  bindCache();
  hydrateAccountForm();
  hydrateFeaturedForm();
  await loadDefaultWishes();
  await loadDefaultArtifacts();
  await loadDefaultCharacters();
  renderAll();
});

async function loadDefaultWishes() {
  try {
    const result = await fetch("/api/wishes/default").then(readResponse);
    if (!result.records?.length) return;
    state.wishes = result.records;
    state.wishSummary = result.summary;
    state.wishFullSummary = result.summary;
    if (!state.account.uid && result.account?.uid) {
      state.account = { ...state.account, uid: result.account.uid };
      hydrateAccountForm();
    }
    touchUpdatedAt();
    updateWishFilters();
  } catch (error) {
    console.warn("Unable to load default wishes", error);
  }
}

async function loadDefaultArtifacts() {
  try {
    const result = await fetch("/api/artifacts/default").then(readResponse);
    if (!result.records?.length) return;
    state.artifacts = result.records;
    state.artifactSummary = result.summary;
    state.selectedArtifactId = result.records[0]?.id || "";
    touchUpdatedAt();
    updateArtifactFilters(result.summary?.templates || result.templates || []);
  } catch (error) {
    console.warn("Unable to load default artifacts", error);
  }
}

async function loadDefaultCharacters() {
  try {
    const result = await fetch("/api/characters/default").then(readResponse);
    applyCharacterResult(result, false);
  } catch (error) {
    console.warn("Unable to load default characters", error);
  }
}

function bindNavigation() {
  document.querySelectorAll(".nav-tab").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $(`${button.dataset.view}View`).classList.add("active");
      requestAnimationFrame(renderCharts);
    });
  });
}

function bindIntervalOptions() {
  const toggle = $("intervalDateToggle");
  if (!toggle) return;
  toggle.checked = Boolean(state.intervalShowDate);
  toggle.addEventListener("change", () => {
    state.intervalShowDate = toggle.checked;
    localStorage.setItem("genshinTool.intervalShowDate", JSON.stringify(state.intervalShowDate));
    renderCharts();
  });
}

function bindAccount() {
  $("saveAccountBtn").addEventListener("click", () => {
    state.account = {
      uid: $("uidInput").value.trim(),
      server: $("serverInput").value,
      note: $("noteInput").value.trim()
    };
    localStorage.setItem("genshinTool.account", JSON.stringify(state.account));
    toast("账号信息已保存。");
    renderAccount();
  });
}

function bindFeaturedItems() {
  $("saveFeaturedBtn").addEventListener("click", async () => {
    state.featuredItems = wishFeaturedItemsFromForm();
    localStorage.setItem("genshinTool.featuredItems", JSON.stringify(state.featuredItems));
    if (state.wishes.length) {
      await reanalyzeWishes();
    }
    toast("UP 五星名单已保存。");
  });
}

function bindWishes() {
  $("wishFile").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const json = await readJsonFile(file);
      const result = await api("/api/wishes/analyze", { uid: currentUid(), records: json, featuredItems: wishFeaturedItems() });
      state.wishes = result.records;
      state.wishSummary = result.summary;
      state.wishFullSummary = result.summary;
      touchUpdatedAt();
      updateWishFilters();
      renderAll();
      toast(`已导入 ${result.records.length} 条抽卡记录。${result.errors.length ? `有 ${result.errors.length} 条错误。` : ""}`);
    } catch (error) {
      toast(error.message);
    } finally {
      event.target.value = "";
    }
  });

  $("fetchWishBtn").addEventListener("click", async () => {
    if (!ensureUid()) return;
    const url = $("wishUrlInput").value.trim();
    if (!url) {
      toast("请先粘贴祈愿历史 URL。");
      return;
    }
    const button = $("fetchWishBtn");
    button.disabled = true;
    button.textContent = "拉取中...";
    try {
      const result = await api("/api/wishes/fetch", { uid: currentUid(), url, maxPages: 50, featuredItems: wishFeaturedItems() });
      applyWishResult(result);
      const warnings = result.source?.warnings?.length ? ` ${result.source.warnings.join(" ")}` : "";
      toast(`已从 URL 拉取 ${result.records.length} 条抽卡记录。${warnings}`);
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.textContent = "从 URL 拉取";
    }
  });

  ["wishPoolFilter", "wishStart", "wishEnd"].forEach((id) => {
    $(id).addEventListener("change", refreshWishSummaryFromFilters);
  });

  $("saveWishCacheBtn").addEventListener("click", async () => {
    if (!ensureUid() || !state.wishes.length) return;
    const summary = await fullWishSummaryForCache();
    await api("/api/cache/wishes", { uid: currentUid(), records: state.wishes, summary });
    toast("抽卡数据已写入本地 JSON 缓存。");
  });
}

function applyWishResult(result) {
  state.wishes = result.records;
  state.wishSummary = result.summary;
  state.wishFullSummary = result.summary;
  touchUpdatedAt();
  updateWishFilters();
  renderAll();
}

function bindArtifacts() {
  $("artifactFile").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const json = await readJsonFile(file);
      const result = await api("/api/artifacts/analyze", { uid: currentUid(), records: json });
      state.artifacts = result.records;
      state.artifactSummary = result.summary;
      state.selectedArtifactId = result.records[0]?.id || "";
      touchUpdatedAt();
      updateArtifactFilters(result.summary.templates || result.templates || []);
      renderAll();
      toast(`已导入 ${result.records.length} 件圣遗物。${result.errors.length ? `有 ${result.errors.length} 条错误。` : ""}`);
    } catch (error) {
      toast(error.message);
    } finally {
      event.target.value = "";
    }
  });

  ["templateSelect", "slotFilter", "setFilter", "mainFilter", "lockFilter", "minCvFilter", "artifactSort"].forEach((id) => {
    $(id).addEventListener("input", renderArtifacts);
  });

  $("saveArtifactCacheBtn").addEventListener("click", async () => {
    if (!ensureUid() || !state.artifacts.length) return;
    await api("/api/cache/artifacts", { uid: currentUid(), records: state.artifacts, summary: state.artifactSummary });
    toast("圣遗物数据已写入本地 JSON 缓存。");
  });
}

function bindCharacters() {
  $("characterFile").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const json = await readJsonFile(file);
      const result = await api("/api/characters/analyze", { records: json });
      applyCharacterResult(result);
      toast(`已分析 ${result.records.length} 名角色的练度。`);
    } catch (error) {
      toast(error.message);
    } finally {
      event.target.value = "";
    }
  });

  ["characterRoleFilter", "characterSort"].forEach((id) => {
    $(id).addEventListener("change", renderCharacters);
  });
  document.querySelectorAll("#characterGradeTabs button").forEach((button) => {
    button.addEventListener("click", () => {
      state.characterGradeFilter = button.dataset.grade || "";
      renderCharacters();
    });
  });
}

function applyCharacterResult(result, render = true) {
  state.characters = result.records || [];
  state.characterSummary = result.summary || null;
  state.selectedCharacterKey = state.characters[0]?.key || "";
  updateCharacterFilters();
  if (render) {
    touchUpdatedAt();
    renderAll();
  }
}

function bindCache() {
  $("loadCacheBtn").addEventListener("click", async () => {
    if (!ensureUid()) return;
    const bundle = await fetch(`/api/cache?uid=${encodeURIComponent(currentUid())}`).then(readResponse);
    state.wishes = bundle.wishes || [];
    if (state.wishes.length) {
      const result = await api("/api/wishes/analyze", { uid: currentUid(), records: recordsForReanalysis(state.wishes), featuredItems: wishFeaturedItems() });
      state.wishes = result.records;
      state.wishSummary = result.summary;
      state.wishFullSummary = result.summary;
    } else {
      state.wishSummary = null;
      state.wishFullSummary = null;
    }
    state.artifacts = bundle.artifacts || [];
    state.artifactSummary = bundle.artifactSummary || null;
    state.selectedArtifactId = state.artifacts[0]?.id || "";
    touchUpdatedAt();
    updateWishFilters();
    updateArtifactFilters(state.artifactSummary?.templates || []);
    renderAll();
    toast("已读取本地缓存。");
  });

  $("clearCacheBtn").addEventListener("click", async () => {
    if (!ensureUid()) return;
    const result = await fetch(`/api/cache?uid=${encodeURIComponent(currentUid())}`, { method: "DELETE" }).then(readResponse);
    state.wishes = [];
    state.wishSummary = null;
    state.wishFullSummary = null;
    state.artifacts = [];
    state.artifactSummary = null;
    state.selectedArtifactId = "";
    renderAll();
    toast(`已清理 ${result.removed} 个缓存文件。`);
  });
}

function hydrateAccountForm() {
  $("uidInput").value = state.account.uid || "";
  $("serverInput").value = state.account.server || "天空岛";
  $("noteInput").value = state.account.note || "";
}

function hydrateFeaturedForm() {
  $("featuredCharacterInput").value = listToText(state.featuredItems.character);
  $("featuredWeaponInput").value = listToText(state.featuredItems.weapon);
}

function renderAll() {
  renderAccount();
  renderDashboard();
  renderWishes();
  renderArtifacts();
  renderCharacters();
  renderCharts();
}

function renderAccount() {
  const uid = currentUid();
  const bits = uid ? [uid, state.account.server, state.account.note].filter(Boolean) : ["未设置账号"];
  $("currentAccount").textContent = bits.join(" · ");
  $("settingsAccount").textContent = bits.join(" · ");
}

function renderDashboard() {
  $("dashWishTotal").textContent = state.wishSummary?.total || 0;
  $("dashFive").textContent = `五星 ${state.wishSummary?.fiveStarCount || 0} / 四星 ${state.wishSummary?.fourStarCount || 0}`;
  $("dashArtifactTotal").textContent = state.artifactSummary?.total || 0;
  $("dashArtifactAvg").textContent = `平均 RV ${state.artifactSummary?.averageScore || 0}`;
  $("dashHighCv").textContent = state.artifactSummary?.highCvCount || 0;
  $("dashUpdated").textContent = state.updatedAt || "-";
  $("wishHint").textContent = state.wishSummary ? `${state.wishSummary.poolCounts.length} 个卡池` : "等待导入";
  $("artifactHint").textContent = state.artifactSummary ? `${state.artifactSummary.grades.length} 个评级` : "等待导入";
}

function renderWishes() {
  const summary = state.wishSummary;
  $("wishTotal").textContent = summary?.total || 0;
  $("wishFive").textContent = summary?.fiveStarCount || 0;
  $("wishFour").textContent = summary?.fourStarCount || 0;
  $("wishWinRate").textContent = summary?.fiftyFifty?.winRate == null ? "-" : `${summary.fiftyFifty.winRate}%`;
  const win = summary?.fiftyFifty?.win || 0;
  const lose = summary?.fiftyFifty?.lose || 0;
  const unknown = summary?.fiftyFifty?.unknown || 0;
  $("fiftyNote").textContent = `胜=命中当期 UP，歪=未命中当期 UP，待判断=缺少 UP 名单或 fiftyFifty 字段。命中率只按胜/歪计算；当前待判断 ${unknown} 条。`;
  $("pityList").innerHTML = summary?.pityCards?.length
    ? summary.pityCards.map((item) => `<div class="pity-row"><span>${escapeHtml(item.poolType)}</span><strong>${item.currentPity}</strong></div>`).join("")
    : `<div class="detail-empty">暂无垫数数据</div>`;
  $("wishTable").innerHTML = (summary?.recentRecords || [])
    .map((item) => `<tr><td>${escapeHtml(item.time)}</td><td>${escapeHtml(item.poolType)}</td><td>${escapeHtml(item.itemName)}</td><td>${escapeHtml(item.itemType)}</td><td>${item.rank}</td><td>${fiftyLabel(item.fiftyFifty)}</td></tr>`)
    .join("");
  $("wishErrors").textContent = state.wishes.length ? `当前显示最近 ${summary?.recentRecords?.length || 0} 条` : "未导入";
}

function renderArtifacts() {
  const list = filteredArtifacts();
  const template = $("templateSelect").value || state.artifactSummary?.templates?.[0] || "暴击主 C";
  $("artifactTotal").textContent = state.artifactSummary?.total || 0;
  $("artifactAvg").textContent = state.artifactSummary?.averageScore || 0;
  $("artifactHighCv").textContent = state.artifactSummary?.highCvCount || 0;
  $("artifactLocked").textContent = state.artifactSummary?.lockedCount || 0;
  $("artifactErrors").textContent = state.artifacts.length ? `筛选后 ${list.length} 件` : "未导入";

  $("artifactList").innerHTML = list.length
    ? list.map((item) => artifactItemHtml(item, template)).join("")
    : `<div class="detail-empty">没有符合条件的圣遗物</div>`;

  document.querySelectorAll(".artifact-item button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedArtifactId = button.dataset.id;
      renderArtifacts();
    });
  });

  const selected = state.artifacts.find((item) => item.id === state.selectedArtifactId) || list[0];
  if (selected) {
    state.selectedArtifactId = selected.id;
    document.querySelectorAll(".artifact-item").forEach((item) => item.classList.toggle("active", item.dataset.id === selected.id));
    $("artifactDetail").innerHTML = artifactDetailHtml(selected, template);
  } else {
    $("artifactDetail").innerHTML = "选择一件圣遗物查看评分解释";
  }
}

function renderCharacters() {
  const summary = state.characterSummary;
  const list = filteredCharacters();
  document.querySelectorAll("#characterGradeTabs button").forEach((button) => {
    button.classList.toggle("active", button.dataset.grade === state.characterGradeFilter);
  });
  $("characterTotal").textContent = summary?.total || 0;
  $("characterAvg").textContent = summary?.averageScore || 0;
  $("characterGraduate").textContent = summary?.graduateCount || 0;
  $("characterComplete").textContent = summary?.completeArtifactCount || 0;
  $("characterHint").textContent = state.characters.length ? `筛选后 ${list.length} 名` : "等待导入";

  $("characterList").innerHTML = list.length
    ? list.map(characterItemHtml).join("")
    : `<div class="detail-empty">没有符合条件的角色</div>`;
  document.querySelectorAll(".character-item button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedCharacterKey = button.dataset.key;
      renderCharacters();
    });
  });

  const selected = state.characters.find((item) => item.key === state.selectedCharacterKey) || list[0];
  if (selected) {
    state.selectedCharacterKey = selected.key;
    document.querySelectorAll(".character-item").forEach((item) => item.classList.toggle("active", item.dataset.key === selected.key));
    $("characterDetail").innerHTML = characterDetailHtml(selected);
  } else {
    $("characterDetail").innerHTML = "选择角色查看毕业模板与培养建议";
  }
}

function filteredCharacters() {
  const role = $("characterRoleFilter").value;
  const grade = state.characterGradeFilter;
  const sort = $("characterSort").value;
  const list = state.characters.filter((item) => {
    return (!role || item.role === role)
      && (!grade || item.grade === grade);
  });
  return list.sort((a, b) => {
    if (sort === "level") return b.level - a.level || b.score - a.score;
    if (sort === "artifact") return b.artifacts.count - a.artifacts.count || b.artifacts.score - a.artifacts.score;
    return b.score - a.score;
  });
}

function updateCharacterFilters() {
  const roles = unique(state.characters.map((item) => item.role));
  setOptions($("characterRoleFilter"), [["", "全部毕业模板"], ...roles.map((item) => [item, item])]);
}

function characterItemHtml(item) {
  const weapon = item.weapon.level ? `${escapeHtml(item.weapon.name)} ${item.weapon.level} 级 R${item.weapon.refinement}` : "未识别到武器";
  const actualSets = item.artifacts.sets.map((set) => `${escapeHtml(set.name)} ${set.count} 件`).join(" / ") || "未装备";
  return `
    <article class="character-item" data-key="${escapeAttr(item.key)}">
      <div>
        <div class="item-title">
          <span>${escapeHtml(item.name)}</span>
          <span class="pill">${escapeHtml(item.role)}</span>
          <span class="pill">${item.level} 级 · C${item.constellation}</span>
          <span class="grade-pill ${characterGradeClass(item.grade)}">${escapeHtml(item.grade)}</span>
        </div>
        <div class="item-meta">${escapeHtml(weapon)} · 实际圣遗物 ${item.artifacts.count}/5 · ${actualSets}</div>
        <div class="substats">${formatTalentSummary(item.talents)} · 总 CV ${item.artifacts.totalCv}</div>
      </div>
      <div class="character-item-score">
        <span>总分</span>
        <strong>${item.score}</strong>
        <small>${escapeHtml(item.rating)}</small>
      </div>
      <button data-key="${escapeAttr(item.key)}">查看</button>
    </article>`;
}

function characterDetailHtml(item) {
  const artifact = item.artifacts;
  const recommendedSets = item.recommendedSets.map((set) => `<span class="pill">${escapeHtml(set)}</span>`).join(" ");
  const actualSets = artifact.sets.length
    ? artifact.sets.map((set) => `<span class="pill">${escapeHtml(set.name)} ${set.count} 件</span>`).join(" ")
    : "未装备圣遗物";
  const comparisonBlock = item.recommendedSetMatched ? "" : `
    <div class="detail-block">
      <h4>圣遗物对照</h4>
      <p class="compare-label">推荐使用</p>
      <p>${recommendedSets}</p>
      <p class="compare-label">实际使用</p>
      <p>${actualSets}</p>
    </div>`;
  return `
    <div class="character-score-row">
      <div><span>圣遗物总分</span><strong>${item.score}</strong><small>逐件副词条等效次数累计</small></div>
      <span class="grade-pill ${characterGradeClass(item.grade)}">${escapeHtml(item.rating)} · ${escapeHtml(item.grade)}</span>
    </div>
    <div class="detail-block">
      <h4>${escapeHtml(item.name)} · ${escapeHtml(item.role)}</h4>
      <p class="item-meta">${item.level} 级 · 突破 ${item.ascension} · C${item.constellation} · ${escapeHtml(item.weapon.name)} ${item.weapon.level ? `${item.weapon.level} 级 R${item.weapon.refinement}` : ""}</p>
      <p>${escapeHtml(item.templatePlan)}</p>
    </div>
    <div class="detail-block">
      <h4>逐件评分</h4>
      <div class="score-breakdown">
        ${artifact.pieceScores.map((piece) => `<span>${escapeHtml(piece.slot)} <strong>${piece.score}</strong></span>`).join("")}
      </div>
      <p class="item-meta">评分仅计算当前已装备圣遗物的副词条；等级、天赋、武器仅作状态展示。</p>
    </div>
    ${comparisonBlock}
    <div class="detail-block">
      <h4>当前圣遗物练度</h4>
      <p>${artifact.count}/5 件 · +20 ${artifact.level20Count} 件 · ${escapeHtml(artifact.topSet)} ${artifact.topSetCount} 件 · 总 CV ${artifact.totalCv}</p>
      <p class="item-meta">主词条命中：${artifact.mainHits.length}/3${artifact.mainMisses.length ? `；待调整：${escapeHtml(artifact.mainMisses.join("、"))}` : ""}</p>
    </div>
    <div class="detail-block">
      <h4>培养建议</h4>
      <ul>${item.suggestions.map((suggestion) => `<li>${escapeHtml(suggestion)}</li>`).join("")}</ul>
    </div>`;
}

function formatTalentSummary(talents) {
  return `普攻 ${talents.auto} / 战技 ${talents.skill} / 爆发 ${talents.burst}`;
}

function characterGradeClass(grade) {
  return ({ "毕业": "grade-graduate", "优秀": "grade-excellent", "可用": "grade-usable", "待培养": "grade-pending" })[grade] || "grade-pending";
}

function artifactGradeClass(grade) {
  return ({ SSS: "artifact-grade-sss", SS: "artifact-grade-ss", S: "artifact-grade-s", A: "artifact-grade-a", B: "artifact-grade-b" })[grade] || "artifact-grade-b";
}

function artifactItemHtml(item, template) {
  const templateScore = item.score.templates[template]?.score ?? "-";
  const subs = item.subStats.map((stat) => `${escapeHtml(stat.name)} ${stat.value}`).join(" / ");
  return `
    <article class="artifact-item" data-id="${escapeAttr(item.id)}">
      <div>
        <div class="item-title">
          <span>${escapeHtml(item.slot)}</span>
          <span class="pill">${escapeHtml(item.setName)}</span>
          <span class="pill">+${item.level}</span>
          ${item.locked ? `<span class="pill">已锁定</span>` : ""}
        </div>
        <div class="item-meta">${escapeHtml(item.mainStat)} ${item.mainValue || ""} · RV ${item.score.general} · ${template} ${templateScore} · CV ${item.score.cv}</div>
        <div class="substats">${subs || "无副词条"}</div>
      </div>
      <div class="artifact-item-score ${artifactGradeClass(item.score.grade)}">
        <span>RV 评分</span>
        <strong>${item.score.general}</strong>
        <small>${escapeHtml(item.score.grade)} 级</small>
      </div>
      <button data-id="${escapeAttr(item.id)}">查看</button>
    </article>`;
}

function artifactDetailHtml(item, template) {
  const templateResult = item.score.templates[template];
  return `
    <div class="detail-block">
      <h4>${escapeHtml(item.slot)} · ${escapeHtml(item.setName)}</h4>
      <p class="item-meta">${item.rarity} 星 +${item.level} · ${escapeHtml(item.equippedBy || "未装备")}</p>
      <p><span class="pill">RV ${item.score.general}</span> <span class="pill">RV 评级 ${item.score.grade}</span> <span class="pill">CV ${item.score.cv}</span></p>
    </div>
    <div class="detail-block">
      <h4>主副词条</h4>
      <p>${escapeHtml(item.mainStat)} ${item.mainValue || ""}</p>
      <ul>${item.subStats.map((stat) => `<li>${escapeHtml(stat.name)} ${stat.value}</li>`).join("")}</ul>
    </div>
    <div class="detail-block">
      <h4>${escapeHtml(template)}</h4>
      <p><span class="pill">模板分 ${templateResult?.score ?? "-"}</span> <span class="pill">${templateResult?.grade ?? "-"}</span></p>
      <p>${escapeHtml(templateResult?.recommendedUse || item.score.recommendedUse)}</p>
      <ul>${(templateResult?.reasons || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>
    </div>
    <div class="detail-block">
      <h4>RV 评分说明</h4>
      <ul>${item.score.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>
    </div>`;
}

function renderCharts() {
  if (!window.echarts) {
    Object.values(charts).forEach((node) => {
      if (node) node.textContent = "ECharts 加载中或加载失败";
    });
    return;
  }
  barChart(charts.dashWishChart, state.wishSummary?.poolCounts || [], { labelKey: "name", valueKey: "value", horizontal: true, maxRows: 5, sort: true });
  donutChart(charts.dashArtifactChart, state.artifactSummary?.grades || [], { inner: "58%" });
  barChart(charts.poolChart, state.wishSummary?.poolCounts || [], { labelKey: "name", valueKey: "value", horizontal: true, sort: true });
  lineChart(charts.monthChart, state.wishSummary?.monthlyTrend || [], { labelKey: "month", valueKey: "count" });
  barChart(charts.fiveChart, state.wishSummary?.fiveStarDistribution || [], { labelKey: "name", valueKey: "value", horizontal: true, sort: true });
  const recentIntervals = (state.wishSummary?.fiveStarIntervals || [])
    .slice()
    .sort((a, b) => String(b.time || "").localeCompare(String(a.time || "")));
  barChart(charts.intervalChart, recentIntervals, {
    labelKey: (item) => state.intervalShowDate ? `${item.time?.slice(0, 10) || ""} ${item.itemName}` : item.itemName,
    valueKey: "count",
    horizontal: true,
    maxRows: 12,
    markLose: true
  });
  donutChart(charts.fiftyChart, [
    { name: "胜", value: state.wishSummary?.fiftyFifty?.win || 0 },
    { name: "歪", value: state.wishSummary?.fiftyFifty?.lose || 0 },
    { name: "待判断", value: state.wishSummary?.fiftyFifty?.unknown || 0, itemStyle: { color: "#9ca3af" } }
  ], { inner: "56%", emptyText: "暂无五星结果" });
}

async function refreshWishSummaryFromFilters() {
  if (!state.wishes.length) return;
  const records = filteredWishes();
  const result = await api("/api/wishes/analyze", { uid: currentUid(), records: recordsForReanalysis(records), featuredItems: wishFeaturedItems() });
  state.wishSummary = result.summary;
  if (!hasWishFilters()) state.wishFullSummary = result.summary;
  renderDashboard();
  renderWishes();
  renderCharts();
}

function filteredWishes() {
  const pool = $("wishPoolFilter").value;
  const start = $("wishStart").value;
  const end = $("wishEnd").value;
  return state.wishes.filter((item) => {
    const day = item.time.slice(0, 10);
    return (!pool || item.poolType === pool) && (!start || day >= start) && (!end || day <= end);
  });
}

function hasWishFilters() {
  return Boolean($("wishPoolFilter").value || $("wishStart").value || $("wishEnd").value);
}

async function fullWishSummaryForCache() {
  if (state.wishFullSummary && !hasWishFilters()) return state.wishFullSummary;
  const result = await api("/api/wishes/analyze", { uid: currentUid(), records: recordsForReanalysis(state.wishes), featuredItems: wishFeaturedItems() });
  state.wishFullSummary = result.summary;
  return result.summary;
}

async function reanalyzeWishes() {
  const full = await api("/api/wishes/analyze", { uid: currentUid(), records: recordsForReanalysis(state.wishes), featuredItems: wishFeaturedItems() });
  state.wishes = full.records;
  state.wishFullSummary = full.summary;
  if (hasWishFilters()) {
    await refreshWishSummaryFromFilters();
  } else {
    state.wishSummary = full.summary;
    renderAll();
  }
}

function filteredArtifacts() {
  const slot = $("slotFilter").value;
  const setName = $("setFilter").value;
  const main = $("mainFilter").value;
  const lock = $("lockFilter").value;
  const minCv = Number($("minCvFilter").value || 0);
  const sort = $("artifactSort").value;
  const template = $("templateSelect").value || state.artifactSummary?.templates?.[0] || "暴击主 C";
  const list = state.artifacts.filter((item) => {
    return (!slot || item.slot === slot)
      && (!setName || item.setName === setName)
      && (!main || item.mainStat === main)
      && (!lock || String(item.locked) === lock)
      && item.score.cv >= minCv;
  });
  return list.sort((a, b) => {
    if (sort === "template") return (b.score.templates[template]?.score || 0) - (a.score.templates[template]?.score || 0);
    if (sort === "cv") return b.score.cv - a.score.cv;
    if (sort === "level") return b.level - a.level;
    if (sort === "recent") return String(b.importedAt).localeCompare(String(a.importedAt));
    return b.score.general - a.score.general;
  });
}

function updateWishFilters() {
  const pools = unique(state.wishes.map((item) => item.poolType));
  setOptions($("wishPoolFilter"), [["", "全部卡池"], ...pools.map((item) => [item, item])]);
}

function updateArtifactFilters(templates) {
  const templateNames = templates.length ? templates : unique(state.artifacts.flatMap((item) => Object.keys(item.score?.templates || {})));
  setOptions($("templateSelect"), templateNames.map((item) => [item, item]));
  setOptions($("slotFilter"), [["", "全部部位"], ...unique(state.artifacts.map((item) => item.slot)).map((item) => [item, item])]);
  setOptions($("setFilter"), [["", "全部套装"], ...unique(state.artifacts.map((item) => item.setName)).map((item) => [item, item])]);
  setOptions($("mainFilter"), [["", "全部主词条"], ...unique(state.artifacts.map((item) => item.mainStat)).map((item) => [item, item])]);
}

function setOptions(select, options) {
  const current = select.value;
  select.innerHTML = options.map(([value, label]) => `<option value="${escapeAttr(value)}">${escapeHtml(label)}</option>`).join("");
  if (options.some(([value]) => value === current)) select.value = current;
}

function barChart(node, rows, opts = {}) {
  const chart = getChart(node);
  if (!chart) return;
  const labelKey = opts.labelKey || "name";
  const valueKey = opts.valueKey || "value";
  const labelOf = (item) => typeof labelKey === "function" ? labelKey(item) : item[labelKey];
  const valueOf = (item) => Number(item[valueKey]) || 0;
  const source = opts.sort ? rows.slice().sort((a, b) => valueOf(b) - valueOf(a)) : rows.slice();
  const data = source.slice(0, opts.maxRows || 12);
  const labels = data.map((item) => truncate(String(labelOf(item) || "-"), opts.horizontal ? 18 : 12));
  const barData = opts.markLose
    ? data.map((item) => ({
      value: valueOf(item),
      fiftyFifty: item.fiftyFifty,
      itemStyle: {
        color: wishResultColors[item.fiftyFifty] || wishResultColors.unknown,
        borderRadius: [0, 6, 6, 0]
      }
    }))
    : data.map(valueOf);
  const loseMarkers = opts.markLose
    ? data.flatMap((item, index) => item.fiftyFifty === "lose" ? [{
      coord: [valueOf(item) / 2, index],
      label: { show: true, formatter: "歪" }
    }] : [])
    : [];
  if (!data.length) {
    chart.setOption(emptyChartOption(), true);
    return;
  }

  if (opts.horizontal) {
    chart.setOption({
      ...baseChartOption(data.length),
      grid: { top: 14, right: opts.markLose ? 86 : 56, bottom: 24, left: 150, containLabel: false },
      color: chartPalette,
      xAxis: {
        type: "value",
        minInterval: 1,
        splitLine: { lineStyle: { color: "#edf0f3" } },
        axisLabel: { color: "#6b7280", fontSize: 12 },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: labels,
        axisTick: { show: false },
        axisLine: { show: false },
        axisLabel: {
          color: "#374151",
          fontSize: 12,
          fontWeight: 520
        }
      },
      series: [{
        type: "bar",
        data: barData,
        barMaxWidth: 22,
        label: {
          show: true,
          position: "right",
          color: "#374151",
          fontSize: 12,
          fontWeight: 620,
          formatter: opts.markLose ? (params) => {
            const value = params.value;
            return `{value|${value}}`;
          } : undefined,
          rich: {
            value: { color: "#374151", fontSize: 12, fontWeight: 620 },
            lose: { color: "#dc2626", fontSize: 12, fontWeight: 760 }
          }
        },
        itemStyle: { borderRadius: [0, 6, 6, 0] },
        markPoint: loseMarkers.length ? {
          silent: true,
          symbol: "circle",
          symbolSize: 1,
          itemStyle: { color: "transparent" },
          label: {
            show: true,
            position: "inside",
            color: "#fff",
            fontSize: 12,
            fontWeight: 760
          },
          data: loseMarkers
        } : undefined,
        emphasis: { focus: "series" }
      }]
    }, true);
    return;
  }

  chart.setOption({
    ...baseChartOption(data.length),
    grid: { top: 18, right: 18, bottom: 58, left: 48, containLabel: true },
    color: chartPalette,
    xAxis: {
      type: "category",
      data: labels,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisLabel: { color: "#6b7280", interval: 0, rotate: data.length > 5 ? 24 : 0, fontSize: 12 }
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      splitLine: { lineStyle: { color: "#edf0f3" } },
      axisLabel: { color: "#6b7280", fontSize: 12 }
    },
    series: [{
      type: "bar",
      data: data.map(valueOf),
      barMaxWidth: 34,
      label: { show: data.length <= 10, position: "top", color: "#374151", fontSize: 12, fontWeight: 620 },
      itemStyle: { borderRadius: [6, 6, 0, 0] },
      emphasis: { focus: "series" }
    }]
  }, true);
}

function lineChart(node, rows, opts = {}) {
  const chart = getChart(node);
  if (!chart) return;
  const labelKey = opts.labelKey || "name";
  const valueKey = opts.valueKey || "value";
  const data = rows;
  if (!data.length) {
    chart.setOption(emptyChartOption(), true);
    return;
  }
  chart.setOption({
    ...baseChartOption(data.length),
    grid: { top: 22, right: 28, bottom: 42, left: 52, containLabel: true },
    color: ["#5e6ad2"],
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: data.map((item) => item[labelKey]),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: "#e5e7eb" } },
      axisLabel: { color: "#6b7280", fontSize: 12 }
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      splitLine: { lineStyle: { color: "#edf0f3" } },
      axisLabel: { color: "#6b7280", fontSize: 12 }
    },
    series: [{
      type: "line",
      data: data.map((item) => Number(item[valueKey]) || 0),
      smooth: true,
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { width: 3 },
      areaStyle: { opacity: 0.1 },
      label: { show: data.length <= 14, position: "top", color: "#374151", fontSize: 11 }
    }]
  }, true);
}

function donutChart(node, rows, opts = {}) {
  const chart = getChart(node);
  if (!chart) return;
  const data = rows.filter((item) => Number(item.value) > 0);
  if (!data.length) {
    chart.setOption(emptyChartOption(opts.emptyText), true);
    return;
  }
  chart.setOption({
    ...baseChartOption(data.length),
    color: chartPalette,
    legend: {
      type: "scroll",
      bottom: 0,
      icon: "circle",
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: "#525866", fontSize: 12 }
    },
    series: [{
      type: "pie",
      radius: [opts.inner || "54%", "76%"],
      center: ["50%", "44%"],
      data,
      label: { color: "#525866", formatter: "{b}: {c}" },
      labelLine: { length: 10, length2: 8 },
      itemStyle: { borderColor: "#fff", borderWidth: 2 },
      emphasis: { scaleSize: 5 }
    }]
  }, true);
}

function getChart(node) {
  if (!node || !window.echarts) return null;
  if (!node.clientWidth || !node.clientHeight) return null;
  const id = node.id;
  if (!chartInstances[id]) {
    chartInstances[id] = echarts.init(node, null, { renderer: "canvas" });
  }
  chartInstances[id].resize();
  return chartInstances[id];
}

function baseChartOption(hasData) {
  return {
    title: { show: false },
    tooltip: {
      trigger: "item",
      backgroundColor: "#171717",
      borderColor: "#171717",
      textStyle: { color: "#fff", fontSize: 12 }
    },
    animationDuration: 260,
    animationEasing: "cubicOut"
  };
}

function emptyChartOption(text = "暂无数据") {
  return {
    title: {
      text,
      left: "center",
      top: "middle",
      textStyle: { color: "#8a9099", fontSize: 13, fontWeight: 500 }
    },
    tooltip: { show: false },
    xAxis: { show: false },
    yAxis: { show: false },
    series: []
  };
}

async function readJsonFile(file) {
  const text = await file.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error("文件不是合法 JSON。");
  }
}

async function api(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return readResponse(response);
}

async function readResponse(response) {
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败。");
  return data;
}

function currentUid() {
  return (state.account.uid || $("uidInput").value || "").trim();
}

function wishFeaturedItems() {
  return {
    character: cleanList(state.featuredItems.character),
    weapon: cleanList(state.featuredItems.weapon)
  };
}

function wishFeaturedItemsFromForm() {
  return {
    character: parseList($("featuredCharacterInput").value),
    weapon: parseList($("featuredWeaponInput").value)
  };
}

function recordsForReanalysis(records) {
  return records.map(({ fiftyFifty, ...item }) => item);
}

function parseList(text) {
  return String(text || "")
    .replaceAll("，", ",")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function cleanList(value) {
  return Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : [];
}

function listToText(value) {
  return cleanList(value).join("\n");
}

function ensureUid() {
  if (!currentUid()) {
    toast("请先填写并保存账号标识。");
    return false;
  }
  return true;
}

function touchUpdatedAt() {
  state.updatedAt = new Date().toLocaleString("zh-CN", { hour12: false });
}

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), "zh-CN"));
}

function fiftyLabel(value) {
  if (value === "win") return "胜";
  if (value === "lose") return "歪";
  return "未知";
}

function truncate(text, length) {
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

let toastTimer = 0;
function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("show"), 3200);
}

window.addEventListener("resize", () => requestAnimationFrame(renderCharts));
