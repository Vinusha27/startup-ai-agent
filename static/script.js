const LOADING_STEPS = [
    "Searching VC websites...",
    "Extracting investor data...",
    "Analyzing portfolios...",
    "Calculating AI scores..."
];

document.addEventListener("DOMContentLoaded", () => {
    initDiscoveryDashboard();
    initDeckAnalyzer();
});

function initDiscoveryDashboard() {
    const discoverForm = document.getElementById("discover-form");
    if (!discoverForm) {
        return;
    }

    const discoverButton = document.getElementById("discover-button");
    const loadingBox = document.getElementById("loading-box");
    const loadingMessages = document.getElementById("loading-messages");
    const errorBox = document.getElementById("error-box");
    const metaBox = document.getElementById("meta-box");
    const metaMode = document.getElementById("meta-mode");
    const metaGenerated = document.getElementById("meta-generated");
    const metaSources = document.getElementById("meta-sources");
    const resultsGrid = document.getElementById("results-grid");
    const resultsCount = document.getElementById("results-count");
    const jsonOutput = document.getElementById("json-output");
    const startupDescriptionInput = document.getElementById("startup-description");

    const competitorForm = document.getElementById("competitor-form");
    const competitorButton = document.getElementById("competitor-button");
    const competitorLoading = document.getElementById("competitor-loading");
    const competitorError = document.getElementById("competitor-error");
    const competitorResults = document.getElementById("competitor-results");

    const fundingForm = document.getElementById("funding-form");
    const fundingButton = document.getElementById("funding-button");
    const fundingLoading = document.getElementById("funding-loading");
    const fundingError = document.getElementById("funding-error");
    const fundingResults = document.getElementById("funding-results");

    const outreachModal = document.getElementById("outreach-modal");
    const closeModalButton = document.getElementById("close-modal-button");
    const outreachStatus = document.getElementById("outreach-status");
    const outreachSubject = document.getElementById("outreach-subject");
    const outreachReason = document.getElementById("outreach-reason");
    const outreachBody = document.getElementById("outreach-body");

    let loadingInterval = null;
    let latestStartupContext = {
        startup_domain: "",
        startup_description: "",
        stage: "",
        location: ""
    };

    discoverForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const payload = {
            domain: document.getElementById("domain").value.trim(),
            stage: document.getElementById("stage").value,
            location: document.getElementById("location").value.trim()
        };

        latestStartupContext = {
            startup_domain: payload.domain,
            startup_description: startupDescriptionInput.value.trim(),
            stage: payload.stage,
            location: payload.location
        };

        resetDiscoveryUI();
        startLoading();
        discoverButton.disabled = true;

        try {
            const response = await fetch("/discover", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            jsonOutput.textContent = JSON.stringify(data, null, 2);

            if (!response.ok) {
                throw new Error(data.error || "Unable to discover investors.");
            }

            renderMeta(data, metaBox, metaMode, metaGenerated, metaSources);
            renderInvestors(resultsGrid, resultsCount, data.investors || []);
        } catch (error) {
            renderError(errorBox, error.message);
            renderInvestors(resultsGrid, resultsCount, []);
            jsonOutput.textContent = JSON.stringify({ error: error.message }, null, 2);
        } finally {
            stopLoading();
            discoverButton.disabled = false;
        }
    });

    resultsGrid.addEventListener("click", async (event) => {
        const outreachButton = event.target.closest("[data-generate-outreach]");
        const saveButton = event.target.closest("[data-save-investor]");

        if (outreachButton) {
            await handleGenerateOutreach(outreachButton);
            return;
        }

        if (saveButton) {
            await handleSaveInvestor(saveButton);
        }
    });

    if (closeModalButton) {
        closeModalButton.addEventListener("click", closeOutreachModal);
    }

    if (outreachModal) {
        outreachModal.addEventListener("click", (event) => {
            if (event.target === outreachModal) {
                closeOutreachModal();
            }
        });
    }

    if (competitorForm) {
        competitorForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            competitorError.classList.add("hidden");
            competitorLoading.classList.remove("hidden");
            competitorButton.disabled = true;

            try {
                const response = await fetch("/competitors", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        domain: document.getElementById("competitor-domain").value.trim(),
                        startup_idea: document.getElementById("startup-idea").value.trim()
                    })
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Unable to analyze competitors.");
                }
                renderCompetitors(competitorResults, data);
            } catch (error) {
                renderError(competitorError, error.message);
            } finally {
                competitorLoading.classList.add("hidden");
                competitorButton.disabled = false;
            }
        });
    }

    if (fundingForm) {
        fundingForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            fundingError.classList.add("hidden");
            fundingLoading.classList.remove("hidden");
            fundingButton.disabled = true;

            try {
                const response = await fetch("/funding_probability", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        domain: document.getElementById("funding-domain").value.trim(),
                        stage: document.getElementById("funding-stage").value,
                        team_size: document.getElementById("team-size").value.trim(),
                        market: document.getElementById("market").value.trim(),
                        traction: document.getElementById("traction").value.trim()
                    })
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || "Unable to predict funding probability.");
                }
                renderFundingProbability(fundingResults, data);
            } catch (error) {
                renderError(fundingError, error.message);
            } finally {
                fundingLoading.classList.add("hidden");
                fundingButton.disabled = false;
            }
        });
    }

    function startLoading() {
        loadingBox.classList.remove("hidden");
        loadingMessages.innerHTML = "";

        let activeIndex = 0;
        renderLoadingSteps(loadingMessages, activeIndex);

        loadingInterval = window.setInterval(() => {
            activeIndex = (activeIndex + 1) % LOADING_STEPS.length;
            renderLoadingSteps(loadingMessages, activeIndex);
        }, 1100);
    }

    function stopLoading() {
        loadingBox.classList.add("hidden");
        if (loadingInterval) {
            window.clearInterval(loadingInterval);
            loadingInterval = null;
        }
    }

    async function handleGenerateOutreach(button) {
        const investorName = button.dataset.investorName || "";
        const firmName = button.dataset.firmName || "";

        outreachStatus.classList.add("hidden");
        outreachSubject.textContent = "Generating...";
        outreachReason.textContent = "Generating...";
        outreachBody.textContent = "Generating...";
        outreachModal.classList.remove("hidden");
        outreachModal.classList.add("flex");

        try {
            const response = await fetch("/generate_outreach", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    startup_domain: latestStartupContext.startup_domain,
                    startup_description: latestStartupContext.startup_description || "An early-stage startup with strong product momentum.",
                    investor_name: investorName,
                    firm_name: firmName
                })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Unable to generate outreach.");
            }

            outreachSubject.textContent = data.email_subject || "No subject generated.";
            outreachReason.textContent = data.reason_for_match || "No reason returned.";
            outreachBody.textContent = data.email_body || "No email body returned.";
            renderOutreachStatus(outreachStatus, data);
        } catch (error) {
            outreachStatus.textContent = error.message;
            outreachStatus.classList.remove("hidden");
            outreachSubject.textContent = "Generation failed";
            outreachReason.textContent = "The platform could not generate outreach right now.";
            outreachBody.textContent = error.message;
        }
    }

    async function handleSaveInvestor(button) {
        const investorName = button.dataset.investorName || "";
        const firmName = button.dataset.firmName || "";
        const profileUrl = button.dataset.profileUrl || "Unknown";

        try {
            const response = await fetch("/save_investor", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    investor_name: investorName,
                    firm_name: firmName,
                    profile_url: profileUrl
                })
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Unable to save investor.");
            }

            button.textContent = "Saved to CRM";
            button.disabled = true;
            button.classList.add("opacity-60", "cursor-not-allowed");
        } catch (error) {
            renderError(errorBox, error.message);
        }
    }

    function closeOutreachModal() {
        outreachModal.classList.add("hidden");
        outreachModal.classList.remove("flex");
    }

    function resetDiscoveryUI() {
        errorBox.classList.add("hidden");
        metaBox.classList.add("hidden");
    }
}

