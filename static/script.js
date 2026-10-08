/**
 * AI Interview Coach — Frontend Application Logic
 * Implements authentication, step-based interview setup, dynamic follow-ups,
 * webcam/microphone recording, objective communication analysis, evidence-based video analysis,
 * resume skill gap analysis, and persistent MySQL history.
 */

'use strict';

// ============================================================================
// 1. APPLICATION STATE
// ============================================================================

const state = {
    user: null,             // { id, name, email }
    token: localStorage.getItem('auth_token') || null,

    // Active Interview Session
    session: null,          // { session_id, mode, technical_subject, role, difficulty, total_questions, current_question_index }
    activeQuestion: null,   // { id, order, text, type, traceability }
    sessionTimerSeconds: 0,
    sessionTimerInterval: null,

    // Active Recording
    recording: {
        stream: null,
        mediaRecorder: null,
        chunks: [],
        seconds: 0,
        interval: null,
        isRecording: false,
    },

    // File Upload State
    selectedFile: null,

    // Attached Resume Context
    resume: {
        id: null,
        filename: null,
        parsed: null,
        insights: null,
    },

    // Current Session Result / Inspection
    latestResult: null,
    historyList: [],
    currentSetupStep: 1,
};

// ============================================================================
// 2. DOM UTILITIES & NAVIGATION
// ============================================================================

function el(id) {
    return document.getElementById(id);
}

function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function showView(viewId) {
    const views = ['viewDashboard', 'viewSetup', 'viewInterview', 'viewProcessing', 'viewResults', 'viewResume', 'viewHistory'];
    views.forEach(id => {
        const node = el(id);
        if (node) {
            node.classList.remove('active-view');
            node.style.display = 'none';
        }
    });

    const activeNode = el(viewId);
    if (activeNode) {
        activeNode.classList.add('active-view');
        activeNode.style.display = 'block';
    }

    // Update nav links active state
    const navMap = {
        'viewDashboard': 'navDashboardBtn',
        'viewSetup': 'navSetupBtn',
        'viewResume': 'navResumeBtn',
        'viewHistory': 'navHistoryBtn',
    };
    document.querySelectorAll('.nav-link').forEach(btn => btn.classList.remove('active'));
    if (navMap[viewId] && el(navMap[viewId])) {
        el(navMap[viewId]).classList.add('active');
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function getAuthHeaders() {
    const headers = {};
    if (state.token) {
        headers['Authorization'] = `Bearer ${state.token}`;
    }
    return headers;
}

// ============================================================================
// 3. AUTHENTICATION & USER PROFILE
// ============================================================================

async function checkAuthStatus() {
    if (!state.token) {
        renderUnauthState();
        return;
    }

    try {
        const res = await fetch('/api/auth/me', {
            headers: getAuthHeaders(),
        });
        if (res.ok) {
            const data = await res.json();
            state.user = data.user;
            renderAuthState();
            loadDashboardData();
            loadLatestResumeInsights();
        } else {
            // Token expired or invalid
            state.user = null;
            state.token = null;
            localStorage.removeItem('auth_token');
            renderUnauthState();
        }
    } catch (err) {
        console.warn('Auth verification check failed:', err);
        renderUnauthState();
    }
}

function renderAuthState() {
    const authArea = el('authArea');
    const unauthArea = el('unauthArea');
    if (authArea) authArea.style.display = 'flex';
    if (unauthArea) unauthArea.style.display = 'none';

    if (state.user) {
        const name = state.user.name || 'Candidate';
        if (el('navUserName')) el('navUserName').textContent = name;
        if (el('navUserInitial')) el('navUserInitial').textContent = name.charAt(0).toUpperCase();
        if (el('dashboardGreeting')) el('dashboardGreeting').textContent = `Welcome back, ${name}`;
    }
}

function renderUnauthState() {
    const authArea = el('authArea');
    const unauthArea = el('unauthArea');
    if (authArea) authArea.style.display = 'none';
    if (unauthArea) unauthArea.style.display = 'flex';
    if (el('dashboardGreeting')) el('dashboardGreeting').textContent = 'Welcome back, Candidate';
}

function showAuthModal(tab = 'login') {
    const modal = el('authModal');
    if (!modal) return;
    modal.style.display = 'flex';
    switchAuthTab(tab);
    clearAuthError();
}

function closeAuthModal() {
    const modal = el('authModal');
    if (modal) modal.style.display = 'none';
    clearAuthError();
}

function switchAuthTab(tab) {
    const tabLogin = el('authTabLogin');
    const tabRegister = el('authTabRegister');
    const formLogin = el('loginForm');
    const formRegister = el('registerForm');

    clearAuthError();

    if (tab === 'login') {
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
        formLogin.style.display = 'flex';
        formRegister.style.display = 'none';
    } else {
        tabRegister.classList.add('active');
        tabLogin.classList.remove('active');
        formRegister.style.display = 'flex';
        formLogin.style.display = 'none';
    }
}

function showAuthError(msg) {
    const banner = el('authErrorBanner');
    if (banner) {
        banner.textContent = msg;
        banner.style.display = 'block';
    }
}

function clearAuthError() {
    const banner = el('authErrorBanner');
    if (banner) {
        banner.textContent = '';
        banner.style.display = 'none';
    }
}

async function handleLogin(e) {
    e.preventDefault();
    clearAuthError();
    const email = el('loginEmail').value.trim();
    const password = el('loginPassword').value;

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (res.ok && data.token) {
            state.token = data.token;
            state.user = data.user;
            localStorage.setItem('auth_token', data.token);
            renderAuthState();
            closeAuthModal();
            loadDashboardData();
            loadLatestResumeInsights();
        } else {
            showAuthError(data.error || 'Login failed. Please check your credentials.');
        }
    } catch (err) {
        showAuthError('Connection error. Please try again.');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    clearAuthError();
    const name = el('regName').value.trim();
    const email = el('regEmail').value.trim();
    const password = el('regPassword').value;
    const confirm_password = el('regConfirmPassword').value;

    if (password !== confirm_password) {
        showAuthError('Passwords do not match.');
        return;
    }

    try {
        const res = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password, confirm_password }),
        });
        const data = await res.json();
        if (res.ok && data.token) {
            state.token = data.token;
            state.user = data.user;
            localStorage.setItem('auth_token', data.token);
            renderAuthState();
            closeAuthModal();
            loadDashboardData();
            loadLatestResumeInsights();
        } else {
            showAuthError(data.error || 'Registration failed. Please try again.');
        }
    } catch (err) {
        showAuthError('Connection error. Please try again.');
    }
}

async function handleLogout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST', headers: getAuthHeaders() });
    } catch (err) {}
    state.user = null;
    state.token = null;
    state.session = null;
    localStorage.removeItem('auth_token');
    renderUnauthState();
    showView('viewDashboard');
}

// ============================================================================
// 4. DASHBOARD DATA & HISTORY LOADING
// ============================================================================

async function loadDashboardData() {
    if (!state.token) {
        renderEmptyDashboard();
        return;
    }

    try {
        const res = await fetch('/api/interview/history', { headers: getAuthHeaders() });
        if (!res.ok) return;

        const data = await res.json();
        const history = data.history || [];
        state.historyList = history;

        renderDashboardStats(history);
        renderRecentTable(history.slice(0, 5));
        renderFullHistoryTable(history);
    } catch (err) {
        console.warn('Failed to load interview history:', err);
    }
}

