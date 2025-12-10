// Question Bank Application JavaScript
// Extracted from index.html for maintainability

// State
        let editor = null;
        let courses = [];
        let banks = [];
        let editingQuestionId = null;
        let selectedQuestions = new Set();
        let bulkSelectedQuestions = new Set(); // For bulk operations in question list
        let bulkMode = false;
        let questionOverrides = {}; // Per-question spacing overrides for exam builder
        let currentExamQuestions = []; // Stores current exam preview questions with points
        let cachedSectionQuestions = {}; // Cache questions per section to avoid re-randomizing
        let cachedFinalQuestions = null; // Cache final question list after all filtering
        let hasCachedQuestions = false; // Simple flag - reset when template changes
        let isRestoringState = false; // Flag to prevent saving during restore

        // Dark mode - check saved preference or system preference
        function initDarkMode() {
            const saved = localStorage.getItem('darkMode');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            if (saved === 'true' || (saved === null && prefersDark)) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        }

        function toggleDarkMode() {
            const isDark = document.documentElement.classList.toggle('dark');
            localStorage.setItem('darkMode', isDark);
            // Update Monaco editor theme
            if (editor) {
                monaco.editor.setTheme(isDark ? 'vs-dark' : 'vs');
            }
            lucide.createIcons();
        }

        // Initialize - fast startup, load data in background
        document.addEventListener('DOMContentLoaded', async () => {
            console.log('[DEBUG] DOMContentLoaded started - app.js loaded');
            initDarkMode();
            lucide.createIcons();
            setupEventListeners();
            // Load data - courses must complete first for dropdowns
            console.log('[DEBUG] Loading courses...');
            await loadCourses();
            console.log('[DEBUG] Courses loaded, loading tags and questions...');
            loadTags();
            loadQuestions();
            // Load trash count for sidebar badge
            updateTrashCount();
            // Load usage stats for sidebar
            loadUsageStats();
            // Restore previous view state
            restoreViewState();
            console.log('[DEBUG] DOMContentLoaded complete');
        });

        // Save/restore view state for page refresh persistence
        function saveViewState() {
            if (isRestoringState) return; // Don't save while restoring
            const state = {
                currentView: document.querySelector('.view:not(.hidden)')?.id?.replace('view-', '') || 'questions',
                currentTemplateId: currentTemplateId,
                templateCourseFilter: document.getElementById('template-course-selector')?.value,
                examSections: examSections,
                questionOverrides: questionOverrides,
                sectionIdCounter: sectionIdCounter,
                examTitle: document.getElementById('exam-title')?.value,
                examCourse: document.getElementById('exam-course')?.value,
                examInstructor: document.getElementById('exam-instructor')?.value,
                examTerm: document.getElementById('exam-term')?.value,
                examInstructions: document.getElementById('exam-instructions')?.value,
                examLineLength: document.getElementById('exam-line-length')?.value,
                examSolutionSpace: document.getElementById('exam-solution-space')?.value,
                examQuizMode: document.getElementById('exam-quiz-mode')?.checked,
                examIncludeId: document.getElementById('exam-include-id')?.checked,
                examSplitMc: document.getElementById('exam-split-mc')?.checked,
                examShuffle: document.getElementById('exam-shuffle')?.checked,
                examAnswers: document.getElementById('exam-answers')?.checked,
            };
            localStorage.setItem('examBuilderState', JSON.stringify(state));
        }

        function restoreViewState() {
            const saved = localStorage.getItem('examBuilderState');
            if (!saved) return;

            try {
                const state = JSON.parse(saved);

                // Restore view after a short delay to let DOM initialize
                setTimeout(async () => {
                    isRestoringState = true; // Prevent saving during restore

                    // Restore exam builder state variables first
                    if (state.examSections) examSections = state.examSections;
                    if (state.questionOverrides) questionOverrides = state.questionOverrides;
                    if (state.sectionIdCounter) sectionIdCounter = state.sectionIdCounter;
                    if (state.currentTemplateId) currentTemplateId = state.currentTemplateId;

                    if (state.currentView && state.currentView !== 'questions') {
                        showView(state.currentView, null);
                    }

                    // Restore form fields
                    if (state.examTitle) document.getElementById('exam-title').value = state.examTitle;
                    if (state.examCourse) document.getElementById('exam-course').value = state.examCourse;
                    if (state.examInstructor) document.getElementById('exam-instructor').value = state.examInstructor;
                    if (state.examTerm) document.getElementById('exam-term').value = state.examTerm;
                    if (state.examInstructions) document.getElementById('exam-instructions').value = state.examInstructions;
                    if (state.examLineLength) document.getElementById('exam-line-length').value = state.examLineLength;
                    if (state.examSolutionSpace) document.getElementById('exam-solution-space').value = state.examSolutionSpace;
                    if (state.examQuizMode !== undefined) document.getElementById('exam-quiz-mode').checked = state.examQuizMode;
                    if (state.examIncludeId !== undefined) document.getElementById('exam-include-id').checked = state.examIncludeId;
                    if (state.examSplitMc !== undefined) document.getElementById('exam-split-mc').checked = state.examSplitMc;
                    if (state.examShuffle !== undefined) document.getElementById('exam-shuffle').checked = state.examShuffle;
                    if (state.examAnswers !== undefined) document.getElementById('exam-answers').checked = state.examAnswers;

                    // Re-render sections and preview if on exam view
                    if (state.currentView === 'exams') {
                        // Wait for templates to load, then set selector
                        await loadExamTemplates('');

                        // Restore course filter first
                        const courseSelector = document.getElementById('template-course-selector');
                        if (state.templateCourseFilter && courseSelector) {
                            courseSelector.value = state.templateCourseFilter;
                            filterTemplatesByCourse(state.templateCourseFilter);
                        }

                        // Then restore template selection (convert to string for comparison)
                        const templateSelector = document.getElementById('template-selector');
                        if (state.currentTemplateId && templateSelector) {
                            const templateIdStr = String(state.currentTemplateId);
                            templateSelector.value = templateIdStr;
                            // Verify the selection was successful
                            if (templateSelector.value === templateIdStr) {
                                // Load the full template to restore all settings including include_answers and versions
                                await loadExamTemplate(templateIdStr);
                            } else {
                                console.warn('Could not restore template selection:', templateIdStr, 'Options:', Array.from(templateSelector.options).map(o => o.value));
                            }
                        } else if (examSections.length > 0) {
                            // Only render manually if no template to load
                            renderExamSections();
                            await refreshExamPreview();
                        }
                    }

                    isRestoringState = false; // Allow saving again
                }, 100);
            } catch (e) {
                console.error('Error restoring view state:', e);
                isRestoringState = false;
            }
        }

        // Monaco state
        let monacoLoaded = false;
        let monacoLoading = false;
        let pendingEditorValue = '';

        function loadMonaco() {
            return new Promise((resolve) => {
                if (monacoLoaded) { resolve(); return; }
                if (monacoLoading) {
                    // Wait for existing load
                    const check = setInterval(() => {
                        if (monacoLoaded) { clearInterval(check); resolve(); }
                    }, 50);
                    return;
                }
                monacoLoading = true;
                const script = document.createElement('script');
                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.min.js';
                script.onload = () => {
                    const isDark = document.documentElement.classList.contains('dark');
                    require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' } });
                    require(['vs/editor/editor.main'], function() {
                        editor = monaco.editor.create(document.getElementById('editor-container'), {
                            value: pendingEditorValue,
                            language: 'markdown',
                            theme: isDark ? 'vs-dark' : 'vs',
                            minimap: { enabled: false },
                            lineNumbers: 'off',
                            wordWrap: 'on',
                            fontSize: 14,
                            padding: { top: 12, bottom: 12 },
                            automaticLayout: true,
                            scrollBeyondLastLine: false,
                        });
                        monacoLoaded = true;
                        resolve();
                    });
                };
                document.head.appendChild(script);
            });
        }

        function setupEventListeners() {
            document.getElementById('search-input')?.addEventListener('input', debounce(() => loadQuestions(), 300));
            ['filter-type', 'filter-difficulty'].forEach(id => {
                document.getElementById(id)?.addEventListener('change', () => loadQuestions());
            });
            document.getElementById('filter-course')?.addEventListener('change', () => {
                loadTagsForCourse();
                loadQuestions();
            });
            ['exam-filter-course', 'exam-filter-type', 'exam-filter-week'].forEach(id => {
                document.getElementById(id)?.addEventListener('change', () => loadExamQuestions());
            });
        }

        // Load weeks for a specific filter dropdown
        async function loadWeeksForFilter(weekSelectId) {
            const weekSelect = document.getElementById(weekSelectId);
            if (!weekSelect) return;

            // Get the corresponding course select
            const courseSelectId = weekSelectId === 'filter-week' ? 'filter-course' : 'exam-filter-course';
            const courseCode = document.getElementById(courseSelectId)?.value;

            // Reset the week dropdown
            weekSelect.innerHTML = '<option value="">All Weeks</option>';

            if (!courseCode) return;

            // Fetch weeks for the selected course
            const data = await api(`weeks/?course=${courseCode}`);
            const weeks = data.results || data || [];

            if (weeks.length > 0) {
                weeks.forEach(w => {
                    const displayName = w.name || `Week ${w.number}`;
                    weekSelect.innerHTML += `<option value="${w.id}">${displayName} (${w.question_count || 0})</option>`;
                });
            }

            // Trigger the filter change
            if (weekSelectId === 'filter-week') {
                loadQuestions();
            } else {
                loadExamQuestions();
            }
        }

        // Navigation
        function showView(view, event) {
            event?.preventDefault();
            document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
            document.getElementById(`view-${view}`).classList.remove('hidden');
            document.querySelectorAll('.sidebar-item').forEach(l => l.classList.remove('active'));
            // Find and activate the correct sidebar item
            if (event?.target) {
                event.target.closest('.sidebar-item')?.classList.add('active');
            } else {
                // Programmatic navigation - find by view name
                document.querySelectorAll('.sidebar-item').forEach(item => {
                    if (item.getAttribute('onclick')?.includes(`'${view}'`)) {
                        item.classList.add('active');
                    }
                });
            }
            lucide.createIcons();
            if (view === 'exams') {
                loadExamQuestions();
                loadExamTemplates('');
            }
            if (view === 'trash') {
                loadTrash();
            }
            saveViewState();
        }

        // Get CSRF token from cookies
        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        // API
        async function api(endpoint, method = 'GET', data = null) {
            console.log('[DEBUG] api() called:', endpoint, method);
            const headers = { 'Content-Type': 'application/json' };

            // Include CSRF token for state-changing requests
            if (method !== 'GET' && method !== 'HEAD') {
                const csrfToken = getCookie('csrftoken');
                if (csrfToken) {
                    headers['X-CSRFToken'] = csrfToken;
                }
            }

            const options = {
                method,
                headers,
                credentials: 'same-origin'  // Include session cookies
            };
            if (data) options.body = JSON.stringify(data);
            const res = await fetch(`/api/${endpoint}`, options);
            console.log('[DEBUG] api() response status:', res.status, res.ok);
            if (!res.ok) {
                if (res.status === 403) {
                    // Try to parse the response to check if it's a permission error or auth failure
                    try {
                        const errorJson = await res.json();
                        if (errorJson.error) {
                            // This is a permission error from the view, show it to user
                            console.log('[DEBUG] 403 - permission error:', errorJson.error);
                            alert('Permission denied: ' + errorJson.error);
                            return {};
                        }
                    } catch (e) {
                        // JSON parse failed, assume it's an auth redirect
                    }
                    // Session expired, redirect to login
                    console.log('[DEBUG] 403 - redirecting to login');
                    window.location.href = '/login/';
                    return {};
                }
                console.log('[DEBUG] api() non-OK response:', res.status);
            }
            if (method === 'DELETE') return {};
            const json = await res.json();
            console.log('[DEBUG] api() returning data for', endpoint);
            return json;
        }

        // Data Loading
        async function loadCourses() {
            const data = await api('courses/');
            courses = data.results || data || [];
            document.getElementById('stat-courses').textContent = courses.length;
            renderCourses();
            updateCourseFilters();
            await loadBanks();
        }

        async function loadBanks() {
            const data = await api('banks/');
            banks = data.results || data || [];
            updateBankSelect();
        }

        let allTags = [];
        let selectedTags = [];

        async function loadTags() {
            const data = await api('tags/');
            allTags = data.results || data || [];
            renderTagCheckboxes();
        }

        async function loadTagsForCourse() {
            const course = document.getElementById('filter-course')?.value;
            selectedTags = []; // Reset selected tags when course changes
            updateTagButtonText();

            if (!course) {
                // No course selected, show all tags
                const data = await api('tags/');
                allTags = data.results || data || [];
            } else {
                // Get tags for this course
                const data = await api(`tags/?course=${course}`);
                allTags = data.results || data || [];
            }
            renderTagCheckboxes();
        }

        function renderTagCheckboxes() {
            const container = document.getElementById('tag-checkboxes');
            if (!container) return;
            container.innerHTML = allTags.map(t => `
                <label class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700 cursor-pointer">
                    <input type="checkbox" value="${escapeHtml(t.name)}" onchange="onTagCheckChange()"
                        class="w-4 h-4 rounded text-sky-500" ${selectedTags.includes(t.name) ? 'checked' : ''}>
                    <span class="text-sm text-gray-700 dark:text-slate-300">${escapeHtml(t.name)}</span>
                </label>
            `).join('');
        }

        function toggleTagDropdown() {
            const dropdown = document.getElementById('tag-dropdown');
            dropdown.classList.toggle('hidden');
        }

        function onTagCheckChange() {
            const checkboxes = document.querySelectorAll('#tag-checkboxes input[type="checkbox"]:checked');
            selectedTags = Array.from(checkboxes).map(cb => cb.value);
            updateTagButtonText();
            loadQuestions();
        }

        function updateTagButtonText() {
            const text = document.getElementById('tag-dropdown-text');
            if (selectedTags.length === 0) {
                text.textContent = 'All Tags';
            } else if (selectedTags.length === 1) {
                text.textContent = selectedTags[0];
            } else {
                text.textContent = `${selectedTags.length} tags`;
            }
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const dropdown = document.getElementById('tag-dropdown');
            const btn = document.getElementById('tag-dropdown-btn');
            if (dropdown && btn && !dropdown.contains(e.target) && !btn.contains(e.target)) {
                dropdown.classList.add('hidden');
            }
        });

        let currentPage = 1;
        let totalQuestions = 0;

        async function loadQuestions(page = 1) {
            console.log('[DEBUG] loadQuestions called, page:', page);
            currentPage = page;
            const params = new URLSearchParams();
            const search = document.getElementById('search-input')?.value;
            const course = document.getElementById('filter-course')?.value;
            const type = document.getElementById('filter-type')?.value;
            const difficulty = document.getElementById('filter-difficulty')?.value;
            if (search) params.append('search', search);
            if (course) params.append('course', course);
            selectedTags.forEach(tag => params.append('tags', tag));
            if (type) params.append('type', type);
            if (difficulty) params.append('difficulty', difficulty);
            params.append('page', page);

            console.log('[DEBUG] Fetching questions with params:', params.toString());
            const data = await api(`questions/?${params.toString()}`);
            console.log('[DEBUG] API response:', data);
            console.log('[DEBUG] data.results:', data?.results);
            console.log('[DEBUG] data.count:', data?.count);
            const questions = data.results || data || [];
            console.log('[DEBUG] questions array length:', questions.length);
            totalQuestions = data.count || questions.length;
            const totalPages = Math.ceil(totalQuestions / 50);
            document.getElementById('stat-questions').textContent = totalQuestions;
            document.getElementById('nav-count').textContent = totalQuestions;
            renderQuestions(questions, totalPages);
        }

        async function loadExamQuestions() {
            const params = new URLSearchParams();
            const course = document.getElementById('exam-filter-course')?.value;
            const week = document.getElementById('exam-filter-week')?.value;
            const type = document.getElementById('exam-filter-type')?.value;
            if (course) params.append('course', course);
            if (week) params.append('week', week);
            if (type) params.append('type', type);

            const data = await api(`questions/?${params.toString()}`);
            renderExamQuestions(data.results || data || []);
        }

        // Renderers
        function renderQuestions(questions, totalPages = 1) {
            const container = document.getElementById('questions-list');
            if (!questions.length) {
                container.innerHTML = `<div class="p-12 text-center text-gray-400 dark:text-slate-500">
                    <i data-lucide="inbox" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                    <p class="font-medium">No questions found</p>
                    <p class="text-sm mt-1">Try adjusting your filters or create a new question</p>
                </div>`;
                lucide.createIcons();
                return;
            }

            const questionsList = questions.map(q => {
                const hasMultipleVariants = q.block_types && q.block_types.length > 1;
                const blockVariantsJson = q.block_types ? escapeHtml(JSON.stringify(q.block_types)) : '';
                const tagsHtml = (q.tags || []).map(t => `<span class="inline-block px-1.5 py-0.5 text-xs rounded bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300">${escapeHtml(t.name)}</span>`).join(' ');
                return `
                <div class="question-row flex items-start gap-4 p-4 hover:bg-gray-50 dark:hover:bg-slate-700/50 border-b border-gray-100 dark:border-slate-700 last:border-0 group"
                    data-original-text="${escapeHtml(q.text)}"
                    data-original-points="${parseInt(q.points)}"
                    ${blockVariantsJson ? `data-block-variants="${blockVariantsJson}"` : ''}>
                    ${bulkMode ? `<input type="checkbox" class="bulk-checkbox mt-1 w-4 h-4 rounded text-sky-600" data-id="${q.id}" ${bulkSelectedQuestions.has(q.id) ? 'checked' : ''} onclick="event.stopPropagation(); toggleBulkQuestion(${q.id}, this)">` : ''}
                    <div class="flex-1 min-w-0 cursor-pointer" onclick="editQuestion(${q.id})">
                        <div class="flex items-center gap-2 mb-1 flex-wrap">
                            ${q.block_types ? q.block_types.map((v, i) => `<span class="badge ${getTypeBadgeClass(v.type)} ${hasMultipleVariants ? 'cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-sky-400' : ''}" ${hasMultipleVariants ? `onmouseenter="previewBlockVariant(event, ${i})" onmouseleave="resetBlockPreview(event)" onclick="event.stopPropagation(); previewBlockVariant(event, ${i})"` : ''}>${formatType(v.type)}</span>`).join('') : `<span class="badge ${getTypeBadgeClass(q.question_type)}">${formatType(q.question_type)}</span>`}
                            <span class="badge ${getDifficultyClass(q.difficulty)}">${q.difficulty || 'medium'}</span>
                            ${q.bank_name ? `<span class="badge bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 flex items-center gap-1" title="Bank: ${escapeHtml(q.bank_name)}"><i data-lucide="folder" class="w-3 h-3"></i>${escapeHtml(q.bank_name)}</span>` : ''}
                            ${q.block_name ? `<span class="badge bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 flex items-center gap-1" title="Block: ${escapeHtml(q.block_name)} (${q.block_variant_count} variants, pick ${q.block_max_questions})"><i data-lucide="layers" class="w-3 h-3"></i>${q.block_variant_count}v</span>` : ''}
                            ${q.linked_count > 1 ? `<span class="badge bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 flex items-center gap-1"><i data-lucide="link" class="w-3 h-3"></i>${q.linked_count}</span>` : ''}
                            ${q.canonical ? `<span class="badge bg-gray-100 dark:bg-slate-700 text-gray-500 dark:text-slate-400 text-xs">copy</span>` : ''}
                            <span class="text-xs text-gray-400 dark:text-slate-500">${q.course_code || ''}</span>
                        </div>
                        <div class="question-text text-gray-800 dark:text-slate-200 text-sm line-clamp-3">${simpleMarkdown(q.text)}</div>
                        ${tagsHtml ? `<div class="flex flex-wrap gap-1 mt-1">${tagsHtml}</div>` : ''}
                    </div>
                    <div class="text-right flex-shrink-0 flex flex-col items-end gap-2">
                        <div class="flex items-center gap-3">
                            ${q.times_used > 0 ? `<div class="text-center" title="Used ${q.times_used} time${q.times_used > 1 ? 's' : ''}${q.last_used ? ' (last: ' + new Date(q.last_used).toLocaleDateString() + ')' : ''}">
                                <div class="text-sm font-medium ${q.times_used > 5 ? 'text-amber-600 dark:text-amber-400' : 'text-gray-500 dark:text-slate-400'}">${q.times_used}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">uses</div>
                            </div>` : ''}
                            <div>
                                <div class="question-points text-lg font-semibold text-gray-900 dark:text-white">${parseInt(q.points)}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">pts</div>
                            </div>
                        </div>
                        <div class="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                            <button onclick="event.stopPropagation(); duplicateQuestion(${q.id})" class="p-1.5 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-600" title="Duplicate">
                                <i data-lucide="copy" class="w-4 h-4 text-gray-500 dark:text-slate-400"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `}).join('');

            // Add pagination controls
            let paginationHtml = '';
            if (totalPages > 1) {
                const pageNumbers = [];
                for (let i = 1; i <= Math.min(totalPages, 10); i++) {
                    pageNumbers.push(i);
                }
                paginationHtml = `
                    <div class="flex items-center justify-center gap-2 p-4 border-t border-gray-100 dark:border-slate-700">
                        <button onclick="loadQuestions(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}
                            class="px-3 py-1.5 rounded-lg text-sm ${currentPage === 1 ? 'text-gray-300 dark:text-slate-600 cursor-not-allowed' : 'text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700'}">
                            <i data-lucide="chevron-left" class="w-4 h-4"></i>
                        </button>
                        ${pageNumbers.map(p => `
                            <button onclick="loadQuestions(${p})"
                                class="px-3 py-1.5 rounded-lg text-sm ${p === currentPage ? 'bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300 font-medium' : 'text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700'}">
                                ${p}
                            </button>
                        `).join('')}
                        ${totalPages > 10 ? `<span class="text-gray-400 dark:text-slate-500">...</span><span class="text-sm text-gray-500 dark:text-slate-400">${totalPages}</span>` : ''}
                        <button onclick="loadQuestions(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}
                            class="px-3 py-1.5 rounded-lg text-sm ${currentPage === totalPages ? 'text-gray-300 dark:text-slate-600 cursor-not-allowed' : 'text-gray-600 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-700'}">
                            <i data-lucide="chevron-right" class="w-4 h-4"></i>
                        </button>
                    </div>
                `;
            }

            container.innerHTML = questionsList + paginationHtml;
            lucide.createIcons();
        }

        function renderCourses() {
            const container = document.getElementById('courses-list');
            if (!courses.length) {
                container.innerHTML = `<div class="col-span-full text-center py-12 text-gray-400 dark:text-slate-500">
                    <p>No courses yet. Create one to get started.</p>
                </div>`;
                return;
            }
            container.innerHTML = courses.map(c => {
                const isOwner = c.is_owner;
                const isShared = c.is_shared;
                const ownerBadge = isOwner
                    ? `<span class="badge bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 text-xs">Owner</span>`
                    : isShared
                        ? `<span class="badge bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 text-xs">Shared by ${escapeHtml(c.owner_username || 'unknown')}</span>`
                        : '';
                const shareBtn = isOwner
                    ? `<button onclick="event.stopPropagation(); openShareModal('course', '${c.code}')" class="p-1.5 rounded-lg hover:bg-sky-100 dark:hover:bg-sky-900/50 text-gray-400 hover:text-sky-600" title="Share course">
                        <i data-lucide="share-2" class="w-4 h-4"></i>
                    </button>`
                    : '';
                return `
                <div class="card p-6 cursor-pointer group" onclick="filterByCourse('${c.code}')">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2">
                            <span class="badge bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300">${c.code}</span>
                            ${ownerBadge}
                        </div>
                        <div class="flex items-center gap-1">
                            ${shareBtn}
                            <span class="text-2xl font-bold text-gray-900 dark:text-white">${c.question_count || 0}</span>
                        </div>
                    </div>
                    <h3 class="font-semibold text-gray-900 dark:text-white mb-1">${escapeHtml(c.name)}</h3>
                    <p class="text-sm text-gray-500 dark:text-slate-400 line-clamp-2">${escapeHtml(c.description || 'No description')}</p>
                </div>
            `}).join('');
            lucide.createIcons();
        }

        function renderExamQuestions(questions) {
            const container = document.getElementById('exam-questions-list');
            container.innerHTML = questions.map(q => {
                const hasMultipleVariants = q.block_types && q.block_types.length > 1;
                const blockVariantsJson = q.block_types ? escapeHtml(JSON.stringify(q.block_types)) : '';
                return `
                <label class="exam-question-row flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors ${selectedQuestions.has(q.id) ? 'bg-sky-50 dark:bg-sky-900/30 ring-1 ring-sky-200 dark:ring-sky-700' : ''}"
                    data-question-id="${q.id}"
                    data-original-text="${escapeHtml(q.text)}"
                    data-original-points="${parseInt(q.points)}"
                    ${blockVariantsJson ? `data-block-variants="${blockVariantsJson}"` : ''}>
                    <input type="checkbox" class="mt-1 w-4 h-4 rounded text-sky-600" ${selectedQuestions.has(q.id) ? 'checked' : ''} onchange="toggleQuestion(${q.id}, ${q.points}, this.checked)">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1 flex-wrap">
                            ${q.block_types ? q.block_types.map((v, i) => `<span class="badge ${getTypeBadgeClass(v.type)} text-xs ${hasMultipleVariants ? 'cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-sky-400' : ''}" ${hasMultipleVariants ? `onmouseenter="previewExamBlockVariant(event, ${i})" onmouseleave="resetExamBlockPreview(event)"` : ''}>${formatType(v.type)}</span>`).join('') : `<span class="badge ${getTypeBadgeClass(q.question_type)} text-xs">${formatType(q.question_type)}</span>`}
                            ${q.block_name ? `<span class="badge bg-orange-100 dark:bg-orange-900/50 text-orange-700 dark:text-orange-300 text-xs flex items-center gap-1" title="Block: ${escapeHtml(q.block_name)} (${q.block_variant_count} variants)"><i data-lucide="layers" class="w-3 h-3"></i>${q.block_variant_count}v</span>` : ''}
                            <span class="exam-question-points text-xs text-gray-400 dark:text-slate-500">${parseInt(q.points)} pts</span>
                        </div>
                        <p class="exam-question-text text-sm text-gray-700 dark:text-slate-300 line-clamp-2">${escapeHtml(q.text)}</p>
                        ${q.block_name ? `<p class="text-xs text-orange-600 dark:text-orange-400 mt-1">${escapeHtml(q.block_name)}</p>` : ''}
                    </div>
                </label>
            `}).join('');
            lucide.createIcons();
        }

        function updateCourseFilters() {
            const options = '<option value="">All Courses</option>' + courses.map(c => `<option value="${c.code}">${c.code}</option>`).join('');
            const filterCourse = document.getElementById('filter-course');
            const examFilterCourse = document.getElementById('exam-filter-course');
            if (filterCourse) filterCourse.innerHTML = options;
            if (examFilterCourse) examFilterCourse.innerHTML = options;
        }

        function updateBankSelect() {
            document.getElementById('q-bank').innerHTML = '<option value="">Select a bank...</option>' +
                banks.map(b => `<option value="${b.id}">${b.course_code}/${b.name}</option>`).join('');
        }

        // New Bank Form (inline in question modal)
        function showNewBankForm() {
            const form = document.getElementById('new-bank-form');
            const courseSelect = document.getElementById('new-bank-course');
            // Populate course dropdown
            courseSelect.innerHTML = '<option value="">Select course...</option>' +
                courses.map(c => `<option value="${c.id}">${c.code}</option>`).join('');
            form.classList.remove('hidden');
            lucide.createIcons();
        }

        function hideNewBankForm() {
            document.getElementById('new-bank-form').classList.add('hidden');
            document.getElementById('new-bank-name').value = '';
        }

        async function createNewBank() {
            const courseId = document.getElementById('new-bank-course').value;
            const name = document.getElementById('new-bank-name').value.trim();

            if (!courseId) return alert('Please select a course');
            if (!name) return alert('Please enter a bank name');

            try {
                const newBank = await api('banks/', 'POST', { course: courseId, name });
                // Reload banks and select the new one
                await loadBanks();
                document.getElementById('q-bank').value = newBank.id;
                hideNewBankForm();
            } catch (err) {
                alert('Failed to create bank: ' + (err.message || err));
            }
        }

        // New Course Form (nested in new bank form)
        function showNewCourseForm() {
            document.getElementById('new-course-form').classList.remove('hidden');
            lucide.createIcons();
        }

        function hideNewCourseForm() {
            document.getElementById('new-course-form').classList.add('hidden');
            document.getElementById('new-course-code').value = '';
            document.getElementById('new-course-name').value = '';
        }

        async function createNewCourse() {
            const code = document.getElementById('new-course-code').value.trim();
            const name = document.getElementById('new-course-name').value.trim();

            if (!code) return alert('Please enter a course code');

            try {
                const newCourse = await api('courses/', 'POST', { code, name: name || code });
                // Reload courses and update the course dropdown
                await loadCourses();
                // Update the new-bank-course dropdown and select the new course
                const courseSelect = document.getElementById('new-bank-course');
                courseSelect.innerHTML = '<option value="">Select course...</option>' +
                    courses.map(c => `<option value="${c.id}">${c.code}</option>`).join('');
                courseSelect.value = newCourse.id;
                hideNewCourseForm();
            } catch (err) {
                alert('Failed to create course: ' + (err.message || err));
            }
        }

        // Question Modal
        async function openNewQuestion() {
            editingQuestionId = null;
            window.currentQuestion = null;
            window.linkedQuestions = [];
            window.blockVariants = [];
            // Clear images gallery
            loadQuestionImages(null);
            document.getElementById('modal-title').textContent = 'New Question';
            document.getElementById('delete-btn').classList.add('hidden');
            document.getElementById('linked-tabs').classList.add('hidden');
            document.getElementById('linked-tabs').innerHTML = '';
            document.getElementById('block-tabs-container').classList.add('hidden');
            document.getElementById('block-tabs').innerHTML = '';
            document.getElementById('sync-section').classList.add('hidden');
            document.getElementById('block-section').classList.add('hidden');
            document.getElementById('q-bank').value = '';
            document.getElementById('q-type').value = 'multipleChoice';
            document.getElementById('q-points').value = '2';
            document.getElementById('q-difficulty').value = 'medium';
            document.getElementById('q-tags').value = '';
            pendingEditorValue = '';
            if (editor) editor.setValue('');
            updateAnswerFields();
            showModal('question-modal');
            // Load Monaco lazily
            await loadMonaco();
        }

        async function editQuestion(id) {
            try {
                // Ensure banks are loaded before editing
                if (!banks.length) {
                    await loadBanks();
                }
                const q = await api(`questions/${id}/`);
                editingQuestionId = id;
                window.currentQuestion = q;
                document.getElementById('modal-title').textContent = 'Edit Question';
                document.getElementById('delete-btn').classList.remove('hidden');
                // Update the bank select first, then set the value
                updateBankSelect();
                document.getElementById('q-bank').value = q.question_bank;
                document.getElementById('q-type').value = q.question_type;
                document.getElementById('q-points').value = q.points;
                document.getElementById('q-difficulty').value = q.difficulty;
                document.getElementById('q-tags').value = (q.tags || []).map(t => t.name).join(', ');
                pendingEditorValue = q.text;
                updateAnswerFields(q.answer_data);
                // Update block section
                updateBlockSection(q);
                // Load and display linked questions (don't await - let it update in background)
                updateLinkedSection(q);
                // Load images for this question
                loadQuestionImages(id);
                // Ensure modal stays visible
                showModal('question-modal');
                // Load Monaco lazily then set value
                await loadMonaco();
                if (editor) editor.setValue(pendingEditorValue || '');
            } catch (err) {
                console.error('Error editing question:', err);
            }
        }

        async function updateBlockSection(q) {
            const blockSection = document.getElementById('block-section');
            const blockTabsContainer = document.getElementById('block-tabs-container');
            const blockTabs = document.getElementById('block-tabs');
            const blockTabsLabel = document.getElementById('block-tabs-label');

            if (q.block && q.block_name) {
                // Show block info
                blockSection.classList.remove('hidden');
                document.getElementById('block-max-display').textContent = `Exam will pick ${q.block_max_questions} of ${q.block_variant_count} variants from "${q.block_name}"`;
                lucide.createIcons();

                // Fetch variants and show tabs
                const variants = await api(`blocks/${q.block}/questions/`);
                window.blockVariants = variants;

                if (variants.length > 1) {
                    blockTabsContainer.classList.remove('hidden');
                    blockTabsLabel.textContent = `${q.block_name} (pick ${q.block_max_questions})`;

                    blockTabs.innerHTML = variants.map((v, idx) => {
                        const isActive = v.id === q.id;
                        return `
                            <button
                                onclick="event.stopPropagation(); switchToVariant(${v.id})"
                                class="px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                                    isActive
                                        ? 'bg-orange-500 text-white shadow-sm'
                                        : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600'
                                }"
                                title="${escapeHtml(v.text.substring(0, 80))}"
                            >
                                V${idx + 1}
                            </button>
                        `;
                    }).join('');
                    lucide.createIcons();
                } else {
                    blockTabsContainer.classList.add('hidden');
                }
            } else {
                blockSection.classList.add('hidden');
                blockTabsContainer.classList.add('hidden');
                blockTabs.innerHTML = '';
            }
        }

        async function switchToVariant(questionId) {
            // Switch to variant - just update the current modal
            await editQuestion(questionId);
        }

        async function addBlockVariant() {
            if (!window.currentQuestion?.block) return;
            const q = window.currentQuestion;

            // Create a copy of the question in the same block
            const newQuestion = {
                question_bank: q.question_bank,
                question_type: q.question_type,
                text: q.text + '\n\n<!-- New variant - edit this question -->',
                points: q.points,
                difficulty: q.difficulty,
                answer_data: q.answer_data,
                block: q.block,
            };

            try {
                const created = await api('questions/', 'POST', newQuestion);
                // Switch to the new variant
                await editQuestion(created.id);
            } catch (err) {
                console.error('Failed to create variant:', err);
                alert('Failed to create variant');
            }
        }

        async function aiBlockVariant() {
            if (!window.currentQuestion?.block) return;
            const q = window.currentQuestion;

            // Show a loading state
            const btn = event.target.closest('button');
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i> Generating...';
            btn.disabled = true;
            lucide.createIcons();

            try {
                // Call AI to generate a variant
                const response = await api('ai/generate-variant/', 'POST', {
                    question_id: q.id,
                    block_id: q.block,
                });

                if (response.id) {
                    // Switch to the new AI-generated variant
                    await editQuestion(response.id);
                } else if (response.error) {
                    alert('AI generation failed: ' + response.error);
                }
            } catch (err) {
                console.error('AI variant generation failed:', err);
                alert('Failed to generate AI variant. Make sure an API key is configured.');
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
                lucide.createIcons();
            }
        }

        async function updateLinkedSection(q) {
            const linkedTabs = document.getElementById('linked-tabs');
            const syncSection = document.getElementById('sync-section');

            // Fetch linked questions if any
            const linked = await api(`questions/${q.id}/linked/`);
            window.linkedQuestions = linked;

            if (linked.length > 1) {
                linkedTabs.classList.remove('hidden');
                linkedTabs.innerHTML = linked.map(lq => {
                    const isActive = lq.id === q.id;
                    const isCanonical = !lq.canonical;
                    return `
                        <button
                            onclick="event.stopPropagation(); switchToLinked(${lq.id})"
                            class="px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                                isActive
                                    ? 'bg-sky-500 text-white shadow-sm'
                                    : 'bg-gray-100 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-200 dark:hover:bg-slate-600'
                            }"
                        >
                            ${isCanonical ? '<i data-lucide="star" class="w-3 h-3 inline mr-1"></i>' : ''}${lq.course_code}/${lq.bank_name}
                        </button>
                    `;
                }).join('');
                lucide.createIcons();

                // Show sync button if this is not the canonical question
                if (q.canonical) {
                    syncSection.classList.remove('hidden');
                } else {
                    syncSection.classList.add('hidden');
                }
            } else {
                linkedTabs.classList.add('hidden');
                linkedTabs.innerHTML = '';
                syncSection.classList.add('hidden');
            }
        }

        async function switchToLinked(questionId) {
            // Check if we already have the linked question data cached
            const cachedQuestion = window.linkedQuestions?.find(q => q.id === questionId);
            if (cachedQuestion) {
                // Quick switch - reuse cached data for tabs
                await editQuestion(questionId);
            } else {
                await editQuestion(questionId);
            }
        }

        async function syncFromCanonical() {
            if (!window.currentQuestion?.canonical) return;
            if (!confirm('This will overwrite this question with the canonical version. Continue?')) return;
            await api(`questions/${editingQuestionId}/sync/`, 'POST');
            await editQuestion(editingQuestionId);
        }

        async function saveQuestion() {
            const data = {
                question_bank: parseInt(document.getElementById('q-bank').value),
                question_type: document.getElementById('q-type').value,
                text: editor?.getValue() || '',
                points: parseFloat(document.getElementById('q-points').value),
                difficulty: document.getElementById('q-difficulty').value,
                answer_data: getAnswerData(),
            };
            if (!data.question_bank) return alert('Please select a question bank');
            if (editingQuestionId) await api(`questions/${editingQuestionId}/`, 'PUT', data);
            else await api('questions/', 'POST', data);
            closeModal();
            await loadQuestions();
        }

        async function deleteQuestion() {
            if (!confirm('Delete this question?')) return;
            await api(`questions/${editingQuestionId}/`, 'DELETE');
            closeModal();
            await loadQuestions();
        }

        function updateAnswerFields(data = {}) {
            const type = document.getElementById('q-type').value;
            const container = document.getElementById('answer-fields');
            if (type === 'multipleChoice') {
                container.innerHTML = `<div class="space-y-3">
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Correct Answer</label>
                    <input type="text" id="a-correct" value="${data.correct || ''}" class="input-modern w-full px-3 py-2 rounded-lg"></div>
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Wrong Answers (one per line)</label>
                    <textarea id="a-wrong" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${(data.wrong || []).join('\n')}</textarea></div>
                </div>`;
            } else if (type === 'trueFalse') {
                container.innerHTML = `<div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Correct Answer</label>
                <div class="flex gap-6"><label class="flex items-center gap-2"><input type="radio" name="tf" value="true" ${data.correct === true ? 'checked' : ''} class="w-4 h-4 text-sky-600"><span class="text-gray-900 dark:text-white">True</span></label>
                <label class="flex items-center gap-2"><input type="radio" name="tf" value="false" ${data.correct === false ? 'checked' : ''} class="w-4 h-4 text-sky-600"><span class="text-gray-900 dark:text-white">False</span></label></div></div>`;
            } else if (type === 'shortAnswer') {
                const lineLength = data.lineLength || '';
                container.innerHTML = `<div class="space-y-3">
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution</label>
                    <textarea id="a-solution" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${data.solution || ''}</textarea></div>
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Answer Line Length</label>
                    <select id="a-lineLength" class="input-modern w-full px-3 py-2 rounded-lg">
                        <option value="" ${lineLength === '' ? 'selected' : ''}>Inherit from exam settings</option>
                        <option value="1in" ${lineLength === '1in' ? 'selected' : ''}>1 inch</option>
                        <option value="2in" ${lineLength === '2in' ? 'selected' : ''}>2 inches</option>
                        <option value="3in" ${lineLength === '3in' ? 'selected' : ''}>3 inches</option>
                        <option value="4in" ${lineLength === '4in' ? 'selected' : ''}>4 inches</option>
                        <option value="5in" ${lineLength === '5in' ? 'selected' : ''}>5 inches</option>
                        <option value="\\linewidth" ${lineLength === '\\linewidth' ? 'selected' : ''}>Full width</option>
                    </select>
                    <p class="text-xs text-gray-400 dark:text-slate-500 mt-1">Leave as "Inherit" to use the exam's default line length</p></div>
                </div>`;
            } else if (type === 'longAnswer') {
                const solutionSpace = data.solutionSpace || '';
                container.innerHTML = `<div class="space-y-3">
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution</label>
                    <textarea id="a-solution" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${data.solution || ''}</textarea></div>
                    <div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution Space</label>
                    <select id="a-solutionSpace" class="input-modern w-full px-3 py-2 rounded-lg">
                        <option value="" ${solutionSpace === '' ? 'selected' : ''}>Inherit from exam settings</option>
                        <option value="1in" ${solutionSpace === '1in' ? 'selected' : ''}>1 inch</option>
                        <option value="1.5in" ${solutionSpace === '1.5in' ? 'selected' : ''}>1.5 inches</option>
                        <option value="2in" ${solutionSpace === '2in' ? 'selected' : ''}>2 inches</option>
                        <option value="3in" ${solutionSpace === '3in' ? 'selected' : ''}>3 inches</option>
                        <option value="4in" ${solutionSpace === '4in' ? 'selected' : ''}>4 inches</option>
                        <option value="\\stretch{1}" ${solutionSpace === '\\stretch{1}' ? 'selected' : ''}>Fill page</option>
                    </select>
                    <p class="text-xs text-gray-400 dark:text-slate-500 mt-1">Leave as "Inherit" to use the exam's default solution space</p></div>
                </div>`;
            } else {
                container.innerHTML = `<div><label class="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">Solution</label>
                <textarea id="a-solution" rows="3" class="input-modern w-full px-3 py-2 rounded-lg">${data.solution || ''}</textarea></div>`;
            }
        }

        function getAnswerData() {
            const type = document.getElementById('q-type').value;
            if (type === 'multipleChoice') return { correct: document.getElementById('a-correct').value, wrong: document.getElementById('a-wrong').value.split('\n').filter(x => x.trim()) };
            if (type === 'trueFalse') return { correct: document.querySelector('input[name="tf"]:checked')?.value === 'true' };
            if (type === 'shortAnswer') {
                const data = { solution: document.getElementById('a-solution')?.value || '' };
                const lineLength = document.getElementById('a-lineLength')?.value;
                if (lineLength) data.lineLength = lineLength;
                return data;
            }
            if (type === 'longAnswer') {
                const data = { solution: document.getElementById('a-solution')?.value || '' };
                const solutionSpace = document.getElementById('a-solutionSpace')?.value;
                if (solutionSpace) data.solutionSpace = solutionSpace;
                return data;
            }
            return { solution: document.getElementById('a-solution')?.value || '' };
        }

        // Course Modal
        function openNewCourse() {
            document.getElementById('c-code').value = '';
            document.getElementById('c-name').value = '';
            document.getElementById('c-description').value = '';
            showModal('course-modal');
        }

        async function saveCourse() {
            await api('courses/', 'POST', {
                code: document.getElementById('c-code').value,
                name: document.getElementById('c-name').value,
                description: document.getElementById('c-description').value,
            });
            closeCourseModal();
            await loadCourses();
        }

        function closeCourseModal() { hideModal('course-modal'); }

        // Exam Templates
        let examTemplates = [];
        let currentTemplateId = null;

        let currentTemplateFilter = ''; // Track current quiz filter

        async function loadExamTemplates(isQuiz = '') {
            currentTemplateFilter = isQuiz;
            const params = new URLSearchParams();
            if (isQuiz !== '') params.append('is_quiz', isQuiz);
            const data = await api(`exams/templates/?${params.toString()}`);
            examTemplates = data.results || data || [];

            // Populate course dropdown with ALL courses (from global courses array)
            const courseSelector = document.getElementById('template-course-selector');
            let courseHtml = '<option value="">All Courses</option>';
            (courses || []).forEach(c => {
                courseHtml += `<option value="${c.code}">${c.code}</option>`;
            });
            courseSelector.innerHTML = courseHtml;

            // Populate template dropdown (all templates initially)
            filterTemplatesByCourse('');
        }

        function filterTemplatesByCourse(courseCode) {
            const selector = document.getElementById('template-selector');
            let html = '<option value="">Select a template...</option>';

            const filtered = courseCode
                ? examTemplates.filter(t => (t.course_code || 'No Course') === courseCode)
                : examTemplates;

            filtered.forEach(t => {
                const typeTag = t.is_quiz ? ' [Quiz]' : '';
                const filterCount = t.filter_count || 0;
                const filterBadge = filterCount > 0 ? ` [${filterCount} filters]` : '';
                const ownerTag = t.is_owner ? '' : t.is_shared ? ` (shared by ${t.owner_username})` : '';
                html += `<option value="${t.id}">${escapeHtml(t.name)}${typeTag}${filterBadge}${ownerTag}</option>`;
            });

            selector.innerHTML = html;
        }

        async function loadExamTemplate(templateId) {
            if (!templateId) {
                currentTemplateId = null;
                document.getElementById('delete-template-btn').classList.add('hidden');
                document.getElementById('share-template-btn')?.classList.add('hidden');
                document.getElementById('copy-template-btn')?.classList.add('hidden');
                updateActiveFiltersDisplay(null);

                // Clear form fields for new template
                document.getElementById('exam-title').value = '';
                document.getElementById('exam-course').value = '';
                document.getElementById('exam-instructor').value = '';
                document.getElementById('exam-term').value = '';
                document.getElementById('exam-instructions').value = '';
                document.getElementById('exam-shuffle').checked = true;
                document.getElementById('exam-answers').checked = false;
                document.getElementById('exam-line-length').value = '3in';
                document.getElementById('exam-solution-space').value = '1.5in';
                document.getElementById('exam-quiz-mode').checked = false;
                document.getElementById('exam-include-id').checked = true;
                document.getElementById('exam-split-mc').checked = false;
                toggleQuizModeOptions();

                // Clear sections
                examSections = [];
                sectionIdCounter = 0;
                renderExamSections();

                // Clear preview
                const previewContainer = document.getElementById('exam-preview');
                if (previewContainer) {
                    previewContainer.innerHTML = '<div class="text-center py-8 text-gray-400"><p>Add sections and questions to see preview</p></div>';
                }

                return;
            }

            // Show loading indicator in preview
            const previewContainer = document.getElementById('exam-preview');
            if (previewContainer) {
                previewContainer.innerHTML = '<div class="text-center py-6"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto text-sky-500"></i><p class="text-sm text-gray-500 mt-2">Loading template...</p></div>';
                lucide.createIcons();
            }

            try {
            // Fetch full template details
            const template = await api(`exams/templates/${templateId}/`);
            if (!template) {
                previewContainer.innerHTML = '<div class="text-center py-6 text-red-500">Failed to load template</div>';
                return;
            }

            currentTemplateId = templateId;

            // Clear question cache when loading a new template
            cachedSectionQuestions = {};
            cachedFinalQuestions = null;
            hasCachedQuestions = false;
            // Don't clear localStorage here - we want to restore previous selection

            // Show template action buttons based on ownership
            const isOwner = template.is_owner;
            document.getElementById('delete-template-btn').classList.toggle('hidden', !isOwner);
            document.getElementById('share-template-btn')?.classList.toggle('hidden', !isOwner);
            // Show copy button for everyone (owners and shared users)
            document.getElementById('copy-template-btn')?.classList.remove('hidden');

            // Fill in the form fields
            document.getElementById('exam-title').value = template.name || '';
            document.getElementById('exam-course').value = template.course_code || '';
            document.getElementById('exam-instructor').value = template.instructor || '';
            document.getElementById('exam-term').value = template.term || '';
            document.getElementById('exam-instructions').value = template.instructions || '';
            document.getElementById('exam-shuffle').checked = template.shuffle_questions ?? true;
            document.getElementById('exam-answers').checked = false;

            // Answer formatting settings
            const lineLengthSelect = document.getElementById('exam-line-length');
            if (lineLengthSelect && template.default_line_length) {
                lineLengthSelect.value = template.default_line_length;
            }
            const solutionSpaceSelect = document.getElementById('exam-solution-space');
            if (solutionSpaceSelect && template.default_solution_space) {
                solutionSpaceSelect.value = template.default_solution_space;
            }

            // Quiz mode settings
            const quizModeCheckbox = document.getElementById('exam-quiz-mode');
            if (quizModeCheckbox) {
                quizModeCheckbox.checked = template.is_quiz || false;
                toggleQuizModeOptions();
            }
            const includeIdCheckbox = document.getElementById('exam-include-id');
            if (includeIdCheckbox) {
                includeIdCheckbox.checked = template.include_id_field ?? true;
            }

            // Template-level point constraints
            document.getElementById('exam-max-points').value = template.max_points || '';
            document.getElementById('exam-max-mc-points').value = template.max_mc_points || '';
            document.getElementById('exam-max-tf-points').value = template.max_tf_points || '';
            document.getElementById('exam-max-short-points').value = template.max_short_points || '';
            document.getElementById('exam-max-long-points').value = template.max_long_points || '';

            // Load sections from selection_rules
            examSections = [];
            sectionIdCounter = 0;

            if (template.selection_rules) {
                // Load include_answers and versions if present
                if (template.selection_rules.include_answers !== undefined) {
                    document.getElementById('exam-answers').checked = template.selection_rules.include_answers;
                }
                if (template.selection_rules.versions !== undefined) {
                    document.getElementById('exam-versions').value = template.selection_rules.versions;
                }

                // Check if it's the new object format with sections property
                const sectionsData = template.selection_rules.sections ||
                    (Array.isArray(template.selection_rules) ? template.selection_rules : null);

                if (sectionsData && Array.isArray(sectionsData) && sectionsData.length > 0) {
                    for (const rule of sectionsData) {
                        const id = ++sectionIdCounter;
                        examSections.push({
                            id,
                            name: rule.name || `Section ${id}`,
                            course: rule.course || template.course_code || '',
                            tags: rule.tags || [],
                            type: rule.type || '',
                            count: rule.count || 5,
                            maxPoints: rule.maxPoints || null,
                            maxMCPoints: rule.maxMCPoints || null,
                            maxTFPoints: rule.maxTFPoints || null,
                            maxShortPoints: rule.maxShortPoints || null,
                            maxLongPoints: rule.maxLongPoints || null,
                            questions: []
                        });
                    }
                }
                // Check if it's the old INI-based format (include_files)
                else if (template.selection_rules.include_files && Array.isArray(template.selection_rules.include_files) && template.selection_rules.include_files.length > 0) {
                    // Convert include_files to tags (e.g., "quizPool/week1.txt" -> "Week 1")
                    const tagSet = new Set();
                    template.selection_rules.include_files.forEach(file => {
                        const match = file.match(/week(\d+)/i);
                        if (match) {
                            tagSet.add(`Week ${match[1]}`);
                        } else {
                            // Try to extract a reasonable tag name from basename
                            const basename = file.split('/').pop().replace('.txt', '');
                            if (basename) tagSet.add(basename);
                        }
                    });
                    const tags = Array.from(tagSet);

                    if (tags.length > 0) {
                        const id = ++sectionIdCounter;
                        examSections.push({
                            id,
                            name: 'Main',
                            course: template.course_code || '',
                            tags: tags,
                            type: '',
                            count: 10,
                            questions: []
                        });
                    }
                }
            }

            // If still no sections but we have filter_tags, create a section from those
            if (examSections.length === 0 && template.filter_tags_data && template.filter_tags_data.length > 0) {
                const id = ++sectionIdCounter;
                examSections.push({
                    id,
                    name: 'Filtered Questions',
                    course: template.course_code || '',
                    tags: template.filter_tags_data.map(t => t.name),
                    type: template.filter_question_types?.[0] || '',
                    count: 10,
                    questions: []
                });
            }

            // Always render sections (even if empty, to clear previous sections)
            renderExamSections();
            if (examSections.length > 0) {
                await refreshExamPreview();
            } else {
                // Clear preview if no sections
                const previewContainer = document.getElementById('exam-preview');
                if (previewContainer) {
                    previewContainer.innerHTML = '<div class="text-center py-8 text-gray-400"><p>No sections defined. Add sections to build your exam.</p></div>';
                }
            }

            // Update active filters display
            updateActiveFiltersDisplay(template);

            lucide.createIcons();
            saveViewState();
            } catch (err) {
                console.error('Error loading template:', err);
                alert('Error loading template: ' + err.message);
            }
        }

        function updateActiveFiltersDisplay(template) {
            const container = document.getElementById('active-filters');
            if (!template) {
                container.classList.add('hidden');
                return;
            }

            const filters = [];
            if (template.filter_weeks && template.filter_weeks.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded">${template.filter_weeks.length} week(s)</span>`);
            }
            if (template.filter_question_types && template.filter_question_types.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded">${template.filter_question_types.map(formatType).join(', ')}</span>`);
            }
            if (template.filter_banks_data && template.filter_banks_data.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300 rounded">${template.filter_banks_data.length} bank(s)</span>`);
            }
            if (template.filter_tags_data && template.filter_tags_data.length > 0) {
                filters.push(`<span class="px-2 py-1 bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 rounded">${template.filter_tags_data.map(t => t.name).join(', ')}</span>`);
            }
            if (template.filter_difficulty) {
                filters.push(`<span class="px-2 py-1 bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 rounded">${template.filter_difficulty}</span>`);
            }
            if (template.max_questions) {
                filters.push(`<span class="px-2 py-1 bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300 rounded">max ${template.max_questions} questions</span>`);
            }

            if (filters.length > 0) {
                container.innerHTML = '<span class="text-gray-500 dark:text-slate-400">Active filters:</span>' + filters.join('');
                container.classList.remove('hidden');
            } else {
                container.classList.add('hidden');
            }
        }

        async function saveAsTemplate() {
            const title = document.getElementById('exam-title').value.trim();
            const courseCode = document.getElementById('exam-course').value.trim();

            if (!title) {
                alert('Please enter an exam title to save as template');
                return;
            }
            if (!courseCode) {
                alert('Please enter a course code');
                return;
            }

            // Find the course ID from the course code
            const course = courses.find(c => c.code === courseCode);
            if (!course) {
                alert(`Course "${courseCode}" not found. Please enter a valid course code.`);
                return;
            }

            // Save sections as selection_rules
            const sectionsToSave = examSections.map(s => ({
                name: s.name,
                course: s.course,
                tags: s.tags,
                type: s.type,
                count: s.count,
                maxPoints: s.maxPoints || null,
                maxMCPoints: s.maxMCPoints || null,
                maxTFPoints: s.maxTFPoints || null,
                maxShortPoints: s.maxShortPoints || null,
                maxLongPoints: s.maxLongPoints || null
            }));

            const templateData = {
                name: title,
                course: course.id,
                instructor: document.getElementById('exam-instructor').value || '',
                term: document.getElementById('exam-term').value || '',
                instructions: document.getElementById('exam-instructions').value || '',
                shuffle_questions: document.getElementById('exam-shuffle').checked,
                shuffle_answers: document.getElementById('exam-shuffle-answers')?.checked ?? true,
                is_quiz: document.getElementById('exam-quiz-mode')?.checked || false,
                include_id_field: document.getElementById('exam-include-id')?.checked || false,
                default_line_length: document.getElementById('exam-line-length')?.value || '3in',
                default_solution_space: document.getElementById('exam-solution-space')?.value || '1.5in',
                selection_rules: {
                    sections: sectionsToSave,
                    include_answers: document.getElementById('exam-answers')?.checked || false,
                    versions: parseInt(document.getElementById('exam-versions')?.value) || 1
                },
                // Template-level point constraints
                max_points: parseFloat(document.getElementById('exam-max-points')?.value) || null,
                max_mc_points: parseFloat(document.getElementById('exam-max-mc-points')?.value) || null,
                max_tf_points: parseFloat(document.getElementById('exam-max-tf-points')?.value) || null,
                max_short_points: parseFloat(document.getElementById('exam-max-short-points')?.value) || null,
                max_long_points: parseFloat(document.getElementById('exam-max-long-points')?.value) || null,
            };

            try {
                let result;
                if (currentTemplateId) {
                    // Update existing template
                    if (!confirm('Update the existing template with current settings?')) return;
                    result = await api(`exams/templates/${currentTemplateId}/`, 'PUT', templateData);
                } else {
                    // Create new template
                    result = await api('exams/templates/', 'POST', templateData);
                }

                if (result.id) {
                    currentTemplateId = result.id;
                    await loadExamTemplates('');
                    document.getElementById('template-selector').value = result.id;
                    document.getElementById('delete-template-btn').classList.remove('hidden');
                    alert(currentTemplateId ? 'Template updated!' : 'Template saved!');
                }
            } catch (err) {
                console.error('Failed to save template:', err);
                alert('Failed to save template. Please try again.');
            }
        }

        async function deleteCurrentTemplate() {
            if (!currentTemplateId) return;
            if (!confirm('Delete this template? This cannot be undone.')) return;

            try {
                await api(`exams/templates/${currentTemplateId}/`, 'DELETE');
                currentTemplateId = null;
                document.getElementById('template-selector').value = '';
                document.getElementById('delete-template-btn').classList.add('hidden');
                updateActiveFiltersDisplay(null);
                await loadExamTemplates('');
                alert('Template deleted.');
            } catch (err) {
                console.error('Failed to delete template:', err);
                alert('Failed to delete template.');
            }
        }

        // New Template Modal
        function openNewTemplateModal() {
            // Populate course dropdown
            const courseSelect = document.getElementById('new-template-course');
            courseSelect.innerHTML = '<option value="">Select a course...</option>';
            for (const course of courses) {
                courseSelect.innerHTML += `<option value="${course.id}" data-code="${course.code}">${course.code} - ${course.name}</option>`;
            }

            // Clear form fields
            document.getElementById('new-template-name').value = '';
            document.getElementById('new-template-instructor').value = '';
            document.getElementById('new-template-term').value = '';
            document.querySelector('input[name="new-template-type"][value="exam"]').checked = true;

            showModal('new-template-modal');
        }

        async function createNewTemplate() {
            const name = document.getElementById('new-template-name').value.trim();
            const courseSelect = document.getElementById('new-template-course');
            const courseId = courseSelect.value;
            const courseCode = courseSelect.selectedOptions[0]?.dataset?.code || '';
            const isQuiz = document.querySelector('input[name="new-template-type"]:checked').value === 'quiz';
            const instructor = document.getElementById('new-template-instructor').value.trim();
            const term = document.getElementById('new-template-term').value.trim();

            if (!name) {
                alert('Please enter a template name');
                return;
            }
            if (!courseId) {
                alert('Please select a course');
                return;
            }

            const templateData = {
                name,
                course: courseId,
                is_quiz: isQuiz,
                instructor,
                term,
                shuffle_questions: true,
                include_id_field: true,
                default_line_length: '3in',
                default_solution_space: '1.5in',
                selection_rules: [],
            };

            try {
                const result = await api('exams/templates/', 'POST', templateData);
                if (result.id) {
                    hideModal('new-template-modal');
                    await loadExamTemplates('');
                    document.getElementById('template-selector').value = result.id;
                    await loadExamTemplate(result.id);
                    alert('Template created! Now add sections to define which questions to include.');
                }
            } catch (err) {
                console.error('Failed to create template:', err);
                alert('Failed to create template. Please try again.');
            }
        }

        // Exam Builder
        function toggleQuestion(id, points, checked) {
            if (checked) selectedQuestions.add(id);
            else selectedQuestions.delete(id);
            updateExamStats();
            loadExamQuestions(); // re-render to update visual state
        }

        function updateExamStats() {
            document.getElementById('selected-count').textContent = selectedQuestions.size;
            // Calculate total points from current exam questions
            const totalPoints = currentExamQuestions.reduce((sum, q) => sum + (parseFloat(q.points) || 0), 0);
            document.getElementById('selected-points').textContent = totalPoints;
            // Update target indicator
            updateTargetIndicator();
        }

        // Update the target indicator to show if we're above/below target
        function updateTargetIndicator() {
            const indicator = document.getElementById('target-indicator');
            const targetInput = document.getElementById('target-points');
            const pointsEl = document.getElementById('selected-points');

            if (!indicator || !targetInput || !pointsEl) return;

            const target = parseFloat(targetInput.value) || 0;
            const current = parseFloat(pointsEl.textContent) || 0;

            if (target <= 0) {
                indicator.classList.add('hidden');
                return;
            }

            indicator.classList.remove('hidden');
            const diff = current - target;
            const percent = Math.round((current / target) * 100);

            if (diff >= 0) {
                // At or above target
                indicator.className = 'mb-4 p-2 rounded-lg text-sm font-medium text-center bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300';
                indicator.innerHTML = `<i data-lucide="check-circle" class="w-4 h-4 inline mr-1"></i>${percent}% of target (+${diff} pts)`;
            } else {
                // Below target
                indicator.className = 'mb-4 p-2 rounded-lg text-sm font-medium text-center bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300';
                indicator.innerHTML = `<i data-lucide="alert-circle" class="w-4 h-4 inline mr-1"></i>${percent}% of target (${diff} pts)`;
            }
            lucide.createIcons();
        }

        // Balance the exam to meet the target points
        async function balanceForTarget() {
            const targetInput = document.getElementById('target-points');
            const target = parseFloat(targetInput.value) || 0;

            if (target <= 0) {
                alert('Please set a target points value first.');
                return;
            }

            const currentPoints = currentExamQuestions.reduce((sum, q) => sum + (parseFloat(q.points) || 0), 0);

            if (currentPoints >= target) {
                // Already at or above target - maybe remove some questions
                const sortedByPoints = [...currentExamQuestions].sort((a, b) => (parseFloat(a.points) || 0) - (parseFloat(b.points) || 0));
                let newTotal = currentPoints;
                let removed = 0;

                while (newTotal > target * 1.1 && sortedByPoints.length > 0) {
                    const q = sortedByPoints.pop(); // Remove highest point question
                    newTotal -= (parseFloat(q.points) || 0);
                    removeQuestionFromExam(q.id);
                    removed++;
                }

                if (removed > 0) {
                    showToast(`Removed ${removed} question(s) to reduce points closer to target`, 'success');
                } else {
                    showToast('Already at target - no changes made', 'info');
                }
            } else {
                // Need more questions - try to add from available pool
                // Get questions from each section that aren't already selected
                let addedCount = 0;
                let currentTotal = currentPoints;

                for (const section of examSections) {
                    if (currentTotal >= target) break;

                    const params = new URLSearchParams();
                    if (section.course) params.append('course', section.course);
                    if (section.type) params.append('type', section.type);
                    section.tags.forEach(t => params.append('tags', t));
                    params.append('page_size', 50);

                    try {
                        const data = await api(`questions/?${params.toString()}`);
                        const availableQuestions = (data.results || data || [])
                            .filter(q => !selectedQuestions.has(q.id))
                            .sort(() => Math.random() - 0.5);

                        for (const q of availableQuestions) {
                            if (currentTotal >= target) break;

                            q._section = section.name;
                            currentExamQuestions.push(q);
                            selectedQuestions.add(q.id);
                            currentTotal += (parseFloat(q.points) || 0);
                            addedCount++;
                        }
                    } catch (e) {
                        console.error('Error fetching questions for section:', section.name, e);
                    }
                }

                if (addedCount > 0) {
                    // Update the cache
                    cachedFinalQuestions = currentExamQuestions;
                    if (currentTemplateId) {
                        localStorage.setItem(`examQuestionIds_${currentTemplateId}`, JSON.stringify(currentExamQuestions.map(q => q.id)));
                    }
                    // Re-render preview
                    refreshExamPreview();
                    showToast(`Added ${addedCount} question(s) to reach target`, 'success');
                } else {
                    showToast('No additional questions available to add', 'warning');
                }
            }
        }

        // Select all visible questions in the exam builder
        function selectAllExamQuestions() {
            const questionCards = document.querySelectorAll('#exam-questions-list label[data-question-id]');
            questionCards.forEach(card => {
                const qid = parseInt(card.getAttribute('data-question-id'));
                if (qid && !selectedQuestions.has(qid)) {
                    selectedQuestions.add(qid);
                }
                // Update visual state immediately
                const checkbox = card.querySelector('input[type="checkbox"]');
                if (checkbox) checkbox.checked = true;
                card.classList.add('bg-sky-50', 'dark:bg-sky-900/30', 'ring-1', 'ring-sky-200', 'dark:ring-sky-700');
            });
            updateExamStats();
        }

        // Deselect all questions in the exam builder
        function deselectAllExamQuestions() {
            selectedQuestions.clear();
            const questionCards = document.querySelectorAll('#exam-questions-list label[data-question-id]');
            questionCards.forEach(card => {
                // Update visual state immediately
                const checkbox = card.querySelector('input[type="checkbox"]');
                if (checkbox) checkbox.checked = false;
                card.classList.remove('bg-sky-50', 'dark:bg-sky-900/30', 'ring-1', 'ring-sky-200', 'dark:ring-sky-700');
            });
            updateExamStats();
        }

        // Section-based exam builder
        let examSections = [];
        let sectionIdCounter = 0;

        function addExamSection() {
            const id = ++sectionIdCounter;
            const section = {
                id,
                name: `Section ${examSections.length + 1}`,
                course: '',
                tags: [],
                type: '',
                count: 5,
                maxPoints: null,
                maxMCPoints: null,
                maxTFPoints: null,
                maxShortPoints: null,
                maxLongPoints: null,
                questions: []
            };
            examSections.push(section);
            renderExamSections();
            saveViewState();
        }

        function removeExamSection(id) {
            examSections = examSections.filter(s => s.id !== id);
            renderExamSections();
            updateExamStats();
            saveViewState();
        }

        function renderExamSections() {
            const container = document.getElementById('exam-sections');
            if (!examSections.length) {
                container.innerHTML = `
                    <div class="text-center py-8 text-gray-400 dark:text-slate-500">
                        <i data-lucide="layout-list" class="w-10 h-10 mx-auto mb-2 opacity-50"></i>
                        <p>Click "Add Section" to start building your exam</p>
                        <p class="text-xs mt-1">Each section can have different tags and question counts</p>
                    </div>`;
                lucide.createIcons();
                return;
            }

            container.innerHTML = examSections.map((s, idx) => `
                <div class="border border-gray-200 dark:border-slate-700 rounded-xl p-4 bg-gray-50 dark:bg-slate-800/50" data-section-id="${s.id}">
                    <div class="mb-2">
                        <input type="text" value="${escapeHtml(s.name)}" onchange="updateSectionName(${s.id}, this.value)"
                            class="font-medium text-gray-900 dark:text-white bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-sky-500 rounded px-1 -ml-1 w-full">
                    </div>
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-2 flex-wrap" id="section-selected-${s.id}">
                            ${s.course ? `<span class="badge bg-sky-100 dark:bg-sky-900/50 text-sky-700 dark:text-sky-300 text-xs">${escapeHtml(s.course)}</span>` : ''}
                            ${s.tags.map(t => `<span class="badge bg-purple-100 dark:bg-purple-900/50 text-purple-700 dark:text-purple-300 text-xs">${escapeHtml(t)}</span>`).join('')}
                        </div>
                        <button onclick="removeExamSection(${s.id})" class="text-red-500 hover:text-red-700 p-1 flex-shrink-0">
                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                        </button>
                    </div>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Course</label>
                            <select onchange="updateSectionCourse(${s.id}, this.value)" class="input-modern w-full px-2 py-1.5 rounded-lg text-sm">
                                <option value="">All Courses</option>
                                ${(courses || []).map(c => `<option value="${c.code}" ${s.course === c.code ? 'selected' : ''}>${c.code}</option>`).join('')}
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Type</label>
                            <select onchange="updateSectionType(${s.id}, this.value)" class="input-modern w-full px-2 py-1.5 rounded-lg text-sm">
                                <option value="" ${!s.type ? 'selected' : ''}>All Types</option>
                                <option value="multipleChoice" ${s.type === 'multipleChoice' ? 'selected' : ''}>Multiple Choice</option>
                                <option value="trueFalse" ${s.type === 'trueFalse' ? 'selected' : ''}>True/False</option>
                                <option value="shortAnswer" ${s.type === 'shortAnswer' ? 'selected' : ''}>Short Answer</option>
                                <option value="longAnswer" ${s.type === 'longAnswer' ? 'selected' : ''}>Long Answer</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1"># Questions</label>
                            <input type="number" value="${s.count}" min="1" max="50" onchange="updateSectionCount(${s.id}, this.value)"
                                class="input-modern w-full px-2 py-1.5 rounded-lg text-sm">
                        </div>
                        <div>
                            <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Available</label>
                            <div class="px-2 py-1.5 text-sm font-medium text-sky-600" id="section-available-${s.id}">--</div>
                        </div>
                    </div>
                    <div class="mt-3">
                        <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Tags (click to select)</label>
                        <div class="flex flex-wrap gap-1" id="section-tags-${s.id}">
                            <span class="text-xs text-gray-400">Loading tags...</span>
                        </div>
                    </div>
                    <details class="mt-3">
                        <summary class="text-xs text-gray-500 dark:text-slate-400 cursor-pointer hover:text-gray-700 dark:hover:text-slate-300">
                            Point Constraints (optional)
                        </summary>
                        <div class="grid grid-cols-2 md:grid-cols-5 gap-2 mt-2 p-2 bg-gray-100 dark:bg-slate-700/50 rounded-lg">
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Max Pts</label>
                                <input type="number" value="${s.maxPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">MC Pts</label>
                                <input type="number" value="${s.maxMCPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxMCPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">T/F Pts</label>
                                <input type="number" value="${s.maxTFPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxTFPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Short Pts</label>
                                <input type="number" value="${s.maxShortPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxShortPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                            <div>
                                <label class="block text-xs text-gray-500 dark:text-slate-400 mb-1">Long Pts</label>
                                <input type="number" value="${s.maxLongPoints || ''}" min="0" placeholder="--"
                                    onchange="updateSectionConstraint(${s.id}, 'maxLongPoints', this.value)"
                                    class="input-modern w-full px-2 py-1 rounded text-xs">
                            </div>
                        </div>
                    </details>
                </div>
            `).join('');
            lucide.createIcons();

            // Load tags for each section
            examSections.forEach(s => loadSectionTags(s.id));
        }

        async function loadSectionTags(sectionId) {
            const section = examSections.find(s => s.id === sectionId);
            if (!section) return;

            let tagsData;
            if (section.course) {
                tagsData = await api(`tags/?course=${section.course}`);
            } else {
                tagsData = await api('tags/');
            }
            const tags = tagsData.results || tagsData || [];

            const container = document.getElementById(`section-tags-${sectionId}`);
            if (!container) return;

            container.innerHTML = tags.map(t => {
                const isSelected = section.tags.includes(t.name);
                return `<button type="button" onclick="toggleSectionTag(${sectionId}, '${escapeHtml(t.name)}')"
                    class="px-2 py-0.5 text-xs rounded-full transition-colors ${isSelected
                        ? 'bg-emerald-500 text-white'
                        : 'bg-gray-200 dark:bg-slate-700 text-gray-600 dark:text-slate-300 hover:bg-gray-300 dark:hover:bg-slate-600'
                    }">${escapeHtml(t.name)}</button>`;
            }).join('');

            // Update available count
            updateSectionAvailable(sectionId);
        }

        function toggleSectionTag(sectionId, tagName) {
            const section = examSections.find(s => s.id === sectionId);
            if (!section) return;

            if (section.tags.includes(tagName)) {
                section.tags = section.tags.filter(t => t !== tagName);
            } else {
                section.tags.push(tagName);
            }
            loadSectionTags(sectionId); // Re-render tags
            saveViewState();
        }

        function updateSectionName(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) section.name = value;
            saveViewState();
        }

        function updateSectionCourse(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) {
                section.course = value;
                section.tags = []; // Reset tags when course changes
                loadSectionTags(id);
            }
            saveViewState();
        }

        function updateSectionType(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) {
                section.type = value;
                updateSectionAvailable(id);
            }
            saveViewState();
        }

        function updateSectionCount(id, value) {
            const section = examSections.find(s => s.id === id);
            if (section) section.count = parseInt(value) || 1;
            updateExamStats();
            saveViewState();
        }

        function updateSectionConstraint(id, field, value) {
            const section = examSections.find(s => s.id === id);
            if (section) {
                section[field] = value ? parseInt(value) : null;
            }
            saveViewState();
        }

        async function updateSectionAvailable(sectionId) {
            const section = examSections.find(s => s.id === sectionId);
            if (!section) return;

            const params = new URLSearchParams();
            if (section.course) params.append('course', section.course);
            if (section.type) params.append('type', section.type);
            section.tags.forEach(t => params.append('tags', t));

            const data = await api(`questions/?${params.toString()}&page_size=1`);
            const count = data.count || 0;

            const el = document.getElementById(`section-available-${sectionId}`);
            if (el) {
                el.textContent = count;
                el.className = `px-2 py-1.5 text-sm font-medium ${count >= section.count ? 'text-emerald-600' : 'text-amber-600'}`;
            }
        }

        async function refreshExamPreview(forceRefresh = false) {
            try {
            const previewContainer = document.getElementById('exam-preview');
            if (!examSections.length) {
                previewContainer.innerHTML = '<div class="text-center py-6 text-gray-400 text-sm">Add sections first</div>';
                return;
            }

            // Try to restore from localStorage on page reload
            if (!forceRefresh && !hasCachedQuestions && currentTemplateId) {
                const savedIds = localStorage.getItem(`examQuestionIds_${currentTemplateId}`);
                if (savedIds) {
                    try {
                        const questionIds = JSON.parse(savedIds);
                        // Fetch these specific questions
                        const questionsData = await Promise.all(
                            questionIds.map(id => api(`questions/${id}/`).catch(() => null))
                        );
                        const restoredQuestions = questionsData.filter(q => q !== null);

                        if (restoredQuestions.length > 0) {
                            // Restore section info
                            restoredQuestions.forEach(q => {
                                const section = examSections.find(s =>
                                    q.tags?.some(t => s.tags.includes(t.name))
                                );
                                q._section = section?.name || 'Unknown';
                            });

                            cachedFinalQuestions = restoredQuestions;
                            hasCachedQuestions = true;
                        }
                    } catch (e) {
                        console.error('Error restoring questions from localStorage:', e);
                    }
                }
            }

            // Use cached final result if available (simple flag - reset when template loads)
            if (!forceRefresh && hasCachedQuestions && cachedFinalQuestions) {
                // Use cached questions - just re-render
                const allQuestions = cachedFinalQuestions;
                currentExamQuestions = allQuestions;
                selectedQuestions.clear();
                allQuestions.forEach(q => selectedQuestions.add(q.id));

                previewContainer.innerHTML = allQuestions.map((q, idx) => `
                    <div class="exam-question-preview p-3 rounded-lg bg-gray-50 dark:bg-slate-800/50 border border-gray-100 dark:border-slate-700" data-question-id="${q.id}">
                        <div class="flex items-start gap-3">
                            <span class="text-xs font-medium text-gray-400 mt-0.5">${idx + 1}</span>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="badge ${getTypeBadgeClass(q.question_type)} text-xs">${formatType(q.question_type)}</span>
                                    <span class="text-xs text-emerald-600 dark:text-emerald-400">${escapeHtml(q._section)}</span>
                                    <span class="exam-points-display text-xs text-gray-400 cursor-pointer hover:text-sky-500 hover:underline"
                                          onclick="editExamQuestionPoints(${q.id}, ${q.points})" title="Click to edit points">${q.points} pts</span>
                                    <div class="ml-auto flex items-center gap-1">
                                        <button onclick="editQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Edit question">
                                            <i data-lucide="pencil" class="w-3.5 h-3.5 text-gray-400 hover:text-sky-500"></i>
                                        </button>
                                        <button onclick="removeQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Remove from exam">
                                            <i data-lucide="x" class="w-3.5 h-3.5 text-gray-400 hover:text-red-500"></i>
                                        </button>
                                    </div>
                                </div>
                                <p class="text-sm text-gray-700 dark:text-slate-300 line-clamp-2">${escapeHtml(q.text)}</p>
                            </div>
                        </div>
                        ${q.question_type === 'longAnswer' ? getAnswerSpaceBox(q) : ''}
                        ${q.question_type === 'shortAnswer' ? getAnswerLineBox(q) : ''}
                    </div>
                `).join('');

                initAnswerSpaceDrag();
                initAnswerLineDrag();
                updateExamStats();
                lucide.createIcons();
                return;
            }

            // If forceRefresh (Shuffle), clear saved question IDs
            if (forceRefresh && currentTemplateId) {
                localStorage.removeItem(`examQuestionIds_${currentTemplateId}`);
            }

            previewContainer.innerHTML = '<div class="text-center py-6"><i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto text-sky-500"></i></div>';
            lucide.createIcons();

            selectedQuestions.clear();
            questionOverrides = {}; // Reset overrides when refreshing
            let allQuestions = [];

            // Helper to create a cache key for a section
            function getSectionCacheKey(section) {
                return JSON.stringify({
                    course: section.course,
                    tags: section.tags.slice().sort(),
                    type: section.type,
                    count: section.count,
                    maxPoints: section.maxPoints,
                    maxMCPoints: section.maxMCPoints,
                    maxTFPoints: section.maxTFPoints,
                    maxShortPoints: section.maxShortPoints,
                    maxLongPoints: section.maxLongPoints
                });
            }

            for (const section of examSections) {
                const cacheKey = getSectionCacheKey(section);

                // Check if we have cached questions for this section config
                if (!forceRefresh && cachedSectionQuestions[cacheKey]) {
                    const sectionQuestions = cachedSectionQuestions[cacheKey];
                    sectionQuestions.forEach(q => {
                        q._section = section.name;
                        selectedQuestions.add(q.id);
                    });
                    allQuestions = allQuestions.concat(sectionQuestions);
                    continue;
                }

                const params = new URLSearchParams();
                if (section.course) params.append('course', section.course);
                if (section.type) params.append('type', section.type);
                section.tags.forEach(t => params.append('tags', t));
                params.append('page_size', 200); // Fetch more to allow for constraint filtering

                const data = await api(`questions/?${params.toString()}`);
                let questions = data.results || data || [];

                // Shuffle questions for random selection
                questions = questions.sort(() => Math.random() - 0.5);

                // Apply point constraints per question type
                let sectionQuestions = [];
                const typePoints = {
                    multipleChoice: 0,
                    trueFalse: 0,
                    shortAnswer: 0,
                    longAnswer: 0
                };
                let totalPoints = 0;
                const maxTotal = section.maxPoints || Infinity;
                const maxByType = {
                    multipleChoice: section.maxMCPoints || Infinity,
                    trueFalse: section.maxTFPoints || Infinity,
                    shortAnswer: section.maxShortPoints || Infinity,
                    longAnswer: section.maxLongPoints || Infinity
                };

                // Check if we have any constraints
                const hasConstraints = section.maxPoints || section.maxMCPoints ||
                    section.maxTFPoints || section.maxShortPoints || section.maxLongPoints;

                if (hasConstraints) {
                    // Use constraint-based selection
                    for (const q of questions) {
                        const pts = parseFloat(q.points) || 0;
                        const qType = q.question_type;
                        const typeMax = maxByType[qType] || Infinity;

                        // Check if adding this question would exceed limits
                        if (typePoints[qType] + pts <= typeMax && totalPoints + pts <= maxTotal) {
                            sectionQuestions.push(q);
                            typePoints[qType] = (typePoints[qType] || 0) + pts;
                            totalPoints += pts;
                        }
                    }
                } else {
                    // Simple count-based selection (original behavior)
                    sectionQuestions = questions.slice(0, section.count);
                }

                // Cache the selected questions for this section config
                cachedSectionQuestions[cacheKey] = sectionQuestions.map(q => ({...q}));

                sectionQuestions.forEach(q => {
                    q._section = section.name;
                    selectedQuestions.add(q.id);
                });
                allQuestions = allQuestions.concat(sectionQuestions);
            }

            // Apply template-level constraints (across all sections)
            const examMaxPoints = parseFloat(document.getElementById('exam-max-points')?.value) || Infinity;
            const examMaxMC = parseFloat(document.getElementById('exam-max-mc-points')?.value) || Infinity;
            const examMaxTF = parseFloat(document.getElementById('exam-max-tf-points')?.value) || Infinity;
            const examMaxShort = parseFloat(document.getElementById('exam-max-short-points')?.value) || Infinity;
            const examMaxLong = parseFloat(document.getElementById('exam-max-long-points')?.value) || Infinity;

            const hasExamConstraints = examMaxPoints !== Infinity || examMaxMC !== Infinity ||
                examMaxTF !== Infinity || examMaxShort !== Infinity || examMaxLong !== Infinity;

            if (hasExamConstraints) {
                const examTypePoints = { multipleChoice: 0, trueFalse: 0, shortAnswer: 0, longAnswer: 0 };
                let examTotalPoints = 0;
                const filteredQuestions = [];

                for (const q of allQuestions) {
                    const pts = parseFloat(q.points) || 0;
                    const qType = q.question_type;
                    const typeMax = {
                        multipleChoice: examMaxMC,
                        trueFalse: examMaxTF,
                        shortAnswer: examMaxShort,
                        longAnswer: examMaxLong
                    }[qType] || Infinity;

                    if (examTypePoints[qType] + pts <= typeMax && examTotalPoints + pts <= examMaxPoints) {
                        filteredQuestions.push(q);
                        examTypePoints[qType] = (examTypePoints[qType] || 0) + pts;
                        examTotalPoints += pts;
                    } else {
                        selectedQuestions.delete(q.id);
                    }
                }
                allQuestions = filteredQuestions;
            }

            // Store for stats calculation and cache for future refreshes
            currentExamQuestions = allQuestions;
            cachedFinalQuestions = allQuestions.map(q => ({...q})); // Deep copy
            hasCachedQuestions = true;

            // Persist selected question IDs to localStorage for browser reload
            if (currentTemplateId) {
                localStorage.setItem(`examQuestionIds_${currentTemplateId}`, JSON.stringify(allQuestions.map(q => q.id)));
            }

            if (!allQuestions.length) {
                previewContainer.innerHTML = '<div class="text-center py-6 text-gray-400 text-sm">No questions match your criteria</div>';
                updateExamStats();
                return;
            }

            previewContainer.innerHTML = allQuestions.map((q, idx) => `
                <div class="exam-question-preview p-3 rounded-lg bg-gray-50 dark:bg-slate-800/50 border border-gray-100 dark:border-slate-700" data-question-id="${q.id}">
                    <div class="flex items-start gap-3">
                        <span class="text-xs font-medium text-gray-400 mt-0.5">${idx + 1}</span>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="badge ${getTypeBadgeClass(q.question_type)} text-xs">${formatType(q.question_type)}</span>
                                <span class="text-xs text-emerald-600 dark:text-emerald-400">${escapeHtml(q._section)}</span>
                                <span class="exam-points-display text-xs text-gray-400 cursor-pointer hover:text-sky-500 hover:underline"
                                      onclick="editExamQuestionPoints(${q.id}, ${q.points})" title="Click to edit points">${q.points} pts</span>
                                <div class="ml-auto flex items-center gap-1">
                                    <button onclick="editQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Edit question">
                                        <i data-lucide="pencil" class="w-3.5 h-3.5 text-gray-400 hover:text-sky-500"></i>
                                    </button>
                                    <button onclick="removeQuestionFromExam(${q.id})" class="p-1 rounded hover:bg-gray-200 dark:hover:bg-slate-600" title="Remove from exam">
                                        <i data-lucide="x" class="w-3.5 h-3.5 text-gray-400 hover:text-red-500"></i>
                                    </button>
                                </div>
                            </div>
                            <p class="text-sm text-gray-700 dark:text-slate-300 line-clamp-2">${escapeHtml(q.text)}</p>
                        </div>
                    </div>
                    ${q.question_type === 'longAnswer' ? getAnswerSpaceBox(q) : ''}
                    ${q.question_type === 'shortAnswer' ? getAnswerLineBox(q) : ''}
                </div>
            `).join('');

            // Initialize drag handlers for answer space boxes and lines
            initAnswerSpaceDrag();
            initAnswerLineDrag();
            updateExamStats();
            } catch (err) {
                console.error('Error in refreshExamPreview:', err);
                alert('Error in refreshExamPreview: ' + err.message);
            }
        }

        // Convert inches to pixels for display (using ~50px per inch for visual representation)
        const PIXELS_PER_INCH = 50;
        const SNAP_SIZES_VERTICAL = [1, 1.5, 2, 2.5, 3, 4, 5, 6]; // Common sizes for solution space
        const SNAP_SIZES_HORIZONTAL = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]; // Common sizes for line length

        function parseInches(value) {
            if (!value) return 1.5; // default
            if (value === '\\stretch{1}') return 4; // treat fill as 4 inches for display
            const match = value.match(/^([\d.]+)in$/);
            return match ? parseFloat(match[1]) : 1.5;
        }

        function getAnswerSpaceBox(q) {
            const defaultSpace = document.getElementById('exam-solution-space')?.value || '1.5in';
            const savedSpace = (q.answer_data || {}).solutionSpace || '';
            const currentSpace = savedSpace || defaultSpace;
            const inches = parseInches(currentSpace);
            const height = Math.round(inches * PIXELS_PER_INCH);

            return `
                <div class="answer-space-container mt-2 ml-6">
                    <div class="answer-space-box"
                         data-question-id="${q.id}"
                         data-inches="${inches}"
                         style="height: ${height}px;">
                        <div class="answer-space-content">
                            <span class="answer-space-label">Answer Space</span>
                        </div>
                        <div class="answer-space-handle">
                            <span class="answer-space-size">${inches} in</span>
                            <i data-lucide="grip-horizontal" class="w-4 h-4"></i>
                        </div>
                    </div>
                </div>`;
        }

        function initAnswerSpaceDrag() {
            document.querySelectorAll('.answer-space-box').forEach(box => {
                const handle = box.querySelector('.answer-space-handle');
                let startY, startHeight, isDragging = false;

                handle.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    isDragging = true;
                    startY = e.clientY;
                    startHeight = box.offsetHeight;
                    document.body.style.cursor = 'ns-resize';
                    document.body.style.userSelect = 'none';
                });

                document.addEventListener('mousemove', (e) => {
                    if (!isDragging) return;
                    const deltaY = e.clientY - startY;
                    const newHeight = Math.max(PIXELS_PER_INCH * 0.5, startHeight + deltaY); // min 0.5 inch
                    box.style.height = newHeight + 'px';

                    // Calculate inches and snap to nearest size
                    let inches = newHeight / PIXELS_PER_INCH;
                    const snapped = SNAP_SIZES_VERTICAL.reduce((prev, curr) =>
                        Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                    );

                    // Show snapped value if close enough
                    const snapThreshold = 0.15;
                    const displayInches = Math.abs(snapped - inches) < snapThreshold ? snapped : Math.round(inches * 4) / 4;

                    box.dataset.inches = displayInches;
                    box.querySelector('.answer-space-size').textContent = displayInches + ' in';
                });

                document.addEventListener('mouseup', () => {
                    if (!isDragging) return;
                    isDragging = false;
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';

                    // Snap to final size
                    const inches = parseFloat(box.dataset.inches);
                    const snapped = SNAP_SIZES_VERTICAL.reduce((prev, curr) =>
                        Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                    );

                    box.style.height = (snapped * PIXELS_PER_INCH) + 'px';
                    box.dataset.inches = snapped;
                    box.querySelector('.answer-space-size').textContent = snapped + ' in';

                    // Update override
                    const questionId = box.dataset.questionId;
                    setQuestionOverride(questionId, 'solutionSpace', snapped + 'in');
                });
            });

            // Re-initialize lucide icons for the grip handles
            lucide.createIcons();
        }

        function getAnswerLineBox(q) {
            const defaultLength = document.getElementById('exam-line-length')?.value || '3in';
            const savedLength = (q.answer_data || {}).lineLength || '';
            const currentLength = savedLength || defaultLength;
            const inches = parseInches(currentLength);
            const width = Math.round(inches * PIXELS_PER_INCH);
            const isFullWidth = currentLength === '\\linewidth';

            return `
                <div class="answer-line-container mt-2 ml-6">
                    <div class="answer-line-box"
                         data-question-id="${q.id}"
                         data-inches="${isFullWidth ? 'full' : inches}"
                         style="width: ${isFullWidth ? '100%' : width + 'px'};">
                        <div class="answer-line"></div>
                        <div class="answer-line-handle">
                            <i data-lucide="grip-vertical" class="w-3 h-3"></i>
                            <span class="answer-line-size">${isFullWidth ? 'Full' : inches + ' in'}</span>
                        </div>
                    </div>
                </div>`;
        }

        function initAnswerLineDrag() {
            document.querySelectorAll('.answer-line-box').forEach(box => {
                const handle = box.querySelector('.answer-line-handle');
                const container = box.closest('.answer-line-container');
                let startX, startWidth, isDragging = false;
                const maxWidth = container.offsetWidth - 20; // Leave room for handle

                handle.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    isDragging = true;
                    startX = e.clientX;
                    startWidth = box.offsetWidth;
                    document.body.style.cursor = 'ew-resize';
                    document.body.style.userSelect = 'none';
                });

                document.addEventListener('mousemove', (e) => {
                    if (!isDragging) return;
                    // Inverted: drag LEFT to make wider (negative deltaX = wider)
                    const deltaX = startX - e.clientX;
                    const newWidth = Math.max(PIXELS_PER_INCH, Math.min(maxWidth, startWidth + deltaX));
                    box.style.width = newWidth + 'px';

                    // Calculate inches
                    let inches = newWidth / PIXELS_PER_INCH;

                    // Check if close to full width
                    const isFullWidth = newWidth >= maxWidth - 10;

                    if (isFullWidth) {
                        box.dataset.inches = 'full';
                        box.querySelector('.answer-line-size').textContent = 'Full';
                    } else {
                        const snapped = SNAP_SIZES_HORIZONTAL.reduce((prev, curr) =>
                            Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                        );
                        const snapThreshold = 0.2;
                        const displayInches = Math.abs(snapped - inches) < snapThreshold ? snapped : Math.round(inches * 2) / 2;
                        box.dataset.inches = displayInches;
                        box.querySelector('.answer-line-size').textContent = displayInches + ' in';
                    }
                });

                document.addEventListener('mouseup', () => {
                    if (!isDragging) return;
                    isDragging = false;
                    document.body.style.cursor = '';
                    document.body.style.userSelect = '';

                    const questionId = box.dataset.questionId;
                    const inchesValue = box.dataset.inches;

                    if (inchesValue === 'full') {
                        box.style.width = '100%';
                        setQuestionOverride(questionId, 'lineLength', '\\linewidth');
                    } else {
                        const inches = parseFloat(inchesValue);
                        const snapped = SNAP_SIZES_HORIZONTAL.reduce((prev, curr) =>
                            Math.abs(curr - inches) < Math.abs(prev - inches) ? curr : prev
                        );
                        box.style.width = (snapped * PIXELS_PER_INCH) + 'px';
                        box.dataset.inches = snapped;
                        box.querySelector('.answer-line-size').textContent = snapped + ' in';
                        setQuestionOverride(questionId, 'lineLength', snapped + 'in');
                    }
                });
            });

            // Re-initialize lucide icons
            lucide.createIcons();
        }

        function setQuestionOverride(questionId, field, value) {
            if (!questionOverrides[questionId]) {
                questionOverrides[questionId] = {};
            }
            if (value) {
                questionOverrides[questionId][field] = value;
            } else {
                delete questionOverrides[questionId][field];
                if (Object.keys(questionOverrides[questionId]).length === 0) {
                    delete questionOverrides[questionId];
                }
            }
            saveViewState();
        }

        // Edit question points inline from exam builder
        function editExamQuestionPoints(questionId, currentPoints) {
            const newPoints = prompt('Enter new points value:', currentPoints);
            if (newPoints === null) return; // Cancelled

            const points = parseFloat(newPoints);
            if (isNaN(points) || points < 0) {
                alert('Please enter a valid positive number');
                return;
            }

            // Update via API
            api(`questions/${questionId}/`, 'PATCH', { points: points })
                .then(() => {
                    // Update the display
                    const container = document.querySelector(`.exam-question-preview[data-question-id="${questionId}"]`);
                    if (container) {
                        const pointsSpan = container.querySelector('.exam-points-display');
                        if (pointsSpan) {
                            pointsSpan.textContent = points + ' pts';
                            pointsSpan.setAttribute('onclick', `editExamQuestionPoints(${questionId}, ${points})`);
                        }
                    }
                    updateExamStats();
                })
                .catch(err => alert('Error updating points: ' + err.message));
        }

        // Open question modal from exam builder
        async function editQuestionFromExam(questionId) {
            await openQuestion(questionId);
        }

        // Remove a question from the exam preview
        function removeQuestionFromExam(questionId) {
            selectedQuestions.delete(questionId);
            delete questionOverrides[questionId];

            // Remove from currentExamQuestions
            currentExamQuestions = currentExamQuestions.filter(q => q.id !== questionId);

            // Remove from DOM
            const container = document.querySelector(`.exam-question-preview[data-question-id="${questionId}"]`);
            if (container) {
                container.remove();
            }

            // Re-number remaining questions
            document.querySelectorAll('.exam-question-preview').forEach((el, idx) => {
                const numSpan = el.querySelector('.text-xs.font-medium.text-gray-400');
                if (numSpan) numSpan.textContent = idx + 1;
            });

            updateExamStats();
            saveViewState();
        }

        async function generateExam(format) {
            if (!selectedQuestions.size) return alert('Please select at least one question');
            const numVersions = parseInt(document.getElementById('exam-versions')?.value || '1');
            const data = {
                question_ids: Array.from(selectedQuestions),
                title: document.getElementById('exam-title').value,
                course: document.getElementById('exam-course').value,
                instructor: document.getElementById('exam-instructor').value,
                term: document.getElementById('exam-term').value,
                instructions: document.getElementById('exam-instructions').value,
                shuffle: document.getElementById('exam-shuffle').checked,
                include_answers: document.getElementById('exam-answers').checked,
                is_quiz: document.getElementById('exam-quiz-mode')?.checked || false,
                include_id: document.getElementById('exam-include-id')?.checked || false,
                split_mc: document.getElementById('exam-split-mc')?.checked || false,
                line_length: document.getElementById('exam-line-length')?.value || '3in',
                solution_space: document.getElementById('exam-solution-space')?.value || '1.5in',
                question_overrides: questionOverrides,
                versions: numVersions,
                format: format
            };

            // Show progress indicator
            const progressDiv = document.getElementById('generation-progress');
            const statusSpan = document.getElementById('generation-status');
            const btnHtml = document.getElementById('btn-generate-html');
            const btnPdf = document.getElementById('btn-generate-pdf');

            function showProgress(message) {
                if (progressDiv) progressDiv.classList.remove('hidden');
                if (statusSpan) statusSpan.textContent = message;
                if (btnHtml) btnHtml.disabled = true;
                if (btnPdf) btnPdf.disabled = true;
            }

            function hideProgress() {
                if (progressDiv) progressDiv.classList.add('hidden');
                if (btnHtml) btnHtml.disabled = false;
                if (btnPdf) btnPdf.disabled = false;
            }

            try {
                if (format === 'html') {
                    showProgress('Generating HTML preview...');
                    const res = await api('exams/generate/', 'POST', data);
                    hideProgress();
                    if (res.content) {
                        const frame = document.getElementById('preview-frame');
                        frame.srcdoc = res.content;
                        showModal('preview-modal');
                    }
                } else if (format === 'pdf') {
                    // Show appropriate message based on number of versions
                    if (numVersions > 1) {
                        showProgress(`Generating ${numVersions} exam versions... This may take a minute.`);
                    } else {
                        showProgress('Generating PDF...');
                    }

                    // For PDF, we need to handle the file download differently
                    const headers = { 'Content-Type': 'application/json' };
                    // Include CSRF token for POST request
                    const csrfToken = getCookie('csrftoken');
                    if (csrfToken) {
                        headers['X-CSRFToken'] = csrfToken;
                    }
                    const response = await fetch('/api/exams/generate/', {
                        method: 'POST',
                        headers: headers,
                        credentials: 'same-origin',
                        body: JSON.stringify(data)
                    });
                    hideProgress();

                    if (response.ok) {
                        const blob = await response.blob();
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        // Filename includes version info if multiple versions
                        const filename = numVersions > 1
                            ? `${data.title.replace(/\s+/g, '_')}_versions.zip`
                            : `${data.title.replace(/\s+/g, '_')}.pdf`;
                        a.download = filename;
                        a.click();
                    } else {
                        const err = await response.json();
                        alert('PDF generation failed: ' + (err.error || 'Unknown error'));
                    }
                }
            } catch (error) {
                hideProgress();
                console.error('Generation error:', error);
                alert('Generation failed: ' + error.message);
            }
        }

        function printPreview() {
            document.getElementById('preview-frame').contentWindow.print();
        }

        function closePreviewModal() { hideModal('preview-modal'); }

        function toggleQuizModeOptions() {
            const quizMode = document.getElementById('exam-quiz-mode')?.checked;
            const optionsDiv = document.getElementById('quiz-mode-options');
            if (optionsDiv) {
                optionsDiv.classList.toggle('hidden', !quizMode);
            }
        }

        // AI Generation
        async function generateQuestions() {
            const btn = document.getElementById('generate-btn');
            const content = document.getElementById('ai-content').value;
            if (!content) return alert('Please enter some content');

            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader-2" class="w-5 h-5 animate-spin"></i> Generating...';
            lucide.createIcons();

            try {
                const res = await api('ai/generate/', 'POST', {
                    provider: document.getElementById('ai-provider').value,
                    content: content,
                    type: document.getElementById('ai-type').value,
                    difficulty: document.getElementById('ai-difficulty').value,
                    count: parseInt(document.getElementById('ai-count').value),
                });
                if (res.error) throw new Error(res.error);
                renderGeneratedQuestions(res.questions);
            } catch (e) {
                document.getElementById('generated-questions').innerHTML = `<div class="p-4 bg-red-50 text-red-600 rounded-lg">${e.message}</div>`;
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i data-lucide="sparkles" class="w-5 h-5"></i> Generate Questions';
                lucide.createIcons();
            }
        }

        function renderGeneratedQuestions(questions) {
            window.generatedQuestions = questions;
            document.getElementById('generated-questions').innerHTML = questions.map((q, i) => `
                <div class="p-4 bg-gray-50 rounded-xl border border-gray-100">
                    <div class="flex justify-between items-start mb-2">
                        <span class="badge bg-purple-100 text-purple-700">Q${i + 1}</span>
                        <button onclick="addGeneratedQuestion(${i})" class="text-sm text-sky-600 hover:text-sky-700 font-medium">+ Add to Bank</button>
                    </div>
                    <p class="text-gray-800 text-sm mb-2">${escapeHtml(q.text)}</p>
                    <div class="text-xs text-gray-500">${q.answer_data.correct !== undefined ? `Answer: ${q.answer_data.correct}` : q.answer_data.solution ? `Solution: ${q.answer_data.solution.substring(0, 100)}...` : ''}</div>
                </div>
            `).join('');
        }

        function addGeneratedQuestion(i) {
            const q = window.generatedQuestions[i];
            document.getElementById('q-type').value = document.getElementById('ai-type').value;
            document.getElementById('q-difficulty').value = q.difficulty || 'medium';
            document.getElementById('q-points').value = q.points || 2;
            if (editor) editor.setValue(q.text);
            updateAnswerFields(q.answer_data);
            editingQuestionId = null;
            document.getElementById('modal-title').textContent = 'Add Generated Question';
            document.getElementById('delete-btn').classList.add('hidden');
            showModal('question-modal');
        }

        // Helpers
        function showModal(id) { document.getElementById(id).classList.remove('hidden'); document.getElementById(id).classList.add('flex'); }
        function hideModal(id) { document.getElementById(id).classList.add('hidden'); document.getElementById(id).classList.remove('flex'); }
        function closeModal() { hideModal('question-modal'); }

        function filterByCourse(code) {
            document.getElementById('filter-course').value = code;
            loadQuestions();
            showView('questions', { preventDefault: () => {}, target: document.querySelector('.sidebar-item') });
        }

        function formatType(t) {
            const m = { multipleChoice: 'MC', trueFalse: 'T/F', shortAnswer: 'Short', longAnswer: 'Long', matching: 'Match', multipart: 'Multi', easy: 'Long' };
            return m[t] || t;
        }

        function getTypeBadgeClass(t) {
            const c = { multipleChoice: 'bg-blue-100 text-blue-700', trueFalse: 'bg-purple-100 text-purple-700', shortAnswer: 'bg-emerald-100 text-emerald-700', longAnswer: 'bg-amber-100 text-amber-700', easy: 'bg-amber-100 text-amber-700' };
            return c[t] || 'bg-gray-100 text-gray-700';
        }

        function getDifficultyClass(d) {
            const c = { easy: 'bg-green-100 text-green-700', medium: 'bg-yellow-100 text-yellow-700', hard: 'bg-red-100 text-red-700' };
            return c[d] || 'bg-gray-100 text-gray-700';
        }

        function escapeHtml(t) { return t?.replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' })[m]) || ''; }
        function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }

        // Simple Markdown to HTML for preview (basic support)
        function simpleMarkdown(text) {
            if (!text) return '';
            let html = escapeHtml(text);
            // Code blocks
            html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="bg-gray-100 dark:bg-slate-800 p-2 rounded text-xs overflow-x-auto"><code>$2</code></pre>');
            // Inline code
            html = html.replace(/`([^`]+)`/g, '<code class="bg-gray-100 dark:bg-slate-700 px-1 rounded text-xs">$1</code>');
            // Images
            html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="max-w-full h-auto rounded my-2">');
            // Links
            html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-sky-600 hover:underline" target="_blank">$1</a>');
            // Bold
            html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
            // Italic
            html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
            // Headers
            html = html.replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold mt-2">$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold mt-2">$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold mt-2">$1</h1>');
            // Lists
            html = html.replace(/^\* (.+)$/gm, '<li class="ml-4">$1</li>');
            html = html.replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>');
            html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4">$2</li>');
            // Line breaks
            html = html.replace(/\n/g, '<br>');
            return html;
        }

        // Image upload functions
        let questionImages = [];

        function triggerImageUpload() {
            document.getElementById('image-upload-input').click();
        }

        async function handleImageUpload(event) {
            const file = event.target.files[0];
            if (!file) return;

            const statusEl = document.getElementById('image-upload-status');
            statusEl.textContent = 'Uploading...';

            const formData = new FormData();
            formData.append('image', file);
            formData.append('alt_text', file.name.replace(/\.[^/.]+$/, ''));

            try {
                // Upload to the appropriate endpoint based on whether we're editing an existing question
                let endpoint = 'images/';
                if (editingQuestionId) {
                    endpoint = `questions/${editingQuestionId}/upload_image/`;
                }

                const response = await fetch(`/api/${endpoint}`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    credentials: 'same-origin',
                    body: formData
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.error || 'Upload failed');
                }

                const image = await response.json();
                questionImages.push(image);
                updateImageGallery();

                // Insert markdown reference at cursor in editor
                if (editor) {
                    const position = editor.getPosition();
                    const markdownRef = `![${image.alt_text || 'image'}](${image.url})`;
                    editor.executeEdits('', [{
                        range: {
                            startLineNumber: position.lineNumber,
                            startColumn: position.column,
                            endLineNumber: position.lineNumber,
                            endColumn: position.column
                        },
                        text: markdownRef
                    }]);
                }

                statusEl.textContent = 'Uploaded!';
                setTimeout(() => { statusEl.textContent = ''; }, 2000);
            } catch (err) {
                console.error('Image upload failed:', err);
                statusEl.textContent = 'Upload failed: ' + err.message;
            }

            // Reset file input
            event.target.value = '';
        }

        function updateImageGallery() {
            const container = document.getElementById('question-images');
            const list = document.getElementById('question-images-list');

            if (questionImages.length === 0) {
                container.classList.add('hidden');
                return;
            }

            container.classList.remove('hidden');
            list.innerHTML = questionImages.map(img => `
                <div class="relative group">
                    <img src="${img.url}" alt="${escapeHtml(img.alt_text || '')}" class="w-16 h-16 object-cover rounded border border-gray-200 dark:border-slate-600">
                    <button onclick="insertImageMarkdown('${img.url}', '${escapeHtml(img.alt_text || 'image')}')"
                            class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded"
                            title="Insert into text">
                        <i data-lucide="plus" class="w-4 h-4 text-white"></i>
                    </button>
                </div>
            `).join('');
            lucide.createIcons();
        }

        function insertImageMarkdown(url, alt) {
            if (editor) {
                const position = editor.getPosition();
                const markdownRef = `![${alt}](${url})`;
                editor.executeEdits('', [{
                    range: {
                        startLineNumber: position.lineNumber,
                        startColumn: position.column,
                        endLineNumber: position.lineNumber,
                        endColumn: position.column
                    },
                    text: markdownRef
                }]);
                editor.focus();
            }
        }

        async function loadQuestionImages(questionId) {
            questionImages = [];
            if (!questionId) {
                updateImageGallery();
                return;
            }

            try {
                const response = await api(`questions/${questionId}/images/`);
                questionImages = response || [];
                updateImageGallery();
            } catch (err) {
                console.error('Failed to load question images:', err);
            }
        }

        // Live preview in editor
        let previewVisible = false;
        function togglePreview() {
            previewVisible = !previewVisible;
            const editorCol = document.getElementById('editor-col');
            const previewCol = document.getElementById('preview-col');
            const editorWrapper = document.getElementById('editor-wrapper');
            const toggleBtn = document.getElementById('preview-toggle');

            if (previewVisible) {
                editorWrapper.classList.remove('grid-cols-1');
                editorWrapper.classList.add('grid-cols-2');
                previewCol.classList.remove('hidden');
                toggleBtn.classList.add('bg-sky-100', 'text-sky-700');
                toggleBtn.classList.remove('bg-gray-100', 'text-gray-600');
                updatePreview();
                // Setup live preview updates
                if (editor) {
                    editor.onDidChangeModelContent(() => updatePreview());
                }
            } else {
                editorWrapper.classList.add('grid-cols-1');
                editorWrapper.classList.remove('grid-cols-2');
                previewCol.classList.add('hidden');
                toggleBtn.classList.remove('bg-sky-100', 'text-sky-700');
                toggleBtn.classList.add('bg-gray-100', 'text-gray-600');
            }
            lucide.createIcons();
        }

        function updatePreview() {
            const previewEl = document.getElementById('markdown-preview');
            if (!previewEl || !editor) return;
            const text = editor.getValue();
            previewEl.innerHTML = simpleMarkdown(text) || '<span class="text-gray-400">Preview will appear here...</span>';
        }

        // Bulk Operations
        function toggleBulkMode() {
            bulkMode = !bulkMode;
            bulkSelectedQuestions.clear();
            updateBulkUI();
            loadQuestions(currentPage);
        }

        function updateBulkUI() {
            const bulkBar = document.getElementById('bulk-action-bar');
            const bulkToggle = document.getElementById('bulk-toggle-btn');
            if (bulkMode) {
                bulkBar?.classList.remove('hidden');
                bulkToggle?.classList.add('bg-sky-100', 'dark:bg-sky-900/50');
            } else {
                bulkBar?.classList.add('hidden');
                bulkToggle?.classList.remove('bg-sky-100', 'dark:bg-sky-900/50');
            }
            updateBulkCount();
        }

        function updateBulkCount() {
            const countEl = document.getElementById('bulk-count');
            if (countEl) countEl.textContent = bulkSelectedQuestions.size;
        }

        function toggleBulkQuestion(id, checkbox) {
            if (checkbox.checked) {
                bulkSelectedQuestions.add(id);
            } else {
                bulkSelectedQuestions.delete(id);
            }
            updateBulkCount();
        }

        function selectAllVisible() {
            document.querySelectorAll('.bulk-checkbox').forEach(cb => {
                cb.checked = true;
                bulkSelectedQuestions.add(parseInt(cb.dataset.id));
            });
            updateBulkCount();
        }

        function deselectAll() {
            bulkSelectedQuestions.clear();
            document.querySelectorAll('.bulk-checkbox').forEach(cb => cb.checked = false);
            updateBulkCount();
        }

        async function bulkDelete() {
            if (!bulkSelectedQuestions.size) return alert('No questions selected');
            if (!confirm(`Delete ${bulkSelectedQuestions.size} questions? This cannot be undone.`)) return;

            for (const id of bulkSelectedQuestions) {
                await api(`questions/${id}/`, 'DELETE');
            }
            bulkSelectedQuestions.clear();
            updateBulkCount();
            loadQuestions(currentPage);
        }

        async function bulkTag() {
            if (!bulkSelectedQuestions.size) return alert('No questions selected');
            const tagName = prompt('Enter tag name to add to selected questions:');
            if (!tagName) return;

            // First ensure tag exists
            let tag = allTags.find(t => t.name.toLowerCase() === tagName.toLowerCase());
            if (!tag) {
                tag = await api('tags/', 'POST', { name: tagName, color: '#10b981' });
            }

            // Add tag to each question
            for (const id of bulkSelectedQuestions) {
                const q = await api(`questions/${id}/`);
                const existingTags = (q.tags || []).map(t => t.name);
                if (!existingTags.includes(tagName)) {
                    existingTags.push(tagName);
                    await api(`questions/${id}/`, 'PATCH', { tag_names: existingTags });
                }
            }

            loadTags();
            loadQuestions(currentPage);
            alert(`Added tag "${tagName}" to ${bulkSelectedQuestions.size} questions`);
        }

        async function bulkMove() {
            if (!bulkSelectedQuestions.size) return alert('No questions selected');

            // Show bank selector
            const bankOptions = banks.map(b => `${b.id}: ${b.course_code}/${b.name}`).join('\n');
            const bankId = prompt(`Enter bank ID to move questions to:\n\n${bankOptions}`);
            if (!bankId) return;

            for (const id of bulkSelectedQuestions) {
                await api(`questions/${id}/`, 'PATCH', { question_bank: parseInt(bankId) });
            }

            loadQuestions(currentPage);
            alert(`Moved ${bulkSelectedQuestions.size} questions to new bank`);
        }

        // Duplicate/clone question
        async function duplicateQuestion(id) {
            try {
                const cloned = await api(`questions/${id}/clone/`, 'POST');
                // Refresh the list and open the cloned question for editing
                await loadQuestions(currentPage);
                editQuestion(cloned.id);
                showNotification('Question cloned successfully', 'success');
            } catch (err) {
                console.error('Failed to clone question:', err);
                showNotification('Failed to clone question', 'error');
            }
        }

        // Simple notification helper
        function showNotification(message, type = 'info') {
            const colors = {
                success: 'bg-green-500',
                error: 'bg-red-500',
                info: 'bg-sky-500'
            };
            const notification = document.createElement('div');
            notification.className = `fixed bottom-4 right-4 ${colors[type]} text-white px-4 py-2 rounded-lg shadow-lg z-50 transition-opacity duration-300`;
            notification.textContent = message;
            document.body.appendChild(notification);
            setTimeout(() => {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }

        // Trash functions
        async function loadTrash() {
            const container = document.getElementById('trash-list');
            container.innerHTML = '<div class="p-4 text-center text-gray-400 dark:text-slate-500">Loading...</div>';

            try {
                const data = await api('questions/?trash=true&page_size=100');
                const questions = data.results || data || [];

                // Update trash count in sidebar
                updateTrashCount(questions.length);

                if (questions.length === 0) {
                    container.innerHTML = `
                        <div class="p-12 text-center text-gray-400 dark:text-slate-500">
                            <i data-lucide="trash-2" class="w-12 h-12 mx-auto mb-3 opacity-50"></i>
                            <p>Trash is empty</p>
                        </div>
                    `;
                    lucide.createIcons();
                    return;
                }

                container.innerHTML = questions.map(q => `
                    <div class="p-4 hover:bg-gray-50 dark:hover:bg-slate-700/50 flex items-center gap-4 group">
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-xs font-medium px-2 py-0.5 rounded-full ${getTypeColor(q.question_type)}">${q.question_type_display || q.question_type}</span>
                                <span class="text-xs text-gray-400 dark:text-slate-500">${q.course_code || ''}</span>
                            </div>
                            <div class="text-sm text-gray-700 dark:text-slate-300 truncate">${q.text?.substring(0, 100) || 'No text'}...</div>
                            <div class="text-xs text-gray-400 dark:text-slate-500 mt-1">
                                Deleted ${q.deleted_at ? new Date(q.deleted_at).toLocaleDateString() : 'recently'}
                            </div>
                        </div>
                        <div class="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onclick="restoreQuestion(${q.id})" class="px-3 py-1.5 text-sm bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-lg hover:bg-green-200 dark:hover:bg-green-900/50 flex items-center gap-1">
                                <i data-lucide="undo-2" class="w-4 h-4"></i>
                                Restore
                            </button>
                            <button onclick="permanentDeleteQuestion(${q.id})" class="px-3 py-1.5 text-sm bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 flex items-center gap-1">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                                Delete
                            </button>
                        </div>
                    </div>
                `).join('');
                lucide.createIcons();
            } catch (err) {
                console.error('Failed to load trash:', err);
                container.innerHTML = '<div class="p-4 text-center text-red-500">Failed to load trash</div>';
            }
        }

        async function restoreQuestion(id) {
            try {
                await api(`questions/${id}/restore/`, 'POST');
                showNotification('Question restored successfully', 'success');
                loadTrash();
                loadQuestions(currentPage);
            } catch (err) {
                console.error('Failed to restore question:', err);
                showNotification('Failed to restore question', 'error');
            }
        }

        async function permanentDeleteQuestion(id) {
            if (!confirm('Permanently delete this question? This cannot be undone.')) return;
            try {
                await api(`questions/${id}/permanent_delete/`, 'DELETE');
                showNotification('Question permanently deleted', 'success');
                loadTrash();
            } catch (err) {
                console.error('Failed to permanently delete question:', err);
                showNotification('Failed to delete question', 'error');
            }
        }

        async function emptyTrash() {
            if (!confirm('Permanently delete all items in trash? This cannot be undone.')) return;
            try {
                const result = await api('questions/empty_trash/', 'POST');
                showNotification(`Deleted ${result.deleted} questions permanently`, 'success');
                loadTrash();
            } catch (err) {
                console.error('Failed to empty trash:', err);
                showNotification('Failed to empty trash', 'error');
            }
        }

        async function updateTrashCount(count = null) {
            if (count === null) {
                try {
                    const data = await api('questions/trash_count/');
                    count = data.count;
                } catch (err) {
                    count = 0;
                }
            }
            const badge = document.getElementById('nav-trash-count');
            if (badge) {
                badge.textContent = count;
                badge.classList.toggle('hidden', count === 0);
            }
        }

        // Load usage statistics for sidebar
        async function loadUsageStats() {
            try {
                const data = await api('questions/usage_stats/');
                const container = document.getElementById('usage-stats-mini');
                const rateEl = document.getElementById('stat-usage-rate');
                const barEl = document.getElementById('stat-usage-bar');

                if (container && data.total_questions > 0) {
                    container.classList.remove('hidden');
                    if (rateEl) rateEl.textContent = `${data.usage_rate}%`;
                    if (barEl) barEl.style.width = `${data.usage_rate}%`;
                }
            } catch (err) {
                console.log('Failed to load usage stats:', err);
            }
        }

        // Export questions
        async function exportQuestions(format) {
            const params = new URLSearchParams();
            const course = document.getElementById('filter-course')?.value;
            if (course) params.append('course', course);
            selectedTags.forEach(tag => params.append('tags', tag));

            const data = await api(`questions/?${params.toString()}&page_size=1000`);
            const questions = data.results || data || [];

            if (format === 'json') {
                const blob = new Blob([JSON.stringify(questions, null, 2)], { type: 'application/json' });
                downloadBlob(blob, 'questions.json');
            } else if (format === 'csv') {
                const headers = ['id', 'type', 'text', 'points', 'difficulty', 'answer'];
                const rows = questions.map(q => [
                    q.id,
                    q.question_type,
                    `"${(q.text || '').replace(/"/g, '""')}"`,
                    q.points,
                    q.difficulty,
                    `"${JSON.stringify(q.answer_data || {}).replace(/"/g, '""')}"`
                ]);
                const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                downloadBlob(blob, 'questions.csv');
            }
        }

        function downloadBlob(blob, filename) {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        }

        // Import questions from file
        function openImportModal() {
            showModal('import-modal');
        }

        async function importQuestions() {
            const fileInput = document.getElementById('import-file');
            const bankId = document.getElementById('import-bank').value;
            if (!fileInput.files.length) return alert('Please select a file');
            if (!bankId) return alert('Please select a question bank');

            const file = fileInput.files[0];
            const text = await file.text();
            let questions;

            try {
                if (file.name.endsWith('.json')) {
                    questions = JSON.parse(text);
                } else if (file.name.endsWith('.csv')) {
                    // Simple CSV parsing
                    const lines = text.split('\n');
                    const headers = lines[0].split(',');
                    questions = lines.slice(1).filter(l => l.trim()).map(line => {
                        const values = line.match(/(".*?"|[^,]+)/g) || [];
                        const obj = {};
                        headers.forEach((h, i) => {
                            let val = values[i] || '';
                            if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1).replace(/""/g, '"');
                            obj[h.trim()] = val;
                        });
                        return obj;
                    });
                } else {
                    return alert('Unsupported file format. Use .json or .csv');
                }
            } catch (e) {
                return alert('Error parsing file: ' + e.message);
            }

            let imported = 0;
            for (const q of questions) {
                try {
                    await api('questions/', 'POST', {
                        question_bank: parseInt(bankId),
                        question_type: q.question_type || q.type || 'shortAnswer',
                        text: q.text || '',
                        points: parseFloat(q.points) || 2,
                        difficulty: q.difficulty || 'medium',
                        answer_data: typeof q.answer_data === 'string' ? JSON.parse(q.answer_data) : (q.answer_data || {}),
                    });
                    imported++;
                } catch (e) {
                    console.error('Failed to import question:', e);
                }
            }

            hideModal('import-modal');
            loadQuestions();
            alert(`Imported ${imported} questions`);
        }

        // Block variant preview functions
        function previewBlockVariant(event, index) {
            const row = event.target.closest('.question-row');
            if (!row) return;
            const variants = row.dataset.blockVariants;
            if (!variants) return;
            try {
                const data = JSON.parse(variants);
                if (data[index]) {
                    const textEl = row.querySelector('.question-text');
                    const pointsEl = row.querySelector('.question-points');
                    if (textEl) textEl.textContent = data[index].text;
                    if (pointsEl) pointsEl.textContent = parseInt(data[index].points);
                }
            } catch (e) { console.error('Error parsing block variants:', e); }
        }
        function resetBlockPreview(event) {
            const row = event.target.closest('.question-row');
            if (!row) return;
            const textEl = row.querySelector('.question-text');
            const pointsEl = row.querySelector('.question-points');
            if (textEl) textEl.textContent = row.dataset.originalText || '';
            if (pointsEl) pointsEl.textContent = row.dataset.originalPoints || '';
        }

        // Build Exam panel variant preview functions
        function previewExamBlockVariant(event, index) {
            const row = event.target.closest('.exam-question-row');
            if (!row) return;
            const variants = row.dataset.blockVariants;
            if (!variants) return;
            try {
                const data = JSON.parse(variants);
                if (data[index]) {
                    const textEl = row.querySelector('.exam-question-text');
                    const pointsEl = row.querySelector('.exam-question-points');
                    if (textEl) textEl.textContent = data[index].text;
                    if (pointsEl) pointsEl.textContent = parseInt(data[index].points) + ' pts';
                }
            } catch (e) { console.error('Error parsing block variants:', e); }
        }
        function resetExamBlockPreview(event) {
            const row = event.target.closest('.exam-question-row');
            if (!row) return;
            const textEl = row.querySelector('.exam-question-text');
            const pointsEl = row.querySelector('.exam-question-points');
            if (textEl) textEl.textContent = row.dataset.originalText || '';
            if (pointsEl) pointsEl.textContent = (row.dataset.originalPoints || '') + ' pts';
        }

        // ========== Sharing Functions ==========
        let currentShareType = null;  // 'course', 'bank', or 'template'
        let currentShareId = null;    // The ID/code of the item being shared

        async function openShareModal(type, id) {
            currentShareType = type;
            currentShareId = id;

            // Update modal title
            const titles = { course: 'Share Course', bank: 'Share Question Bank', template: 'Share Exam Template' };
            document.getElementById('share-modal-title').textContent = titles[type] || 'Share';

            // Clear search input
            document.getElementById('share-user-search').value = '';
            document.getElementById('share-user-results').classList.add('hidden');
            document.getElementById('share-user-results').innerHTML = '';

            // Load current shares
            await loadCurrentShares();

            showModal('share-modal');
            lucide.createIcons();
        }

        async function loadCurrentShares() {
            const container = document.getElementById('current-shares');
            container.innerHTML = '<p class="text-sm text-gray-400">Loading...</p>';

            try {
                let endpoint;
                switch (currentShareType) {
                    case 'course':
                        endpoint = `courses/${currentShareId}/shares/`;
                        break;
                    case 'bank':
                        endpoint = `banks/${currentShareId}/shares/`;
                        break;
                    case 'template':
                        endpoint = `exams/templates/${currentShareId}/shares/`;
                        break;
                }

                const shares = await api(endpoint);
                const sharesArray = shares.results || shares || [];

                if (sharesArray.length === 0) {
                    container.innerHTML = '<p class="text-sm text-gray-400 dark:text-slate-500">Not shared with anyone</p>';
                    return;
                }

                container.innerHTML = sharesArray.map(share => `
                    <div class="flex items-center justify-between p-2 bg-gray-50 dark:bg-slate-700/50 rounded-lg">
                        <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-sky-400 to-cyan-500 flex items-center justify-center text-white font-bold text-sm">
                                ${(share.shared_with_username || 'U')[0].toUpperCase()}
                            </div>
                            <div>
                                <div class="text-sm font-medium text-gray-700 dark:text-slate-300">${escapeHtml(share.shared_with_username)}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">${share.permission === 'edit' ? 'Can Edit' : 'View Only'}</div>
                            </div>
                        </div>
                        <button onclick="removeShare('${share.shared_with_username}')" class="p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500" title="Remove access">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>
                `).join('');
                lucide.createIcons();
            } catch (err) {
                console.error('Error loading shares:', err);
                container.innerHTML = '<p class="text-sm text-red-500">Error loading shares</p>';
            }
        }

        const searchUsersDebounced = debounce(searchUsers, 300);

        async function searchUsers() {
            const query = document.getElementById('share-user-search').value.trim();
            const resultsContainer = document.getElementById('share-user-results');

            if (query.length < 2) {
                resultsContainer.classList.add('hidden');
                return;
            }

            try {
                const users = await api(`users/?search=${encodeURIComponent(query)}`);
                const usersArray = users.results || users || [];

                if (usersArray.length === 0) {
                    resultsContainer.innerHTML = '<div class="p-3 text-sm text-gray-400">No users found</div>';
                } else {
                    resultsContainer.innerHTML = usersArray.map(user => `
                        <button onclick="selectUserToShare('${escapeHtml(user.username)}')"
                            class="w-full text-left px-3 py-2 hover:bg-gray-100 dark:hover:bg-slate-700 flex items-center gap-2">
                            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center text-white font-bold text-sm">
                                ${(user.username || 'U')[0].toUpperCase()}
                            </div>
                            <div>
                                <div class="text-sm font-medium text-gray-700 dark:text-slate-300">${escapeHtml(user.username)}</div>
                                <div class="text-xs text-gray-400 dark:text-slate-500">${escapeHtml(user.email || '')}</div>
                            </div>
                        </button>
                    `).join('');
                }
                resultsContainer.classList.remove('hidden');
            } catch (err) {
                console.error('Error searching users:', err);
            }
        }

        async function selectUserToShare(username) {
            const permission = document.getElementById('share-permission').value;
            document.getElementById('share-user-results').classList.add('hidden');
            document.getElementById('share-user-search').value = '';

            try {
                let endpoint;
                switch (currentShareType) {
                    case 'course':
                        endpoint = `courses/${currentShareId}/share/`;
                        break;
                    case 'bank':
                        endpoint = `banks/${currentShareId}/share/`;
                        break;
                    case 'template':
                        endpoint = `exams/templates/${currentShareId}/share/`;
                        break;
                }

                await api(endpoint, 'POST', { username, permission });
                await loadCurrentShares();
            } catch (err) {
                console.error('Error sharing:', err);
                alert('Error sharing. Please try again.');
            }
        }

        async function removeShare(username) {
            if (!confirm(`Remove ${username}'s access?`)) return;

            try {
                let endpoint;
                switch (currentShareType) {
                    case 'course':
                        endpoint = `courses/${currentShareId}/unshare/`;
                        break;
                    case 'bank':
                        endpoint = `banks/${currentShareId}/unshare/`;
                        break;
                    case 'template':
                        endpoint = `exams/templates/${currentShareId}/unshare/`;
                        break;
                }

                await api(endpoint, 'DELETE', { username });
                await loadCurrentShares();
            } catch (err) {
                console.error('Error removing share:', err);
                alert('Error removing share. Please try again.');
            }
        }

        async function copyBank(bankId) {
            const newName = prompt('Name for the copy:');
            if (!newName) return;

            try {
                await api(`banks/${bankId}/copy/`, 'POST', { name: newName });
                await loadBanks();
                alert('Bank copied successfully!');
            } catch (err) {
                console.error('Error copying bank:', err);
                alert('Error copying bank. Please try again.');
            }
        }

        async function copyTemplate(templateId) {
            const newName = prompt('Name for the copy:');
            if (!newName) return;

            try {
                await api(`exams/templates/${templateId}/copy/`, 'POST', { name: newName });
                await loadExamTemplates(currentTemplateFilter);
                alert('Template copied successfully!');
            } catch (err) {
                console.error('Error copying template:', err);
                alert('Error copying template. Please try again.');
            }
        }