function initDeckAnalyzer() {
    const analyzeDeckForm = document.getElementById("analyze-deck-form");
    if (!analyzeDeckForm) {
        return;
    }

    const analyzeDeckButton = document.getElementById("analyze-deck-button");
    const deckLoading = document.getElementById("deck-loading");
    const deckError = document.getElementById("deck-error");
    const deckScore = document.getElementById("deck-score");
    const deckSummary = document.getElementById("deck-summary");
    const deckEvaluations = document.getElementById("deck-evaluations");
    const deckStrengths = document.getElementById("deck-strengths");
    const deckImprovements = document.getElementById("deck-improvements");

    analyzeDeckForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        deckError.classList.add("hidden");
        deckLoading.classList.remove("hidden");
        analyzeDeckButton.disabled = true;

        const formData = new FormData(analyzeDeckForm);

        try {
            const response = await fetch("/analyze_deck", {
                method: "POST",
                body: formData
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || "Unable to analyze the pitch deck.");
            }
            renderDeckAnalysis({
                deckScore,
                deckSummary,
                deckEvaluations,
                deckStrengths,
                deckImprovements
            }, data);
        } catch (error) {
            renderError(deckError, error.message);
        } finally {
            deckLoading.classList.add("hidden");
            analyzeDeckButton.disabled = false;
        }
    });
}