function renderEmptyDashboard() {
    if (el('dashReadinessScore')) el('dashReadinessScore').textContent = '--';
    if (el('dashReadinessLevel')) el('dashReadinessLevel').textContent = 'Sign In to Track';
    if (el('dashTotalSessions')) el('dashTotalSessions').textContent = '0';
    if (el('dashAvgScore')) el('dashAvgScore').textContent = '--';
    if (el('dashAvgWpm')) el('dashAvgWpm').textContent = '-- WPM';
    if (el('dashRecentTbody')) {
        el('dashRecentTbody').innerHTML = `
            <tr><td colspan="8" class="empty-state">Sign in or register to record persistent interviews and calculate readiness scores.</td></tr>
        `;
    }
}

function renderDashboardStats(history) {
    const totalSessions = history.length;
    const completedSessions = history.filter(s => s.status === 'completed' && s.overall_score != null);

    if (el('dashTotalSessions')) el('dashTotalSessions').textContent = totalSessions;

    if (completedSessions.length > 0) {
        const latest = completedSessions[0];
        const avgScore = Math.round(
            completedSessions.reduce((acc, s) => acc + (s.overall_score || 0), 0) / completedSessions.length
        );

        if (el('dashReadinessScore')) el('dashReadinessScore').textContent = latest.readiness_score != null ? latest.readiness_score : '--';
        if (el('dashReadinessLevel')) el('dashReadinessLevel').textContent = latest.readiness_level || 'Developing';
        if (el('dashReadinessCaption')) {
            const roleStr = latest.role && latest.role !== 'None' ? `for ${latest.role}` : 'interview practice';
            el('dashReadinessCaption').textContent = `Computed from ${latest.total_questions} questions ${roleStr}.`;
        }
        if (el('dashAvgScore')) el('dashAvgScore').textContent = `${avgScore} / 100`;
        if (el('dashTargetRole')) el('dashTargetRole').textContent = latest.role && latest.role !== 'None' ? latest.role : 'Optional (None)';
    } else {
        if (el('dashReadinessScore')) el('dashReadinessScore').textContent = '--';
        if (el('dashReadinessLevel')) el('dashReadinessLevel').textContent = 'Developing';
        if (el('dashAvgScore')) el('dashAvgScore').textContent = '--';
    }
}