function renderLoadingSteps(container, activeIndex) {
    container.innerHTML = LOADING_STEPS.map((message, index) => `
        <div class="flex items-center gap-3 ${index === activeIndex ? "text-white" : "text-slate-400"}">
            <span class="h-2.5 w-2.5 rounded-full ${index === activeIndex ? "bg-emerald-300 shadow-[0_0_18px_rgba(0,255,156,0.8)]" : "bg-white/20"}"></span>
            <span>${escapeHtml(message)}</span>
        </div>
    `).join("");
}

function renderMeta(data, metaBox, metaMode, metaGenerated, metaSources) {
    metaMode.textContent = data.mode || "unknown";
    metaGenerated.textContent = data.generated_at || "n/a";
    metaSources.textContent = (data.sources || []).join(", ") || "n/a";
    metaBox.classList.remove("hidden");
}

function renderInvestors(resultsGrid, resultsCount, investors) {
    resultsCount.textContent = `${investors.length} investor${investors.length === 1 ? "" : "s"}`;

    if (!investors.length) {
        resultsGrid.innerHTML = `
            <div class="rounded-3xl border border-dashed border-white/10 bg-black/20 p-10 text-center text-sm text-slate-500">
                No investors matched this search yet.
            </div>
        `;
        return;
    }

    resultsGrid.innerHTML = investors.map((investor) => {
        const scorecard = investor.scorecard || {};
        const totalScore = Number(investor.total_match_score || investor.match_score || 0);
        const profileLink = investor.profile_url && investor.profile_url !== "Unknown"
            ? `<a href="${escapeAttribute(investor.profile_url)}" target="_blank" rel="noreferrer" class="secondary-button inline-flex !px-3 !py-2 !text-xs">View Profile</a>`
            : `<span class="text-xs text-slate-500">Profile unavailable</span>`;
        const warmIntroCards = (investor.warm_intro_suggestions || []).map((item) => `
            <div class="rounded-2xl border border-white/8 bg-black/20 p-3">
                <div class="text-sm font-semibold text-white">${escapeHtml(item.introducer_name || "Potential connector")}</div>
                <div class="mt-1 text-xs uppercase tracking-[0.2em] text-brand">${escapeHtml(item.role || "Warm intro path")}</div>
                <div class="mt-2 text-sm text-slate-300">${escapeHtml(item.connection_path || "")}</div>
                <div class="mt-2 text-xs leading-6 text-slate-400">${escapeHtml(item.rationale || "")}</div>
            </div>
        `).join("");

        const portfolioTags = (investor.portfolio_examples || []).map((company) => `
            <span class="rounded-full border border-white/8 bg-black/20 px-3 py-1 text-xs text-slate-300">${escapeHtml(company)}</span>
        `).join("");

        return `
            <article class="rounded-[28px] border border-white/6 bg-black/20 p-6">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <p class="text-xs uppercase tracking-[0.3em] text-brand">${escapeHtml(investor.firm_name || "Unknown firm")}</p>
                        <h4 class="mt-2 text-2xl font-semibold text-white">${escapeHtml(investor.investor_name || "Unknown investor")}</h4>
                        <p class="mt-3 text-sm leading-7 text-slate-400">${escapeHtml(investor.investment_focus || "Unknown focus")}</p>
                    </div>
                    <div class="rounded-3xl border border-white/8 bg-white/[0.03] px-4 py-3 text-right">
                        <div class="text-xs uppercase tracking-[0.2em] text-slate-500">Total Match</div>
                        <div class="mt-2 text-3xl font-bold text-white">${escapeHtml(String(totalScore))}%</div>
                    </div>
                </div>

                <div class="mt-5 flex flex-wrap items-center gap-3 text-sm text-slate-400">
                    <span class="rounded-full border border-white/8 bg-white/[0.03] px-3 py-1.5">${escapeHtml(investor.location || "Unknown location")}</span>
                    ${profileLink}
                </div>

                <div class="mt-5 rounded-3xl border border-white/8 bg-white/[0.03] p-4">
                    <div class="text-sm font-semibold text-white">Investor Bio Signal</div>
                    <p class="mt-3 text-sm leading-7 text-slate-300">${escapeHtml(investor.bio_text || "No bio text returned.")}</p>
                </div>

                <div class="mt-5 rounded-3xl border border-white/8 bg-white/[0.03] p-4">
                    <div class="flex items-center justify-between">
                        <h5 class="text-sm font-semibold text-white">AI Match Scorecard</h5>
                        <span class="text-xs uppercase tracking-[0.2em] text-slate-500">Investor Fit ${escapeHtml(String(totalScore))}%</span>
                    </div>
                    ${renderScoreBar("Domain Fit", Number(scorecard.domain_fit || 0))}
                    ${renderScoreBar("Stage Fit", Number(scorecard.stage_fit || 0))}
                    ${renderScoreBar("Geography Fit", Number(scorecard.geography_fit || 0))}
                    ${renderScoreBar("Portfolio Similarity", Number(scorecard.portfolio_similarity || 0))}
                </div>

                <div class="mt-5 rounded-3xl border border-white/8 bg-white/[0.03] p-4">
                    <div class="text-sm font-semibold text-white">Portfolio Analysis Agent</div>
                    <p class="mt-3 text-sm leading-7 text-slate-300">${escapeHtml(investor.portfolio_insight || "No portfolio insight available yet.")}</p>
                    <div class="mt-4 flex flex-wrap gap-2">${portfolioTags || `<span class="text-xs text-slate-500">No portfolio examples returned.</span>`}</div>
                </div>

                <div class="mt-5 rounded-3xl border border-white/8 bg-white/[0.03] p-4">
                    <div class="text-sm font-semibold text-white">Warm Intro Finder</div>
                    <div class="mt-4 grid gap-3">${warmIntroCards || `<div class="text-sm text-slate-500">No warm intro suggestions yet.</div>`}</div>
                </div>

                <div class="mt-5 flex flex-wrap gap-3">
                    <button
                        type="button"
                        class="primary-button"
                        data-generate-outreach="true"
                        data-investor-name="${escapeAttribute(investor.investor_name || "")}"
                        data-firm-name="${escapeAttribute(investor.firm_name || "")}"
                    >
                        Generate Outreach Email
                    </button>
                    <button
                        type="button"
                        class="secondary-button"
                        data-save-investor="true"
                        data-investor-name="${escapeAttribute(investor.investor_name || "")}"
                        data-firm-name="${escapeAttribute(investor.firm_name || "")}"
                        data-profile-url="${escapeAttribute(investor.profile_url || "Unknown")}"
                    >
                        Save Investor
                    </button>
                </div>
            </article>
        `;
    }).join("");
}