function renderRecentTable(sessions) {
    const tbody = el('dashRecentTbody');
    if (!tbody) return;

    if (!sessions || sessions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="empty-state">No interview sessions found. Click "Start Interview" above to begin.</td></tr>`;
        return;
    }

    tbody.innerHTML = sessions.map(s => {
        const domainOrRole = (s.technical_subject && s.technical_subject !== 'None') 
            ? s.technical_subject 
            : (s.role && s.role !== 'None' ? s.role : 'General');
        return `
            <tr>
                <td><strong>${s.date}</strong> <span class="text-secondary" style="font-size: 0.75rem;">${s.time}</span></td>
                <td><span class="badge badge-primary">${s.mode}</span></td>
                <td>${domainOrRole}</td>
                <td>${s.total_questions} Questions</td>
                <td><strong>${s.overall_score !== null ? s.overall_score + '/100' : 'In Progress'}</strong></td>
                <td><span class="badge badge-secondary">${s.readiness_level || 'Pending'}</span></td>
                <td><span class="badge ${s.status === 'completed' ? 'badge-primary' : 'badge-outline'}">${s.status}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline" onclick="openSessionDetailModal(${s.id})">
                        View Results
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function renderFullHistoryTable(sessions) {
    const tbody = el('historyTableBody');
    if (!tbody) return;

    if (!sessions || sessions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="empty-state">No interview sessions found. Start a practice interview to see your progress here!</td></tr>`;
        return;
    }

    tbody.innerHTML = sessions.map(s => `
        <tr>
            <td>#${s.id}</td>
            <td><strong>${s.date}</strong> <span class="text-secondary" style="font-size: 0.75rem;">${s.time}</span></td>
            <td><span class="badge badge-primary">${s.mode}</span></td>
            <td>${s.technical_subject || 'None'}</td>
            <td>${s.role || 'None'}</td>
            <td>${s.total_questions}</td>
            <td><strong>${s.overall_score !== null ? s.overall_score + '/100' : '--'}</strong></td>
            <td><span class="badge badge-secondary">${s.readiness_score ? s.readiness_score + '/100 (' + s.readiness_level + ')' : '--'}</span></td>
            <td><span class="badge ${s.status === 'completed' ? 'badge-primary' : 'badge-outline'}">${s.status}</span></td>
            <td>
                <div style="display: flex; gap: 4px;">
                    <button class="btn btn-sm btn-outline" onclick="openSessionDetailModal(${s.id})">View</button>
                    <a href="/api/interview/pdf/${s.id}" class="btn btn-sm btn-secondary" target="_blank" download>PDF</a>
                </div>
            </td>
        </tr>
    `).join('');
}

// ============================================================================
// 5. RESUME ATTACHMENT & INSIGHTS
// ============================================================================

async function loadLatestResumeInsights(targetRole = null) {
    if (!state.token) return;
    try {
        const url = targetRole ? `/api/resume/latest?target_role=${encodeURIComponent(targetRole)}` : '/api/resume/latest';
        const res = await fetch(url, { headers: getAuthHeaders() });
        if (!res.ok) return;

        const data = await res.json();
        if (data.status === 'success' && data.resume) {
            state.resume.id = data.resume.id;
            state.resume.filename = data.resume.filename;
            state.resume.parsed = data.resume;
            state.resume.insights = data.resume.insights;

            renderResumeInsights(data.resume);
        }
    } catch (err) {
        console.warn('Could not load resume insights:', err);
    }
}

function renderResumeInsights(resume) {
    const insights = resume.insights || {};
    const skills = resume.skills || [];
    const structuredSkills = resume.structured_skills || {};
    const strengths = insights.resume_strengths || [];
    const gaps = insights.skill_gaps || [];
    const recommendations = insights.recommended_improvements || [];
    const candidateName = resume.candidate_name || state.user?.name || 'Candidate';
    const education = resume.education || [];
    const projects = resume.projects || [];
    const internships = resume.internships || [];
    const experience = resume.experience || [];
    const certifications = resume.certifications || [];
    const achievements = resume.achievements || [];

    // Dashboard Cards
    if (el('dashResumeSub')) {
        el('dashResumeSub').textContent = `Uploaded: ${resume.filename} • Analyzed for ${candidateName}`;
    }
    const dashTags = el('dashResumeSkillsTags');
    if (dashTags) {
        dashTags.innerHTML = skills.length > 0 
            ? skills.slice(0, 12).map(s => `<span class="tag-pill">${esc(s)}</span>`).join('')
            : '<span class="tag-empty">No skills detected.</span>';
    }
    const dashStrengths = el('dashResumeStrengths');
    if (dashStrengths) {
        dashStrengths.innerHTML = strengths.length > 0
            ? strengths.slice(0, 3).map(st => `<li>${esc(st)}</li>`).join('')
            : '<li>Demonstrated project foundation.</li>';
    }
    const dashGaps = el('dashResumeGaps');
    if (dashGaps) {
        dashGaps.innerHTML = gaps.length > 0
            ? gaps.slice(0, 3).map(g => `<li><strong>${esc(g.skill)}:</strong> ${esc(g.status || 'Not detected in the uploaded resume.')} (${esc(g.importance || 'Medium')})</li>`).join('')
            : '<li class="text-secondary">No significant gaps detected for current target role.</li>';
    }

    // Setup Wizard Resume Info
    if (el('resumeLoadedName')) el('resumeLoadedName').textContent = resume.filename;
    if (el('resumeCandidateDetected')) {
        if (resume.candidate_name) {
            el('resumeCandidateDetected').textContent = `Candidate: ${resume.candidate_name}`;
            el('resumeCandidateDetected').style.display = 'inline-block';
        }
    }
    if (el('resumeSummaryText')) {
        el('resumeSummaryText').textContent = `Extracted ${skills.length} skills, ${projects.length} projects, and ${internships.length || experience.length} internships from ${resume.filename}`;
    }
    const wizardTags = el('resumeSkillsTags');
    if (wizardTags) {
        wizardTags.innerHTML = skills.slice(0, 10).map(s => `<span class="tag-pill">${esc(s)}</span>`).join('');
    }
    if (el('resumeDropZone')) el('resumeDropZone').style.display = 'none';
    if (el('resumeLoadedInfo')) el('resumeLoadedInfo').style.display = 'block';

    // Detailed Resume View (viewResume)
    if (el('resViewCandidateName')) el('resViewCandidateName').textContent = candidateName;
    if (el('resViewFileName')) el('resViewFileName').textContent = resume.filename;

    // Contact Information
    const contactBar = el('resContactInfo');
    if (contactBar) {
        const contactChips = [];
        if (resume.candidate?.email || resume.email) contactChips.push(`📧 ${esc(resume.candidate?.email || resume.email)}`);
        if (resume.candidate?.phone || resume.phone) contactChips.push(`📱 ${esc(resume.candidate?.phone || resume.phone)}`);
        if (resume.candidate?.location || resume.location) contactChips.push(`📍 ${esc(resume.candidate?.location || resume.location)}`);
        if (contactChips.length > 0) {
            contactBar.innerHTML = contactChips.map(c => `<span class="resume-contact-chip">${c}</span>`).join('');
            contactBar.style.display = 'flex';
        } else {
            contactBar.style.display = 'none';
        }
    }

    // Education Section
    const eduContainer = el('resEducationContainer');
    if (eduContainer) {
        if (education.length > 0) {
            eduContainer.innerHTML = education.map(ed => {
                const title = typeof ed === 'string' ? ed : (ed.degree ? `${ed.degree}${ed.branch ? ' in ' + ed.branch : ''}` : (ed.institution || 'Education'));
                const inst = typeof ed === 'object' ? (ed.institution || '') : '';
                const duration = typeof ed === 'object' ? (ed.duration || '') : '';
                const score = typeof ed === 'object' ? (ed.score || '') : '';
                return `
                    <div class="resume-item-card">
                        <div class="resume-item-header">
                            <h5 class="resume-item-title">${esc(title)}</h5>
                            ${score ? `<span class="resume-item-badge">${esc(score)}</span>` : ''}
                        </div>
                        ${inst || duration ? `<div class="resume-item-sub"><strong>${esc(inst)}</strong> ${duration ? `• ${esc(duration)}` : ''}</div>` : ''}
                    </div>
                `;
            }).join('');
        } else {
            eduContainer.innerHTML = '<div class="text-secondary italic-empty">No education details detected in the uploaded resume.</div>';
        }
    }

    // Categorized Skills (9 canonical categories)
    const skillsContainer = el('resCategorizedSkillsContainer');
    if (skillsContainer) {
        const categoryMap = [
            { key: 'languages', label: 'Programming Languages' },
            { key: 'core_cs', label: 'Core Computer Science' },
            { key: 'frameworks', label: 'Frameworks & Libraries' },
            { key: 'databases', label: 'Databases' },
            { key: 'web', label: 'Web Technologies' },
            { key: 'cloud_devops', label: 'Cloud / DevOps' },
            { key: 'tools', label: 'Development Tools' },
            { key: 'design', label: 'Design Tools' },
            { key: 'other', label: 'Other Technical Skills' },
        ];

        let hasAnyCat = false;
        let catsHtml = '';

        categoryMap.forEach(cat => {
            const catItems = structuredSkills[cat.key] || [];
            if (Array.isArray(catItems) && catItems.length > 0) {
                hasAnyCat = true;
                catsHtml += `
                    <div class="cat-group">
                        <span class="cat-label">${cat.label}:</span>
                        <div class="tag-cloud">
                            ${catItems.map(s => `<span class="tag-pill">${esc(s)}</span>`).join('')}
                        </div>
                    </div>
                `;
            }
        });

        // Fallback if structured_skills was empty but flat skills exist
        if (!hasAnyCat && skills.length > 0) {
            hasAnyCat = true;
            catsHtml = `
                <div class="cat-group">
                    <span class="cat-label">Extracted Skills:</span>
                    <div class="tag-cloud">
                        ${skills.map(s => `<span class="tag-pill">${esc(s)}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        skillsContainer.innerHTML = hasAnyCat ? catsHtml : '<div class="text-secondary italic-empty">No skills detected in the uploaded resume.</div>';
    }

    // Projects Section
    const projsContainer = el('resProjectsContainer');
    if (projsContainer) {
        if (projects.length > 0) {
            projsContainer.innerHTML = projects.map(p => {
                const title = typeof p === 'string' ? p : (p.title || 'Project');
                const techs = (typeof p === 'object' && Array.isArray(p.technologies)) ? p.technologies : [];
                const desc = typeof p === 'object' ? (p.description || '') : '';
                const resp = (typeof p === 'object' && Array.isArray(p.responsibilities)) ? p.responsibilities : [];
                return `
                    <div class="resume-item-card">
                        <div class="resume-item-header">
                            <h5 class="resume-item-title">${esc(title)}</h5>
                            ${techs.length > 0 ? `<div>${techs.map(t => `<span class="resume-item-badge">${esc(t)}</span>`).join(' ')}</div>` : ''}
                        </div>
                        ${desc ? `<p class="resume-item-desc">${esc(desc)}</p>` : ''}
                        ${resp.length > 0 ? `
                            <ul class="resume-item-bullets">
                                ${resp.map(r => `<li>${esc(r)}</li>`).join('')}
                            </ul>
                        ` : ''}
                    </div>
                `;
            }).join('');
        } else {
            projsContainer.innerHTML = '<div class="text-secondary italic-empty">No projects detected in the uploaded resume.</div>';
        }
    }

    // Internships & Work Experience Section
    const expContainer = el('resExperienceContainer');
    if (expContainer) {
        const allExp = internships.length > 0 ? internships : experience;
        if (allExp.length > 0) {
            expContainer.innerHTML = allExp.map(e => {
                const role = typeof e === 'string' ? e : (e.role || 'Role');
                const company = typeof e === 'object' ? (e.company || '') : '';
                const duration = typeof e === 'object' ? (e.duration || '') : '';
                const techs = (typeof e === 'object' && Array.isArray(e.technologies)) ? e.technologies : [];
                const resp = (typeof e === 'object' && Array.isArray(e.responsibilities)) ? e.responsibilities : [];
                return `
                    <div class="resume-item-card">
                        <div class="resume-item-header">
                            <h5 class="resume-item-title">${esc(role)} ${company ? '— ' + esc(company) : ''}</h5>
                            ${duration ? `<span class="resume-item-badge">${esc(duration)}</span>` : ''}
                        </div>
                        ${techs.length > 0 ? `<div style="margin: 0.25rem 0;">${techs.map(t => `<span class="resume-item-badge">${esc(t)}</span>`).join(' ')}</div>` : ''}
                        ${resp.length > 0 ? `
                            <ul class="resume-item-bullets">
                                ${resp.map(r => `<li>${esc(r)}</li>`).join('')}
                            </ul>
                        ` : ''}
                    </div>
                `;
            }).join('');
        } else {
            expContainer.innerHTML = '<div class="text-secondary italic-empty">No internship experience detected in the uploaded resume.</div>';
        }
    }

    // Certifications Section
    const certsContainer = el('resCertificationsContainer');
    if (certsContainer) {
        if (certifications.length > 0) {
            certsContainer.innerHTML = `
                <ul class="resume-item-bullets" style="margin-left: 1rem;">
                    ${certifications.map(c => `<li><strong>${esc(c)}</strong></li>`).join('')}
                </ul>
            `;
        } else {
            certsContainer.innerHTML = '<div class="text-secondary italic-empty">No certifications detected in the uploaded resume.</div>';
        }
    }

    // Achievements Section
    const achContainer = el('resAchievementsContainer');
    if (achContainer) {
        if (achievements.length > 0) {
            achContainer.innerHTML = `
                <ul class="resume-item-bullets" style="margin-left: 1rem;">
                    ${achievements.map(a => `<li>${esc(a)}</li>`).join('')}
                </ul>
            `;
        } else {
            achContainer.innerHTML = '<div class="text-secondary italic-empty">No achievements detected in the uploaded resume.</div>';
        }
    }

    // Role-Aware Skill Gaps
    if (el('resGapsList')) {
        el('resGapsList').innerHTML = gaps.length > 0
            ? gaps.map(g => `
                <div class="gap-card">
                    <span class="gap-skill-name">${esc(g.skill)}</span>
                    <span class="gap-status-text">${esc(g.status || 'Not detected in the uploaded resume.')} (${esc(g.importance || 'Medium')})</span>
                </div>
            `).join('')
            : '<p class="text-secondary">No significant gaps detected for this role.</p>';
    }

    // Resume Strengths
    if (el('resStrengthsList')) {
        el('resStrengthsList').innerHTML = strengths.length > 0
            ? strengths.map(st => `<li>${esc(st)}</li>`).join('')
            : '<li class="text-secondary">Demonstrated project foundation.</li>';
    }

    // Recommended Improvements
    if (el('resImprovementsList')) {
        el('resImprovementsList').innerHTML = recommendations.length > 0
            ? recommendations.map(r => `<li>${esc(r)}</li>`).join('')
            : '<li class="text-secondary">Continue practicing hands-on problem solving.</li>';
    }
}

function setupResumeUpload() {
    const dropZone = el('resumeDropZone');
    const fileInput = el('resumeFileInput');
    const removeBtn = el('removeResumeBtn');

    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--primary)';
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'var(--border-color)';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border-color)';
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            uploadResumeFile(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files[0]) {
            uploadResumeFile(fileInput.files[0]);
        }
    });

    if (removeBtn) {
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            state.resume = { id: null, filename: null, parsed: null, insights: null };
            fileInput.value = '';
            el('resumeLoadedInfo').style.display = 'none';
            el('resumeDropZone').style.display = 'block';
            updateWizardSummary();
        });
    }
}

async function uploadResumeFile(file) {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (ext !== '.pdf' && ext !== '.docx') {
        alert('Unsupported file format. Please upload a .pdf or .docx resume.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const promptEl = el('resumeDropPrompt');
    if (promptEl) promptEl.textContent = 'Uploading and analyzing resume...';

    try {
        const res = await fetch('/upload-resume', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: formData,
        });
        const data = await res.json();

        if (res.ok) {
            state.resume.id = data.resume_id || null;
            state.resume.filename = data.filename;
            state.resume.parsed = data.parsed;
            state.resume.insights = data.insights;

            const resumePayload = {
                id: data.resume_id,
                filename: data.filename,
                candidate_name: data.parsed?.candidate_name || state.user?.name,
                candidate: data.parsed?.candidate || {},
                skills: data.parsed?.skills || [],
                structured_skills: data.parsed?.structured_skills || {},
                projects: data.parsed?.projects || [],
                internships: data.parsed?.internships || [],
                experience: data.parsed?.experience || [],
                certifications: data.parsed?.certifications || [],
                achievements: data.parsed?.achievements || [],
                education: data.parsed?.education || [],
                insights: data.insights,
            };
            renderResumeInsights(resumePayload);
            updateWizardSummary();
        } else {
            alert(data.error || 'Failed to parse resume.');
            if (promptEl) promptEl.textContent = 'Click or Drag & Drop your Resume (.PDF or .DOCX)';
        }
    } catch (err) {
        alert('Failed to upload resume. Please try again.');
        if (promptEl) promptEl.textContent = 'Click or Drag & Drop your Resume (.PDF or .DOCX)';
    }
}

// ============================================================================
// 6. STEP-BASED WIZARD NAVIGATION
// ============================================================================

function goToWizardStep(step) {
    state.currentSetupStep = Math.max(1, Math.min(5, step));

    for (let i = 1; i <= 5; i++) {
        const stepView = el(`wizardStep${i}`);
        const indicator = el(`stepInd${i}`);
        if (stepView) {
            stepView.style.display = i === state.currentSetupStep ? 'block' : 'none';
        }
        if (indicator) {
            indicator.classList.toggle('active', i === state.currentSetupStep);
            indicator.classList.toggle('completed', i < state.currentSetupStep);
        }
    }

    const selectedMode = el('setupModeSelect')?.value || 'Technical';

    // Step 2 adjustments
    if (state.currentSetupStep === 2) {
        const subjGroup = el('setupSubjectGroup');
        if (subjGroup) {
            subjGroup.style.display = (selectedMode === 'Technical' || selectedMode === 'Mixed') ? 'block' : 'none';
        }
    }

    // Step 4 adjustments
    if (state.currentSetupStep === 4) {
        const notice = el('resumeStepNotice');
        if (notice) {
            notice.textContent = selectedMode === 'Resume-Based'
                ? 'Required for Resume-Based interviews. Please upload your PDF or DOCX resume.'
                : 'Optional for other interview modes. You may proceed without attaching a resume.';
        }
    }

    // Step 5 summary update
    if (state.currentSetupStep === 5) {
        updateWizardSummary();
    }

    window.scrollTo({ top: 120, behavior: 'smooth' });
}

function updateWizardSummary() {
    const mode = el('setupModeSelect')?.value || 'Technical';
    const subj = el('setupSubjectSelect')?.value || 'General';
    const role = el('setupRoleSelect')?.value || 'None';
    const count = el('setupQuestionsCountSelect')?.value || '5';
    const hasResume = !!state.resume.filename;

    if (el('summaryMode')) el('summaryMode').textContent = mode;
    const subjRow = el('summarySubjectRow');
    if (subjRow) {
        subjRow.style.display = (mode === 'Technical' || mode === 'Mixed') ? 'flex' : 'none';
        if (el('summarySubject')) el('summarySubject').textContent = subj;
    }
    if (el('summaryRole')) el('summaryRole').textContent = role === 'None' ? 'None (No Role Constraints)' : role;
    if (el('summaryQuestions')) {
        el('summaryQuestions').textContent = count === '1' ? '1 Question (Single Practice)' : `${count} Questions`;
    }
    if (el('summaryDifficulty')) el('summaryDifficulty').textContent = el('setupDifficultySelect')?.value || 'Medium';
    if (el('summaryResume')) {
        el('summaryResume').textContent = hasResume 
            ? `Attached (${state.resume.filename})` 
            : (mode === 'Resume-Based' ? 'Required (Please upload in Step 4)' : 'Not Attached (Optional)');
    }
}

// ============================================================================
// 7. STARTING AN INTERVIEW SESSION
// ============================================================================

async function startInterviewSession() {
    if (!state.token) {
        showAuthModal('login');
        return;
    }

    const mode = el('setupModeSelect').value;
    const technical_subject = (mode === 'Technical' || mode === 'Mixed') ? el('setupSubjectSelect').value : null;
    const role = el('setupRoleSelect').value === 'None' ? null : el('setupRoleSelect').value;
    const difficulty = el('setupDifficultySelect').value;
    const total_questions = parseInt(el('setupQuestionsCountSelect').value, 10) || 5;

    if (mode === 'Resume-Based' && !state.resume.filename) {
        alert('Resume upload is required for Resume-Based interview mode. Please upload your resume in Step 4.');
        goToWizardStep(4);
        return;
    }

    const startBtn = el('startSessionBtn');
    startBtn.disabled = true;
    startBtn.textContent = 'Initializing Session...';

    try {
        const res = await fetch('/api/interview/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...getAuthHeaders(),
            },
            body: JSON.stringify({
                mode,
                technical_subject,
                role,
                difficulty,
                total_questions,
                resume_id: state.resume.id,
            }),
        });

        const data = await res.json();
        if (res.ok && data.session) {
            state.session = data.session;
            state.activeQuestion = data.session.question;

            setupInterviewView();
            showView('viewInterview');
        } else {
            alert(data.error || 'Could not start interview session.');
        }
    } catch (err) {
        alert('Error starting session. Please verify backend connection.');
    } finally {
        startBtn.disabled = false;
        startBtn.textContent = '🚀 Start Interview';
    }
}

function setupInterviewView() {
    const sess = state.session;

    if (el('sessionModeBadge')) el('sessionModeBadge').textContent = sess.mode;

    const subjBadge = el('sessionSubjectBadge');
    if (subjBadge) {
        if (sess.technical_subject && sess.technical_subject !== 'None') {
            subjBadge.textContent = sess.technical_subject;
            subjBadge.style.display = 'inline-block';
        } else {
            subjBadge.style.display = 'none';
        }
    }

    if (el('sessionRoleBadge')) el('sessionRoleBadge').textContent = sess.role || 'Role: None';
    if (el('sessionDifficultyBadge')) el('sessionDifficultyBadge').textContent = sess.difficulty;

    updateSessionProgressUI();
    renderActiveQuestion();
    resetRecordingUI();
}

function renderActiveQuestion() {
    const q = state.activeQuestion;
    if (!q) return;

    if (el('interviewQuestionText')) el('interviewQuestionText').textContent = q.text;
    if (el('questionTraceability')) el('questionTraceability').textContent = q.traceability || 'Practice Question';

    const followUpBanner = el('followUpBanner');
    const questionTypePill = el('questionTypePill');

    if (q.type === 'follow_up') {
        if (followUpBanner) followUpBanner.style.display = 'flex';
        if (questionTypePill) questionTypePill.textContent = 'AI Follow-Up Question';
    } else {
        if (followUpBanner) followUpBanner.style.display = 'none';
        if (questionTypePill) questionTypePill.textContent = `Main Question #${q.order}`;
    }
}

function updateSessionProgressUI() {
    const sess = state.session;
    const q = state.activeQuestion;
    const currentIdx = q ? q.order : (sess.current_question_index || 1);
    const totalQ = sess.total_questions || 5;

    if (el('sessionProgressNumber')) {
        const typeStr = q && q.type === 'follow_up' ? ' (Follow-up)' : '';
        el('sessionProgressNumber').textContent = `Question ${currentIdx} of ${totalQ}${typeStr}`;
    }

    const pct = Math.min(100, Math.round((currentIdx / totalQ) * 100));
    if (el('sessionProgressBar')) {
        el('sessionProgressBar').style.width = `${pct}%`;
    }
}

// ============================================================================
// 8. WEBCAM & MICROPHONE RECORDING
// ============================================================================

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } },
            audio: { echoCancellation: true, noiseSuppression: true },
        });

        state.recording.stream = stream;
        const previewVideo = el('previewVideo');
        if (previewVideo) {
            previewVideo.srcObject = stream;
            previewVideo.style.display = 'block';
            if (el('cameraPlaceholder')) el('cameraPlaceholder').style.display = 'none';
        }

        let mimeType = 'video/webm;codecs=vp8,opus';
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = 'video/webm';
            if (!MediaRecorder.isTypeSupported(mimeType)) {
                mimeType = '';
            }
        }

        const options = mimeType ? { mimeType } : {};
        const mediaRecorder = new MediaRecorder(stream, options);
        state.recording.mediaRecorder = mediaRecorder;
        state.recording.chunks = [];

        mediaRecorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) {
                state.recording.chunks.push(event.data);
            }
        };

        mediaRecorder.start(250);
        state.recording.isRecording = true;

        el('startRecordingBtn').style.display = 'none';
        el('stopRecordingBtn').style.display = 'inline-flex';
        el('recLiveIndicator').style.display = 'flex';
        el('recStatusBadge').textContent = 'Recording';
        el('recStatusBadge').classList.add('status-recording');

        state.recording.seconds = 0;
        state.recording.interval = setInterval(() => {
            state.recording.seconds++;
            const mins = String(Math.floor(state.recording.seconds / 60)).padStart(2, '0');
            const secs = String(state.recording.seconds % 60).padStart(2, '0');
            if (el('recordingTimer')) el('recordingTimer').textContent = `${mins}:${secs}`;
        }, 1000);

    } catch (err) {
        console.error('Camera/Mic access error:', err);
        alert('Could not access camera or microphone. Please ensure browser permissions are granted.');
    }
}

function stopRecordingAndSubmit() {
    if (!state.recording.mediaRecorder || !state.recording.isRecording) return;

    state.recording.isRecording = false;
    clearInterval(state.recording.interval);

    state.recording.mediaRecorder.onstop = async () => {
        const mimeType = state.recording.mediaRecorder.mimeType || 'video/webm';
        const blob = new Blob(state.recording.chunks, { type: mimeType });
        const file = new File([blob], `answer_${Date.now()}.webm`, { type: mimeType });

        // Stop camera tracks
        if (state.recording.stream) {
            state.recording.stream.getTracks().forEach(t => t.stop());
            state.recording.stream = null;
        }

        await submitAnswerFile(file);
    };

    state.recording.mediaRecorder.stop();
}

function resetRecordingUI() {
    if (state.recording.interval) clearInterval(state.recording.interval);
    state.recording.seconds = 0;
    state.recording.chunks = [];
    state.recording.isRecording = false;

    if (el('previewVideo')) {
        el('previewVideo').srcObject = null;
        el('previewVideo').style.display = 'none';
    }
    if (el('cameraPlaceholder')) el('cameraPlaceholder').style.display = 'flex';
    if (el('recLiveIndicator')) el('recLiveIndicator').style.display = 'none';
    if (el('startRecordingBtn')) el('startRecordingBtn').style.display = 'inline-flex';
    if (el('stopRecordingBtn')) el('stopRecordingBtn').style.display = 'none';
    if (el('recStatusBadge')) {
        el('recStatusBadge').textContent = 'Ready';
        el('recStatusBadge').classList.remove('status-recording');
    }
    if (el('recordingTimer')) el('recordingTimer').textContent = '00:00';
}