function renderCompetitors(container, data) {
    const competitors = data.competitors || [];
    if (!competitors.length) {
        container.innerHTML = `
            <div class="rounded-3xl border border-dashed border-white/10 bg-black/20 p-8 text-center text-sm text-slate-500">
                No competitor intelligence returned.
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="rounded-3xl border border-white/8 bg-black/20 p-5">
            <div class="text-xs uppercase tracking-[0.3em] text-brand">Market Summary</div>
            <div class="mt-3 text-sm leading-7 text-slate-300">${escapeHtml(data.market_summary || "No summary returned.")}</div>
        </div>
        ${competitors.map((competitor) => `
            <article class="rounded-3xl border border-white/8 bg-black/20 p-5">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <div class="text-xl font-semibold text-white">${escapeHtml(competitor.company_name || "Unknown company")}</div>
                        <div class="mt-2 text-sm text-slate-400">Raised ${escapeHtml(competitor.funding_raised || "Unknown")}</div>
                    </div>
                    <span class="rounded-full border border-white/8 bg-white/[0.03] px-3 py-1 text-xs text-slate-300">${escapeHtml(data.mode || "demo")}</span>
                </div>
                <div class="mt-4 text-sm text-slate-300"><span class="font-semibold text-white">Investors:</span> ${escapeHtml(competitor.investors || "Unknown")}</div>
                <div class="mt-3 text-sm leading-7 text-slate-400">${escapeHtml(competitor.differentiation_note || "")}</div>
            </article>
        `).join("")}
    `;
}

function renderFundingProbability(container, data) {
    const factors = data.factors || [];
    container.innerHTML = `
        <article class="rounded-3xl border border-white/8 bg-black/20 p-5">
            <div class="flex items-start justify-between gap-4">
                <div>
                    <div class="text-xs uppercase tracking-[0.3em] text-brand">Funding Probability</div>
                    <div class="mt-3 text-5xl font-bold text-white">${escapeHtml(String(data.funding_probability || 0))}%</div>
                </div>
                <span class="rounded-full border border-white/8 bg-white/[0.03] px-3 py-1 text-xs text-slate-300">${escapeHtml(data.mode || "demo")}</span>
            </div>
            <p class="mt-4 text-sm leading-7 text-slate-300">${escapeHtml(data.summary || "No summary returned.")}</p>
            <div class="mt-6 space-y-4">
                ${factors.map((factor) => `
                    <div>
                        <div class="mb-2 flex items-center justify-between text-xs uppercase tracking-[0.2em] text-slate-400">
                            <span>${escapeHtml(factor.label || "Factor")}</span>
                            <span>${escapeHtml(String(factor.score || 0))}%</span>
                        </div>
                        <div class="score-track">
                            <div class="score-fill" style="width: ${Math.max(0, Math.min(100, Number(factor.score || 0)))}%"></div>
                        </div>
                        <div class="mt-2 text-sm text-slate-500">${escapeHtml(factor.detail || "")}</div>
                    </div>
                `).join("")}
            </div>
        </article>
    `;
}

function renderDeckAnalysis(elements, data) {
    elements.deckScore.textContent = `${data.pitch_score || 0}/100`;
    elements.deckSummary.textContent = data.summary || "No summary returned.";

    const evaluations = data.evaluations || {};
    elements.deckEvaluations.innerHTML = `
        <div class="text-sm font-semibold text-white">Evaluation Breakdown</div>
        <div class="mt-4 space-y-4">
            ${renderScoreBar("Problem Clarity", Number(evaluations.problem_clarity || 0))}
            ${renderScoreBar("Market Size", Number(evaluations.market_size || 0))}
            ${renderScoreBar("Traction", Number(evaluations.traction || 0))}
            ${renderScoreBar("Team Strength", Number(evaluations.team_strength || 0))}
            ${renderScoreBar("Investment Readiness", Number(evaluations.investment_readiness || 0))}
        </div>
    `;

    elements.deckStrengths.innerHTML = (data.strengths || []).map((item) => `
        <li class="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">${escapeHtml(item)}</li>
    `).join("") || `<li class="text-slate-500">No strengths returned.</li>`;

    elements.deckImprovements.innerHTML = (data.improvements || []).map((item) => `
        <li class="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">${escapeHtml(item)}</li>
    `).join("") || `<li class="text-slate-500">No suggestions returned.</li>`;
}

function renderOutreachStatus(container, data) {
    const message = `Outreach mode: ${data.mode || "unknown"}.`;
    container.textContent = message;
    container.classList.remove("hidden");
}

function renderScoreBar(label, value) {
    const safeValue = Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 0;
    return `
        <div class="mt-4">
            <div class="mb-2 flex items-center justify-between text-xs uppercase tracking-[0.2em] text-slate-400">
                <span>${escapeHtml(label)}</span>
                <span>${safeValue}%</span>
            </div>
            <div class="score-track">
                <div class="score-fill" style="width: ${safeValue}%"></div>
            </div>
        </div>
    `;
}

function renderError(element, message) {
    element.textContent = message;
    element.classList.remove("hidden");
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
    return escapeHtml(value);
}