function setupInterviewFileDrop() {
    const dropZone = el('dragDropZone');
    const fileInput = el('fileInput');
    const analyzeBtn = el('analyzeBtn');

    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files[0]) {
            state.selectedFile = fileInput.files[0];
            if (el('dragDropPrompt')) el('dragDropPrompt').textContent = `Selected: ${fileInput.files[0].name}`;
            if (analyzeBtn) analyzeBtn.style.display = 'block';
        }
    });

    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', () => {
            if (state.selectedFile) {
                submitAnswerFile(state.selectedFile);
            }
        });
    }
}

// ============================================================================
// 9. ANSWER SUBMISSION & PROGRESSION
// ============================================================================

async function submitAnswerFile(file) {
    if (!state.session || !state.activeQuestion) {
        alert('No active session question found.');
        return;
    }

    showView('viewProcessing');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', state.session.session_id || state.session.id);
    formData.append('question_id', state.activeQuestion.id);

    try {
        const res = await fetch('/api/interview/submit-answer', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: formData,
        });

        const json = await res.json();
        if (res.ok && json.data) {
            handleAnswerProgression(json.data);
        } else {
            alert(json.error || 'Failed to process answer.');
            showView('viewInterview');
        }
    } catch (err) {
        alert('Network error while processing interview answer.');
        showView('viewInterview');
    }
}

async function handleAnswerProgression(progData) {
    // If complete, fetch full results and show results screen
    if (progData.is_completed) {
        const sessId = state.session.session_id || state.session.id;
        try {
            const res = await fetch(`/api/interview/details/${sessId}`, { headers: getAuthHeaders() });
            const data = await res.json();
            if (res.ok && data.session) {
                renderSessionResults(data.session);
                showView('viewResults');
                loadDashboardData();
                return;
            }
        } catch (e) {
            console.error('Failed to fetch complete session details:', e);
        }
    }

    // Advance to next question (follow-up or next main)
    if (progData.has_next_question && progData.next_question) {
        state.activeQuestion = progData.next_question;
        state.session.current_question_index = progData.current_question_index;

        setupInterviewView();
        showView('viewInterview');
    }
}

// ============================================================================
// 10. SESSION RESULTS & EVIDENCE-BASED VIDEO TIMELINE
// ============================================================================

function renderSessionResults(sess) {
    state.latestResult = sess;
    const res = sess.result || {};

    const modeLabel = (sess.technical_subject && sess.technical_subject !== 'None') 
        ? `${sess.mode} (${sess.technical_subject})`
        : sess.mode;
    if (el('resultSessionTitle')) {
        el('resultSessionTitle').textContent = `${modeLabel} Interview Complete!`;
    }
    if (el('resultOverallScore')) el('resultOverallScore').textContent = sess.overall_score || 0;
    if (el('resultReadinessScore')) el('resultReadinessScore').textContent = `${sess.readiness_score || 0} / 100`;
    if (el('resultReadinessLevel')) el('resultReadinessLevel').textContent = sess.readiness_level || 'Developing';

    // Dimension Scores
    const tScore = res.technical_avg || 0;
    const cScore = res.communication_avg || 0;
    const pScore = res.problem_solving_avg || 0;
    const confScore = res.confidence_avg || 7;

    if (el('resTechScore')) el('resTechScore').textContent = `${tScore}/10`;
    if (el('resTechBar')) el('resTechBar').style.width = `${tScore * 10}%`;

    if (el('resCommScore')) el('resCommScore').textContent = `${cScore}/10`;
    if (el('resCommBar')) el('resCommBar').style.width = `${cScore * 10}%`;

    if (el('resProbScore')) el('resProbScore').textContent = `${pScore}/10`;
    if (el('resProbBar')) el('resProbBar').style.width = `${pScore * 10}%`;

    if (el('resConfScore')) el('resConfScore').textContent = `${confScore}/10`;
    if (el('resConfBar')) el('resConfBar').style.width = `${confScore * 10}%`;

    // Aggregated Communication & Video Metrics
    const questions = sess.questions || [];
    let totalWpm = 0, totalDuration = 0, totalFillers = 0, answeredCount = 0;
    let totalFaceVisible = 0, totalLookAways = 0, totalEyeContact = 0, totalHeadStability = 0;
    let allLookAwayEvents = [];
    let hasInsufficientEvidence = false;
    let videoEvaluatedCount = 0;

    questions.forEach(q => {
        if (q.has_answer) {
            answeredCount++;
            totalWpm += (q.words_per_minute || 0);
            totalDuration += (q.duration || 0);
            totalFillers += (q.filler_words_count || 0);

            if (q.evaluation && q.evaluation.video_metrics) {
                const vm = q.evaluation.video_metrics;
                if (vm.insufficient_evidence || vm.face_frames === 0) {
                    hasInsufficientEvidence = true;
                } else {
                    videoEvaluatedCount++;
                    totalFaceVisible += (vm.face_visible_percent || 0);
                    totalLookAways += (vm.look_away_count || 0);
                    if (vm.eye_contact_score !== null && vm.eye_contact_score !== undefined) {
                        totalEyeContact += vm.eye_contact_score;
                    }
                    if (vm.head_stability_score !== null && vm.head_stability_score !== undefined) {
                        totalHeadStability += vm.head_stability_score;
                    }
                    if (vm.look_away_events && Array.isArray(vm.look_away_events)) {
                        allLookAwayEvents.push(...vm.look_away_events);
                    }
                }
            }
        }
    });

    const avgWpm = answeredCount > 0 ? Math.round(totalWpm / answeredCount) : 0;
    if (el('resWpm')) el('resWpm').textContent = avgWpm;
    if (el('resSpeechDuration')) el('resSpeechDuration').textContent = `${Math.round(totalDuration)}s`;
    if (el('resFillerCount')) el('resFillerCount').textContent = totalFillers;
    if (el('resFillerRate')) {
        const rate = totalDuration > 0 ? ((totalFillers / (totalDuration / 60)) || 0).toFixed(1) : '0.0';
        el('resFillerRate').textContent = `${rate} /min`;
    }

    // Evidence-Based Video Rendering (Zero False Positives)
    if (hasInsufficientEvidence && videoEvaluatedCount === 0) {
        if (el('resFaceVisible')) el('resFaceVisible').textContent = '0%';
        if (el('resLookAwayCount')) el('resLookAwayCount').textContent = '0';
        if (el('resEyeContact')) el('resEyeContact').textContent = 'Unable to determine';
        if (el('resHeadStability')) el('resHeadStability').textContent = 'Unable to determine';
        if (el('videoGazeBadge')) {
            el('videoGazeBadge').textContent = 'Insufficient Visual Evidence';
            el('videoGazeBadge').className = 'badge badge-outline';
        }
    } else if (videoEvaluatedCount > 0) {
        const avgFace = Math.round(totalFaceVisible / videoEvaluatedCount);
        const avgEye = (totalEyeContact / videoEvaluatedCount).toFixed(1);
        const avgHead = (totalHeadStability / videoEvaluatedCount).toFixed(1);

        if (el('resFaceVisible')) el('resFaceVisible').textContent = `${avgFace}%`;
        if (el('resLookAwayCount')) el('resLookAwayCount').textContent = totalLookAways;
        if (el('resEyeContact')) el('resEyeContact').textContent = `${avgEye}/10`;
        if (el('resHeadStability')) el('resHeadStability').textContent = `${avgHead}/10`;
        if (el('videoGazeBadge')) {
            el('videoGazeBadge').textContent = totalLookAways === 0 ? 'Consistent Gaze' : 'Active Engagement';
            el('videoGazeBadge').className = 'badge badge-secondary';
        }
    }

    // Look-Away Timeline (Only Confirmed Events)
    const timelineContainer = el('resLookAwayTimelineContainer');
    const eventsContainer = el('resLookAwayEvents');
    if (timelineContainer && eventsContainer) {
        timelineContainer.style.display = 'block';
        if (allLookAwayEvents.length > 0) {
            eventsContainer.innerHTML = allLookAwayEvents.map((ev, i) => `
                <div class="event-chip">
                    <span class="event-chip-time">Event ${ev.event_num || (i + 1)}: ${ev.start_time} → ${ev.end_time}</span>
                    <span class="event-chip-dur">Duration: ${ev.duration}s</span>
                    <span class="event-chip-dir">Direction: ${ev.direction || 'Away'}</span>
                </div>
            `).join('');
        } else {
            eventsContainer.innerHTML = `<span class="text-secondary" style="font-size: 0.85rem;">No look-away events detected.</span>`;
        }
    }

    // Strengths, Weaknesses, Suggestions
    renderListItems(el('resStrengthsList'), res.strengths || ['Good domain clarity and steady conversational pace.']);
    renderListItems(el('resWeaknessesList'), res.weaknesses || ['Provide more concrete technical tradeoffs in explanations.']);
    renderListItems(el('resSuggestionsList'), res.improvement_suggestions || ['Focus on structure and specific algorithms for higher depth scores.']);

    // Question-wise breakdown
    renderQuestionBreakdown(questions);

    // Setup PDF button
    const pdfBtn = el('downloadSessionPdfBtn');
    if (pdfBtn) {
        pdfBtn.onclick = () => {
            window.open(`/api/interview/pdf/${sess.id}`, '_blank');
        };
    }
}

function renderListItems(container, items) {
    if (!container) return;
    if (!items || items.length === 0) {
        container.innerHTML = `<p class="text-secondary">None noted.</p>`;
        return;
    }
    container.innerHTML = `<ul>${items.map(item => `<li>${item}</li>`).join('')}</ul>`;
}

function renderQuestionBreakdown(questions) {
    const list = el('questionBreakdownList');
    if (!list) return;

    if (!questions || questions.length === 0) {
        list.innerHTML = `<p class="text-secondary">No questions answered yet.</p>`;
        return;
    }

    list.innerHTML = questions.map(q => {
        const ev = q.evaluation || {};
        const isFollowUp = q.type === 'follow_up';

        let starHtml = '';
        if (ev.star_analysis && Object.keys(ev.star_analysis).length > 0) {
            const star = ev.star_analysis;
            starHtml = `
                <div class="star-analysis-box">
                    <strong>STAR Framework Breakdown:</strong>
                    <div><strong>Situation:</strong> ${star.situation || 'Outlined'}</div>
                    <div><strong>Task:</strong> ${star.task || 'Defined'}</div>
                    <div><strong>Action:</strong> ${star.action || 'Described'}</div>
                    <div><strong>Result:</strong> ${star.result || 'Provided'}</div>
                </div>
            `;
        }

        return `
            <div class="breakdown-card">
                <div class="breakdown-card-header">
                    <div>
                        <span class="badge ${isFollowUp ? 'badge-primary' : 'badge-outline'}">
                            ${isFollowUp ? 'Follow-Up' : `Question #${q.order}`}
                        </span>
                        <h4 class="breakdown-q-title" style="margin-top: 4px;">${q.text}</h4>
                    </div>
                    <span class="breakdown-score-badge">
                        ${ev.overall_score !== undefined ? ev.overall_score + '/100' : 'Score Pending'}
                    </span>
                </div>

                <div class="transcript-quote-box">
                    <strong>Your Spoken Answer:</strong><br>
                    "${q.transcript || 'No speech recorded.'}"
                </div>

                ${starHtml}

                <div class="ideal-answer-box">
                    <strong>💡 Ideal Practice Answer:</strong><br>
                    ${ev.ideal_answer || 'Key concepts: address core requirements, trade-offs, and verification.'}
                </div>

                <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 6px;">
                    <strong>Interviewer Feedback:</strong> ${ev.feedback || 'Answer successfully recorded and evaluated.'}
                </div>
            </div>
        `;
    }).join('');
}

// ============================================================================
// 11. SESSION DETAIL MODAL
// ============================================================================

async function openSessionDetailModal(sessionId) {
    const modal = el('detailModal');
    if (!modal) return;

    modal.style.display = 'flex';
    el('modalSessionTitle').textContent = `Loading Session #${sessionId}...`;
    el('modalSessionBody').innerHTML = `<p class="text-secondary">Fetching session details from MySQL...</p>`;

    try {
        const res = await fetch(`/api/interview/details/${sessionId}`, {
            headers: getAuthHeaders(),
        });
        const data = await res.json();
        if (res.ok && data.session) {
            const sess = data.session;
            const domainOrRole = (sess.technical_subject && sess.technical_subject !== 'None') 
                ? sess.technical_subject 
                : (sess.role || 'General');

            el('modalSessionTitle').textContent = `${sess.mode} Interview (${domainOrRole})`;
            el('modalSessionSub').textContent = `Session #${sess.id} • ${sess.created_at} • Score: ${sess.overall_score}/100 • Readiness: ${sess.readiness_score}/100 (${sess.readiness_level})`;

            const body = el('modalSessionBody');
            body.innerHTML = `
                <div style="margin-bottom: 1rem;">
                    <h4>Question-by-Question Details:</h4>
                </div>
                <div class="breakdown-list" id="modalBreakdownList"></div>
            `;

            renderQuestionBreakdownModal(sess.questions, el('modalBreakdownList'));

            el('modalDownloadPdfBtn').onclick = () => {
                window.open(`/api/interview/pdf/${sess.id}`, '_blank');
            };
        } else {
            el('modalSessionBody').innerHTML = `<p class="text-danger">Failed to load session details.</p>`;
        }
    } catch (err) {
        el('modalSessionBody').innerHTML = `<p class="text-danger">Error retrieving session data.</p>`;
    }
}

function renderQuestionBreakdownModal(questions, container) {
    if (!container) return;
    container.innerHTML = questions.map(q => {
        const ev = q.evaluation || {};
        return `
            <div class="breakdown-card">
                <div class="breakdown-card-header">
                    <div>
                        <span class="badge ${q.type === 'follow_up' ? 'badge-primary' : 'badge-outline'}">
                            ${q.type === 'follow_up' ? 'Follow-Up' : `Question #${q.order}`}
                        </span>
                        <h4 style="margin-top: 4px;">${q.text}</h4>
                    </div>
                    <span class="breakdown-score-badge">${ev.overall_score !== undefined ? ev.overall_score + '/100' : '--'}</span>
                </div>
                <div class="transcript-quote-box">
                    <strong>Transcript:</strong> "${q.transcript || 'No transcript'}"
                </div>
                <div class="ideal-answer-box">
                    <strong>Ideal Answer:</strong> ${ev.ideal_answer || 'N/A'}
                </div>
                <div style="font-size: 0.85rem; color: var(--text-secondary);">
                    <strong>Feedback:</strong> ${ev.feedback || 'N/A'}
                </div>
            </div>
        `;
    }).join('');
}

function closeSessionDetailModal() {
    const modal = el('detailModal');
    if (modal) modal.style.display = 'none';
}

// ============================================================================
// 12. EVENT LISTENERS & INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Top Navigation
    if (el('brandLogo')) el('brandLogo').addEventListener('click', () => showView('viewDashboard'));
    if (el('navDashboardBtn')) el('navDashboardBtn').addEventListener('click', () => {
        showView('viewDashboard');
        loadDashboardData();
        loadLatestResumeInsights();
    });
    if (el('navSetupBtn')) el('navSetupBtn').addEventListener('click', () => {
        showView('viewSetup');
        goToWizardStep(1);
    });
    if (el('navResumeBtn')) el('navResumeBtn').addEventListener('click', () => {
        showView('viewResume');
        loadLatestResumeInsights();
    });
    if (el('navHistoryBtn')) el('navHistoryBtn').addEventListener('click', () => {
        showView('viewHistory');
        loadDashboardData();
    });

    // Dashboard CTAs
    if (el('dashboardStartBtn')) el('dashboardStartBtn').addEventListener('click', () => {
        showView('viewSetup');
        goToWizardStep(1);
    });
    if (el('dashboardViewHistoryBtn') || el('dashSeeAllHistoryBtn')) {
        const hBtn = el('dashboardViewHistoryBtn');
        if (hBtn) hBtn.addEventListener('click', () => { showView('viewHistory'); loadDashboardData(); });
        const seeAll = el('dashSeeAllHistoryBtn');
        if (seeAll) seeAll.addEventListener('click', () => { showView('viewHistory'); loadDashboardData(); });
    }
    if (el('dashManageResumeBtn')) el('dashManageResumeBtn').addEventListener('click', () => {
        showView('viewResume');
        loadLatestResumeInsights();
    });
    if (el('dashRecStartBtn')) el('dashRecStartBtn').addEventListener('click', () => {
        showView('viewSetup');
        if (el('setupModeSelect')) el('setupModeSelect').value = 'Technical';
        if (el('setupSubjectSelect')) el('setupSubjectSelect').value = 'Java';
        goToWizardStep(2);
    });
    if (el('setupBackDashBtn')) el('setupBackDashBtn').addEventListener('click', () => showView('viewDashboard'));
    if (el('historyStartNewBtn')) el('historyStartNewBtn').addEventListener('click', () => {
        showView('viewSetup');
        goToWizardStep(1);
    });
    if (el('resumeUploadNewBtn')) el('resumeUploadNewBtn').addEventListener('click', () => {
        showView('viewSetup');
        goToWizardStep(4);
    });

    // Mode Selector Tiles (Dashboard & Wizard Step 1)
    document.querySelectorAll('.mode-tile').forEach(tile => {
        tile.addEventListener('click', () => {
            const mode = tile.getAttribute('data-mode');
            selectMode(mode);
            showView('viewSetup');
            goToWizardStep(2);
        });
    });

    document.querySelectorAll('.mode-select-card').forEach(card => {
        card.addEventListener('click', () => {
            const mode = card.getAttribute('data-mode-val');
            selectMode(mode);
        });
    });

    function selectMode(mode) {
        if (el('setupModeSelect')) el('setupModeSelect').value = mode;
        document.querySelectorAll('.mode-select-card').forEach(c => {
            c.classList.toggle('selected', c.getAttribute('data-mode-val') === mode);
        });
        const subjGroup = el('setupSubjectGroup');
        if (subjGroup) {
            subjGroup.style.display = (mode === 'Technical' || mode === 'Mixed') ? 'block' : 'none';
        }
    }

    // Question Count Cards (Wizard Step 3)
    document.querySelectorAll('.q-count-card').forEach(card => {
        card.addEventListener('click', () => {
            const count = card.getAttribute('data-count');
            if (el('setupQuestionsCountSelect')) el('setupQuestionsCountSelect').value = count;
            document.querySelectorAll('.q-count-card').forEach(c => {
                c.classList.toggle('selected', c.getAttribute('data-count') === count);
            });
        });
    });

    // Wizard Navigation Buttons
    if (el('step1NextBtn')) el('step1NextBtn').addEventListener('click', () => goToWizardStep(2));
    if (el('step2BackBtn')) el('step2BackBtn').addEventListener('click', () => goToWizardStep(1));
    if (el('step2NextBtn')) el('step2NextBtn').addEventListener('click', () => goToWizardStep(3));
    if (el('step3BackBtn')) el('step3BackBtn').addEventListener('click', () => goToWizardStep(2));
    if (el('step3NextBtn')) el('step3NextBtn').addEventListener('click', () => goToWizardStep(4));
    if (el('step4BackBtn')) el('step4BackBtn').addEventListener('click', () => goToWizardStep(3));
    if (el('step4NextBtn')) el('step4NextBtn').addEventListener('click', () => goToWizardStep(5));
    if (el('step5BackBtn')) el('step5BackBtn').addEventListener('click', () => goToWizardStep(4));

    // Direct Stepper Click
    document.querySelectorAll('.step-indicator').forEach(ind => {
        ind.addEventListener('click', () => {
            const step = parseInt(ind.getAttribute('data-step'), 10);
            if (step) goToWizardStep(step);
        });
    });

    // Role-Aware Gap Selector in Resume View
    if (el('resGapRoleSelect')) {
        el('resGapRoleSelect').addEventListener('change', (e) => {
            loadLatestResumeInsights(e.target.value);
        });
    }

    // Launch Interview Session Button
    if (el('startSessionBtn')) el('startSessionBtn').addEventListener('click', startInterviewSession);

    // Recording Controls
    if (el('startRecordingBtn')) el('startRecordingBtn').addEventListener('click', startRecording);
    if (el('stopRecordingBtn')) el('stopRecordingBtn').addEventListener('click', stopRecordingAndSubmit);

    // Copy Question
    if (el('copyQuestionBtn')) {
        el('copyQuestionBtn').addEventListener('click', () => {
            if (state.activeQuestion && state.activeQuestion.text) {
                navigator.clipboard.writeText(state.activeQuestion.text);
                el('copyQuestionBtn').textContent = '✅ Copied!';
                setTimeout(() => { el('copyQuestionBtn').textContent = '📋 Copy Question'; }, 2000);
            }
        });
    }

    // Results Actions
    if (el('resultsNewInterviewBtn')) el('resultsNewInterviewBtn').addEventListener('click', () => {
        showView('viewSetup');
        goToWizardStep(1);
    });
    if (el('resultsBackDashboardBtn')) el('resultsBackDashboardBtn').addEventListener('click', () => showView('viewDashboard'));

    // Auth Password Toggles
    if (el('loginTogglePwdBtn')) {
        el('loginTogglePwdBtn').addEventListener('click', () => {
            const pwdInput = el('loginPassword');
            if (pwdInput.type === 'password') {
                pwdInput.type = 'text';
                el('loginTogglePwdBtn').textContent = 'Hide';
            } else {
                pwdInput.type = 'password';
                el('loginTogglePwdBtn').textContent = 'Show';
            }
        });
    }
    if (el('regTogglePwdBtn')) {
        el('regTogglePwdBtn').addEventListener('click', () => {
            const p1 = el('regPassword');
            const p2 = el('regConfirmPassword');
            const isPwd = p1.type === 'password';
            p1.type = isPwd ? 'text' : 'password';
            if (p2) p2.type = isPwd ? 'text' : 'password';
            el('regTogglePwdBtn').textContent = isPwd ? 'Hide' : 'Show';
        });
    }

    // Auth Modal Handlers
    if (el('openLoginBtn')) el('openLoginBtn').addEventListener('click', () => showAuthModal('login'));
    if (el('openRegisterBtn')) el('openRegisterBtn').addEventListener('click', () => showAuthModal('register'));
    if (el('closeAuthModalBtn')) el('closeAuthModalBtn').addEventListener('click', closeAuthModal);
    if (el('authTabLogin')) el('authTabLogin').addEventListener('click', () => switchAuthTab('login'));
    if (el('authTabRegister')) el('authTabRegister').addEventListener('click', () => switchAuthTab('register'));
    if (el('loginForm')) el('loginForm').addEventListener('submit', handleLogin);
    if (el('registerForm')) el('registerForm').addEventListener('submit', handleRegister);
    if (el('logoutBtn')) el('logoutBtn').addEventListener('click', handleLogout);

    // Detail Modal Handlers
    if (el('closeDetailModalBtn')) el('closeDetailModalBtn').addEventListener('click', closeSessionDetailModal);
    if (el('modalCloseBtn')) el('modalCloseBtn').addEventListener('click', closeSessionDetailModal);

    // Setup Resume & File Upload Handlers
    setupResumeUpload();
    setupInterviewFileDrop();

    // Initial Auth & Data Fetch
    checkAuthStatus();
});
